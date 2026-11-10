from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, orgs, teams, documents, query, api_keys, admin, feedback, evals

app = FastAPI(
    title="SecureRAG API",
    description="Multi-tenant RAG platform with retrieval-time access control",
    version="0.1.0",
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "SecureRAG"}


# Include API routers
app.include_router(auth.router)
app.include_router(orgs.router)
app.include_router(teams.router)
app.include_router(documents.router)
app.include_router(query.router)
app.include_router(api_keys.router)
app.include_router(admin.router)
app.include_router(feedback.router)
app.include_router(evals.router)
