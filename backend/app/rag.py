"""
app/rag.py — Grounded RAG with strict deterministic refusals

CORE RULE:
"The LLM talks. Rules decide. Humans act."
- LLM output is text only. Never creates flags, never diagnoses, never changes doses.
- Emergency guidance is returned deterministically without waiting for LLM.
- Dose change requests are deterministically refused and a follow-up task is created.
- Answers MUST come ONLY from the discharge document excerpts.
- If information is not in the excerpts, return safe refusal and create a staff follow-up task.
"""

import os
import logging
from typing import Tuple, List, Optional
import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))
load_dotenv(".env")
logger = logging.getLogger(__name__)
from .llm import generate
from .safety import is_dose_change_question, has_emergency_term, EMERGENCY_GUIDANCE, DOSE_CHANGE_REFUSAL

logger = logging.getLogger(__name__)

NOT_FOUND_MSG = {
    "en": "I could not find this in your discharge papers. I have asked your care team to reply.",
    "hi": "यह आपके डिस्चार्ज पेपर्स में नहीं मिला। मैंने आपकी केयर टीम से जवाब देने को कहा है।",
}

SYSTEM = (
    "You are a post-discharge assistant. Answer ONLY from the CONTEXT. "
    "If the context does not contain the answer, reply exactly: NOT_IN_DOCUMENTS. "
    "Never diagnose, never advise changing, stopping or doubling any medicine, "
    "and never reassure about symptoms. Reply in the language of the question. Be brief."
)


class GeminiEmbeddingFunction(EmbeddingFunction):
    def __init__(self):
        api_key = os.getenv("LLM_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=api_key)

    def __call__(self, input: Documents) -> Embeddings:
        res = []
        for doc in input:
            try:
                r = self.client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=doc,
                    config=types.EmbedContentConfig(output_dimensionality=768)
                )
                res.append(r.embeddings[0].values)
            except Exception as e:
                logger.warning(f"Embedding API call failed ({e}); using deterministic fallback embedding.")
                import hashlib
                h = hashlib.sha256(doc.encode("utf-8")).digest()
                vals = [((h[i % len(h)] / 255.0) - 0.5) for i in range(768)]
                norm = sum(x * x for x in vals) ** 0.5 or 1.0
                res.append([x / norm for x in vals])
        return res


_chroma_client = None
_embedding_fn = None


def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        chroma_path = os.getenv("CHROMA_PATH", "./chroma")
        _chroma_client = chromadb.PersistentClient(path=chroma_path)
    return _chroma_client


def get_embedding_fn():
    global _embedding_fn
    if _embedding_fn is None:
        try:
            _embedding_fn = GeminiEmbeddingFunction()
        except Exception as e:
            logger.warning(f"Could not initialize GeminiEmbeddingFunction: {e}")
            _embedding_fn = None
    return _embedding_fn


from .rag_config import USE_UPGRADED_RAG
from .rag_pipeline import answer_patient_query

def answer(
    patient_id: int,
    question: str,
    lang: str = "en",
    col=None,
    conn=None,
    conversation_id: Optional[str] = None,
) -> Tuple[str, bool, List[str]]:
    """Answer patient questions strictly grounded in discharge documents.
    
    Returns:
        (answer_text, is_grounded, citation_vector_ids)
    """
    if USE_UPGRADED_RAG:
        result = answer_patient_query(
            patient_id=patient_id,
            question=question,
            conversation_id=conversation_id,
            language=lang,
        )
        return result["answer"], result["is_grounded"], result["citations"]

    # --- Legacy Assistant Path (when USE_UPGRADED_RAG=False) ---
    # 1. Deterministic emergency check (instant, no LLM)
    if has_emergency_term(question):
        guidance = EMERGENCY_GUIDANCE.get(lang, EMERGENCY_GUIDANCE["en"])
        return guidance, False, []

    # 2. Deterministic dose change check (instant refusal)
    if is_dose_change_question(question):
        refusal = DOSE_CHANGE_REFUSAL.get(lang, DOSE_CHANGE_REFUSAL["en"])
        return refusal, False, []

    # 3. Retrieve relevant discharge document chunks
    if col is None:
        client = get_chroma_client()
        discharge_id = None
        if conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT discharge_id FROM discharge_records WHERE patient_id = %s ORDER BY discharge_date DESC LIMIT 1",
                    (patient_id,)
                )
                row = cur.fetchone()
                if row:
                    discharge_id = row["discharge_id"]
        if not discharge_id:
            discharge_id = patient_id

        try:
            ef = get_embedding_fn()
            if ef:
                col = client.get_or_create_collection(f"discharge_{discharge_id}", embedding_function=ef)
            else:
                col = client.get_or_create_collection(f"discharge_{discharge_id}")
        except Exception as e:
            logger.error(f"Failed to access Chroma collection discharge_{discharge_id}: {e}")
            return (
                NOT_FOUND_MSG.get(lang, NOT_FOUND_MSG["en"]),
                False,
                [],
            )

    try:
        res = col.query(query_texts=[question], n_results=3)
        docs = res.get("documents", [[]])[0] if res.get("documents") else []
        ids = res.get("ids", [[]])[0] if res.get("ids") else []
    except Exception as e:
        logger.error(f"Chroma query failed: {e}")
        docs, ids = [], []

    if not docs:
        return (
            NOT_FOUND_MSG.get(lang, NOT_FOUND_MSG["en"]),
            False,
            [],
        )

    # 4. Generate answer constrained strictly to context
    context_str = "\n---\n".join(docs)
    user_prompt = f"CONTEXT:\n{context_str}\n\nQUESTION: {question}"
    out = generate(SYSTEM, user_prompt)

    if not out or "NOT_IN_DOCUMENTS" in out:
        return (
            NOT_FOUND_MSG.get(lang, NOT_FOUND_MSG["en"]),
            False,
            [],
        )

    ans = out.strip()
    prefix = "From your discharge summary: " if lang == "en" else "आपके डिस्चार्ज पेपर्स के अनुसार: "
    if not ans.startswith(prefix):
        ans = f"{prefix}{ans}"

    return ans, True, ids
