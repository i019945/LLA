Import a YouTube story into the LLA app.

The user has provided a YouTube URL as the argument: $ARGUMENTS

The user is a TRUE BEGINNER still learning Hangul. Generate cards for EVERY content word — never curate or skip "basic" vocabulary.

---

## Step 1 — Download Korean subtitles

```
yt-dlp --write-auto-sub --sub-lang ko --skip-download \
  -o "/private/tmp/claude-501/-Users-i019945-LLA/bd7384cf-41b6-4267-b0ef-ee0c68098372/scratchpad/yt_import" \
  "$ARGUMENTS"
```

Parse the resulting `.ko.vtt` file:
- Strip the `WEBVTT` header line and blank separators.
- Strip timing lines (`\d{2}:\d{2}:\d{2}\.\d{3} --> ...`).
- Strip inline cue tags (`<\d{2}:\d{2}:\d{2}\.\d{3}>`, `<c>`, `</c>`).
- Deduplicate adjacent identical lines (auto-captions repeat).
- Join fragments into natural sentences (split on sentence-final `.`, `?`, `!`, `~`, `요.`, `다.` etc.).

## Step 2 — Get the video title

```
yt-dlp --get-title "$ARGUMENTS"
```

Use the title as both `story.title` and `story.deck`. Shorten to ≤ 40 chars if needed (e.g. "Walk in Seoul 016").

## Step 3 — Translate and generate cards (no API call needed — you are Claude)

For each sentence, provide a natural English translation.

For **every** content word (nouns, verbs, adjectives, adverbs) in the story, generate one card:

| Field | Rule |
|---|---|
| `korean` | **Nouns/adverbs**: bare dictionary form (e.g. `여행`, not `여행을`). The app's prefix-match lookup handles all particle-suffixed forms automatically. **Verbs/adjectives**: exact surface form as it appears in the sentence (e.g. `설레고`, not `설레다`). |
| `english` | `'dictionary form' (word type) English meaning` — e.g. `'설레다' (verb) to feel excitement/flutter` |
| `examples` | Array with one entry: `"Korean sentence = English translation"` |
| `notes` | One or two lines; each line: `Korean form : explanation`. Always note the dictionary form and what the surface form's conjugation/ending means. |
| `tag` | `"story"` |
| `deck` | Story title (same as `story.deck`) |
| `ease` | `2.0` — pre-set as difficult (all story vocabulary is new/unfamiliar to a beginner; lower ease = more frequent review until mastered) |
| `interval` | `1` |
| `nextReview` | `Date.now()` |
| `reps` | `0` |

Skip: particles (은/는/이/가/을/를/에/의/와/과…), pure copula 이다 when standalone, purely grammatical endings.

Do NOT skip words because they seem elementary. 있다, 되다, 좋다, 오다, 가다 all need cards.

## Step 4 — Build the injection script

Write `import_<slug>.js` to `/Users/i019945/LLA/`. Template:

```javascript
(function() {
  var DECK = '<story title>';

  // ── Story ──
  var stories = JSON.parse(localStorage.getItem('lla_stories') || '[]');
  if (stories.find(s => s.title === DECK)) return; // guard: don't re-import
  var story = {
    id: Date.now(),
    title: DECK,
    youtubeUrl: '<url>',
    sentences: [ /* {ko, en} objects */ ],
    deck: DECK,
    created: Date.now()
  };
  stories.unshift(story);
  localStorage.setItem('lla_stories', JSON.stringify(stories));

  // ── Cards ──
  var existing = JSON.parse(localStorage.getItem('lla_cards') || '[]');
  var existingKo = new Set(existing.filter(c => c.deck === DECK).map(c => c.korean));
  var base = Date.now();
  var newCards = [
    // { korean, english, examples: [...], notes, tag:'story', deck:DECK,
    //   level:'', trap:'', created:base, nextReview:base,
    //   interval:1, ease:2.0, reps:0, id:base+<index> }
  ];
  var toAdd = newCards.filter(c => !existingKo.has(c.korean));
  if (toAdd.length > 0) {
    localStorage.setItem('lla_cards', JSON.stringify(existing.concat(toAdd)));
  }

  alert(DECK + ' imported! Tap Stories to read it.');
})();
```

If the card list is long (> ~60 cards), split into two files: `import_<slug>.js` for the story + first half of cards, `import_<slug>_cards2.js` for the rest. Both use the same guard pattern.

## Step 5 — Wire into index.html and deploy

1. Add `<script src="import_<slug>.js"></script>` (and `_cards2.js` if split) to `index.html`, just before the main `<script>` block.
2. Bump `sw.js` cache version (e.g. `lla-v11` → `lla-v12`).
3. Commit:
   ```
   git add index.html sw.js import_<slug>.js && git commit -m "Import story: <title>"
   ```
4. `git push`
5. `rsync -av --exclude='.git' /Users/i019945/LLA/ stevenmeng@i019945mini:~/LLA/`

## Step 6 — Tell the user

Instruct the user to open the app — the story auto-imports on first load and shows an alert. Tell them to reply here when done so you can remove the injection script.

## Step 7 — Cleanup (after user confirms)

1. Remove `<script src="import_<slug>.js"></script>` (and `_cards2.js`) from `index.html`.
2. Delete `import_<slug>.js` (and `_cards2.js`) from the repo.
3. Bump SW version.
4. Commit, push, rsync.
