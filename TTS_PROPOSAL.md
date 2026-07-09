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

## 4. Notes: line-based format — `Korean : English` breakdowns

*(Format proposed by the user, 2026-07-09.)* Cards hold not just words but daily phrases and proverbs; Notes is where a sentence gets broken down into grammatical elements. So Notes gets its own convention, applied **per line** (Notes is a multi-line textarea — each line stands alone):

**Line type 1 — pure English.** Free commentary, no Hangul anywhere.

**Line type 2 — `Korean : English` breakdown.** Everything left of the first `:` is Korean (a grammatical element of the sentence), everything right of it is the English explanation. The `:` functions as a pause and is never spoken.

```
✓ 저는 : I plus the topic marker
✓ 이에요 : polite copula
✓ A proverb about persistence, used encouragingly.
✗ Pattern: Subject + noun + 이에요/예요     ← English line citing Hangul — rewrite as a breakdown line
```

As in Examples, keep each side pure — the English side of a breakdown shouldn't itself cite Hangul.

**Delimiter semantics across the card (deliberate):** `=` in Examples means *"is translated as"*; `:` in Notes means *"is explained as"*. Two delimiters, two relationships — a parser never guesses which one a line expresses.

### 4.1 The parser

Per line: if the text left of the first `:` contains Hangul → breakdown line (Korean voice for the left side, English voice for the right); otherwise → English line (English voice for the whole line). No thresholds, no guessing.

```js
async function speakNoteLine(line) {
  const [left, right] = splitOnce(line, ':');
  if (right && hasHangul(left)) {
    await speakSlowAndWait(left.trim(), koreanVoice, 'ko-KR');
    await speakSlowAndWait(right.trim(), engVoice, 'en-US');   // the gap = the pause
  } else {
    await speakSlowAndWait(line, engVoice, 'en-US');
  }
}
```

**Safety net (same as Examples):** any English side / English line that unexpectedly contains Hangul is routed through binary Hangul-run splitting (Korean runs → Korean voice, the rest → English voice — exact now that Chinese is out of scope) instead of letting the English voice `onerror` and skip. Legacy notes written in the old `저는 = I + topic marker 는.` style stay audible until cleaned up.

### 4.2 Whether to read Notes aloud at all

Still worth a toggle: Notes on a proverb card can be long, and hearing the full breakdown at 0.6× on *every* auto-play pass may drag. Suggested: a "read notes" checkbox in the auto-play bar (persisted like the interval), default **off**.

### 4.3 Auto-filling Notes later

The user intends to eventually have Claude fill the Notes field. The format makes this reliable in both directions: the auto-fill prompt can *demand* the format ("output one `Korean : English` line per grammatical element, or pure-English lines"), and the app can *validate* the output mechanically (every line either Hangul-free or `Hangul-left : colon : English-right`) before inserting it — malformed AI output gets rejected instead of silently polluting a card. This extends the existing `autoFill()` (which already fills Meaning + Trap via Claude Haiku) with a Notes section in the same request.

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

Confirmed so far (user feedback 2026-07-09):

- **Korean + English only** — Chinese dropped; all classification is binary Hangul-or-not.
- **Notes format (user's own proposal):** each line is either pure English or `Korean : English` with `:` as a spoken pause — see §4.
- **Future:** user may ask Claude to auto-fill Notes following this format (§4.3).

Still open:

1. **Adopt the Examples/Meaning format?** (4 rules in §3.1 — you're already ~90% compliant)
2. **Cleanup mode:** auto-fix existing cards mechanically, or produce a list for you to edit by hand? (Old notes in `저는 = …` style would also be converted to `저는 : …`.)
3. **"Read notes" toggle default:** proposal says default off (§4.2) — confirm or change.

Say "implement the TTS proposal" in a future session once you've decided.
