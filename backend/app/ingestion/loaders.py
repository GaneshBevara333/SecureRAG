import io
from typing import List, Dict, Any
from pypdf import PdfReader


class LoadedPage:
    def __init__(self, text: str, page_number: int | None = None):
        self.text = text
        self.page_number = page_number


def load_file_content(filename: str, content_bytes: bytes) -> List[LoadedPage]:
    """Load text and page information from PDF, MD, or TXT content bytes."""
    lower_name = filename.lower()

    if lower_name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(content_bytes))
        pages: List[LoadedPage] = []
        for idx, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(LoadedPage(text=page_text, page_number=idx + 1))
        return pages

    elif lower_name.endswith(".md") or lower_name.endswith(".markdown") or lower_name.endswith(".txt"):
        text = content_bytes.decode("utf-8", errors="replace")
        return [LoadedPage(text=text, page_number=1)]

    else:
        # Default text attempt
        text = content_bytes.decode("utf-8", errors="replace")
        return [LoadedPage(text=text, page_number=1)]
