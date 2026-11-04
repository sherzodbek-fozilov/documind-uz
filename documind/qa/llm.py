"""Optional LLM mode: an LLM phrases an answer from the retrieved passages.

Off by default (``DOCUMIND_ANSWER_MODE=extractive``). With ``DOCUMIND_ANSWER_MODE=llm``
a provider is loaded from ``DOCUMIND_LLM_PROVIDER="package.module:factory"``; the
factory gets the settings and returns any object with
``complete(prompt: str, max_tokens: int) -> str``. No provider SDK is a dependency of
this package.

The model must answer in JSON with verbatim quotes. Every quote is then located in
the cited chunk and checked (``citations.check_citation``); a citation that is not an
exact span of a chunk given to the model is dropped and counted as invalid.
"""

from __future__ import annotations

import importlib
import json
import re
from collections.abc import Sequence
from typing import Protocol

from ..config import Settings


class LLMClient(Protocol):
    def complete(self, prompt: str, max_tokens: int) -> str: ...


class LLMConfigError(RuntimeError):
    pass


def load_llm(settings: Settings) -> LLMClient:
    spec = settings.llm_provider
    if not spec or ":" not in spec:
        raise LLMConfigError("DOCUMIND_ANSWER_MODE=llm needs DOCUMIND_LLM_PROVIDER="
                             "'package.module:factory'")
    module, _, attr = spec.partition(":")
    try:
        factory = getattr(importlib.import_module(module), attr)
    except (ImportError, AttributeError) as exc:
        raise LLMConfigError(f"cannot load LLM provider {spec!r}: {exc}") from exc
    return factory(settings)


PROMPT = """You answer questions about Uzbek and Russian legal documents.
Use ONLY the passages below. Answer in the language of the question.
Every claim must be supported by a citation. A citation is the passage id and a quote
copied CHARACTER FOR CHARACTER from that passage (no changes, no ellipsis).
If the passages do not answer the question, say so and give no citations.

Reply with JSON only:
{{"answer": "...", "citations": [{{"chunk_id": "...", "quote": "..."}}]}}

Question: {question}

Passages:
{passages}
"""


def build_prompt(question: str, passages: Sequence[tuple[str, str]]) -> str:
    """``passages``: (chunk id, chunk text)."""
    body = "\n\n".join(f"[{cid}]\n{text}" for cid, text in passages)
    return PROMPT.format(question=question, passages=body)


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$")


def parse_response(raw: str) -> tuple[str, list[tuple[str, str]]]:
    """(answer, [(chunk id, quote)]). Raises ValueError on output that is not the JSON
    asked for."""
    data = json.loads(_FENCE_RE.sub("", raw.strip()))
    if not isinstance(data, dict) or not isinstance(data.get("answer"), str):
        raise ValueError("LLM reply has no 'answer' string")
    cites = data.get("citations") or []
    if not isinstance(cites, list):
        raise ValueError("LLM reply: 'citations' is not a list")
    out = []
    for c in cites:
        if isinstance(c, dict):
            out.append((str(c.get("chunk_id", "")), str(c.get("quote", ""))))
    return data["answer"], out
