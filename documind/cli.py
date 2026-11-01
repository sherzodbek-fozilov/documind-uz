"""Command line: ``documind ingest PATH...``, ``documind stats``, ``documind split``."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import func, select

from .config import get_settings
from .ingestion.pipeline import SUPPORTED_SUFFIXES, ingest_file
from .split import check_no_leakage, load_overrides, stratified_split
from .storage import models
from .storage.db import make_session_factory

MANIFEST = "manifest.jsonl"


def _load_manifest(directory: Path) -> dict[str, dict]:
    path = directory / MANIFEST
    if not path.exists():
        return {}
    entries = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip())
    return {e["file"]: e for e in entries}


def _collect(paths: list[Path]) -> list[tuple[Path, dict]]:
    """Expand directories; attach manifest metadata (doc_id, group_id, synthetic, source)."""
    out = []
    for p in paths:
        if p.is_dir():
            manifest = _load_manifest(p)
            files = ([p / name for name in manifest] if manifest else
                     sorted(f for f in p.rglob("*") if f.suffix.lower() in SUPPORTED_SUFFIXES))
            out += [(f, manifest.get(f.relative_to(p).as_posix(), {})) for f in files]
        else:
            out.append((p, {}))
    return out


def cmd_ingest(args) -> int:
    settings = get_settings()
    Session = make_session_factory(settings.database_url)
    failures = 0
    with Session() as session:
        for path, meta in _collect(args.paths):
            try:
                res = ingest_file(path, session, settings, doc_id=meta.get("doc_id"),
                                  group_id=meta.get("group_id"),
                                  is_synthetic=bool(meta.get("synthetic", args.synthetic)),
                                  source=meta.get("source", args.source),
                                  force_ocr=args.force_ocr)
                print(json.dumps({"file": str(path), **asdict(res)}, ensure_ascii=False))
            except Exception as exc:  # keep going; report at the end
                session.rollback()
                failures += 1
                print(json.dumps({"file": str(path), "status": "error", "error": str(exc)},
                                 ensure_ascii=False), file=sys.stderr)
    return 1 if failures else 0


def cmd_stats(args) -> int:
    settings = get_settings()
    Session = make_session_factory(settings.database_url)
    with Session() as s:
        docs = s.execute(select(models.Document.id, models.Document.group_id,
                                models.Document.split, models.Document.language,
                                models.Document.is_synthetic, models.Document.n_ocr_pages)).all()
        n_chunks = s.scalar(select(func.count()).select_from(models.Chunk))
        stats = {
            "documents": len(docs),
            "chunks": n_chunks,
            "by_split": Counter(d.split for d in docs),
            "by_kind_and_split": Counter(
                f"{'synthetic' if d.is_synthetic else 'real'}/{d.split}" for d in docs),
            "by_language": Counter(d.language for d in docs),
            "synthetic": sum(d.is_synthetic for d in docs),
            "documents_with_ocr": sum(d.n_ocr_pages > 0 for d in docs),
            "leaking_groups": check_no_leakage((d.id, d.group_id, d.split) for d in docs),
        }
        if args.list:
            stats["document_ids"] = {d.id: d.split for d in docs}
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 1 if stats["leaking_groups"] else 0


def cmd_split(args) -> int:
    """Write a split stratified by kind (real / synthetic) and language; apply it to the DB.

    Real and synthetic documents get separate strata, so the real test set has its own
    ~test_fraction share per language and real results never depend on synthetic data.
    """
    settings = get_settings()
    Session = make_session_factory(settings.database_url)
    existing = {} if args.reset else load_overrides(settings.splits_file)
    with Session() as s:
        docs = s.scalars(select(models.Document)).all()
        groups: dict[str, tuple[set[str], set[str]]] = {}
        for d in docs:
            kinds, langs = groups.setdefault(d.group_id, (set(), set()))
            kinds.add("synthetic" if d.is_synthetic else "real")
            langs.add(d.language)
        # stratum = kind + the set of languages in the group (e.g. "real/ru+uz-Latn" for
        # an act available in two languages)
        strata = {g: f"{'+'.join(sorted(k))}/{'+'.join(sorted(lang))}"
                  for g, (k, lang) in groups.items()}
        splits = stratified_split(strata, settings.test_fraction, existing)
        changed = 0
        for d in docs:
            if d.split != splits[d.group_id]:
                d.split = splits[d.group_id]
                changed += 1
        s.commit()
    settings.splits_file.parent.mkdir(parents=True, exist_ok=True)
    settings.splits_file.write_text(json.dumps(splits, ensure_ascii=False, indent=1) + "\n",
                                    encoding="utf-8")
    summary = Counter((strata[g], sp) for g, sp in splits.items() if g in strata)
    print(json.dumps({"splits_file": str(settings.splits_file), "documents_changed": changed,
                      "groups": {f"{k[0]}/{k[1]}": v for k, v in sorted(summary.items())}},
                     ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="documind")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingest", help="ingest PDF / DOCX / image files or directories")
    ing.add_argument("paths", nargs="+", type=Path)
    ing.add_argument("--synthetic", action="store_true", help="mark documents as synthetic")
    ing.add_argument("--source", help="source URL or description (see docs/data.md)")
    ing.add_argument("--force-ocr", action="store_true", help="OCR every PDF page")
    ing.set_defaults(func=cmd_ingest)
    st = sub.add_parser("stats", help="corpus statistics and leakage check")
    st.add_argument("--list", action="store_true", help="also list document ids and splits")
    st.set_defaults(func=cmd_stats)
    sp = sub.add_parser("split", help="write a language-stratified split to the splits file")
    sp.add_argument("--reset", action="store_true",
                    help="ignore the existing splits file (only before labels/training exist)")
    sp.set_defaults(func=cmd_split)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
