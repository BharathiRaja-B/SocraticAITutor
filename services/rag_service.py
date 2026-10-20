"""
services/rag_service.py — Simple RAG (Retrieval-Augmented Generation) service

Features:
- Ingests PDF and TXT files via `ingest_file(file_path, namespace)`.
- Splits text into chunks using LangChain's text splitter.
- Embeds chunks using SentenceTransformers (`all-MiniLM-L6-v2`) via Chromadb's embedding function.
- Stores embeddings & metadata in a persistent Chroma collection under `./chroma_db`.
- Querying via `query(question, k=4)` returns LLM-augmented answer using `ai_helper.call_ai`.

Notes:
- Uses `chromadb` and `langchain` components; add packages to `requirements.txt`.
- Does not change normal chat; endpoints must call this service explicitly.
"""
from typing import List, Dict, Optional
import os
import uuid
import tempfile
import shutil

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import TextLoader
from langchain.document_loaders import PyPDFLoader

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

import ai_helper

# Persistent Chroma directory inside the workspace
CHROMA_DIR = os.environ.get("CHROMA_DIR", "./chroma_db")
os.makedirs(CHROMA_DIR, exist_ok=True)

# Initialize chroma client with persistent persistence
client = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", persist_directory=CHROMA_DIR))

# Use sentence-transformers embedding function via chromadb util wrapper
# Model: all-MiniLM-L6-v2 (compact and commonly available)
embed_fn = embedding_functions.SentenceTransformersEmbeddingFunction(model_name="all-MiniLM-L6-v2")

# Collection name used for documents
COLLECTION_NAME = "rag_docs"


class RAGService:
    def __init__(self, collection_name: str = COLLECTION_NAME):
        self.collection_name = collection_name
        try:
            self.col = client.get_collection(self.collection_name)
        except Exception:
            # create if not exists
            self.col = client.create_collection(self.collection_name, embedding_function=embed_fn)

        # Text splitter tuned for short chunks
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
        )

    def ingest_file(self, file_path: str, namespace: Optional[str] = None) -> Dict[str, object]:
        """Ingest a PDF or TXT file into the Chroma collection.

        Returns metadata about the ingestion.
        """
        # Load file content
        ext = os.path.splitext(file_path)[1].lower()
        docs = []
        if ext == ".pdf":
            loader = PyPDFLoader(file_path)
            docs = loader.load()
        elif ext in (".txt", ".md"):
            loader = TextLoader(file_path, encoding="utf-8")
            docs = loader.load()
        else:
            raise ValueError("Unsupported file type")

        # Extract text pieces and split into chunks
        texts = [d.page_content for d in docs]
        full_text = "\n\n".join(texts)
        chunks = self.splitter.split_text(full_text)

        # Prepare ids and metadatas
        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [{"source": os.path.basename(file_path), "namespace": namespace or "default"} for _ in chunks]

        # Persist to chroma
        self.col.add(ids=ids, documents=chunks, metadatas=metadatas, namespace=namespace)
        client.persist()

        return {"source": os.path.basename(file_path), "chunks_added": len(chunks), "namespace": namespace}

    def has_documents(self, namespace: Optional[str] = None) -> bool:
        """Return True if there are any documents in the collection (optionally in namespace)."""
        try:
            if namespace:
                count = len(self.col.get(ids=None, where={"metadata": {"namespace": namespace}}))
                return count > 0
        except Exception:
            # Fallback to generic count — chroma has collection.count()
            try:
                return self.col.count() > 0
            except Exception:
                return False
        return True

    def retrieve(self, query: str, k: int = 4, namespace: Optional[str] = None) -> List[Dict[str, str]]:
        """Retrieve top-k documents relevant to the query."""
        # Simple similarity search
        res = self.col.query(query_texts=[query], n_results=k, namespace=namespace)
        # `res` is a dict with 'documents' and 'metadatas' keys (list-of-list)
        docs = []
        if res and "documents" in res:
            docs_list = res["documents"][0]
            metas = res.get("metadatas", [[]])[0]
            for d, m in zip(docs_list, metas):
                docs.append({"text": d, "metadata": m})
        return docs

    def query(self, question: str, namespace: Optional[str] = None, k: int = 4) -> Dict[str, object]:
        """Run retrieval + LLM answer composition.

        Returns {answer, sources: [...], raw_ai_output}
        """
        # If no documents exist, raise or return sentinel
        try:
            if not self.has_documents(namespace=namespace):
                return {"error": "no_documents"}
        except Exception:
            # if chroma fails, avoid breaking the app — fallback
            return {"error": "chroma_unavailable"}

        docs = self.retrieve(question, k=k, namespace=namespace)
        context_text = "\n\n".join([f"Source: {d['metadata'].get('source','unknown')}\n{d['text']}" for d in docs])

        # Build a user prompt that instructs the model to use the provided context.
        prompt = (
            "You are an assistant using retrieved documents to answer the user's question. \n"
            "Refer to the provided sources and answer concisely. Include a short "
            "list of sources at the end.\n\n"
            "Context:\n" + context_text + "\n\nQuestion: " + question
        )

        messages = [{"role": "user", "content": prompt}]
        # Delegate to existing ai_helper which calls OpenRouter.
        ai_output = ai_helper.call_ai(messages, max_tokens=512, temperature=0.0)

        return {"answer": ai_output, "sources": [d.get("metadata", {}).get("source") for d in docs], "raw_ai_output": ai_output}


# Singleton instance for the app to reuse
rag_service = RAGService()
