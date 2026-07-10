Import a YouTube story into the LLA app.

The user has provided a YouTube URL as the argument: $ARGUMENTS

Steps:
1. Use yt-dlp to download Korean auto-subtitles: `yt-dlp --write-auto-sub --sub-lang ko --skip-download -o "/private/tmp/claude-501/-Users-i019945-LLA/bd7384cf-41b6-4267-b0ef-ee0c68098372/scratchpad/yt_import" "$ARGUMENTS"`
2. Parse the .ko.vtt file: strip WEBVTT headers, timing lines, inline timing tags, and deduplicate lines to get clean Korean text.
3. Infer a short title from the video title (use yt-dlp --get-title, or ask the user if unclear).
4. Translate each sentence to English and generate 15-20 vocabulary cards using your own knowledge (no API call needed — you are Claude).
5. Build the story JSON and cards in the format defined in the functional spec §13.
6. Write an `import_<slug>.js` one-time injection script to /Users/i019945/LLA/, add a `<script src="import_<slug>.js"></script>` tag to index.html before the main `<script>` block, bump sw.js cache version, commit, push, and rsync to Mini.
7. Tell the user to open the app — the story will auto-import on first load. Remind them to tell you when done so you can clean up the import script.
