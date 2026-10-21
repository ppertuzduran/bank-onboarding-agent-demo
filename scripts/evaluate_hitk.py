"""Evalúa la estrategia de chunking + retrieval sobre un set de preguntas sintéticas.

Reporta hit@1, hit@3, hit@5. Un "hit" en k es: alguno de los top-k chunks
coincide con `expected_document` y `expected_section`.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.config import BASE_DIR
from app.rag.embedder import get_embedding_provider
from app.rag.retriever import get_retriever
from app.schemas import EvaluationQuestion, HitAtKReport

_K_VALUES: list[int] = [1, 3, 5]


def _load_questions(path: Path) -> list[EvaluationQuestion]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [EvaluationQuestion.model_validate(item) for item in raw]


def _is_hit(hit_document: str, hit_section: str, expected_doc: str, expected_section: str) -> bool:
    return hit_document == expected_doc and hit_section.strip().lower() == expected_section.strip().lower()


def main() -> int:
    questions_path = BASE_DIR / "eval" / "test_questions.json"
    questions = _load_questions(questions_path)

    retriever = get_retriever()
    max_k = max(_K_VALUES)

    hits_at: dict[int, int] = dict.fromkeys(_K_VALUES, 0)
    per_question: list[dict] = []

    for q in questions:
        results = retriever.query(text=q.question, top_k=max_k)
        hit_positions: list[int] = []
        for idx, hit in enumerate(results, start=1):
            if _is_hit(hit.document, hit.section, q.expected_document, q.expected_section):
                hit_positions.append(idx)

        first_hit = hit_positions[0] if hit_positions else None
        for k in _K_VALUES:
            if first_hit is not None and first_hit <= k:
                hits_at[k] += 1

        per_question.append(
            {
                "question": q.question,
                "expected": f"{q.expected_document} :: {q.expected_section}",
                "first_hit_position": first_hit,
                "top1": f"{results[0].document} :: {results[0].section}" if results else None,
                "top1_score": results[0].score if results else None,
            }
        )

    total = len(questions)
    recall_at = {k: (hits_at[k] / total if total else 0.0) for k in _K_VALUES}
    report = HitAtKReport(
        k_values=_K_VALUES,
        total_questions=total,
        hits_at=hits_at,
        recall_at=recall_at,
        per_question=per_question,
    )

    embedder = get_embedding_provider()
    print("=" * 70)
    print(f"Modelo embeddings : {embedder.model_id}")
    print(f"Dimensión vector  : {embedder.dimension}")
    print(f"Preguntas evaluadas: {total}")
    print(report.summary())
    print("=" * 70)
    print("Detalle por pregunta:")
    for item in per_question:
        marker = "OK " if item["first_hit_position"] else "MISS"
        pos = item["first_hit_position"] or "-"
        print(f"  [{marker}] pos={pos} :: {item['question']}")
        print(f"         esperado: {item['expected']}")
        print(f"         top1:     {item['top1']}  (score={item['top1_score']})")

    out_path = BASE_DIR / "eval" / "hitk_report.json"
    out_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"\nReporte guardado en {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
