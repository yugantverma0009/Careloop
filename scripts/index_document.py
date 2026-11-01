#!/usr/bin/env python3
"""
scripts/index_document.py — Index a synthetic discharge summary PDF into CareLoop

Extracts text using pypdf, chunks text (500 chars, 80 overlap),
inserts document into discharge_documents ('Pending' -> 'Indexed'),
inserts chunks into document_chunks, and indexes vectors into ChromaDB.
"""

import sys
import os
import re
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

def parse_document_sections(reader):
    """
    Extracts text per page and detects clinical section headings.
    Returns list of (chunk_text, section_title, section_type, page_no).
    """
    SECTION_RULES = [
        (r"(?i)\b(medications?|medication plan|prescriptions?)\b", "Medication Plan", "medications"),
        (r"(?i)\b(follow-?up|appointments?|clinic visit)\b", "Appointments & Follow-up", "follow_up"),
        (r"(?i)\b(warning signs?|red flags?|danger signs?|when to call)\b", "Warning Signs & Red Flags", "warning_signs"),
        (r"(?i)\b(activity|exercise|mobility|physical activity)\b", "Activity Guidelines", "activity"),
        (r"(?i)\b(wound care|incision|dressing|stitches|bandage)\b", "Sternal Wound Management", "wound_care"),
        (r"(?i)\b(diet|nutrition|food|meals|hydration)\b", "Diet & Nutrition", "diet"),
    ]

    results = []
    current_sec_title = "General Recovery Instructions"
    current_sec_type = "general"

    for page_idx, page in enumerate(reader.pages):
        page_no = page_idx + 1
        page_text = page.extract_text() or ""
        paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]

        for p in paragraphs:
            # Check for section heading in paragraph header
            header_line = p.split("\n")[0]
            matched_rule = False
            for pat, stitle, stype in SECTION_RULES:
                if re.search(pat, header_line):
                    current_sec_title = stitle
                    current_sec_type = stype
                    matched_rule = True
                    break

            # If paragraph is long, chunk it
            if len(p) > 600:
                sub_chunks = chunk(p, size=500, overlap=60)
                for sc in sub_chunks:
                    if sc.strip():
                        results.append((sc.strip(), current_sec_title, current_sec_type, page_no))
            else:
                results.append((p, current_sec_title, current_sec_type, page_no))

    return results if results else [("General discharge instructions.", "General", "general", 1)]


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
    parsed_sections = parse_document_sections(reader)
    if not parsed_sections:
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

        for i, (c_text, s_title, s_type, p_no) in enumerate(parsed_sections):
            vid = f"{doc_id}-{i}"
            cur.execute(
                """
                INSERT INTO document_chunks (document_id, chunk_index, chunk_text, vector_id, section_title, section_type, page_no)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (doc_id, i, c_text, vid, s_title, s_type, p_no)
            )
            col.add(ids=[vid], documents=[c_text])

        cur.execute(
            "UPDATE discharge_documents SET indexing_status = 'Indexed' WHERE document_id = %s",
            (doc_id,)
        )

    conn.commit()
    conn.close()
    print(f"Successfully indexed document {doc_id} with {len(parsed_sections)} section-aware chunks into collection {col_name}.")


if __name__ == "__main__":
    main()
