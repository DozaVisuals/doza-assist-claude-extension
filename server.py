#!/usr/bin/env python3
"""Doza Assist: local MCP server (stdio transport, no dependencies).

Launched by the AI client (Claude Desktop, Claude Code, an agent) from the
config the project page's "AI assistant access" panel shows. It is a thin
bridge: every tool call becomes an HTTP request to the running Doza Assist
backend on 127.0.0.1 (``POST /studio/mcp/tool/<name>``, the same path the
Studio edition serves so one connector works with whichever edition is
running), which enforces the privacy gate: only projects whose "AI assistant
access" is ON are visible, on a licensed copy or within the trial (trial
transcripts are capped at two minutes). Media never leaves the Mac; only
transcript text and selects travel over loopback.

Protocol: MCP over stdio (newline-delimited JSON-RPC 2.0). The server speaks
the client's protocol revision when it is one we know (2024-11-05 through
2025-11-25; the tools-only surface is identical across them) and otherwise
answers with the newest. Answering 2025-11-25 matters for the connector icon:
``icons`` on serverInfo and tools entered the spec in that revision, and
Claude Desktop discards them from a server that claims an older one.
initialize → notifications/initialized → tools/list / tools/call / ping.
Tool schemas live in schema.json next to this file and are validated here
(required keys, types, enums, bounds) before the request leaves the process.

Backend discovery: DOZA_BACKEND_URL env, else the ``backend.json`` the app
writes in its support dir when Flask is ready.
"""
from __future__ import annotations

import json
import math
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(HERE, 'schema.json')
PROTOCOL_VERSIONS = ('2024-11-05', '2025-03-26', '2025-06-18', '2025-11-25')
PROTOCOL_VERSION = PROTOCOL_VERSIONS[-1]


def negotiate_protocol(requested) -> str:
    """Echo the client's revision when we support it, else offer our newest."""
    return requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSION


def _log(msg: str) -> None:
    sys.stderr.write(f'[doza-mcp] {msg}\n')
    sys.stderr.flush()


def load_schema() -> dict:
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    return {'server': raw.get('server') or {'name': 'Doza Assist (this Mac)', 'version': '0'},
            'tools': [t for t in raw.get('tools') or [] if isinstance(t, dict)]}


def backend_url() -> str | None:
    url = (os.environ.get('DOZA_BACKEND_URL') or '').strip()
    if url:
        return url.rstrip('/')
    support = os.environ.get('DOZA_DATA_DIR') or os.path.join(
        os.path.expanduser('~'), 'Library', 'Application Support', 'DozaAssist')
    try:
        with open(os.path.join(support, 'backend.json'), 'r', encoding='utf-8') as f:
            info = json.load(f)
        u = (info.get('url') or '').strip()
        return u.rstrip('/') or None
    except (OSError, ValueError, AttributeError):  # unreadable, or not {"url": "..."}
        return None


# ── minimal JSON-schema validation (required / type / enum / bounds) ────────

_TYPES = {
    'string': str, 'number': (int, float), 'integer': int, 'boolean': bool,
    'array': list, 'object': dict,
}


def _finite(value) -> bool:
    try:
        return math.isfinite(value)
    except OverflowError:  # an int too large for a float
        return False


def _check(value, schema, path):
    """Return a list of error strings (empty when valid)."""
    errs = []
    if 'anyOf' in schema:
        alts = schema['anyOf']
        if not any(not _check(value, alt, path) for alt in alts):
            errs.append(f'{path}: does not match any allowed shape')
        return errs
    typ = schema.get('type')
    if typ:
        py = _TYPES.get(typ)
        if py is not None:
            ok = isinstance(value, py) and not (typ in ('number', 'integer') and isinstance(value, bool))
            if typ == 'integer' and isinstance(value, float) and value.is_integer():
                ok = True
            if not ok:
                errs.append(f'{path}: expected {typ}')
                return errs
            # json.loads takes NaN and Infinity; neither is a time or a count.
            if typ in ('number', 'integer') and not _finite(value):
                errs.append(f'{path}: must be a finite number')
                return errs
    if 'enum' in schema and value not in schema['enum']:
        errs.append(f'{path}: must be one of {schema["enum"]}')
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 'minimum' in schema and value < schema['minimum']:
            errs.append(f'{path}: must be ≥ {schema["minimum"]}')
        if 'maximum' in schema and value > schema['maximum']:
            errs.append(f'{path}: must be ≤ {schema["maximum"]}')
    if isinstance(value, str):
        if 'minLength' in schema and len(value) < schema['minLength']:
            errs.append(f'{path}: too short')
        if 'maxLength' in schema and len(value) > schema['maxLength']:
            errs.append(f'{path}: too long (max {schema["maxLength"]})')
    if isinstance(value, list):
        if 'minItems' in schema and len(value) < schema['minItems']:
            errs.append(f'{path}: needs at least {schema["minItems"]} item(s)')
        item_schema = schema.get('items')
        if item_schema:
            for i, item in enumerate(value):
                errs.extend(_check(item, item_schema, f'{path}[{i}]'))
    if isinstance(value, dict):
        props = schema.get('properties') or {}
        for req in schema.get('required') or []:
            if req not in value:
                errs.append(f'{path}.{req}: required')
        if schema.get('additionalProperties') is False:
            for k in value:
                if k not in props:
                    errs.append(f'{path}.{k}: unknown argument')
        for k, sub in props.items():
            if k in value:
                errs.extend(_check(value[k], sub, f'{path}.{k}'))
    return errs


