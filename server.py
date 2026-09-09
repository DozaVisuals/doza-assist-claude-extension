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
    except (OSError, ValueError):
        return None


# ── minimal JSON-schema validation (required / type / enum / bounds) ────────

_TYPES = {
    'string': str, 'number': (int, float), 'integer': int, 'boolean': bool,
    'array': list, 'object': dict,
}


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

def _app_running() -> bool:
    """True when a Doza Assist app process exists (macOS: the Electron shell)."""
    try:
        import subprocess
        out = subprocess.run(['pgrep', '-f', r'Doza Assist(?: \(Studio\))?\.app/Contents/MacOS/'],
                             capture_output=True, text=True, timeout=3)
        return out.returncode == 0 and bool(out.stdout.strip())
    except Exception:
        return False


def call_backend(name: str, args: dict, base: str | None = None, timeout: float = 120.0) -> dict:
    base = base or backend_url()
    if not base:
        return {'error': 'Doza Assist is not running (no backend found). Open the app and try again.'}
    data = json.dumps(args or {}).encode('utf-8')
    req = urllib.request.Request(
        f'{base}/studio/mcp/tool/{name}', data=data, method='POST',
        headers={'Content-Type': 'application/json', 'X-Doza-MCP': '1'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode('utf-8')
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode('utf-8'))
        except Exception:
            payload = {}
        return {'error': payload.get('error') or f'Doza Assist returned HTTP {e.code}', 'code': payload.get('code')}
    except (urllib.error.URLError, OSError) as e:
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
        """Return a response dict, or None for notifications."""
        method = msg.get('method')
        mid = msg.get('id')
        params = msg.get('params') or {}
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
        if method == 'notifications/initialized' or (method or '').startswith('notifications/'):
            return None
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
            tool = self.tools.get(name)
            if not tool:
                return self._err(mid, -32602, f'Unknown tool: {name}')
            args = params.get('arguments') or {}
            errs = validate_args(tool, args)
            if errs:
                return self._ok(mid, self._tool_error('Invalid arguments: ' + '; '.join(errs)))
            result = call_backend(name, args, base=self.base)
            if isinstance(result, dict) and result.get('error'):
                return self._ok(mid, self._tool_error(result['error']))
            return self._ok(mid, {'content': [{'type': 'text', 'text': json.dumps(result, ensure_ascii=False)}],
                                  'isError': False})
        if mid is None:
            return None
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


def serve(stdin=None, stdout=None) -> None:
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
        except ValueError:
            stdout.write(json.dumps({'jsonrpc': '2.0', 'id': None,
                                     'error': {'code': -32700, 'message': 'Parse error'}}) + '\n')
            stdout.flush()
            continue
        if isinstance(msg, list):
            responses = [r for r in (server.handle(m) for m in msg if isinstance(m, dict)) if r is not None]
            if responses:
                stdout.write(json.dumps(responses) + '\n')
                stdout.flush()
            continue
        if not isinstance(msg, dict):
            continue
        resp = server.handle(msg)
        if resp is not None:
            stdout.write(json.dumps(resp, ensure_ascii=False) + '\n')
            stdout.flush()


if __name__ == '__main__':
    serve()
