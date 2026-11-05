"""Checks for uploaded (untrusted) files, run before any parser sees them.

Order of checks for one upload:

1. Name and type: the extension must be in ``ALLOWED`` and the declared content type
   must be one of the types allowed for that extension. The original file name is only
   kept as a display name (``safe_display_name``); it is never used in a path.
2. Size: the body is copied to a private temp directory with a fixed file name
   (``upload<ext>``), stopping as soon as ``upload_max_bytes`` is exceeded.
3. Content: the first bytes must match the format (``sniff``), so a renamed file is
   rejected before it reaches the wrong parser.
4. Limits per format (``check_limits``), read from headers/metadata without decoding
   the content: PDF page count, encryption and page size at the OCR resolution; image
   frames and pixels; DOCX zip entries, total uncompressed size and required parts.

Every rejection raises ``UploadRejected`` with an HTTP status and a message meant for
the user.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
import zipfile
from collections.abc import Callable
from pathlib import Path

from ..config import Settings
from .docx_parser import DOCX_MIME

# extension -> accepted content types
ALLOWED: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".docx": {DOCX_MIME},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".tif": {"image/tiff"},
    ".tiff": {"image/tiff"},
}
_MAGIC = {".pdf": (b"%PDF-",), ".docx": (b"PK\x03\x04",), ".png": (b"\x89PNG\r\n\x1a\n",),
          ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",),
          ".tif": (b"II*\x00", b"MM\x00*"), ".tiff": (b"II*\x00", b"MM\x00*")}
_PIL_FORMATS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".tif": "TIFF",
                ".tiff": "TIFF"}
_DOCX_REQUIRED = ("[Content_Types].xml", "word/document.xml")
MAX_NAME_CHARS = 200
COPY_BLOCK = 1 << 16


class UploadRejected(ValueError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def safe_display_name(name: str | None) -> str:
    """The last path component of ``name``, without control characters, at most 200
    characters. Only for display and the ``documents.filename`` column."""
    name = unicodedata.normalize("NFC", name or "")
    name = re.split(r"[/\\]", name)[-1]
    name = "".join(c for c in name if unicodedata.category(c)[0] != "C").strip().strip(".")
    if len(name) > MAX_NAME_CHARS:
        stem, dot, ext = name.rpartition(".")
        name = (stem[:MAX_NAME_CHARS - len(ext) - 1] + "." + ext if dot and len(ext) <= 10
                else name[:MAX_NAME_CHARS])
    return name or "upload"


def check_name_and_type(filename: str | None, content_type: str | None) -> str:
    """Return the (lower-case) extension, or raise UploadRejected (415)."""
    suffix = Path(safe_display_name(filename)).suffix.lower()
    allowed = ", ".join(sorted(ALLOWED))
    if suffix not in ALLOWED:
        raise UploadRejected(415, f"file type {suffix or '(none)'!r} is not accepted; "
                                  f"allowed: {allowed}")
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype not in ALLOWED[suffix]:
        raise UploadRejected(415, f"content type {ctype or '(none)'!r} does not match a "
                                  f"{suffix} file; send it as "
                                  f"{' or '.join(sorted(ALLOWED[suffix]))}")
    return suffix


def save_limited(read: Callable[[int], bytes], dest: Path, max_bytes: int) -> tuple[str, int]:
    """Copy ``read`` into ``dest`` (created, must not exist), at most ``max_bytes``.
    Returns (sha256, size). On any error the partial file is removed."""
    h, size = hashlib.sha256(), 0
    try:
        with open(dest, "xb") as out:
            while block := read(COPY_BLOCK):
                size += len(block)
                if size > max_bytes:
                    raise UploadRejected(413, f"file is larger than the limit of "
                                              f"{max_bytes // (1024 * 1024)} MB"
                                         if max_bytes >= 1024 * 1024 else
                                         f"file is larger than the limit of {max_bytes} bytes")
                h.update(block)
                out.write(block)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    if size == 0:
        dest.unlink(missing_ok=True)
        raise UploadRejected(422, "the file is empty")
    return h.hexdigest(), size


def sniff(path: Path, suffix: str) -> None:
    with open(path, "rb") as f:
        head = f.read(16)
    if not head.startswith(_MAGIC[suffix]):
        raise UploadRejected(415, f"the content is not a {suffix} file (wrong file signature)")


def _check_pdf(path: Path, s: Settings) -> None:
    import pymupdf

    try:
        doc = pymupdf.open(path, filetype="pdf")
    except Exception as exc:
        raise UploadRejected(422, "the PDF cannot be opened (damaged or not a PDF)") from exc
    with doc:
        if doc.needs_pass or doc.is_encrypted:
            raise UploadRejected(422, "encrypted or password-protected PDFs are not accepted")
        if doc.page_count == 0:
            raise UploadRejected(422, "the PDF has no pages")
        if doc.page_count > s.upload_max_pages:
            raise UploadRejected(422, f"the PDF has {doc.page_count} pages; the limit is "
                                      f"{s.upload_max_pages}")
        scale = s.ocr_dpi / 72.0
        for i, page in enumerate(doc, start=1):
            w, h = page.rect.width * scale, page.rect.height * scale
            if w * h > s.upload_max_pixels:
                raise UploadRejected(422, f"page {i} is too large to process "
                                          f"({page.rect.width:.0f} x {page.rect.height:.0f} pt)")


def _check_image(path: Path, suffix: str, s: Settings) -> None:
    from PIL import Image, UnidentifiedImageError

    try:
        img = Image.open(path)  # lazy: reads the header, decodes nothing
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise UploadRejected(422, "the image cannot be opened (damaged or too large)") from exc
    with img:
        if img.format != _PIL_FORMATS[suffix]:
            raise UploadRejected(415, f"the content is {img.format}, not {suffix}")
        frames = getattr(img, "n_frames", 1)
        if frames > s.upload_max_pages:
            raise UploadRejected(422, f"the image has {frames} pages; the limit is "
                                      f"{s.upload_max_pages}")
        for i in range(frames):
            img.seek(i)
            if img.width * img.height > s.upload_max_pixels:
                raise UploadRejected(422, f"image page {i + 1} is too large "
                                          f"({img.width} x {img.height} pixels)")


def _check_docx(path: Path, s: Settings) -> None:
    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
    except (zipfile.BadZipFile, OSError) as exc:
        raise UploadRejected(422, "the DOCX cannot be opened (damaged or not a DOCX)") from exc
    if len(infos) > s.upload_max_zip_entries:
        raise UploadRejected(422, f"the DOCX has {len(infos)} parts; the limit is "
                                  f"{s.upload_max_zip_entries}")
    # the declared sizes bound decompression: zipfile stops reading a member at its size
    total = sum(i.file_size for i in infos)
    if total > s.upload_max_unzipped_bytes:
        raise UploadRejected(422, "the DOCX is too large when unpacked")
    names = {i.filename for i in infos}
    if any(n not in names for n in _DOCX_REQUIRED):
        raise UploadRejected(422, "the file is a zip archive but not a Word document")


def check_limits(path: Path, suffix: str, settings: Settings) -> None:
    if suffix == ".pdf":
        _check_pdf(path, settings)
    elif suffix == ".docx":
        _check_docx(path, settings)
    else:
        _check_image(path, suffix, settings)
