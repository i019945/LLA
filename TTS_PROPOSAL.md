# Proposal: Reading Mixed-Language Card Content Aloud Without Strange Accents

*Status: proposal only — no code changed. 2026-07-09*

## 1. What went wrong

We tried to make auto-play read the whole card (meaning + example sentences), and it failed in two opposite ways:

| Attempt | Rule | Failure |
|---|---|---|
| 1 | Detect one language per field, assign one voice | Meaning `"love (사랑)"` → 2 Hangul chars tipped detection to Korean → English read with Korean accent |
| 2 | 30% threshold before switching away from English | Example `"어디 있어요? = Where are you? 있어요 = is/are…"` → classified English → **English voice hits Hangul, fires `onerror`, skips the rest of the card** |
| 3 | Any Hangul → Korean voice | Whole mixed sentences read by the Korean voice → strong Korean accent on the English parts |

**Root cause:** every attempt assigned *one voice to one whole string*, but the strings themselves are multi-lingual. No single voice can read `어디 있어요? = Where are you?` correctly. The unit of voice assignment must be smaller than the field.

A second, minor issue: symbols like `=` are read aloud by some voices ("equals") and silently break flow in others.

## 2. Recommended approach: segment-level voice assignment

Split each text into **contiguous same-language runs**, then speak the runs in order, each with its own voice.

```
"어디 있어요? = Where are you? 있어요 = is/are, exists (from 있다)"
 └── ko: "어디 있어요?"
 └── en: "Where are you?"
 └── ko: "있어요"
 └── en: "is/are, exists (from"
 └── ko: "있다"
```

### 2.1 Segmentation algorithm (deterministic, no AI, no network)

Walk the string character by character and classify each char:

- **ko** — Hangul syllables U+AC00–U+D7A3, plus Jamo U+3130–U+318F
- **zh** — CJK Unified Ideographs U+4E00–U+9FFF (also U+3400–U+4DBF)
- **en** — Latin letters
- **neutral** — digits, spaces, punctuation, symbols (`= ( ) ? .` …)

Group consecutive same-class chars into runs. Neutral chars never start a run; they attach to the run in progress (or to the following run if at the start). This automatically solves the `(사랑)` problem: the parentheses are neutral, and `사랑` becomes its own 2-char Korean run read by the Korean voice — correct, since it *is* Korean.

**Smoothing rules** (to avoid choppy output):

1. Merge runs shorter than 2 letters into the neighboring run (protects against stray romanization letters).
2. Replace flow-breaking symbols before speaking: `=` → `", "` (a comma produces a natural pause in every engine); drop `( )` entirely.
3. Digits inherit the language of the surrounding run, so "3 days" is read in English and "3일" in Korean.

### 2.2 Speaking the segments

We already have everything needed:

- `speakSlowAndWait(text, voice, lang)` — awaits utterance end, 5s fallback
- `koreanVoice`, `engVoice`, `chnVoice` — loaded at init
- `detectLang()` logic can be repurposed for per-run classification

Pseudo-code:

```js
async function speakMixed(text) {
  for (const run of segmentByLanguage(text)) {
    if (!autoPlayActive || autoPlaySkip) return;
    const { voice, lang } = voiceFor(run.lang);   // ko→koreanVoice, zh→chnVoice, en→engVoice
    await speakSlowAndWait(run.text, voice, lang);
  }
}
```

**Voice-missing fallback:** if a device has no English or Chinese voice (`engVoice`/`chnVoice` null), fall back to the Korean voice for that run rather than skipping — accented is better than silent, and it can never `onerror` on its own script.

### 2.3 Why this fixes each observed failure

- **No more skipping:** no voice is ever asked to read a script it can't handle, so `onerror` doesn't fire mid-card.
- **No more Korean-accented English:** English runs always go to the en-US voice.
- **`(사랑)` case:** read as Korean — which is right, the word is Korean. The English part stays English.
- **`=` case:** replaced with a comma pause before speaking.

### 2.4 Costs and risks

- Free, offline, no API keys — still pure Web Speech API.
- Each voice switch adds ~100–300ms gap (the `safeSpeak` cancel-settle delay). A card back with 3 mixed examples might take a few seconds longer. Acceptable at auto-play's slow pace.
- iOS Safari utterance chaining is quirky, but we already run chained utterances with fallback timers in `speakSyllables` — the same pattern applies.
- Estimated size: ~40 lines (one `segmentByLanguage` function + one `speakMixed` function + swapping the auto-play back-face calls).

## 3. Alternatives considered (not recommended now)

**B. Claude-assisted annotation at save time.** Use the existing Anthropic key to have Claude split/annotate the card text once when the card is saved, storing a `speechSegments` array on the card. More intelligent (could handle romanization like "meo-geo" or decide some text isn't worth reading aloud), but adds cost, latency, an online dependency, and a data-model change. Character-class segmentation is deterministic and covers our real cards; revisit only if §2 proves insufficient.

**C. Cloud TTS (Google Cloud TTS, OpenAI audio).** Genuinely multilingual single voices with natural code-switching — the best possible audio quality. But: paid per character, needs an API key and network, and audio must be streamed/cached. Overkill for a personal PWA; the Web Speech route should be exhausted first.

## 4. Suggested test cards before rollout

1. `어디` — the example that exposed the skipping bug (ko + en + `=` symbols)
2. `사랑` — meaning `"love (사랑)"` (parenthetical Hangul inside English)
3. `아니요` — meaning contains Chinese (`注意這不是…`) → zh voice segment
4. A pure-English meaning (`"where"`) → en voice only
5. A card on a device with no Google voices (iPhone offline) → fallback path

## 5. Decision needed

If this looks right, say "implement the TTS proposal" in a future session — §2 is self-contained enough to build directly from this document.
