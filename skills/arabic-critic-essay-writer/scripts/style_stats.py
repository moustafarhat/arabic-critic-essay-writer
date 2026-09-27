#!/usr/bin/env python3
"""style_stats.py - quantitative fingerprint of a writing style.

Commands:

  analyze FILE [FILE ...] [--json OUT.json]
      Measure sentence rhythm, paragraph shape, punctuation habits, vocabulary
      texture, sentence openers and recurring phrases. Prints a readable report
      and optionally saves the numbers as a JSON "profile".

  compare PROFILE.json DRAFT_FILE [--json]
      Measure a new draft and show, metric by metric, how far it is from the
      profile. Prints a similarity score and the three most important fixes first.

  check MARKERS.json DRAFT_FILE [--json]
      Count the style's own signature moves (dosage per 1,000 words) and
      never-list violations, as defined in the skill's references/markers.json.

  overlap DRAFT_FILE SOURCE [SOURCE ...] [--n 8] [--json]
      Find word sequences (default 8+ words; twice as many characters for
      Chinese/Japanese) that the draft shares verbatim with the source or the
      anchors. Any hit means copying: rewrite it.

Exit code: 0 = ok, 1 = problems found (compare: score below 70; check:
violations or dosage out of range; overlap: shared sequences), 2 = usage error.

Works on any language written in Unicode. Stop-words and person pronouns are
built in for English, German, French, Spanish, Portuguese, Italian and Arabic;
other languages get every metric except the person counts. Chinese and
Japanese are measured in characters instead of words. Markdown, code, URLs and
hard line wraps (PDF/e-book copies) are cleaned out before measuring.
Sentence splitting is heuristic, so treat numbers as good approximations, not
exact truth. Numbers describe the surface; the real style lives in the
qualitative analysis - use this as evidence, not as the goal.
"""
import argparse
import json
import re
import statistics
import sys
from collections import Counter

TASHKEEL = re.compile(r"[ً-ْٰـ]")  # Arabic diacritics + tatweel
CJK = "぀-ヿ㐀-䶿一-鿿豈-﫿"  # kana + Han (not Hangul: Korean uses spaces)
CJK_CHAR = re.compile(f"[{CJK}]")
# a token is one CJK character, or a run of letters (with inner apostrophes/hyphens)
WORD = re.compile(
    rf"[{CJK}]|(?:(?![{CJK}])[^\W\d_])+(?:['’\-](?:(?![{CJK}])[^\W\d_])+)*", re.UNICODE
)
CLOSERS = "\"'”’»)\\]」』"
SENT_SPLIT = re.compile(
    rf"(?<=[.!?؟…])[{CLOSERS}]*\s+"  # Latin/Arabic: end mark + whitespace
    rf"|(?<=[。！？])[{CLOSERS}]*"  # CJK: end mark, no space needed
)
QUOTED = re.compile(
    r"«[^»]*»|“[^”]*”|„[^“”]*[“”]"
    r"|「[^」]*」|\"[^\"\n]{1,400}\""
)

# Abbreviations that end in a period but do not end a sentence (casefolded, without final dot).
ABBREV = set(
    "mr mrs ms dr prof st jr sr vs etc e.g i.e cf fig no vol ch pp approx dept est inc ltd co "
    "z.b d.h u.a usw bzw ca nr vgl evtl ggf s bzgl inkl sog str "
    "m mme mlle p.ex av apr env "
    "sra srta dra p.ej pág núm "
    "sig dott ecc".split()
)