def validate_args(tool: dict, args) -> list:
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return ['arguments: expected an object']
    return _check(args, tool.get('inputSchema') or {'type': 'object'}, 'arguments')


# ── backend bridge ─────────────────────────────────────────────────────────

# Matches the Electron shell of either edition. macOS pgrep compiles this as a
# POSIX extended regex, which has no (?:...) groups: a plain group is required,
# or pgrep exits 2 and the "starting up" hint below can never appear.
APP_PROCESS_PATTERN = r'Doza Assist( \(Studio\))?\.app/Contents/MacOS/'


def _app_running() -> bool:
    """True when a Doza Assist app process exists (macOS: the Electron shell)."""
    try:
        import subprocess
        out = subprocess.run(['pgrep', '-f', APP_PROCESS_PATTERN],
                             capture_output=True, text=True, timeout=3)
        return out.returncode == 0 and bool(out.stdout.strip())
    except Exception:
        return False


_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))
# The backend is up but busy (a long export): not "starting up".
_TIMED_OUT = {'error': 'Doza Assist took too long to answer. Try again in a moment.', 'code': 'timeout'}


def call_backend(name: str, args: dict, base: str | None = None, timeout: float = 120.0) -> dict:
    base = base or backend_url()
    if not base:
        # No backend.json yet: on the app's first launch Flask hasn't written it.
        if _app_running():
            return {'error': 'Doza Assist is starting up (the app is open but its backend is not '
                             'ready yet). Try again in a minute.', 'code': 'starting'}
        return {'error': 'Doza Assist is not running (no backend found). Open the app and try again.',
                'code': 'not_running'}
    data = json.dumps(args or {}).encode('utf-8')
    req = urllib.request.Request(
        f'{base}/studio/mcp/tool/{name}', data=data, method='POST',
        headers={'Content-Type': 'application/json', 'X-Doza-MCP': '1'})
    try:
        # Loopback only: never through an HTTP proxy (env or the macOS setting).
        with _NO_PROXY.open(req, timeout=timeout) as resp:
            body = resp.read().decode('utf-8')
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode('utf-8'))
        except Exception:
            payload = {}
        return {'error': payload.get('error') or f'Doza Assist returned HTTP {e.code}', 'code': payload.get('code')}
    except TimeoutError:
        return _TIMED_OUT
    except (urllib.error.URLError, OSError) as e:
        if isinstance(getattr(e, 'reason', None), TimeoutError):
            return _TIMED_OUT
        # The backend is not answering. If the app itself is running the
        # backend is starting (first launch, or the restart after a license
        # activation) and a retry in a moment will work; otherwise the app
        # is closed.
        if _app_running():
            return {'error': 'Doza Assist is starting up (the app is open but its backend is not '
                             'ready yet). Try again in a minute.', 'code': 'starting'}
        return {'error': f'Doza Assist is not running ({e}). Open the app and try again.',
                'code': 'not_running'}
    except ValueError:
        return {'error': 'Doza Assist returned an unreadable response.'}


# ── JSON-RPC dispatch ──────────────────────────────────────────────────────

