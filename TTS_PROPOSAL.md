# Proposal: Reading Mixed-Language Card Content Aloud Without Strange Accents

*Status: proposal only — no code changed. 2026-07-09, revised same day to make a content convention the primary approach.*

## 1. What went wrong

We tried to make auto-play read the whole card (meaning + example sentences), and it failed in two opposite ways:

| Attempt | Rule | Failure |
|---|---|---|
| 1 | Detect one language per field, assign one voice | Meaning `"love (사랑)"` → 2 Hangul chars tipped detection to Korean → English read with Korean accent |
| 2 | 30% threshold before switching away from English | Example `"어디 있어요? = Where are you? 있어요 = is/are…"` → classified English → **English voice hits Hangul, fires `onerror`, skips the rest of the card** |
| 3 | Any Hangul → Korean voice | Whole mixed sentences read by the Korean voice → strong Korean accent on the English parts |

**Root cause:** every attempt assigned *one voice to one whole string*, but the strings themselves are multi-lingual. The unit of voice assignment must be smaller than the field. There are two ways to get smaller units: **guess** the structure from characters, or **agree on a format** so no guessing is needed. Guessing alone is what kept failing at the edges; the format is the fix.

## 2. Recommended approach: a content convention + a trivial parser

The good news: the existing cards already *almost* follow a convention. `어디`'s example is `어디 있어요? = Where are you?` — Korean, `=`, translation. We formalize exactly that.

### 2.1 The format (what you follow when writing cards)

**Rule 1 — Example fields: `Korean sentence = translation`, one pair per example slot.**
Everything **left of the first `=`** is Korean. Everything **right of it** is the translation (English or Chinese — auto-detected, they're trivially distinguishable by script).

```
✓ 어디 있어요? = Where are you?
✓ 저는 학생이에요 = 我是學生
✗ 어디 있어요? = Where are you? 있어요 = is/are…   ← two pairs in one slot; use Example 2
```

You have three example slots per card — one pair per slot. The 어디 card would become:
- Example 1: `어디 있어요? = Where are you?`
- Example 2: `있어요 = is/are, exists`

**Rule 2 — Keep each side pure.**
No Hangul on the translation side, no English on the Korean side. Instead of `is/are, exists (from 있다)`, put the dictionary form where it belongs: in **Notes** (not read aloud today) or as its own example pair (`있다 = to exist, dictionary form`).

**Rule 3 — Meaning field is translation-language only.**
`where` — not `where (어디)`. The Korean is already on the front of the card; repeating it in the meaning adds nothing for TTS and breaks purity.

**Rule 4 — No structural symbols other than the one `=`.**
Parentheses for optional info are fine but will be read as a pause; `=`, `→`, `|` inside a side are not.

### 2.2 The parser (what the code does)

Trivial by design — this is the point of the convention:

```js
function speakExample(ex) {
  const [kor, rest] = splitOnce(ex, '=');       // no '=' → treat whole as Korean
  await speakSlowAndWait(kor.trim(), koreanVoice, 'ko-KR');
  if (rest) {
    const lang = detectLang(rest);              // en vs zh by script — unambiguous
    await speakSlowAndWait(rest.trim(), voiceFor(lang), langFor(lang));
  }
}
```

The meaning field is one `detectLang` + one utterance. No thresholds, no run-merging heuristics, no edge cases — because the format eliminated them.

### 2.3 Handling cards that don't follow the format (yet)

Existing cards weren't written to a spec, so:

- **Safety net in code:** before speaking any side, check it for out-of-place script (Hangul on the translation side). If found, speak that side with the Korean voice rather than let the English voice `onerror` and skip. Accented is better than silent — and it only happens on non-conforming cards.
- **One-time cleanup:** I can scan `cards.json` and list every card whose examples/meaning violate the format (multiple `=`, mixed sides), and either fix them mechanically or hand you the list to edit. Current data is small (~40 cards); this is minutes, not hours.
- **Nudge at entry time (optional):** the Add/Edit form could show a soft hint when an example has no `=` or has Hangul after it. No enforcement — just a reminder.

### 2.4 Why this beats pure auto-segmentation

| | Format + parser | Character-run segmentation (previous §2) |
|---|---|---|
| Correctness | Deterministic — you told it the structure | Heuristic — merging rules, thresholds, edge cases |
| Code size | ~15 lines | ~40 lines + smoothing rules |
| Failure mode | Non-conforming card → falls back to Korean voice, still audible | Odd text → choppy or misassigned runs |
| Cost to you | Follow 4 simple rules (you mostly already do) | None |
| Also fixes | The `=`-read-aloud problem (it's a separator now, never spoken) | Needs a symbol-replacement step |

The character-run segmentation idea is kept in the appendix as a fallback if the convention ever feels too restrictive, but it shouldn't be built first.

## 3. Alternatives considered (not recommended now)

**B. Structured example fields** — split each example into two input boxes (Korean / translation), stored as `{ko, en}` objects. Cleanest data, but: data-model migration, wider edit forms on a phone screen, and the `=` convention gives the same information with zero UI change. Revisit only if the convention proves annoying.

**C. Claude-assisted annotation at save time** — have Claude segment card text via the existing API key, store `speechSegments`. Smart but adds cost, latency, and an online dependency for something a `split('=')` now does.

**D. Cloud TTS (Google/OpenAI)** — natural code-switching voices, best audio quality, but paid, online-only, and overkill for a personal PWA.

## 4. Test cards before rollout

1. `어디` — restructure into two example pairs per Rule 1; verify no skipping, correct voices
2. `사랑` — meaning cleaned to pure English per Rule 3
3. A Chinese-translation example (`… = 我是學生`) → zh voice on the right side
4. A legacy card with Hangul on the translation side → safety-net path (Korean voice, no skip)
5. iPhone with no Google voices → fallback voices still assigned per language

## 5. Decision needed

Two things to confirm, then it's buildable directly from this document:

1. **Adopt the format?** (4 rules in §2.1 — you're already ~90% compliant)
2. **Cleanup mode:** should I auto-fix existing cards mechanically, or produce a list for you to edit by hand?

Say "implement the TTS proposal" in a future session once you've decided.

---

## Appendix: character-run segmentation (fallback idea, superseded)

Split text into contiguous same-language runs by character class (Hangul U+AC00–U+D7A3 / CJK U+4E00–U+9FFF / Latin; neutral chars attach to the current run), speak each run with its own voice, merge runs shorter than 2 letters, replace `=` with a comma. Fixes skipping and accents without any content convention, at the cost of heuristics and choppier audio on dense mixes. Build only if the §2 convention proves too restrictive in practice.
