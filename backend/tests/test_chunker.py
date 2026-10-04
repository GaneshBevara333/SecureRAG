from app.ingestion.loaders import LoadedPage
from app.ingestion.chunker import chunk_document_pages


def test_chunker_basic():
    pages = [
        LoadedPage(text="First paragraph of test data.\n\nSecond paragraph of test data.", page_number=1)
    ]
    chunks = chunk_document_pages(pages, chunk_size=50, chunk_overlap=10)
    assert len(chunks) >= 2
    assert chunks[0].page == 1
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
    assert "First paragraph" in chunks[0].text


def test_chunker_preserves_page_numbers():
    pages = [
        LoadedPage(text="Page one text content.", page_number=1),
        LoadedPage(text="Page two text content.", page_number=2),
    ]
    chunks = chunk_document_pages(pages, chunk_size=100, chunk_overlap=10)
    assert len(chunks) == 2
    assert chunks[0].page == 1
    assert chunks[1].page == 2
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1


def test_chunker_empty_pages():
    pages = [LoadedPage(text="   \n  ", page_number=1)]
    chunks = chunk_document_pages(pages)
    assert len(chunks) == 0