STOP = {
    "en": set("the a an and or but of to in on at for with as by is are was were be been it this that these those i you he she we they not from so if then than there their his her its our your my me him them who which what when".split()),
    "de": set("der die das und oder aber von zu in im auf an für mit als bei ist sind war waren sein es dies diese ich du er sie wir ihr nicht aus den dem des ein eine einen einem einer auch so wie wenn dass zum zur um nach über noch nur schon mehr sich hat haben wird werden".split()),
    "fr": set("le la les un une des et ou mais de du au aux à en dans sur pour par avec ce cette ces il elle ils elles nous vous je tu on ne pas que qui est sont était être a ont son sa ses leur leurs plus se comme si".split()),
    "es": set("el la los las un una unos unas y o pero de del al a en con por para que es son era fue ser se su sus lo le les no como más mi me te yo tú él ella nosotros ellos este esta estos si ya muy".split()),
    "pt": set("o a os as um uma uns umas e ou mas de do da dos das no na nos nas em com por para que é são era foi ser se seu sua seus não como mais eu me te você ele ela nós eles este esta isso muito já".split()),
    "it": set("il lo la i gli le un una e o ma di del della dei delle a al alla in nel nella con per che è sono era essere si suo sua non come più io mi ti tu lui lei noi voi loro questo questa anche già".split()),
    "ar": set("في من على إلى الى عن مع أن ان إن و ما لا هذا هذه ذلك تلك التي الذي الذين كان كانت كانوا هو هي هم هن أو ثم قد لم لن كل بعد قبل عند حتى أي كما إذا اذا لكن بل هنا هناك كي ليس".split()),
}
FIRST = {
    "en": set("i me my mine myself we us our ours".split()),
    "de": set("ich mich mir mein meine meinen meiner meines wir uns unser unsere unseren".split()),
    "fr": set("je j me m moi mon ma mes nous notre nos".split()),
    "es": set("yo me mí mi mis conmigo nosotros nosotras nos nuestro nuestra nuestros nuestras".split()),
    "pt": set("eu me mim meu minha meus minhas nós nos nosso nossa nossos nossas".split()),
    "it": set("io me mi mio mia miei mie noi ci nostro nostra nostri nostre".split()),
    "ar": set("أنا انا نحن".split()),
}
SECOND = {
    "en": set("you your yours yourself".split()),
    "de": set("du dich dir dein deine deinen deiner ihr euch euer eure".split()),
    "fr": set("tu te t toi ton ta tes vous votre vos".split()),
    "es": set("tú tu te ti tus contigo usted ustedes vosotros vosotras os vuestro vuestra".split()),
    "pt": set("tu te ti teu tua teus tuas você vocês vos".split()),
    "it": set("tu te ti tuo tua tuoi tue voi vi vostro vostra".split()),
    "ar": set("أنت انت أنتم انتم أنتما".split()),
}

PUNCT = {
    "comma": ",،、，",
    "semicolon": ";؛；",
    "colon": ":：",
    "dash": "—–",
    "parens": "(（",
    "quote_marks": "\"“”«»„「」",
    "question": "?؟？",
    "exclaim": "!！",
}


def quantile(sorted_vals, q):
    if not sorted_vals:
        return 0.0
    pos = (len(sorted_vals) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def detect_lang(text, tokens):
    """Return a language code with built-in word lists, 'cjk', or 'other'."""
    letters = [c for c in text if c.isalpha()]
    if letters and sum(1 for c in letters if CJK_CHAR.match(c)) / len(letters) > 0.3:
        return "cjk"
    lw = [t.casefold() for t in tokens]
    n = max(len(lw), 1)
    ratios = sorted(((sum(1 for t in lw if t in words) / n, lang) for lang, words in STOP.items()), reverse=True)
    (best, lang), (second, _) = ratios[0], ratios[1]
    # prose in a listed language is ~30-50% stop-words; an unlisted language that shares a few
    # short words (Dutch "de/en", Persian in Arabic script) scores lower and without a clear winner
    return lang if best >= 0.20 or (best >= 0.12 and best >= 2 * second) else "other"


def _continues(prev, nxt):
    """True if a split after `prev` was a false sentence break (abbreviation, lowercase follow-on)."""
    if not prev.endswith("."):
        return False
    if nxt[:1].islower():
        return True
    last = prev.rsplit(None, 1)[-1].casefold().rstrip(".")
    return last in ABBREV or (len(last) == 1 and last.isalpha())  # "J. K. Rowling"


def split_sentences(text):
    out = []
    for line in text.split("\n"):  # never merge across line breaks
        parts = [p.strip() for p in SENT_SPLIT.split(line) if p and p.strip()]
        merged = []
        for p in parts:
            if merged and _continues(merged[-1], p):
                merged[-1] += " " + p
            else:
                merged.append(p)
        out += merged
    return out


def get_paragraphs(text):
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paras) < 3 and text.count("\n") > 5:  # one paragraph per line
        paras = [p.strip() for p in text.split("\n") if p.strip()]
    return paras


