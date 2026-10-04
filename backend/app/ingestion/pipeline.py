from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import Document, Chunk
from app.ingestion.loaders import load_file_content
from app.ingestion.chunker import chunk_document_pages
from app.retrieval.embed import default_embedding_service


def ingest_document(
    db: Session,
    org_id: str,
    owner_id: str,
    filename: str,
    file_bytes: bytes,
    title: Optional[str] = None,
    visibility: str = "private",
    team_id: Optional[str] = None,
) -> Document:
    """Ingest a file (PDF/MD/TXT), parse, chunk, embed, and store in database."""
    doc_title = title if title else filename

    doc = Document(
        org_id=org_id,
        owner_id=owner_id,
        team_id=team_id,
        title=doc_title,
        filename=filename,
        visibility=visibility,
        status="processing",
        version=1,
    )
    db.add(doc)
    db.flush()

    try:
        pages = load_file_content(filename, file_bytes)
        chunk_data_list = chunk_document_pages(pages)

        if chunk_data_list:
            texts = [c.text for c in chunk_data_list]
            embeddings = default_embedding_service.embed_documents(texts)

            is_postgres = db.bind is not None and db.bind.dialect.name == "postgresql"

            for idx, c_data in enumerate(chunk_data_list):
                embedding = embeddings[idx] if idx < len(embeddings) else None

                chunk = Chunk(
                    document_id=doc.id,
                    org_id=org_id,
                    chunk_index=c_data.chunk_index,
                    page=c_data.page,
                    text=c_data.text,
                    embedding=embedding,
                    tsv=func.to_tsvector("english", c_data.text) if is_postgres else c_data.text,
                )
                db.add(chunk)

        doc.status = "processed"
        db.commit()
        db.refresh(doc)
        return doc

    except Exception as e:
        db.rollback()
        # Mark as error
        doc.status = "error"
        db.commit()
        raise e
