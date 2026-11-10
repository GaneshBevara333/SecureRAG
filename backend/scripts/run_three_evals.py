import os
import sys
sys.path.insert(0, ".")
os.environ["USE_MOCK_EMBEDDINGS"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.db.session import Base, engine, SessionLocal
from app.db.models import Organization, User, Document, EvalCase, EvalRun
from app.ingestion.pipeline import ingest_document
from app.evals.runner import run_evaluation
from app.evals.judge import judge_service

def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # 1. Setup sample org, admin, docs, and cases
    org = Organization(name="Eval Benchmark Org")
    db.add(org)
    db.flush()

    admin = User(org_id=org.id, email="admin@benchmark.local", password_hash="hash", role="admin")
    db.add(admin)
    db.flush()

    docs_data = [
        ("security_policy.txt", b"Multi-factor authentication (MFA) is strictly required for all production SSH and VPN sessions.", "Security Policy"),
        ("incident_response.txt", b"P0 incident escalations must alert the VP of Infrastructure within 15 minutes of detection.", "Incident Response"),
        ("retention_guide.txt", b"Customer audit logs are retained in cold storage for a minimum duration of 7 years.", "Data Retention"),
    ]

    doc_ids = []
    for fname, content, title in docs_data:
        d = ingest_document(db=db, org_id=org.id, owner_id=admin.id, filename=fname, file_bytes=content, title=title)
        doc_ids.append(d.id)

    cases_data = [
        ("What are the MFA requirements for SSH?", doc_ids[0], "MFA is required for production SSH and VPN."),
        ("What is the P0 escalation timeframe?", doc_ids[1], "15 minutes of detection to VP of Infrastructure."),
        ("How long are audit logs retained?", doc_ids[2], "Minimum 7 years in cold storage."),
    ]

    for q, exp_doc, exp_ans in cases_data:
        c = EvalCase(org_id=org.id, question=q, expected_doc_id=exp_doc, expected_answer=exp_ans, source="manual")
        db.add(c)
    db.commit()

    # 2. Run the three modes
    modes = ["dense", "hybrid", "hybrid+rerank"]
    rows = []
    for mode in modes:
        run = run_evaluation(
            db=db,
            org_id=org.id,
            label=f"benchmark-{mode}",
            config={"retrieval_mode": mode, "top_k": 5},
        )
        rows.append(run)

    print("\n" + "="*80)
    print(f"{'Run Label':<22} | {'Mode':<15} | {'Hit@k':<8} | {'MRR':<8} | {'Faithfulness':<12} | {'p50 (ms)':<9} | {'p95 (ms)':<9}")
    print("-" * 80)
    for r in rows:
        mode_str = r.config.get("retrieval_mode", "unknown")
        print(f"{r.label:<22} | {mode_str:<15} | {r.hit_at_k:<8.4f} | {r.mrr:<8.4f} | {r.faithfulness:<12.4f} | {r.p50_ms:<9.2f} | {r.p95_ms:<9.2f}")
    print("="*80 + "\n")

    db.close()

if __name__ == "__main__":
    main()
