# Proposal: Reading Mixed-Language Card Content Aloud Without Strange Accents

*Status: proposal only — no code changed. 2026-07-09, revised twice same day: (1) content convention as primary approach, (2) user feedback — Chinese dropped, Notes handling added.*

**Scope: Korean and English only.** No Chinese voice, no three-way detection. This makes every classification binary — a character either is Hangul or it isn't — which removes all ambiguity from the design below.

## 1. What went wrong

We tried to make auto-play read the whole card (meaning + example sentences), and it failed in two opposite ways:

| Attempt | Rule | Failure |
|---|---|---|
| 1 | Detect one language per field, assign one voice | Meaning `"love (사랑)"` → 2 Hangul chars tipped detection to Korean → English read with Korean accent |
| 2 | 30% threshold before switching away from English | Example `"어디 있어요? = Where are you? 있어요 = is/are…"` → classified English → **English voice hits Hangul, fires `onerror`, skips the rest of the card** |
| 3 | Any Hangul → Korean voice | Whole mixed sentences read by the Korean voice → strong Korean accent on the English parts |

**Root cause:** every attempt assigned *one voice to one whole string*, but the strings themselves are multi-lingual. The unit of voice assignment must be smaller than the field. There are two ways to get smaller units: **guess** the structure from characters, or **agree on a format** so no guessing is needed.

## 2. Two kinds of fields, two treatments

The user's feedback exposed an important distinction: some fields *can* follow a format, and one field *legitimately can't*.

| Field | Nature | Treatment |
|---|---|---|
| Examples 1–3 | Sentence pairs — structure is natural | **Format convention** (§3) |
| Meaning | Single translation — purity is natural | **Format convention** (§3, Rule 3) |
| Notes | Grammar explanations — English prose citing Korean words, mixing is *inevitable and correct* | **Hangul-run splitting** (§4), or simply not read aloud |
| Korean (front) | Always pure Korean | Korean voice, as today |

## 3. Examples and Meaning: a content convention + a trivial parser

The existing cards already *almost* follow a convention. `어디`'s example is `어디 있어요? = Where are you?` — Korean, `=`, translation. We formalize exactly that.

### 3.1 The format (what you follow when writing cards)

**Rule 1 — Example fields: `Korean sentence = English translation`, one pair per example slot.**
Everything **left of the first `=`** is Korean. Everything **right of it** is English.

```
✓ 어디 있어요? = Where are you?
✗ 어디 있어요? = Where are you? 있어요 = is/are…   ← two pairs in one slot; use Example 2
```

You have three example slots per card — one pair per slot. The 어디 card would become:
- Example 1: `어디 있어요? = Where are you?`
- Example 2: `있어요 = is/are, exists`

**Rule 2 — Keep each side pure.**
No Hangul on the English side, no English on the Korean side. Instead of `is/are, exists (from 있다)`, put the dictionary form where it belongs: in **Notes** (where mixing is expected — see §4) or as its own example pair (`있다 = to exist, dictionary form`).

**Rule 3 — Meaning field is English only.**
`where` — not `where (어디)`. The Korean is already on the front of the card; repeating it in the meaning adds nothing for TTS and breaks purity.

**Rule 4 — No structural symbols other than the one `=`.**
Parentheses for optional info are fine but will be read as a pause; extra `=`, `→`, `|` inside a side are not.

### 3.2 The parser (what the code does)

Trivial by design — this is the point of the convention:

```js
async function speakExample(ex) {
  const [kor, eng] = splitOnce(ex, '=');        // no '=' → treat whole as Korean
  await speakSlowAndWait(kor.trim(), koreanVoice, 'ko-KR');
  if (eng) await speakSlowAndWait(eng.trim(), engVoice, 'en-US');
}
```

The meaning field is one English utterance. No language detection at all in the happy path — the format already says which side is which.

### 3.3 Handling cards that don't follow the format (yet)

- **Safety net in code:** before speaking the English side, check it for Hangul. If found, speak it with the Korean voice rather than let the English voice `onerror` and skip. Accented is better than silent — and it only happens on non-conforming cards. (Better: route it through the §4 Hangul-run splitter, same code path as Notes.)
- **One-time cleanup:** I can scan `cards.json` and list every card whose examples/meaning violate the format (multiple `=`, mixed sides), and either fix them mechanically or hand you the list to edit. Current data is small (~40 cards); this is minutes, not hours.
- **Nudge at entry time (optional):** the Add/Edit form could show a soft hint when an example has no `=` or has Hangul after it. No enforcement — just a reminder.

## 4. Notes: mixing is legitimate — split by Hangul runs

Notes are English prose that cites Korean (`저는 = I + topic marker 는. 이에요 = polite copula.`). Forcing a format here would fight the field's purpose, so no rules apply to Notes. Two options:

**Option A (default): don't read Notes aloud.** This is today's behavior. Notes are long; hearing a grammar paragraph at 0.6× on every auto-play pass would drag. Notes stay on-screen reading material.

**Option B (if wanted): Hangul-run splitting.** With Chinese out of scope this is *not* the fragile heuristic from the failed attempts — it's exact:

- Walk the string; every char is either Hangul (U+AC00–U+D7A3, plus Jamo) or not.
- Group into alternating runs; punctuation/digits/spaces attach to the run in progress.
- Korean runs → Korean voice; everything else → English voice.

```
"저는 = I + topic marker 는. 이에요 = polite copula."
 ko: "저는"      en: "= I + topic marker"      ko: "는."
 ko: "이에요"    en: "= polite copula."
```

No thresholds, no language guessing — binary classification can't misfire the way three-way detection did. The only remaining imperfection is cadence: rapid ko/en alternation produces slightly choppy audio with ~100–300ms voice-switch gaps. That's inherent to switching voices and acceptable for an optional feature.

Recommendation: ship §3 with Option A first; add Option B behind a toggle (e.g. a "read notes" checkbox in auto-play controls) only if you find you want it.

## 5. Alternatives considered (not recommended now)

**B. Structured example fields** — split each example into two input boxes (Korean / English), stored as `{ko, en}` objects. Cleanest data, but: data-model migration, wider edit forms on a phone screen, and the `=` convention gives the same information with zero UI change. Revisit only if the convention proves annoying.

**C. Claude-assisted annotation at save time** — have Claude segment card text via the existing API key, store `speechSegments`. Smart but adds cost, latency, and an online dependency for something a `split('=')` and a Hangul-run splitter now do.

**D. Cloud TTS (Google/OpenAI)** — natural code-switching voices, best audio quality, but paid, online-only, and overkill for a personal PWA.

## 6. Test cards before rollout

1. `어디` — restructure into two example pairs per Rule 1; verify no skipping, correct voices
2. `사랑` — meaning cleaned to pure English per Rule 3
3. A legacy card with Hangul on the English side → safety-net path (no skip, no crash)
4. A card with mixed-language Notes + "read notes" enabled → Hangul-run splitting (if Option B is built)
5. iPhone with no Google voices → fallback voices still assigned per language

## 7. Decision needed

Confirmed so far (user feedback 2026-07-09): **Korean + English only** — Chinese dropped; **Notes may mix freely** — handled by §4, no format rules there.

Still open:

1. **Adopt the format for Examples/Meaning?** (4 rules in §3.1 — you're already ~90% compliant)
2. **Cleanup mode:** auto-fix existing cards mechanically, or produce a list for you to edit by hand?
3. **Notes aloud:** Option A (not read — default) or Option B (Hangul-run splitting behind a toggle)?

Say "implement the TTS proposal" in a future session once you've decided.