class Server:
    def __init__(self, schema: dict | None = None, base: str | None = None):
        self.schema = schema or load_schema()
        self.tools = {t['name']: t for t in self.schema['tools']}
        self.base = base

    def handle(self, msg: dict):
        """Return a response dict, or None for notifications. A malformed
        message gets a JSON-RPC error, never an exception: one bad line
        must not take the connector down for the whole session."""
        mid = msg.get('id')
        if isinstance(mid, (dict, list, bool)) or (isinstance(mid, float) and not _finite(mid)):
            return self._err(None, -32600, 'Invalid Request: bad id')
        if 'method' not in msg and ('result' in msg or 'error' in msg):
            return None  # a client's response; this server sends no requests
        method = msg.get('method')
        if not isinstance(method, str):
            return self._err(mid, -32600, 'Invalid Request: method must be a string')
        # JSON-RPC: a message without an id is a notification. It gets no
        # reply, so it must not run anything (a tool call needs an id).
        if 'id' not in msg:
            return None
        params = msg.get('params')
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return self._err(mid, -32602, 'Invalid params: expected an object')
        if method == 'initialize':
            return self._ok(mid, {
                'protocolVersion': negotiate_protocol(params.get('protocolVersion')),
                'capabilities': {'tools': {'listChanged': False}},
                'serverInfo': self.schema['server'],
                'instructions': ('"Doza Assist (this Mac)": the editor\'s OWN projects on this computer that '
                                 'they opened to AI assistants. Read transcripts and selects, search a '
                                 'transcript, create selects, build a selects stringout. Only projects the '
                                 'editor switched on are listed. Nothing here can delete or edit the '
                                 'editor\'s own clips.'),
            })
        if method.startswith('notifications/'):
            # Sent as a request: answer it, unless its id is null (a loose client's notification).
            return None if mid is None else self._err(mid, -32601, f'Method not found: {method} is a notification')
        if method == 'ping':
            return self._ok(mid, {})
        if method == 'tools/list':
            # `title` and `annotations` (readOnlyHint etc.) let clients label
            # tools and auto-approve the read-only ones; `icons` (MCP spec
            # field) carries the Doza Assist app icon so clients that show
            # tool or connector icons display the logo.
            return self._ok(mid, {'tools': [
                {k: v for k, v in (
                    ('name', t['name']), ('title', t.get('title')),
                    ('description', t.get('description', '')),
                    ('inputSchema', t.get('inputSchema')),
                    ('annotations', t.get('annotations')), ('icons', t.get('icons')),
                ) if v is not None}
                for t in self.schema['tools']]})
        if method == 'tools/call':
            name = params.get('name')
            tool = self.tools.get(name) if isinstance(name, str) else None
            if not tool:
                return self._err(mid, -32602, f'Unknown tool: {name}')
            args = params.get('arguments')
            if args is None:
                args = {}
            if not isinstance(args, dict):
                return self._err(mid, -32602, 'Invalid params: arguments must be an object')
            errs = validate_args(tool, args)
            if errs:
                return self._ok(mid, self._tool_error('Invalid arguments: ' + '; '.join(errs)))
            result = call_backend(name, args, base=self.base)
            if isinstance(result, dict) and result.get('error'):
                return self._ok(mid, self._tool_error(result['error']))
            return self._ok(mid, {'content': [{'type': 'text', 'text': json.dumps(result, ensure_ascii=False)}],
                                  'isError': False})
        return self._err(mid, -32601, f'Method not found: {method}')

    @staticmethod
    def _tool_error(text: str) -> dict:
        return {'content': [{'type': 'text', 'text': text}], 'isError': True}

    @staticmethod
    def _ok(mid, result):
        return {'jsonrpc': '2.0', 'id': mid, 'result': result}

    @staticmethod
    def _err(mid, code, message):
        return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': code, 'message': message}}


def _handle_safely(server: 'Server', msg):
    """One message's reply (None for a notification). A message that isn't a
    JSON object is an Invalid Request; an unexpected failure is an internal
    error for that message, and the session carries on."""
    if not isinstance(msg, dict):
        return Server._err(None, -32600, 'Invalid Request: expected a JSON object')
    try:
        return server.handle(msg)
    except Exception as e:  # noqa: BLE001 - never let one message end the session
        _log(f'error handling {msg.get("method")!r}: {e!r}')
        mid = msg.get('id')
        if mid is None or isinstance(mid, (dict, list, bool)):
            return None
        return Server._err(mid, -32603, 'Internal error')


def serve(stdin=None, stdout=None) -> None:
    if stdin is None:
        # A byte that isn't UTF-8 becomes U+FFFD (then a parse error), not a crash.
        try:
            sys.stdin.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    server = Server()
    _log(f'ready (backend: {backend_url() or "not found yet"})')
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except (ValueError, RecursionError):  # RecursionError: absurdly deep nesting
            stdout.write(json.dumps({'jsonrpc': '2.0', 'id': None,
                                     'error': {'code': -32700, 'message': 'Parse error'}}) + '\n')
            stdout.flush()
            continue
        if isinstance(msg, list):
            if not msg:
                resp = Server._err(None, -32600, 'Invalid Request: empty batch')
            else:
                resp = [r for r in (_handle_safely(server, m) for m in msg) if r is not None] or None
        else:
            resp = _handle_safely(server, msg)
        if resp is not None:
            # ASCII escapes: a lone surrogate (half an emoji, which the page
            # can store in a select's text) can't be encoded as UTF-8 raw.
            stdout.write(json.dumps(resp) + '\n')
            stdout.flush()


if __name__ == '__main__':
    serve()
