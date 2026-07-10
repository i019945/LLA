# Korean Morphological Precision Guide

This skill defines how to decompose Korean words into their constituent parts when analyzing story text for the LLA app. Apply it during every `/import` and whenever writing notes for a card.

---

## Core Principle

Korean is agglutinative. A single space-delimited token can contain:

- A **root word** (noun, verb stem, adjective stem, adverb)
- One or more **particles** (suffixes marking the noun's grammatical role)
- One or more **grammar endings** (verb/adjective conjugation layers, which can stack)

Every layer must be accounted for in the card's `notes` field, even if there is already a reference card for that particle or ending.

---

## Root Form Rules

| Word type | `korean` field | Reason |
|---|---|---|
| Noun / adverb | Bare dictionary form (`여행`, not `여행을`) | App prefix-match finds bare form inside any particle-suffixed token |
| Verb / adjective | Surface form exactly as it appears in the sentence (`걸을`, `되셨나요`) | Card shows the real text the user sees; dictionary form goes in `notes` |

---

## Layer 1 — Particles (noun suffixes)

**Do NOT create new particle cards.** The following are already covered by built-in reference cards (`tag: 'particle'`). Just note them in the word card's `notes`.

| Particle | Role |
|---|---|
| 은 / 는 | Topic marker (은 after consonant, 는 after vowel) |
| 이 / 가 | Subject marker (이 after consonant, 가 after vowel) |
| 을 / 를 | Object marker (을 after consonant, 를 after vowel) |
| 와 / 과 | And / with (와 after vowel, 과 after consonant) |
| 에 | Location / time marker |
| 에서 | Location (action happening there) |
| 에게 / 한테 | To (a person) |
| 으로 / 로 | Direction / means (으로 after consonant, 로 after vowel/ㄹ) |
| 의 | Possessive |
| 도 | Also / even |
| 만 | Only |
| 부터 | From (starting point) |
| 까지 | Until / up to |
| 랑 / 이랑 | And / with (casual; 이랑 after consonant) |

**Vowel harmony reminder:** 을/를, 은/는, 이/가, 와/과, 으로/로 all follow consonant/vowel-final rules on the noun.

---

## Layer 2 — Grammar Endings (verb/adjective conjugation)

**Do NOT create new grammar ending cards.** The following are already covered by built-in reference cards (`tag: 'grammar'`). Note them in the word card's `notes`.

| Ending | Meaning |
|---|---|
| 고 | and / and then (connective) |
| 아서 / 어서 | because / so / and then (causal/sequential) |
| 면 / 으면 | if / when (conditional) |
| 지만 | but / although |
| 는데 / 은데 | background / contrast |
| 려고 / 으려고 | intending to / in order to |
| 네요 | I notice / how ~ (discovery) |
| 잖아요 | as you know / isn't it |
| 거든요 | you see / that's because |
| 기 | nominalizer (gerund) |
| 게 | adverbially / so that |
| 아요 / 어요 | polite present tense |

**Stacked endings are common.** Always decompose all layers:
- `되셨나요` = 되다 + 시 (honorific) + 었 (past) + 나요 (soft question)
- `살다 보면` = 살다 (live) + 보다 (try/experience) + 면 (if) → "if you keep living like this"
- `알게 됐어요` = 알다 + 게 (adverbial) + 되다 (become) + 았 (past) + 어요

---

## Layer 3 — Irregular Conjugations

Always identify and note irregular patterns. These must appear in the card's `notes` field with the rule name.

| Pattern | Trigger | Example |
|---|---|---|
| **ㄷ-irregular** | ㄷ stem before vowel ending → ㄹ | 걷다 → 걸어요, 걸을, 걸으면 (NOT 걷어요) |
| **ㄹ-irregular** | ㄹ stem drops before ㄴ, ㅂ, 시 | 살다 → 사는, 삽니다, 사세요 (NOT 살는) |
| **ㅂ-irregular** | ㅂ stem before vowel → 우 | 덥다 → 더워요, 추우면 |
| **ㅎ-irregular** | ㅎ adjective drops + vowel contracts | 빨갛다 → 빨개요 |
| **르-irregular** | 르 before 아/어 → ㄹㄹ | 모르다 → 몰라요; 부르다 → 불러요 |
| **으-irregular** | 으 drops before 아/어 | 쓰다 → 써요; 크다 → 커요 |

---

## Notes Field Format

For every content word card, the `notes` field should answer: **What is this word really?**

Structure:
```
dictionary_form (type) meaning in context
surface_form ← dictionary_form + ending1 + ending2 (explanation)
irregular_rule_name if applicable
```

**Example — 걸을:**
```
걷다 (verb) to walk
걸을 ← 걷다 + 을 (future/adjective modifier form)
ㄷ-irregular: 걷 → 걸 before vowel endings
```

**Example — 되셨나요:**
```
되다 (verb) to become / to be ready
되셨나요 ← 되다 + 시 (honorific) + 었 (past) + 나요 (soft question)
준비 되셨나요 = lit. "Has it become ready?" = "Are you ready?"
```

**Example — 여행을:**
(This word's card `korean` = `여행`, the particle is just noted)
```
여행 : noun, no irregulars
여행을 : 여행 + 을 (object marker, consonant-final noun)
```

---

## What NOT to do

- Do **not** make a card with `korean: '걸을'` and `notes: ''`. The notes must explain where `걸을` comes from.
- Do **not** create a new card for `을`, `는`, `고`, etc. — built-in reference cards exist.
- Do **not** use the bare dictionary form for verbs as the `korean` field — use the surface form that appears in the sentence text.
- Do **not** skip the decomposition if the ending is "obvious" — the user is a beginner who needs every layer spelled out.

---

## Quick Reference: App Infrastructure

The app's inline suffix-splitting in story text (`tokenizeKo`) automatically tries to visually separate a known particle/grammar ending from its base when:
1. The ending matches a built-in particle or grammar card's `korean` value
2. The base word has a card in `ivMap`

The word popup (`showWordPopup`) uses `findParticleCard` to detect a suffix even when no card matches the full token, showing "No card yet for [base]" + the ending's reference card.

These are best-effort heuristics — stacked endings and irregular forms won't always split cleanly inline. The `notes` field on the card is the authoritative decomposition.
