from typing import List, Dict, Any, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config import get_settings
from app.ingestion.loaders import LoadedPage


class ChunkData:
    def __init__(self, text: str, chunk_index: int, page: Optional[int] = None):
        self.text = text
        self.chunk_index = chunk_index
        self.page = page

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "chunk_index": self.chunk_index,
            "page": self.page,
        }


def chunk_document_pages(
    pages: List[LoadedPage],
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> List[ChunkData]:
    """Split loaded pages into chunks using RecursiveCharacterTextSplitter, preserving page numbers."""
    settings = get_settings()
    c_size = chunk_size if chunk_size is not None else settings.CHUNK_SIZE
    c_overlap = chunk_overlap if chunk_overlap is not None else settings.CHUNK_OVERLAP

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=c_size,
        chunk_overlap=c_overlap,
        separators=["\n\n", "\n", " ", ""],
    )

    chunks: List[ChunkData] = []
    chunk_counter = 0

    for page in pages:
        page_chunks = splitter.split_text(page.text)
        for piece in page_chunks:
            piece_cleaned = piece.strip()
            if piece_cleaned:
                chunks.append(
                    ChunkData(
                        text=piece_cleaned,
                        chunk_index=chunk_counter,
                        page=page.page_number,
                    )
                )
                chunk_counter += 1

    return chunks