def ngrams(tokens, n):
    return zip(*[tokens[i:] for i in range(n)])


LINE_END = rf"[.!?؟…。！？:{CLOSERS}]"  # a line ending in one of these was not hard-wrapped


def unwrap(text):
    """Join hard-wrapped lines (PDF/e-book copies) back into paragraphs.
    A line is treated as wrapped when most lines are long and don't end a sentence."""
    lines = [l for l in text.split("\n") if l.strip()]
    if len(lines) < 8:
        return text
    typical = sorted(len(l) for l in lines)[len(lines) // 2]
    open_ends = sum(1 for l in lines if not re.search(LINE_END + r"\s*$", l))
    if typical < 45 or open_ends / len(lines) < 0.5:
        return text
    out = re.sub(rf"(?<!{LINE_END})[ \t]*\n(?!\s*\n)[ \t]*", " ", text)
    return re.sub(r"(?<=[^\W\d_])-\s(?=[a-zäöüßàâçéèêëîïôûù])", "", out)  # re-join hyphenated breaks


def clean(text, keep_markup=False):
    """Remove what is not prose: code, URLs, HTML, Markdown markers, front matter.
    keep_markup=True keeps headings, list markers and bold (for never-list checks)."""
    text = text.replace("\r\n", "\n").lstrip("﻿")
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    text = re.sub(r"```.*?```|~~~.*?~~~", "\n\n", text, flags=re.S)
    text = re.sub(r"<[^>\n]+>", " ", text)
    text = re.sub(r"`[^`\n]+`", " ", text)
    text = re.sub(r"!?\[([^\]\n]*)\]\([^)\n]*\)", r"\1", text)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    if keep_markup:
        return text
    text = re.sub(r"^[ \t]*#{1,6}[ \t]+", "", text, flags=re.M)
    text = re.sub(r"^[ \t]*(?:[-*•]|\d+[.)])[ \t]+", "", text, flags=re.M)
    text = re.sub(r"\*\*|__", "", text)
    return unwrap(text)


def analyze_text(text, min_words=50):
    text = TASHKEEL.sub("", clean(text))
    tokens = WORD.findall(text)
    n_words = len(tokens)
    if n_words < min_words:
        raise SystemExit(f"Text too short to measure ({n_words} words; need at least {min_words}, "
                         "1,500+ is far better for a source).")
    lw = [t.casefold() for t in tokens]
    lang = detect_lang(text, tokens)
    stop = STOP.get(lang, set())

    # sentences
    sents = []
    for s in split_sentences(text):
        n = len(WORD.findall(s))
        if n:
            sents.append((s, n))
    lens = [n for _, n in sents]
    mean_len = statistics.fmean(lens)
    cv = statistics.pstdev(lens) / mean_len if mean_len else 0.0
    burst = (
        statistics.fmean(abs(a - b) for a, b in zip(lens, lens[1:])) / mean_len
        if len(lens) > 1 and mean_len
        else 0.0
    )
    sl = sorted(lens)
    # thresholds for "short" / "long" scale with the unit (CJK characters run ~2x a word count)
    short_max, long_min = (16, 60) if lang == "cjk" else (8, 30)

    # paragraphs
    paras = get_paragraphs(text)
    para_sents = [max(1, len(split_sentences(p))) for p in paras]
    para_words = [len(WORD.findall(p)) for p in paras]

    # punctuation per 1000 words
    per1k = {k: round(sum(text.count(c) for c in chars) * 1000 / n_words, 2) for k, chars in PUNCT.items()}
    per1k["ellipsis"] = round((text.count("…") + len(re.findall(r"\.{3}", text))) * 1000 / n_words, 2)

    # quoted speech share
    quoted_words = sum(len(WORD.findall(m.group(0))) for m in QUOTED.finditer(text))

    # lexical texture
    windows = [lw[i : i + 500] for i in range(0, n_words - 499, 500)]
    ttr = statistics.fmean(len(set(w)) / len(w) for w in windows) if windows else len(set(lw)) / n_words
    avg_word_len = statistics.fmean(len(t) for t in tokens)

    # openers
    openers = Counter(WORD.findall(s)[0].casefold() for s, _ in sents)
    top_openers = [(w, round(c / len(sents), 3)) for w, c in openers.most_common(8)]

    # persons (only where we have pronoun lists)
    if lang in FIRST:
        first = round(sum(1 for t in lw if t in FIRST[lang]) * 1000 / n_words, 2)
        second = round(sum(1 for t in lw if t in SECOND[lang]) * 1000 / n_words, 2)
    else:
        first = second = None

    # content words and recurring phrases
    min_len = 1 if lang == "cjk" else 3
    content = Counter(t for t in lw if t not in stop and len(t) >= min_len)
    min_count = 3 if n_words >= 3000 else 2
    joiner = "" if lang == "cjk" else " "
    phrases = []
    for n, keep in ((4, 8), (3, 12)):
        c = Counter(g for g in ngrams(lw, n) if not all(t in stop for t in g))
        found = [(joiner.join(g), k) for g, k in c.most_common(keep * 3) if k >= min_count][:keep]
        # drop shorter phrases that only echo an already-listed longer one
        found = [(g, k) for g, k in found if not any(g in longer and k <= kl for longer, kl in phrases)]
        phrases += found

    return {
        "language": lang,
        "unit": "characters" if lang == "cjk" else "words",
        "words": n_words,
        "sentences": len(sents),
        "paragraphs": len(paras),
        "mean_sentence_len": round(mean_len, 2),
        "median_sentence_len": round(statistics.median(lens), 2),
        "p10_sentence_len": round(quantile(sl, 0.10), 1),
        "p90_sentence_len": round(quantile(sl, 0.90), 1),
        "max_sentence_len": max(lens),
        "short_sentence_share": round(sum(1 for n in lens if n <= short_max) / len(lens), 3),
        "long_sentence_share": round(sum(1 for n in lens if n >= long_min) / len(lens), 3),
        "sentence_len_cv": round(cv, 3),
        "burstiness": round(burst, 3),
        "paragraph_len_sentences": round(statistics.fmean(para_sents), 2),
        "paragraph_len_words": round(statistics.fmean(para_words), 1),
        "avg_word_len": round(avg_word_len, 2),
        "ttr_500": round(ttr, 3),
        "quoted_share": round(quoted_words / n_words, 3),
        "first_person_per1k": first,
        "second_person_per1k": second,
        "opener_top1_share": top_openers[0][1] if top_openers else 0,
        "punct_per1k": per1k,
        "top_openers": top_openers,
        "top_content_words": content.most_common(25),
        "recurring_phrases": phrases,
    }


def report(p):
    unit = p.get("unit", "words")
    short_max, long_min = (16, 60) if p["language"] == "cjk" else (8, 30)
    L = []
    L.append(f"Language guess: {p['language']} | {p['words']} {unit}, {p['sentences']} sentences, {p['paragraphs']} paragraphs")
    if p["words"] < 1500:
        L.append("  (!) Under ~1,500 words: treat these numbers as a rough sketch.")
    if p["language"] == "other":
        L.append("  (language without built-in word lists: person counts skipped, phrase lists may include function words)")
    L.append("")
    L.append(f"SENTENCE RHYTHM ({unit})")
    L.append(f"  mean {p['mean_sentence_len']} | median {p['median_sentence_len']} | p10 {p['p10_sentence_len']} | p90 {p['p90_sentence_len']} | max {p['max_sentence_len']}")
    L.append(f"  short (<={short_max}): {p['short_sentence_share']:.0%} | long (>={long_min}): {p['long_sentence_share']:.0%}")
    L.append(f"  variation (cv): {p['sentence_len_cv']} | burstiness (avg jump between neighbours / mean): {p['burstiness']}")
    L.append("PARAGRAPHS")
    L.append(f"  {p['paragraph_len_sentences']} sentences / {p['paragraph_len_words']} {unit} on average")
    L.append(f"PUNCTUATION (per 1,000 {unit})")
    L.append("  " + " | ".join(f"{k} {v}" for k, v in p["punct_per1k"].items()))
    L.append("VOICE")
    if p["first_person_per1k"] is None:
        L.append(f"  quoted speech {p['quoted_share']:.0%} of {unit} (person counts not available for this language)")
    else:
        L.append(f"  first person {p['first_person_per1k']}/1k | second person {p['second_person_per1k']}/1k | quoted speech {p['quoted_share']:.0%} of words")
    if p["language"] in ("ar", "es", "pt", "it"):
        L.append("  (pronouns only - person carried by verb endings is not counted)")
    L.append("VOCABULARY TEXTURE")
    L.append(f"  avg word length {p['avg_word_len']} | type-token ratio (500-{unit[:-1]} windows) {p['ttr_500']}")
    L.append("SENTENCE OPENERS (share of sentences)")
    L.append("  " + ", ".join(f"{w} {s:.0%}" for w, s in p["top_openers"]))
    L.append("TOP CONTENT WORDS (mostly topic - do not confuse with style)")
    L.append("  " + ", ".join(f"{w} ({c})" for w, c in p["top_content_words"]))
    L.append("RECURRING PHRASES (candidate signature moves - check them in context)")
    L.append("  " + (" | ".join(f"{g} ({c})" for g, c in p["recurring_phrases"]) or "none found"))
    return "\n".join(L)


# metric: (hint if draft is higher, hint if lower, relative tolerance)
# rhythm-variation metrics are noisy on short drafts, so they get more room
HINTS = {
    "mean_sentence_len": ("sentences run long - split or cut", "sentences run short - let some clauses extend", 0.25),
    "sentence_len_cv": ("rhythm too uneven", "rhythm too uniform - vary sentence lengths", 0.35),
    "burstiness": ("jumps between short and long are stronger than the source", "not enough short/long alternation", 0.35),
    "paragraph_len_sentences": ("paragraphs too long - break them", "paragraphs too short - merge", 0.35),
    "avg_word_len": ("vocabulary heavier than the source", "vocabulary plainer than the source", 0.10),
    "ttr_500": ("vocabulary more varied than the source", "vocabulary more repetitive than the source", 0.15),
    "quoted_share": ("more quoted speech than the source", "less quoted speech than the source", 0.50),
    "first_person_per1k": ("more 'I/we' than the source", "less 'I/we' than the source", 0.40),
    "second_person_per1k": ("addresses the reader more than the source", "addresses the reader less than the source", 0.40),
    "opener_top1_share": ("sentence openers too repetitive", "sentence openers more varied than the source", 0.50),
}
PUNCT_TOL = 0.40
# below these absolute levels a difference is noise, not style
FLOOR = {"quoted_share": 0.03, "opener_top1_share": 0.05, "first_person_per1k": 2, "second_person_per1k": 2}
PUNCT_FLOOR = 1.5


WEIGHTS = {  # how much each metric matters for how a voice *feels*; punctuation rows weigh 1
    "mean_sentence_len": 3, "sentence_len_cv": 3, "burstiness": 2, "paragraph_len_sentences": 2,
    "avg_word_len": 1, "ttr_500": 1, "quoted_share": 1, "first_person_per1k": 2,
    "second_person_per1k": 2, "opener_top1_share": 1,
}


def compare_data(profile, draft):
    """Score a draft profile against a source profile (0-100) and list the top fixes."""
    scale = 1.5 if draft["words"] < 400 else 1.0  # short drafts: widen every tolerance
    rows = []
    for k, (hi, lo, tol) in HINTS.items():
        s, d = profile.get(k), draft.get(k)
        if s is None or d is None:
            continue
        rows.append((k, s, d, hi, lo, tol, FLOOR.get(k, 0), WEIGHTS.get(k, 1)))
    for k, s in profile["punct_per1k"].items():
        d = draft["punct_per1k"].get(k, 0)
        rows.append((f"{k}/1k", s, d, f"more {k} than the source", f"fewer {k} than the source",
                     PUNCT_TOL, PUNCT_FLOOR, 1))
    out, total, good = [], 0, 0.0
    for name, s, d, hi, lo, tol, floor, w in rows:
        dev = abs(d - s) / max(abs(s), 1e-9)
        allowed = tol * scale
        ok = max(abs(s), abs(d)) < floor or dev <= allowed
        total += w
        good += w if ok else w * max(0.0, 1 - (dev - allowed))  # partial credit for near misses
        out.append({"metric": name, "source": s, "draft": d, "ok": ok, "weight": w,
                    "deviation": round(dev, 2), "tolerance": round(allowed, 2),
                    "hint": "" if ok else (hi if d > s else lo)})
    score = round(100 * good / total) if total else 100
    misses = [r for r in out if not r["ok"]]
    fixes = sorted(misses, key=lambda r: -r["weight"] * min(r["deviation"] / max(r["tolerance"], 1e-9), 3))[:3]
    return {"score": score, "rows": out, "top_fixes": [f"{r['metric']}: {r['hint']}" for r in fixes],
            "draft_words": draft["words"]}


def compare(profile, draft):
    res = compare_data(profile, draft)
    L = [f"Similarity score: {res['score']}/100 (surface metrics only; 70+ is usually close enough)"]
    if res["top_fixes"]:
        L.append("Fix first:")
        L += [f"  {i}. {f}" for i, f in enumerate(res["top_fixes"], 1)]
    L.append("")
    L.append(f"{'metric':<26}{'source':>10}{'draft':>10}   verdict")
    off = 0
    for r in res["rows"]:
        if not r["ok"]:
            off += 1
        L.append(f"{r['metric']:<26}{r['source']:>10}{r['draft']:>10}   {'ok' if r['ok'] else '-> ' + r['hint']}")
    L.append("")
    L.append(f"{off} of {len(res['rows'])} metrics outside their tolerance.")
    if draft["words"] < 200:
        L.append("(!) Draft under 200 words: these numbers are noisy - weigh them lightly.")
    L.append("Reminder: metrics catch surface drift only. Re-read the draft against the style guide's signature moves and never-list.")
    return "\n".join(L)


# ------------------------------------------------------------ markers check
_AR_UNIFY = str.maketrans({"آ": "ا", "أ": "ا", "إ": "ا", "ى": "ي"})


def norm(text):
    """Normalise for matching: no diacritics/tatweel, unified alef/ya, casefolded."""
    return TASHKEEL.sub("", text).translate(_AR_UNIFY).casefold()


def norm_pat(pattern):
    """Normalise a regex the same way, without casefolding (\\S must stay \\S)."""
    return TASHKEEL.sub("", pattern).translate(_AR_UNIFY)


def check_data(markers, raw):
    """markers.json format:
    {"dosage": [{"name": "...", "patterns": ["regex", ...], "per1k": [min, max]}],
     "never":  [{"name": "...", "pattern": "regex"}],
     "paragraph_openers_no_repeat": ["regex", ...]}    (optional)
    Patterns are matched on normalised text (see norm), multiline, case-insensitive."""
    text = norm(clean(raw, keep_markup=True))
    words = max(len(WORD.findall(text)), 1)
    res = {"words": words, "dosage": [], "never": [], "problems": 0}
    for d in markers.get("dosage", []):
        n = sum(len(re.findall(norm_pat(p), text, flags=re.M | re.I)) for p in d["patterns"])
        rate = round(n * 1000 / words, 2)
        lo, hi = d.get("per1k", [0, 1e9])
        status = "ok" if lo <= rate <= hi else ("too few" if rate < lo else "too many")
        if status != "ok" and words >= 250:
            res["problems"] += 1
        res["dosage"].append({"name": d["name"], "count": n, "per1k": rate, "target": [lo, hi], "status": status})
    for v in markers.get("never", []):
        hits = [m.group(0).strip()[:60] for m in re.finditer(norm_pat(v["pattern"]), text, flags=re.M | re.I)]
        if hits:
            res["problems"] += 1
            res["never"].append({"name": v["name"], "count": len(hits), "examples": hits[:3]})
    pats = markers.get("paragraph_openers_no_repeat", [])
    if pats:
        paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        flags_ = [any(re.match(norm_pat(p), para, flags=re.I) for p in pats) for para in paras]
        runs = sum(1 for a, b in zip(flags_, flags_[1:]) if a and b)
        if runs:
            res["problems"] += 1
            res["never"].append({"name": "consecutive paragraphs open with the same move", "count": runs, "examples": []})
    return res


def check(markers, raw):
    r = check_data(markers, raw)
    L = [f"Signature check on {r['words']} words: {'OK' if not r['problems'] else str(r['problems']) + ' problem(s)'}"]
    if r["words"] < 250:
        L.append("(!) Under 250 words: dosage is only indicative, not enforced.")
    if r["dosage"]:
        L.append("\nDosage (per 1,000 words):")
        for d in r["dosage"]:
            L.append(f"  {d['name']:<38} {d['per1k']:>6}  target {d['target'][0]}-{d['target'][1]}   {d['status']}")
    if r["never"]:
        L.append("\nNever-list violations:")
        for v in r["never"]:
            ex = f"  e.g. {' | '.join(v['examples'])}" if v["examples"] else ""
            L.append(f"  - {v['name']} (x{v['count']}){ex}")
    return "\n".join(L), r


# ------------------------------------------------------------ copy check
def overlap_data(draft, sources, n=8):
    """Find runs of n+ tokens the draft shares verbatim with any source (CJK: 2n characters)."""
    dt = WORD.findall(norm(clean(draft)))
    cjk = bool(dt) and sum(1 for t in dt if CJK_CHAR.match(t)) / len(dt) > 0.3
    if cjk:
        n *= 2  # one CJK token is one character, roughly half a word
    joiner = "" if cjk else " "
    grams = set()
    for src in sources:
        st = WORD.findall(norm(clean(src)))
        grams.update(tuple(st[i:i + n]) for i in range(len(st) - n + 1))
    spans, i = [], 0
    while i <= len(dt) - n:
        if tuple(dt[i:i + n]) in grams:
            j = i + n
            while j < len(dt) and tuple(dt[j - n + 1:j + 1]) in grams:
                j += 1
            spans.append(joiner.join(dt[i:j]))
            i = j
        else:
            i += 1
    return {"n": n, "shared_sequences": spans,
            "shared_words": sum(len(s) if cjk else len(s.split()) for s in spans)}


def read_files(paths):
    chunks = []
    for p in paths:
        with open(p, encoding="utf-8", errors="replace") as f:
            chunks.append(f.read())
    return "\n\n".join(chunks)


def main():
    if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to a legacy code page
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="fingerprint one or more text files")
    a.add_argument("files", nargs="+")
    a.add_argument("--json", help="save the profile as JSON")
    c = sub.add_parser("compare", help="compare a draft to a saved profile")
    c.add_argument("profile")
    c.add_argument("draft")
    c.add_argument("--json", action="store_true")
    k = sub.add_parser("check", help="count signature moves and never-list violations")
    k.add_argument("markers")
    k.add_argument("draft")
    k.add_argument("--json", action="store_true")
    o = sub.add_parser("overlap", help="find word sequences copied from the source/anchors")
    o.add_argument("draft")
    o.add_argument("sources", nargs="+")
    o.add_argument("--n", type=int, default=8)
    o.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.cmd == "analyze":
        prof = analyze_text(read_files(args.files))
        print(report(prof))
        if args.json:
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(prof, f, ensure_ascii=False, indent=2)
            print(f"\nProfile saved to {args.json}")
        return 0
    if args.cmd == "compare":
        with open(args.profile, encoding="utf-8") as f:
            prof = json.load(f)
        draft = analyze_text(read_files([args.draft]), min_words=30)
        res = compare_data(prof, draft)
        print(json.dumps(res, ensure_ascii=False, indent=2) if args.json else compare(prof, draft))
        return 0 if res["score"] >= 70 else 1
    if args.cmd == "check":
        with open(args.markers, encoding="utf-8") as f:
            markers = json.load(f)
        text, res = check(markers, read_files([args.draft]))
        print(json.dumps(res, ensure_ascii=False, indent=2) if args.json else text)
        return 1 if res["problems"] else 0
    if args.cmd == "overlap":
        res = overlap_data(read_files([args.draft]), [read_files([p]) for p in args.sources], args.n)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        elif res["shared_sequences"]:
            print(f"COPYING: {len(res['shared_sequences'])} sequence(s) of {res['n']}+ tokens shared with the source:")
            for sp in res["shared_sequences"]:
                print(f"  - {sp}")
        else:
            print(f"OK: no {res['n']}-token sequence shared with the source.")
        return 1 if res["shared_sequences"] else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
