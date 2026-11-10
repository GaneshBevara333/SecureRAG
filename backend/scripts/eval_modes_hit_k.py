import os
import sys

# Ensure backend root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if "--real" not in sys.argv:
    os.environ.setdefault("USE_MOCK_EMBEDDINGS", "1")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.db.models import Organization, User, Document, Chunk
from app.ingestion.pipeline import ingest_document
from app.retrieval.search import retrieve_chunks


def run_benchmark():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # 1. Setup sample org and user
    org = Organization(name="Benchmark Org")
    db.add(org)
    db.flush()

    user = User(org_id=org.id, email="eval@benchmark.local", password_hash="hash", role="admin")
    db.add(user)
    db.commit()

    # 2. Ingest corpus documents
    sample_corpus = [
        (
            "arch_overview.txt",
            "SecureRAG uses PostgreSQL with pgvector for unified storage of relational data, full-text search, and vector embeddings.",
        ),
        (
            "auth_security.txt",
            "Authentication is handled via JWT access tokens and hashed API keys. Passwords are encrypted using bcrypt.",
        ),
        (
            "acl_retrieval.txt",
            "Retrieval time access control enforces document permissions inside the SQL WHERE clause before results reach the LLM.",
        ),
        (
            "hybrid_rerank.txt",
            "Hybrid retrieval combines dense semantic vector search with sparse tsvector full-text search fused using Reciprocal Rank Fusion.",
        ),
        (
            "eval_loop.txt",
            "The continuous evaluation loop benchmarks hit at k, MRR, faithfulness via LLM-as-judge, and latency across runs.",
        ),
    ]

    doc_ids = {}
    for filename, text in sample_corpus:
        doc = ingest_document(
            db=db,
            org_id=org.id,
            owner_id=user.id,
            filename=filename,
            file_bytes=text.encode("utf-8"),
            title=filename,
            visibility="org",
        )
        doc_ids[filename] = doc.id

    # 3. Define sample eval test cases
    eval_cases = [
        {"question": "How does SecureRAG store vectors and relational data?", "expected_doc": "arch_overview.txt"},
        {"question": "What encryption is used for storing user passwords?", "expected_doc": "auth_security.txt"},
        {"question": "Where is the ACL filter applied during retrieval?", "expected_doc": "acl_retrieval.txt"},
        {"question": "How are dense and sparse search fused together?", "expected_doc": "hybrid_rerank.txt"},
        {"question": "What metrics are measured by the continuous evaluation loop?", "expected_doc": "eval_loop.txt"},
    ]

    modes = ["dense", "hybrid", "hybrid+rerank"]
    results = {}

    for mode in modes:
        hits_at_1 = 0
        hits_at_3 = 0
        hits_at_5 = 0
        reciprocal_ranks = []

        for case in eval_cases:
            target_doc_id = doc_ids[case["expected_doc"]]
            retrieved = retrieve_chunks(
                db=db,
                query=case["question"],
                org_id=org.id,
                user_id=user.id,
                is_admin=True,
                retrieval_mode=mode,
                top_k=5,
            )

            retrieved_doc_ids = [r.document_id for r in retrieved]

            # hit@k
            if target_doc_id in retrieved_doc_ids[:1]:
                hits_at_1 += 1
            if target_doc_id in retrieved_doc_ids[:3]:
                hits_at_3 += 1
            if target_doc_id in retrieved_doc_ids[:5]:
                hits_at_5 += 1

            # MRR
            if target_doc_id in retrieved_doc_ids:
                rank = retrieved_doc_ids.index(target_doc_id) + 1
                reciprocal_ranks.append(1.0 / rank)
            else:
                reciprocal_ranks.append(0.0)

        n = len(eval_cases)
        results[mode] = {
            "hit@1": hits_at_1 / n,
            "hit@3": hits_at_3 / n,
            "hit@5": hits_at_5 / n,
            "mrr": sum(reciprocal_ranks) / n,
        }

    # Print comparison table
    print("=" * 60)
    print("       Retrieval Mode Benchmark Evaluation (hit@k & MRR)")
    print("=" * 60)
    print(f"{'Retrieval Mode':<18} | {'hit@1':<8} | {'hit@3':<8} | {'hit@5':<8} | {'MRR':<8}")
    print("-" * 60)
    for mode, m in results.items():
        print(f"{mode:<18} | {m['hit@1']:<8.2f} | {m['hit@3']:<8.2f} | {m['hit@5']:<8.2f} | {m['mrr']:<8.2f}")
    print("=" * 60)


if __name__ == "__main__":
    run_benchmark()
