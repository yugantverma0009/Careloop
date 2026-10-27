#!/usr/bin/env python3
"""
scripts/index_document.py — Index a synthetic discharge summary PDF into CareLoop

Extracts text using pypdf, chunks text (500 chars, 80 overlap),
inserts document into discharge_documents ('Pending' -> 'Indexed'),
inserts chunks into document_chunks, and indexes vectors into ChromaDB.
"""

import sys
import os
import pypdf
import chromadb
import pymysql
from dotenv import load_dotenv

# Try multiple env locations
load_dotenv(os.path.join(os.path.dirname(__file__), "../backend/.env"))
load_dotenv(".env")


from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from google import genai

class GeminiEmbeddingFunction(EmbeddingFunction):
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def __call__(self, input: Documents) -> Embeddings:
        res = []
        for doc in input:
            r = self.client.models.embed_content(
                model="gemini-embedding-001",
                contents=doc
            )
            res.append(r.embeddings[0].values)
        return res

def chunk(t, size=500, overlap=80):
    out, i = [], 0
    while i < len(t):
        out.append(t[i:i + size])
        i += size - overlap
    return out


def main():
    if len(sys.argv) < 3:
        print("Usage: python index_document.py <discharge_id> <pdf_path>")
        sys.exit(1)

    discharge_id = int(sys.argv[1])
    pdf_path = sys.argv[2]

    if not os.path.exists(pdf_path):
        print(f"Error: PDF file '{pdf_path}' not found.")
        sys.exit(1)

    reader = pypdf.PdfReader(pdf_path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    chunks = [c.strip() for c in chunk(text) if c.strip()]
    if not chunks:
        print("Warning: No text extracted from PDF.")
        sys.exit(1)

    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "3306"))
    db_user = os.getenv("DB_USER", "careloop_api")
    db_pass = os.getenv("DB_PASSWORD", "careloop_dev_pass")
    db_name = os.getenv("DB_NAME", "careloop")
    chroma_path = os.getenv("CHROMA_PATH", "./chroma")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("GOOGLE_API_KEY")

    conn = pymysql.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_pass,
        database=db_name,
        charset="utf8mb4",
    )

    chroma_client = chromadb.PersistentClient(path=chroma_path)
    ef = GeminiEmbeddingFunction(api_key=api_key)
    col_name = f"discharge_{discharge_id}"
    col = chroma_client.get_or_create_collection(col_name, embedding_function=ef)

    with conn.cursor() as cur:
        file_name = os.path.basename(pdf_path)
        cur.execute(
            """
            INSERT INTO discharge_documents (discharge_id, file_name, indexing_status, vector_collection)
            VALUES (%s, %s, 'Pending', %s)
            """,
            (discharge_id, file_name, col_name)
        )
        doc_id = cur.lastrowid

        for i, c in enumerate(chunks):
            vid = f"{doc_id}-{i}"
            cur.execute(
                """
                INSERT INTO document_chunks (document_id, chunk_index, chunk_text, vector_id)
                VALUES (%s, %s, %s, %s)
                """,
                (doc_id, i, c, vid)
            )
            col.add(ids=[vid], documents=[c])

        cur.execute(
            "UPDATE discharge_documents SET indexing_status = 'Indexed' WHERE document_id = %s",
            (doc_id,)
        )

    conn.commit()
    conn.close()
    print(f"Successfully indexed document {doc_id} with {len(chunks)} chunks into collection {col_name}.")


if __name__ == "__main__":
    main()
