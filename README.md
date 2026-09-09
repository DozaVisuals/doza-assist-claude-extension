# Doza Assist connector for Claude Desktop

Lets Claude read the Doza Assist projects you choose on this Mac: the
transcript, the selects in the Clip Library, a transcript search, new selects
attributed to the assistant, and a selects stringout for your editing app.

Doza Assist is a local-first transcription and story-finding app for interview
and documentary editors, made by Doza Visuals (https://doza.ai). This
extension is a thin bridge: every tool call becomes a request to the Doza
Assist app running on your Mac, over the loopback interface only.

**This repo is the Claude Desktop extension (MCPB bundle) only.** It is a thin
bridge, MIT licensed. It talks to the paid **Doza Assist** app for macOS
(https://doza.ai, free trial included); it does not work with the open-source
Doza Assist Core, which has no assistant-access panel. The packed `Doza-Assist.mcpb` sits at the root of this repo (and on the
Releases page); the same bundle ships inside the app behind its
**Add to Claude Desktop** button.

## Requirements

- macOS 15 or later, Apple silicon.
- Doza Assist 1.1 or later installed in /Applications
  (free trial: https://doza.ai/download.html). The trial transcribes the
  first two minutes of a file; a license key removes the cap.
- Doza Assist must be open while Claude uses the connector.

## Setup

1. Install Doza Assist and open it. Import an interview and let it transcribe.
2. On the project page, open the gear menu and choose **AI assistant access**.
   Switch on **Claude can read this project**. Only projects you switch on are
   visible to Claude; everything else stays invisible. (On a collection page
   the same menu item switches every interview in the collection at once.)
3. Install this extension in Claude Desktop (double-click the .mcpb, or use
   the panel's **Add to Claude Desktop** button inside Doza Assist, which does
   the same thing). Leave the app folder setting at its default unless you run
   Doza Assist from another folder.
4. In Claude, ask: *"List my Doza projects."*

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
"AI assistant" so you always know which are yours.

## What it cannot do

Delete or change your clips, see your media files, see projects you have not
switched on, or read your My Style profiles. There is no delete tool.

## Privacy Policy

Full policy: https://doza.ai/legal/privacy. Contact: privacy@doza.ai.

**What the connector collects and sends.** Nothing goes to Doza Visuals. The
connector runs entirely on your Mac and talks only to the Doza Assist app on
the same machine (127.0.0.1). When you switch a project on, the transcript
text and the selects of that project are made readable by the AI assistant
you connected. Claude is a cloud service operated by Anthropic, so whatever
Claude reads through this connector is transmitted to and handled by
Anthropic under Anthropic's own terms and privacy policy, not ours.

**What never leaves your Mac.** Your video and audio files, projects you have
not switched on, your My Style profiles, and your Doza Assist settings.

**Storage and retention.** The connector stores nothing of its own. Selects
created by Claude are saved in your local Doza Assist project like any other
select and stay until you delete them in the app. Stringouts are written to
your Exports folder (~/Documents/Doza Assist/Exports). Access to a project
stays on until you turn it off in the same menu.

**Third-party sharing.** Doza Visuals does not receive, log, or share any
data from this connector. The only third party involved is the AI assistant
you chose to connect.

**Contact.** privacy@doza.ai, or https://doza.ai/legal/contact. Doza Visuals
LLC, North Easton, Massachusetts, USA.

## For reviewers

Doza Assist is a macOS app; the connector needs it installed and open.

1. Download Doza Assist from https://doza.ai/download.html (Apple silicon,
   macOS 15+), drag it to /Applications and open it. First launch downloads
   the local speech and language models (about a minute).
2. Optional: enter the review license key from the submission notes in
   Settings > License to lift the two-minute trial cap. Every tool also runs
   on the trial's two-minute transcripts.
3. Drag any short interview video or audio file onto the app (a talking-head
   clip is ideal). Wait for the transcript to appear.
4. On the project page: gear menu > **AI assistant access** > switch on
   **Claude can read this project**.
5. Install the extension: double-click `Doza-Assist.mcpb` from this repo
   (or press **Add to Claude Desktop** in that same panel). Keep the
   default app folder.
6. In Claude Desktop:
   - "List my Doza projects" -> `list_my_projects` returns the project.
   - "Read the transcript of <name>" -> `get_my_transcript`.
   - "Search <name> for <a word from the clip>" -> `search_my_projects`.
   - "What selects are in <name>?" -> `get_my_selects` (an empty list is
     valid on a fresh project).
   - "Mark 0:05 to 0:20 as a select" -> `create_my_select`; it appears in the
     app's Clip Library within seconds, labeled "AI assistant".
   - "Build a stringout of the selects in <name>" -> `export_my_stringout`
     returns the path of the timeline written to ~/Documents/Doza Assist/Exports.

   Switch the project off in the same menu and "List my Doza projects" returns
   nothing: that is the privacy gate.

## Building the bundle

`./pack.sh` zips this folder into `Doza-Assist.mcpb`. `npx @anthropic-ai/mcpb
validate manifest.json` checks the manifest. The server is plain Python with no
dependencies (`server.py`, schemas in `schema.json`); `run.sh` runs it with the
Python bundled inside the installed app, so users need no separate runtime.

## Support

https://doza.ai/legal/contact (one inbox, answered within a business day) or
the community Discord linked from https://doza.ai.
