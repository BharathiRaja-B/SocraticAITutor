"""
routers/rag.py — FastAPI router for RAG functionality

Endpoints:
- POST /upload : multipart file upload (PDF or TXT). Saves file to `uploads/` and ingests into Chroma.
- POST /query  : JSON {question, namespace?} runs retrieval and returns LLM answer.

Requirements:
- Protected endpoints: require authentication via `auth.get_current_user` dependency.
- Does not modify normal chat endpoints — only used when documents exist.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
import os
import shutil
from typing import Optional

from auth import get_current_user
from services.rag_service import rag_service

router = APIRouter()

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), user=Depends(get_current_user), namespace: Optional[str] = None):
    """Upload a PDF or TXT file and ingest into the RAG store."""
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".pdf", ".txt", ".md"):
        raise HTTPException(status_code=400, detail="Only PDF, TXT, or MD files are supported")

    # Save to disk
    dest_path = os.path.join(UPLOAD_DIR, f"{user['id']}_{int(__import__('time').time())}_{filename}")
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Ingest into RAG service under a namespace (per-user by default)
    ns = namespace or f"user_{user['id']}"
    try:
        info = rag_service.ingest_file(dest_path, namespace=ns)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    return {"message": "File ingested", "details": info}


@router.post("/query")
async def rag_query(payload: dict, user=Depends(get_current_user)):
    """Query the RAG index. Payload: {question: str, namespace?: str, k?: int} """
    q = payload.get("question")
    if not q:
        raise HTTPException(status_code=400, detail="question is required")
    ns = payload.get("namespace") or f"user_{user['id']}"
    k = int(payload.get("k", 4))

    res = rag_service.query(q, namespace=ns, k=k)
    if res.get("error") == "no_documents":
        raise HTTPException(status_code=404, detail="No documents found for this user/namespace")
    if res.get("error"):
        raise HTTPException(status_code=500, detail=res.get("error"))

    return res
