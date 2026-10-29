#!/usr/bin/env python3
"""Print RAG retrieval debug info for recent chat messages (Phase 4 Brief Sec 8.7)."""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.db import get_conn


def main():
    with get_conn() as conn:
        with conn.cursor() as cursor:
            query = """
                SELECT 
                    m.message_id,
                    m.patient_id,
                    m.conversation_id,
                    m.sender,
                    LEFT(m.message_text, 120) AS snippet,
                    m.answer_type,
                    m.retrieval_debug,
                    m.created_at,
                    f.rating,
                    f.comment
                FROM chat_messages m
                LEFT JOIN chat_feedback f ON m.message_id = f.message_id
                WHERE m.sender IN ('AI_Nurse', 'AI_Assistant')
                ORDER BY m.message_id DESC
                LIMIT 50;
            """
            cursor.execute(query)
            rows = cursor.fetchall()

    print(f"\nFound {len(rows)} recent AI assistant messages in careloop.chat_messages:\n")
    print("-" * 100)
    for r in rows:
        debug = {}
        if r["retrieval_debug"]:
            try:
                debug = json.loads(r["retrieval_debug"]) if isinstance(r["retrieval_debug"], str) else r["retrieval_debug"]
            except Exception:
                debug = {"raw": r["retrieval_debug"]}

        rating_str = f"★ {r['rating']} ({r['comment']})" if r["rating"] is not None else "No rating"
        print(f"Msg #{r['message_id']} | Patient: {r['patient_id']} | Type: {r['answer_type']} | {r['created_at']} | Rating: {rating_str}")
        print(f"Text: {r['snippet']}...")
        if debug:
            intent = debug.get("intent", "n/a")
            tool = debug.get("tool_called", "none")
            chunks = debug.get("chunks_count", 0)
            guard = debug.get("numeric_guard", {}).get("guard_action", "ok")
            sources = debug.get("sources", [])
            print(f"  Debug: Intent={intent} | Tool={tool} | Chunks={chunks} | Guard={guard} | Sources={len(sources)}")
            for idx, s in enumerate(sources[:3]):
                print(f"    Source {idx+1}: {s.get('doc_title', 'Doc')} · {s.get('section_title', 'Sec')} (page {s.get('page_no', 1)})")
        print("-" * 100)


if __name__ == "__main__":
    main()
