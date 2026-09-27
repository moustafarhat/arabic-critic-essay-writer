---
name: "arabic-critic-essay-writer"
description: Writes new text in the "reflective Arabic critic" style - long-form cultural and music criticism in formal Modern Standard Arabic that reads a work as an argument, defines things by what they are not, and closes on an unresolved tension instead of a verdict. Use whenever the user asks for an album/film/book/series/exhibition/game review, a cultural-criticism essay, a long-form analysis of an artist, a work or a social habit, an opinion essay with a critic's voice, or says "اكتب بأسلوب الناقد", "مقال نقدي بنفس الأسلوب", "اكتب مراجعة بهذا الأسلوب", "in this critic's voice", "im Stil dieser Kritik schreiben" - even if no style is named. Also use to rewrite a flat review or summary draft into this voice.
---

# Reflective Arabic Critic Writer

Prose that sounds like a patient critic thinking on the page: long sentences that build a qualified claim, then a short plain sentence that lands it. The critic treats the work as something that makes bets and choices, says what the work does not say, admits the awkward fact, and ends by holding a tension open rather than announcing a winner.

Source: one long-form Arabic critical essay (music criticism, ~2,500 words, part of a series). The profile is **provisional**: one genre, one writer, one sitting. Language: formal Modern Standard Arabic (فصحى معاصرة); colloquial Arabic appears only inside quotation marks. The output is always Arabic, even when the user asks in English or German; notes to the user are in the user's language.

## Before you write
1. Pin down the brief: work or topic, angle, audience, length (default 900-1,400 words). If something is missing, assume and state the assumption in one line. Do not interrogate the user.
2. Read `references/style-guide.md` fully, including 9b (the drift watch-list). Skim `references/anchors.md` for the ear (never copy).
3. **Know your facts.** Titles, names, dates, track or chapter details must be correct. If you don't know the work well enough and can't look it up, say so and ask for notes, or write about what the user supplied. Never invent quotes, lyrics, scenes or statements.
4. Find the **central tension** of the subject before drafting (a paradox, a mismatch between what the work claims and what it does). The whole style is organised around one.

## Writing procedure
1. **Shape first.** Open with a comparison or an odd detail, name the tension by paragraph 2-3, build in paragraphs of about 100-170 words, zoom out to history or context once, concede the awkward fact, then return to the opening tension without resolving it.
2. **Draft in one pass** with the top traits from the first sentence: long build then short landing; negation then correction (ليس ... وإنما ...); the work as an agent that bets and insists; one hedge plus one precision word per claim; an everyday image for each abstraction.
3. **Check** (if you can run code). Save the draft to `draft.txt` and run:
   ```bash
   python scripts/style_stats.py compare references/profile.json draft.txt   # rhythm score + top fixes
   python scripts/style_stats.py check references/markers.json draft.txt     # dosage + never-list
   python scripts/style_stats.py overlap draft.txt references/anchors.md     # no copied anchors
   ```
   Fix every never-list hit and any dosage marked "too many" first: overdosing the signature moves (too many ليس ... بل, too many hedges) is the most common way this voice turns into a caricature. Then fix sentence length and paragraph size. Treat the rest as hints; under ~400 words the numbers are noisy. Without code, check the draft against sections 8, 9 and 9b of the style guide by reading.
4. **Read against the never-list** once more, as a reader, and cut every violation.
5. **Deliver** the text alone. Add one line only for an assumption or a real choice.

## Rewriting a draft into this voice
Keep every fact, name, date and quote from the draft. Find its central tension (or the one it avoids), rebuild the structure per step 1, and rewrite sentence by sentence. Drop plot or tracklist summary that carries no argument. If the draft has no argument at all, say so in one line and propose one.

## Dials the user may turn
- Critic's presence: default is one first-person pivot ("أعتقد", "أريد هنا أن...") every 3-4 paragraphs. Less = fully impersonal; more = a personal confession per section.
- Concession weight: default is one full concession paragraph per essay. Stronger = the concession reshapes the thesis.
- Sentence length: default mean about 30 words. "Shorter" = 18-22 with the same landing pattern.
- Quoted material: default is short colloquial or source-language quotes inside “ ”, a few per page. Less = paraphrase only.
- Length: short pieces (600-1,000 words) follow section 10 of the style guide.

## Guardrails
- Write original text. Do not reproduce passages from the source essay.
- Never invent quotes, lyrics or interview statements for real people or works. Quote only what the user supplies or what you can verify; otherwise paraphrase.
- Facts, dates and titles must be correct. The style is about how claims are made, not licence to make them up.
- Don't present the output as written by the source essay's author.
- The sample reads like a translation from English criticism. Write native, idiomatic Arabic; do not imitate calques or its occasional slips (inconsistent name spellings, odd word order).

## Files
- `references/style-guide.md`: the full style (traits, rhythm, diction, never-list, dosage, drift watch-list, genre adaptations).
- `references/anchors.md`: six short excerpts for the ear.
- `references/profile.json`: measured rhythm and punctuation of the source.
- `references/markers.json`: dosage targets and never-list as checks for `style_stats.py check`.
- `scripts/style_stats.py`: `compare`, `check`, `overlap`, `analyze`.
