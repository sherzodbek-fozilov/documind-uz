"""Query–passage training pairs for fine-tuning the embedding model, from TRAIN chunks only.

Unit of data: an *article* (``CorpusChunk.article_key``), with one version per language.
Its passage is the article's first chunk (it holds the heading and the first sentence),
indexed the same way as in the service (``CorpusChunk.index_text``).

Rules (each enforced in code, see ``build_pairs``):
  * Only chunks whose split is "train" are read; a test chunk can never become a query
    source, a positive or a negative. The uz and ru versions of an article are in the
    same chapter group, so they are always on the same side of the split.
  * Validation = whole chapter groups held out from train (``holdout_groups``), so no
    article, translation or neighbouring chunk of a validation pair is trained on.
  * Queries: the article title and the article's first sentence, in uz-Latn and ru;
    cross-lingual pairs (uz title -> ru passage, ru title -> uz passage) only for
    articles whose two versions correspond (``versions_correspond``).
  * Noise (typos, no apostrophes, Cyrillic transliteration, dropped diacritics) is
    applied to queries only, never to passages; a few code-mixed uz/ru queries.
  * Hard negatives: the best BM25 hit (passage language, same side of the split) that is
    not a chunk of the positive's article in any language.

Randomness is seeded per (seed, article, language, query type), so a pair does not
change when other articles are added or removed.
"""

from __future__ import annotations

import hashlib
import random
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from ..retrieval.analyzers import get_analyzer
from ..retrieval.bm25 import BM25
from ..retrieval.corpus import CorpusChunk
from ..translit import latin_to_cyrillic

PAIR_LANGUAGES = ("uz-Latn", "ru")
QUERY_TYPES = ("title", "first_sentence", "xling_title", "mixed")
NOISE_TYPES = ("none", "typos", "no_apostrophes", "cyrillic", "cyrillic_no_diacritics",
               "no_diacritics")

