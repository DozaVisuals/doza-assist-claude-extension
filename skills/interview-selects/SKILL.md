---
name: interview-selects
description: Find soundbites and mark selects in the user's Doza Assist interview projects, then build a selects stringout. Use when the user mentions their Doza projects, asks for quotes or soundbites from an interview, wants selects marked or reviewed, or wants a stringout for their editing app.
---

# Selects from Doza Assist interviews

The Doza Assist tools read the projects the editor opened to AI in the Doza Assist app on their Mac: `list_my_projects`, `search_my_projects`, `get_my_transcript`, `get_my_selects`, `create_my_select` and `export_my_stringout`.

If those tools aren't available in this conversation, say so instead of guessing at transcript content. They run where Claude can start local tools on the editor's Mac: in Cowork tasks on that Mac and in Claude Code. For chat in the Claude desktop app, the editor installs them from Doza Assist (project page gear menu › AI assistant access › Add to Claude Desktop).

## Find the moments

1. Call `list_my_projects` and use the `id` it returns for the project the editor means. If it lists nothing, ask the editor to open Doza Assist and switch on AI assistant access for the project. If it says the app is starting up or not running, tell the editor and try again once the app is open.
2. For a theme, a name or a phrase, start with `search_my_projects`. Then read around the hits with `get_my_transcript`, passing `start` and `end` in seconds, rather than loading a long interview whole.
3. Trial copies of Doza Assist transcribe only the first two minutes of each file. If a long interview's transcript stops at 2:00, tell the editor that's the trial limit.

## Mark selects

1. Call `get_my_selects` first, so you don't duplicate selects the editor already marked.
2. Take `start` and `end` from the transcript segments. Start where a thought begins and end once it's complete; the app snaps the edges to the spoken words.
3. Give each select a short `note` on why it matters: the story beat, the emotion, or the fact it carries.
4. Before marking more than a handful, tell the editor how many you're about to add.

## Build the stringout

When the editor asks for one, call `export_my_stringout` and give them the file path it returns. The file is a timeline of the selects for their editing app.

## Report back

List each select with its timecode (mm:ss) and the first words of the quote. Selects you create show up in the project's Clip Library labeled "AI assistant". You can't delete or change the editor's clips; if they want a select removed, they do it in the app.
