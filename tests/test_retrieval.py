import numpy as np
import pytest

from documind.retrieval.analyzers import get_analyzer
from documind.retrieval.bm25 import build
from documind.retrieval.corpus import CorpusChunk
from documind.retrieval.hybrid import rrf
from documind.retrieval.retrievers import BM25Retriever, DenseRetriever, HybridRetriever


def test_analyzers():
    plain, fold = get_analyzer("plain"), get_analyzer("fold")
    assert plain("Oʻzbekiston o'zbekiston O`ZBEKISTON") == ["ozbekiston"] * 3
    # cross-script and OCR-confusion folding
    assert fold("Ўзбекистон") == fold("Oʻzbekiston") == ["ozbekiston"]
    assert fold("миқдори") == fold("микдори") == fold("miqdori")
    assert fold("ҳақи") == fold("хаки") == fold("haqi")
    assert get_analyzer("plain+stem4")("shartnomaning shartnomasi") == ["shar", "shar"]
    with pytest.raises(ValueError):
        get_analyzer("snowball")


def test_bm25_ranks_and_idf():
    docs = ["ijara haqi oylik toʻlanadi", "fors major holatlari", "ijara muddati bir yil",
            "nizolar sudda koʻriladi"]
    index = build(docs, get_analyzer("plain"))
    top = index.search(get_analyzer("plain")("ijara haqi qancha"), k=4)
    assert [i for i, _ in top][:2] == [0, 2]
    assert top[0][1] > top[1][1] > 0
    # rare terms weigh more than frequent ones
    assert index.idf["haqi"] > index.idf["ijara"]
    # candidate filter
    assert [i for i, _ in index.search(["ijara"], candidates={2})] == [2]
    assert index.search(["yoʻq"]) == []


def test_rrf():
    assert rrf([["a", "b", "c"], ["b", "a", "d"]], k=60) == ["a", "b", "c", "d"]
    assert rrf([["a", "b"], ["c", "b"]], k=1, top_n=1) == ["b"]
    assert rrf([]) == []


def _chunks():
    texts = [("d1", "Oylik ijara haqi 5 000 000 soʻm."), ("d1", "Fors-major holatlari."),
             ("d2", "Ежемесячная арендная плата 5 000 000 сумов."), ("d2", "Форс-мажор.")]
    return [CorpusChunk(f"{d}#c{i:04d}", d, "test", "uz-Latn", t, None, "v")
            for i, (d, t) in enumerate(texts)]


class FakeEmbedder:
    """Deterministic bag-of-letters embedding, enough to test the plumbing."""

    model_id = "fake"

    def _vec(self, texts):
        out = np.zeros((len(texts), 64), dtype=np.float32)
        for i, t in enumerate(texts):
            for ch in t.lower():
                out[i, ord(ch) % 64] += 1
        return out / np.linalg.norm(out, axis=1, keepdims=True)

    def embed_queries(self, texts):
        return self._vec(texts)

    def embed_passages(self, texts, cache_dir=None):
        return self._vec(texts)


def test_retrievers_and_document_scope():
    chunks = _chunks()
    bm25 = BM25Retriever(chunks, "fold+stem6")
    assert bm25.search("ijara haqi", k=1) == ["d1#c0000"]
    assert bm25.search("форс-мажор", k=1, doc_id="d2") == ["d2#c0003"]
    assert all(c.startswith("d2#") for c in bm25.search("ijara", k=4, doc_id="d2"))
    dense = DenseRetriever(chunks, FakeEmbedder(), "test_chunks")
    res = dense.search("Fors-major holatlari.", k=2)
    assert res[0] == "d1#c0001" and len(res) == 2
    assert all(c.startswith("d1#") for c in dense.search("x", k=4, doc_id="d1"))
    hybrid = HybridRetriever([bm25, dense], depth=4)
    assert hybrid.search("Fors-major holatlari", k=1) == ["d1#c0001"]


def test_index_text_adds_section_title_to_continuations():
    c = CorpusChunk("d#c0001", "d", "test", "ru", "2.3. Расходы несёт Поставщик.",
                    "ДОГОВОР / 2. ЦЕНА", "v")
    assert c.index_text.startswith("ДОГОВОР / 2. ЦЕНА\n")
    head = CorpusChunk("d#c0000", "d", "test", "ru", "2. ЦЕНА\n\n2.1. Цена.", "2. ЦЕНА", "v")
    assert head.index_text == head.text


def test_article_key_is_shared_across_language_versions_and_chunks():
    uz = CorpusChunk("a-uz#c1", "a-uz", "test", "uz-Latn", "t", "29-bob. X / 386-modda. Y", "v",
                     "a")
    ru = CorpusChunk("a-ru#c7", "a-ru", "test", "ru", "t", "Глава 29 / Статья 386. Y", "v", "a")
    assert uz.article_key == ru.article_key == ("a", 386)
    assert CorpusChunk("a-ru#c0", "a-ru", "test", "ru", "t", "Глава 29. X", "v", "a").article_key \
        is None
