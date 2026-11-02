"""Parser for legal acts saved as HTML from lex.uz (National Database of Legislation).

Page structure (observed 2026-11-02): every element of the act is a
``<div class="KIND lx_elem">`` whose text sits in a child ``<div id="ELEMENT_ID">``;
a sibling child ``<div class="lx_elem2">`` holds on-page buttons. KIND is one of

    ACT_TITLE             title of the act                  -> heading
    TEXT_HEADER_DEFAULT   part / section / chapter / §      -> heading
    CLAUSE_DEFAULT        article title ("386-modda. ...")  -> heading
    ACT_TEXT, ACT_FORM    paragraph text                    -> text
    BY_DEFAULT, NEW_EDITION  usually empty spacers          -> text if not empty

Editorial material is in separate ``<div class="... lx_no_select">`` blocks (amendment
notes, cross-reference indexes, "changes origins") and is skipped, as are scripts,
styles and the page chrome. The whole act becomes one logical page; each block keeps
its lex.uz element id in ``Block.anchor`` so citations can link to ``#<id>``.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from .text import normalize_block
from .types import Block, ParsedDocument, ParsedPage

HTML_MIME = "text/html"
KINDS = {"ACT_TITLE": "heading", "TEXT_HEADER_DEFAULT": "heading",
         "CLAUSE_DEFAULT": "heading", "ACT_TEXT": "text", "ACT_FORM": "text",
         "BY_DEFAULT": "text", "NEW_EDITION": "text"}
_BREAK_TAGS = {"br", "p", "li", "tr"}


class _LexParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self.title_parts: list[str] = []
        self.edition: str | None = None
        self._depth = 0                 # current <div> nesting depth
        self._skip_depth: int | None = None   # inside a skipped div subtree
        self._elem: tuple[int, str] | None = None   # (depth, kind) of the current element
        self._content_depth: int | None = None     # depth of the element's text div
        self._anchor: str | None = None
        self._buf: list[str] = []
        self._in_title = self._in_script = False
        self._date_selected = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if tag in ("script", "style"):
            self._in_script = True
        if tag == "title":
            self._in_title = True
        if "lx_date_selected" in cls:
            self._date_selected = True
        if tag != "div":
            if tag in _BREAK_TAGS and self._content_depth is not None:
                self._buf.append("\n")
            return
        self._depth += 1
        if self._skip_depth is not None:
            return
        if "lx_no_select" in cls or "lx_elem2" in cls:
            self._skip_depth = self._depth
            return
        if "lx_elem" in cls and cls and cls[0] in KINDS:
            self._elem = (self._depth, KINDS[cls[0]])
            self._content_depth, self._anchor, self._buf = None, None, []
            return
        if self._elem is not None and self._content_depth is None and "id" in a:
            self._content_depth, self._anchor = self._depth, a["id"]
        elif self._content_depth is not None:
            self._buf.append("\n")  # nested div inside the text: a line break

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._in_script = False
        if tag == "title":
            self._in_title = False
        if tag != "div":
            return
        if self._skip_depth is not None:
            if self._depth == self._skip_depth:
                self._skip_depth = None
            self._depth -= 1
            return
        if self._content_depth == self._depth:
            self._content_depth = -1  # text div closed; ignore anything after it
        if self._elem is not None and self._elem[0] == self._depth:
            text = normalize_block("".join(self._buf))
            if text:
                self.blocks.append(Block(text=text, kind=self._elem[1], anchor=self._anchor))
            self._elem, self._content_depth, self._buf = None, None, []
        self._depth -= 1

    def handle_data(self, data):
        if self._in_script:
            return
        if self._in_title:
            self.title_parts.append(data)
        if self._date_selected:
            if data.strip():
                self.edition = data.strip()
                self._date_selected = False
            return
        if (self._skip_depth is None and self._content_depth is not None
                and self._content_depth > 0):
            self._buf.append(data)


def is_lexuz_html(path: Path) -> bool:
    head = Path(path).read_text(encoding="utf-8", errors="replace")[:500_000]
    return 'class="ACT_TEXT lx_elem"' in head or 'class="CLAUSE_DEFAULT lx_elem"' in head


def parse_lexuz_html(path: Path) -> ParsedDocument:
    parser = _LexParser()
    parser.feed(Path(path).read_text(encoding="utf-8", errors="replace"))
    parser.close()
    title = re.sub(r"\s+", " ", "".join(parser.title_parts)).strip() or None
    warnings = [] if parser.blocks else ["no act text found in the HTML"]
    return ParsedDocument(filename=Path(path).name, mime=HTML_MIME,
                          pages=[ParsedPage(page_no=1, blocks=parser.blocks)],
                          warnings=warnings,
                          meta={"title": title, "edition": parser.edition,
                                "source_format": "lex.uz html"})