_ARTICLE_HEAD_RE = re.compile(r"^\s*(?:\d{1,5}\s*-\s*(?:modda|модда)|статья\s+\d{1,5})\.?\s*",
                              re.IGNORECASE)
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+(?=[\"«(]?[A-ZА-ЯЁЎҚҒҲ0-9])")
_ENUM_RE = re.compile(r"^\s*(?:\(?\d{1,3}[.)]|[a-zа-я]\))\s+")
_APOSTROPHES_RE = re.compile("['`‘’ʻʼ´]")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
_WORD_RE = re.compile(r"[^\W\d_]{4,}")

MIN_BODY_WORDS = 6  # shorter articles are usually "repealed" stubs
MIN_SENTENCE_WORDS = 5
MAX_SENTENCE_WORDS = 40

# code-mixed templates: a title in one language inside a question frame of the other.
# The passage is in the frame's language (the language the user writes in).
MIXED_FRAMES = {
    "uz-Latn": ["{t} haqida qonunda nima deyilgan?", "{t} boʻyicha qoida qanday?"],
    "ru": ["что говорится про {t}?", "какие правила по {t}?"],
}

_UZ_CYRL_PLAIN = str.maketrans("ўқғҳЎҚҒҲ", "укгхУКГХ")
_RU_PLAIN = str.maketrans("ёйЁЙ", "еиЕИ")
_LATIN_LETTERS = "abdefghijklmnopqrstuvxyz"
_CYRILLIC_LETTERS = "абвгдежзиклмнопрстуфхцчшыэюя"


# --- article structure ------------------------------------------------------------------

def article_title(section_title: str | None) -> str | None:
    """"§ 2. … / 85-modda. Jamoa kelishuvlari" -> "Jamoa kelishuvlari"."""
    if not section_title:
        return None
    last = section_title.split(" / ")[-1]
    if not _ARTICLE_HEAD_RE.match(last):
        return None
    title = _ARTICLE_HEAD_RE.sub("", last).strip(" .:")
    return title if len(title) >= 3 else None


def article_body(text: str) -> str:
    """Text of a chunk after its article heading paragraph (and any heading before it)."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    for i, p in enumerate(paras):
        if _ARTICLE_HEAD_RE.match(p):
            return "\n\n".join(paras[i + 1:])
    return "\n\n".join(paras)


def first_sentence(text: str) -> str | None:
    """First sentence of the article body: at least MIN_SENTENCE_WORDS words, cut to
    MAX_SENTENCE_WORDS words; None when the body has no such sentence."""
    for para in article_body(text).split("\n\n"):
        para = _ENUM_RE.sub("", " ".join(para.split()))
        sentence = _SENTENCE_END_RE.split(para, maxsplit=1)[0].strip()
        words = sentence.split()
        if len(words) >= MIN_SENTENCE_WORDS:
            return " ".join(words[:MAX_SENTENCE_WORDS])
    return None


def _signature(text: str) -> tuple[int, tuple[str, ...]]:
    paras = [p for p in text.split("\n\n") if p.strip()]
    return len(paras), tuple(sorted(x.replace(",", ".") for x in _NUMBER_RE.findall(text)))


def versions_correspond(text_a: str, text_b: str) -> bool:
    """Two language versions of an article correspond when they have the same number of
    paragraphs and the same numbers in the text (the check of scripts/compare_versions.py,
    applied to the chunk texts). Wording changes that keep all numbers are not found."""
    return _signature(text_a) == _signature(text_b)


@dataclass
class ArticleVersion:
    key: tuple[str, int]
    language: str
    split_group: str
    chunks: list[CorpusChunk]

    @property
    def first(self) -> CorpusChunk:
        return self.chunks[0]

    @property
    def text(self) -> str:
        return "\n\n".join(c.text for c in self.chunks)

    @property
    def title(self) -> str | None:
        return article_title(self.first.section_title)


Articles = dict[tuple[str, int], dict[str, ArticleVersion]]


def group_articles(chunks: Iterable[CorpusChunk]) -> Articles:
    """{article key: {language: version}}; chunks keep corpus order. Chunks outside a
    numbered article are left out (they have no title to ask about)."""
    out: dict[tuple[str, int], dict[str, ArticleVersion]] = defaultdict(dict)
    for c in chunks:
        key = c.article_key
        if key is None:
            continue
        version = out[key].get(c.language)
        if version is None:
            out[key][c.language] = ArticleVersion(key, c.language, c.split_group or c.doc_id,
                                                  [c])
        else:
            version.chunks.append(c)
    return dict(out)


def holdout_groups(groups: Iterable[str], fraction: float, salt: str = "val-v1") -> set[str]:
    """Pick ~fraction of the split groups of each act (the part before "/") for validation,
    ordered by a salted hash: deterministic and independent of the test split."""
    by_act: dict[str, list[str]] = defaultdict(list)
    for g in set(groups):
        by_act[g.split("/")[0]].append(g)
    out: set[str] = set()
    for members in by_act.values():
        members.sort(key=lambda g: hashlib.sha256(f"{salt}:{g}".encode()).hexdigest())
        n = round(fraction * len(members))
        if fraction > 0 and len(members) > 1:
            n = max(1, min(n, len(members) - 1))
        out.update(members[:n])
    return out


# --- query noise (queries only) ---------------------------------------------------------

def strip_apostrophes(text: str) -> str:
    """"oʻz shartnomasiʼ" -> "oz shartnomasi" (how many people type Uzbek)."""
    return _APOSTROPHES_RE.sub("", text)


def drop_diacritics(text: str, language: str) -> str:
    """uz-Cyrl: ў қ ғ ҳ -> у к г х (keyboard without Uzbek letters, OCR); ru: ё й -> е и."""
    if language == "uz-Cyrl":
        return text.translate(_UZ_CYRL_PLAIN)
    if language == "ru":
        return text.translate(_RU_PLAIN)
    return unicodedata.normalize("NFC", text)


def add_typos(text: str, rng: random.Random, n_max: int = 2) -> str:
    """1..n_max character edits (swap, delete, double, replace) in words of >= 4 letters."""
    words = list(_WORD_RE.finditer(text))
    if not words:
        return text
    chars = list(text)
    targets = rng.sample(words, k=min(len(words), rng.randint(1, n_max)))
    # edit right to left so earlier offsets stay valid
    for m in sorted(targets, key=lambda m: m.start(), reverse=True):
        i = rng.randrange(m.start() + 1, m.end() - 1)  # never the first letter
        op = rng.choice(("swap", "delete", "double", "replace"))
        if op == "swap":
            chars[i], chars[i + 1] = chars[i + 1], chars[i]
        elif op == "delete":
            del chars[i]
        elif op == "double":
            chars.insert(i, chars[i])
        else:
            alphabet = _CYRILLIC_LETTERS if "Ѐ" <= chars[i].lower() <= "ӿ" else _LATIN_LETTERS
            options = [a for a in alphabet if a != chars[i].lower()]
            new = rng.choice(options)
            chars[i] = new.upper() if chars[i].isupper() else new
    return "".join(chars)


def noisy_variants(query: str, language: str, rng: random.Random) -> list[tuple[str, str, str]]:
    """Applicable (noise type, query language, noisy query); variants equal to the clean
    query are dropped."""
    out = [("typos", language, add_typos(query, rng))]
    if language == "uz-Latn":
        out.append(("no_apostrophes", language, strip_apostrophes(query)))
        cyrl = latin_to_cyrillic(query)
        out.append(("cyrillic", "uz-Cyrl", cyrl))
        out.append(("cyrillic_no_diacritics", "uz-Cyrl", drop_diacritics(cyrl, "uz-Cyrl")))
    elif language == "ru":
        out.append(("no_diacritics", language, drop_diacritics(query, "ru")))
    seen = {query}
    unique = []
    for noise, lang, text in out:
        if text not in seen:
            seen.add(text)
            unique.append((noise, lang, text))
    return unique


def _rng(seed: int, *parts: object) -> random.Random:
    return random.Random(":".join(str(p) for p in (seed, *parts)))


# --- hard negatives ---------------------------------------------------------------------

class NegativeMiner:
    """BM25 over a fixed set of chunks; returns the best hit in a language that is not in
    the excluded article."""

    def __init__(self, chunks: Sequence[CorpusChunk], analyzer: str = "fold+stem6",
                 depth: int = 50):
        self.chunks = list(chunks)
        self.analyze = get_analyzer(analyzer)
        self.depth = depth
        self.index = BM25().fit([self.analyze(c.index_text) for c in self.chunks])
        self.by_lang: dict[str, set[int]] = defaultdict(set)
        for i, c in enumerate(self.chunks):
            self.by_lang[c.language].add(i)

    def mine(self, query: str, language: str, exclude_article: tuple[str, int],
             exclude_text: str) -> tuple[CorpusChunk | None, int | None]:
        """(negative, its BM25 rank among the language's chunks) or (None, None)."""
        cand = self.by_lang.get(language, set())
        hits = self.index.search(self.analyze(query), self.depth, cand)
        for rank, (i, _score) in enumerate(hits, start=1):
            c = self.chunks[i]
            if c.article_key != exclude_article and c.index_text != exclude_text:
                return c, rank
        return None, None

    def random(self, language: str, exclude_article: tuple[str, int],
               rng: random.Random) -> CorpusChunk | None:
        pool = sorted(i for i in self.by_lang.get(language, set())
                      if self.chunks[i].article_key != exclude_article)
        return self.chunks[rng.choice(pool)] if pool else None


# --- pairs ------------------------------------------------------------------------------

@dataclass
class PairSet:
    train: list[dict] = field(default_factory=list)
    val: list[dict] = field(default_factory=list)
    corpus: list[dict] = field(default_factory=list)  # train + val passages, for val retrieval
    val_groups: list[str] = field(default_factory=list)
    skipped: Counter = field(default_factory=Counter)


def _article_id(key: tuple[str, int]) -> str:
    return f"{key[0]}/{key[1]}"


def _clean_queries(versions: dict[str, ArticleVersion], seed: int,
                   mixed_fraction: float, skipped: Counter) -> list[dict]:
    """Clean queries of one article: (type, query, query language, passage language,
    mining language)."""
    out = []
    usable = {}
    for lang in PAIR_LANGUAGES:
        v = versions.get(lang)
        if v is None:
            continue
        if len(article_body(v.text).split()) < MIN_BODY_WORDS:
            skipped[f"short_body_{lang}"] += 1
            continue
        usable[lang] = v
        if v.title:
            out.append({"query_type": "title", "query": v.title, "query_lang": lang,
                        "passage_lang": lang, "mine_query": v.title})
        else:
            skipped[f"no_title_{lang}"] += 1
        sentence = first_sentence(v.first.text)
        if sentence:
            out.append({"query_type": "first_sentence", "query": sentence,
                        "query_lang": lang, "passage_lang": lang, "mine_query": sentence})
        else:
            skipped[f"no_first_sentence_{lang}"] += 1
    if len(usable) == 2:
        uz, ru = usable["uz-Latn"], usable["ru"]
        if not versions_correspond(uz.text, ru.text):
            skipped["versions_differ"] += 1
        elif uz.title and ru.title:
            for q, p in ((uz, ru), (ru, uz)):
                out.append({"query_type": "xling_title", "query": q.title,
                            "query_lang": q.language, "passage_lang": p.language,
                            "mine_query": p.title})
            key = uz.key
            rng = _rng(seed, _article_id(key), "mixed")
            if rng.random() < mixed_fraction:
                for frame_lang, title_v in (("uz-Latn", ru), ("ru", uz)):
                    t = title_v.title
                    frame = rng.choice(MIXED_FRAMES[frame_lang])
                    if not frame.startswith("{t}"):
                        t = t[0].lower() + t[1:]
                    out.append({"query_type": "mixed", "query": frame.format(t=t),
                                "query_lang": "mixed", "passage_lang": frame_lang,
                                "mine_query": usable[frame_lang].title})
    return out


def build_pairs(chunks: Sequence[CorpusChunk], seed: int = 13, val_fraction: float = 0.15,
                mixed_fraction: float = 0.1, analyzer: str = "fold+stem6") -> PairSet:
    """Build train and validation pairs from the TRAIN split of ``chunks`` (test chunks
    are dropped before anything else happens)."""
    result = PairSet()
    # canonical order (chunk ids are "<doc>#c<idx>"): BM25 ties and the "first chunk of
    # an article" must not depend on the order the corpus was loaded in
    train_chunks = sorted((c for c in chunks if c.split == "train"), key=lambda c: c.id)
    result.skipped["test_or_other_split_chunks_ignored"] = len(chunks) - len(train_chunks)
    articles = group_articles(train_chunks)

    groups = {v.split_group for vs in articles.values() for v in vs.values()}
    val_groups = holdout_groups(groups, val_fraction)
    result.val_groups = sorted(val_groups)

    def role_of(c: CorpusChunk) -> str:
        return "val" if (c.split_group or c.doc_id) in val_groups else "train"

    in_scope = [c for c in train_chunks if c.article_key is not None]
    result.skipped["chunks_outside_articles"] = len(train_chunks) - len(in_scope)
    result.corpus = [{"id": c.id, "text": c.index_text, "language": c.language,
                      "article": _article_id(c.article_key), "split_group": c.split_group,
                      "role": role_of(c)} for c in in_scope]
    miner = NegativeMiner([c for c in in_scope if role_of(c) == "train"], analyzer)

    for key in sorted(articles):
        versions = articles[key]
        roles = {role_of(c) for v in versions.values() for c in v.chunks}
        if len(roles) != 1:  # cannot happen with chapter groups; guard anyway
            result.skipped["article_across_roles"] += 1
            continue
        role = roles.pop()
        for q in _clean_queries(versions, seed, mixed_fraction, result.skipped):
            positive = versions[q["passage_lang"]].first
            base = {"query": q["query"], "positive": positive.index_text,
                    "positive_id": positive.id, "query_type": q["query_type"],
                    "noise": "none", "query_lang": q["query_lang"],
                    "passage_lang": q["passage_lang"], "article": _article_id(key),
                    "split_group": positive.split_group}
            if role == "train":
                neg, rank = miner.mine(q["mine_query"], q["passage_lang"], key,
                                       positive.index_text)
                source = "bm25"
                if neg is None:
                    neg = miner.random(q["passage_lang"], key,
                                       _rng(seed, _article_id(key), "neg", q["query_type"]))
                    source, rank = "random", None
                if neg is None:
                    result.skipped["no_negative"] += 1
                    continue
                base |= {"negative": neg.index_text, "negative_id": neg.id,
                         "negative_article": _article_id(neg.article_key),
                         "negative_source": source, "negative_rank": rank}
            rows = [base]
            if q["query_type"] != "mixed":
                rng = _rng(seed, _article_id(key), q["query_lang"], q["passage_lang"],
                           q["query_type"], "noise")
                variants = noisy_variants(q["query"], q["query_lang"], rng)
                if variants:
                    noise, lang, text = rng.choice(variants)
                    rows.append(base | {"query": text, "noise": noise, "query_lang": lang})
            (result.train if role == "train" else result.val).extend(rows)
    return result


def check_pairs(pairs: PairSet, chunks: Sequence[CorpusChunk]) -> list[str]:
    """Problems that must never happen: a test chunk in the output, a validation article or
    split group in training, a negative from the positive's article."""
    split_of = {c.id: c.split for c in chunks}
    problems = []
    for name, rows in (("train", pairs.train), ("val", pairs.val)):
        for r in rows:
            for k in ("positive_id", "negative_id"):
                if k in r and split_of.get(r[k]) != "train":
                    problems.append(f"{name}: {k} {r[k]} is not a train chunk")
    for r in pairs.corpus:
        if split_of.get(r["id"]) != "train":
            problems.append(f"corpus: {r['id']} is not a train chunk")
    val_articles = {r["article"] for r in pairs.val}
    val_groups = set(pairs.val_groups)
    by_id = {c.id: c for c in chunks}
    for r in pairs.train:
        if r["article"] in val_articles or r["split_group"] in val_groups:
            problems.append(f"train: article {r['article']} is in validation")
        neg = by_id.get(r["negative_id"])
        if neg is not None and (neg.split_group in val_groups
                                or _article_id(neg.article_key) == r["article"]):
            problems.append(f"train: negative {r['negative_id']} is from validation or the "
                            "positive's article")
    return problems


def pair_stats(pairs: PairSet) -> dict:
    """Counts only (no text), for the committed report."""
    def counts(rows: list[dict]) -> dict:
        by_type = Counter(r["query_type"] for r in rows)
        by_noise = Counter(r["noise"] for r in rows)
        by_type_noise = Counter(f"{r['query_type']}/{r['noise']}" for r in rows)
        by_lang = Counter(f"{r['query_lang']}->{r['passage_lang']}" for r in rows)
        return {"pairs": len(rows),
                "articles": len({r["article"] for r in rows}),
                "split_groups": len({r["split_group"] for r in rows}),
                "by_query_type": dict(sorted(by_type.items())),
                "by_noise": dict(sorted(by_noise.items())),
                "by_query_type_and_noise": dict(sorted(by_type_noise.items())),
                "by_query_lang_to_passage_lang": dict(sorted(by_lang.items()))}

    train = counts(pairs.train)
    neg_sources = Counter(r["negative_source"] for r in pairs.train)
    ranks = Counter(r["negative_rank"] for r in pairs.train if r["negative_rank"] is not None)
    train["negatives"] = {
        "by_source": dict(sorted(neg_sources.items())),
        "bm25_rank_of_chosen": {str(k): ranks[k] for k in sorted(ranks)},
        "distinct_negative_chunks": len({r["negative_id"] for r in pairs.train}),
    }
    corpus = Counter(f"{r['role']}/{r['language']}" for r in pairs.corpus)
    return {"train": train, "val": counts(pairs.val),
            "corpus_chunks": dict(sorted(corpus.items())),
            "val_split_groups": pairs.val_groups,
            "skipped": dict(sorted((k, v) for k, v in pairs.skipped.items() if v))}
