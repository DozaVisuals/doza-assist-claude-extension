# Doza Assist

![Doza Assist](icon.png)

Find the soundbites in your interviews without leaving Claude. This plugin
connects Claude to the projects you choose in Doza Assist, the Mac app for
interview and documentary editors, so Claude can read and search timecoded
transcripts, see the selects you've marked, mark new selects with a note on why
each moment matters, and build a selects stringout to open in your editing app.
A bundled skill walks Claude through that workflow.

Everything runs on your Mac. The plugin talks only to the Doza Assist app on the
same computer, and your video and audio files never leave it.

## Requirements

- A Mac with Apple silicon, running macOS 15 or later.
- Doza Assist 1.1 or later, any edition, installed in Applications and open
  while Claude works ([doza.ai/download](https://doza.ai/download)). In trial
  mode, transcripts cover the first two minutes of each file, so that's all
  Claude can read.

## Where it works

The plugin's connector is a local server, so it runs where Claude can start
tools on your Mac:

- **Cowork**, in tasks that run on your Mac
- **Claude Code**

Claude chat on the web, desktop and mobile doesn't start a plugin's local tools.
To use Doza Assist in chat in the Claude desktop app, install the extension that
ships with the app instead: on a project page, open the gear menu, choose
**AI assistant access** and press **Add to Claude Desktop**.

## Setup

1. Open Doza Assist, import an interview and let it transcribe.
2. On the project page, open the gear menu, choose **AI assistant access** and
   switch on **Claude can read this project**. Only projects you switch on are
   visible to Claude. On a collection page, the same switch covers every
   interview in the collection.
3. Install this plugin, then ask Claude: *"List my Doza projects."*

## What you can ask

| Tool | Example prompt |
| --- | --- |
| List My Doza Projects | "Which Doza projects can you see?" |
| Read a Transcript | "Read the transcript of *Maria interview* and summarize the story in five beats." |
| Search a Transcript | "Search *Maria interview* for every time she mentions her father." |
| Read Selects | "What selects have I already marked in *Maria interview*?" |
| Create a Select | "Mark the strongest 20 seconds about leaving home as a select." |
| Export a Selects Stringout | "Build a stringout of all the selects in *Maria interview*." |

Selects Claude creates appear in the open project within seconds, labeled
"AI assistant", so you always know which are yours.

## What it can't do

Delete or change your clips, see your video or audio files, see projects you
haven't switched on, or read your My Style profiles. There is no delete tool.

## What the plugin runs and sends

- `mcp/run.sh` finds the Doza Assist app (in /Applications or ~/Applications,
  or through Spotlight) and starts `mcp/server.py` with the Python bundled
  inside the app. Nothing is downloaded or installed, and nothing is written
  into the app.
- `mcp/server.py` reads `~/Library/Application Support/DozaAssist/backend.json`,
  which the app writes, to find the app's local address. It sends each tool call
  to the app at `http://127.0.0.1` (ports 5050 to 5060), never through a proxy.
  When the app doesn't answer, it runs `pgrep` to tell "starting up" from
  "not running".
- `mcp/schema.json` holds the tool definitions. Arguments are checked against
  them before anything is sent to the app.
- The app answers only for projects you switched on. Selects Claude creates are
  saved in that project, and stringouts are written to
  `~/Documents/Doza Assist/Exports`.
- The plugin makes no other network calls and sends nothing to Doza Visuals: no
  telemetry, no analytics.
- What Claude reads through the plugin (project names, transcript text and
  selects) becomes part of your conversation with Claude, which Anthropic
  handles under its own terms and privacy policy.

## Privacy

Full policy: [doza.ai/legal/privacy](https://doza.ai/legal/privacy). Contact:
privacy@doza.ai.

**What never leaves your Mac.** Your video and audio files, projects you haven't
switched on, your My Style profiles and your Doza Assist settings.

**Storage and retention.** The plugin stores nothing of its own. Selects Claude
creates stay in your Doza Assist project until you delete them in the app.
Access to a project stays on until you turn it off in the same menu.

**Third-party sharing.** Doza Visuals doesn't receive, log or share any data
from this plugin. The only third party involved is Anthropic, as the provider
of Claude.

Doza Visuals LLC, North Easton, Massachusetts, USA.

## For reviewers

Doza Assist is a macOS app, so the plugin needs it installed and open.

1. Download Doza Assist from https://doza.ai/download (Apple silicon, macOS 15
   or later), drag it to Applications and open it. The first launch downloads
   the local speech and language models, which takes about a minute.
2. Drag a short interview video or audio file onto the app (a talking-head clip
   is ideal) and wait for the transcript. The trial is enough: every tool works
   on trial transcripts.
3. On the project page, open the gear menu, choose **AI assistant access** and
   switch on **Claude can read this project**.
4. Install the plugin, then start a Cowork task on the same Mac or run Claude
   Code there.
5. Try each tool:
   - "List my Doza projects": `list_my_projects` returns the project.
   - "Read the transcript of <name>": `get_my_transcript`.
   - "Search <name> for <a word from the clip>": `search_my_projects`.
   - "What selects are in <name>?": `get_my_selects`. An empty list is valid
     on a fresh project.
   - "Mark 0:05 to 0:20 as a select": `create_my_select`. The select appears in
     the app's Clip Library within seconds, labeled "AI assistant".
   - "Build a stringout of the selects in <name>": `export_my_stringout`
     returns the path of the timeline it wrote to
     ~/Documents/Doza Assist/Exports.

Switch the project off in the same menu and "List my Doza projects" returns
nothing. That's the privacy gate.

## Support

[doza.ai/legal/contact](https://doza.ai/legal/contact), answered within a
business day, or the community Discord linked from [doza.ai](https://doza.ai).

## License

MIT. See [LICENSE](LICENSE).
