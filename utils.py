from pathlib import Path

import fitz
import httpx

from models import Artifact, ArtifactSource

_ARXIV_PDF_PREFIX = "https://arxiv.org/pdf/"


def _arxiv_url_to_pdf_url(url: str) -> str:
    """Convert arxiv abstract URL to PDF URL if needed."""
    url = url.rstrip("/")
    if "arxiv.org/abs/" in url:
        paper_id = url.split("/abs/")[-1]
        return f"{_ARXIV_PDF_PREFIX}{paper_id}"
    if "arxiv.org/pdf/" in url:
        return url if url.endswith(".pdf") else url + ".pdf"
    raise ValueError(f"Not a recognized arxiv URL: {url}")


def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> tuple[str, str]:
    """Extract full text and title from PDF bytes."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    title = doc.metadata.get("title", "").strip() if doc.metadata else ""
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages), title


def load_artifact(source: str, filename: str | None = None) -> Artifact:
    """Load an artifact from an arxiv URL or a local PDF path.

    Args:
        source: An arxiv URL (abs or pdf) or a path to a local PDF file.
        filename: Original filename from upload, used as title fallback.

    Returns:
        An Artifact with the extracted text.
    """
    if source.startswith("http://") or source.startswith("https://"):
        pdf_url = _arxiv_url_to_pdf_url(source)
        resp = httpx.get(pdf_url, follow_redirects=True, timeout=60)
        resp.raise_for_status()
        text, title = _extract_text_from_pdf_bytes(resp.content)
        return Artifact(
            source=ArtifactSource.ARXIV,
            url=source,
            title=title or pdf_url.split("/")[-1],
            text=text,
        )

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {source}")
    pdf_bytes = path.read_bytes()
    text, title = _extract_text_from_pdf_bytes(pdf_bytes)
    return Artifact(
        source=ArtifactSource.PDF,
        url=str(path.resolve()),
        title=title or (Path(filename).stem if filename else path.stem),
        text=text,
    )
