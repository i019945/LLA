Import a YouTube story into the LLA app (production = the Mac Mini).

The user has provided a YouTube URL as the argument: $ARGUMENTS

The user is a TRUE BEGINNER still learning Hangul. Generate cards for EVERY content word — never curate or skip "basic" vocabulary.

**How data works now:** LLA's cards and stories live on the Mac Mini (`~/lla-data/data.json`, served at https://i019945mini.taila20961.ts.net/). An import is a DATA change made through the app's own API with `tools/import_story.py`. Do NOT create `import_*.js` scripts, do NOT edit `index.html` or `sw.js`, do NOT commit or rsync anything, and do NOT touch `cards.json` in the repo (it is only the first-start seed). The MacBook must be on Tailscale to reach the Mini.

---

## Step 1 — Get the Korean transcript

```
python3 /Users/i019945/workspace/yt_transcript.py "$ARGUMENTS" --lang ko --whisper-lang ko
```

It prints TITLE, CHANNEL and a transcript. It uses Korean captions when they exist and otherwise transcribes the audio locally with whisper. If the transcript says it came from whisper, tell the user it is machine-transcribed and double-check unusual words. Never ask the user to paste a transcript.

Turn the transcript into natural sentences (split on sentence-final `.`, `?`, `!`, `~`, `요.`, `다.` etc.; the captions are repeated and flattened, so de-duplicate).

## Step 2 — Get the video title

```
yt-dlp --get-title "$ARGUMENTS"
```

Use the title as both `story.title` and `story.deck`. Shorten to ≤ 40 chars if needed (e.g. "Walk in Seoul 016").

## Step 3 — Translate and generate cards (no API call needed — you are Claude)

For each sentence, provide a natural English translation.

### Morphological precision (CRITICAL — apply the `/morphology` skill)

Before writing any card, decompose every space-delimited token into its layers: root + particles + grammar endings + any irregular conjugation. The `/morphology` skill contains the full rules, particle list, grammar ending list, and irregular conjugation patterns.

Key rules (see `/morphology` for complete reference):
- **Nouns/adverbs**: `korean` = bare dictionary form (`여행`, not `여행을`). Note the particle in `notes`.
- **Verbs/adjectives**: `korean` = surface form exactly as it appears in the sentence (`걸을`, `되셨나요`). Decompose all layers in `notes`.
- **Stacked endings** (e.g. 되셨나요 = 되다+시+었+나요): decompose every layer — the user is a beginner.
- **Irregular conjugations** (ㄷ, ㄹ, ㅂ, ㅎ, 르, 으 irregulars): always name the rule in `notes`.
- Do NOT make cards for particles or grammar endings — built-in reference cards (tag: 'particle'/'grammar') already exist.

### Card fields

| Field | Rule |
|---|---|
| `korean` | See morphological rules above |
| `english` | `'dictionary form' (word type) English meaning` — e.g. `'설레다' (verb) to feel excitement/flutter` |
| `examples` | Array with one entry: `"Korean sentence = English translation"` |
| `notes` | Decompose the word per `/morphology` rules: dictionary form, conjugation layers, irregular rule name if applicable |
| `tag` | `"story"` |
| `deck` | Story title (same as `story.deck`) |
| `ease` | `2.0` — pre-set as difficult (all story vocabulary is new/unfamiliar to a beginner; lower ease = more frequent review until mastered) |
| `interval` | `1` |
| `nextReview` | `Date.now()` |
| `reps` | `0` |

Skip: particles (은/는/이/가/을/를/에/의/와/과…), pure copula 이다 when standalone, purely grammatical endings — these are already built-in reference cards.

Do NOT skip words because they seem elementary. 있다, 되다, 좋다, 오다, 가다 all need cards.

---

### ⚠ Lessons learned — do not skip these

**1. The `english` field is TTS-sensitive — format must be exact.**

The app's `speakMeaning()` function parses `'...' (type) meaning` and routes the quoted part to the **Korean voice** and the rest to the **English voice**. Errors here cause Korean words to be read with a Western accent.

Rules:
- The single-quoted part must be the **actual Hangul** dictionary form — nothing else.
- Do not put romanization, English gloss, or punctuation inside the quotes.
- Example correct: `'걷다' (verb) to walk`
- Example wrong: `'geotda' (verb) to walk` ← romanization in quotes → Korean TTS garbles it
- Example wrong: `'걷다, 걸어' (verb) to walk` ← extra forms in quotes → Korean TTS reads the comma

**2. Nouns must be bare dictionary form — it drives both lookup AND visual display.**

The story reader's `tokenizeKo()` function only visually splits a suffixed token (e.g. `생각만`) into word + subscript particle (`생각` + `만`) when the bare noun exists in the card interval map. Without a `생각` card, the word appears as an unsplit lump and the particle box never shows in the popup. The prefix-match lookup (levels 3–4 of `findCardForToken`) also depends on bare form. Never store nouns as `생각만`, `여행을`, etc.

**3. The vocab.json auto-add popup is a safety net, not a substitute for thorough import.**

When a tapped story word is absent from the user's cards but present in `vocab.json`, the app now auto-creates a card on the spot. However, these auto-added cards are bare-minimum quality:
- `ease: 2.5` (not the story-appropriate `2.0`)
- No example sentence from the story
- No morphology notes
- No `deck` / `tag` association with the story

A complete import at `ease: 2.0` with examples and notes is always preferred. The auto-add exists only as a fallback for words genuinely missed.

## Step 4 — Write the import file

Write `story.json` into the scratchpad directory (not into the repo):

```json
{
  "story": {
    "title": "<story title>",
    "youtubeUrl": "<url>",
    "sentences": [ {"ko": "<Korean sentence>", "en": "<English translation>"} ]
  },
  "cards": [
    { "korean": "<per the morphology rules>",
      "english": "'<Hangul dictionary form>' (<word type>) <English meaning>",
      "examples": ["<Korean sentence> = <English translation>"],
      "notes": "<decomposition per /morphology>" }
  ]
}
```

You do not need to fill `tag`, `deck`, `ease`, `interval`, `nextReview`, `reps`, `id`, `created`, `level` or `trap`: the tool sets them (tag `story`, deck = story title, ease 2.0, interval 1, due now, reps 0).

## Step 5 — Dry run (always first)

```
python3 /Users/i019945/LLA/tools/import_story.py <path>/story.json --dry-run
```

The tool validates the file (the quoted part of `english` must be Hangul only; required fields), skips a story title that already exists and any card whose Korean text already exists in ANY deck, and prints exactly what would be added. Fix every reported problem. Tell the user how many cards would be added and which words were skipped as duplicates.

## Step 6 — Import

```
python3 /Users/i019945/LLA/tools/import_story.py <path>/story.json
```

It saves with the server's revision check (a conflict is retried once). Running it again is harmless: nothing is added twice. Expect `"written": true` and a higher `rev_after`.

## Step 7 — Tell the user

Tell the user to open LLA on the phone and tap **↓ Load from Mini** (Vocabulary tab): the story appears under Stories and the cards under the story's deck. There is nothing to deploy and nothing to clean up afterwards. The Mini keeps its own backups, and the hourly backup copies the data to GitHub.
