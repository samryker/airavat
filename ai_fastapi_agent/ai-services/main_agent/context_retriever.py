from __future__ import annotations

import re
from typing import Dict, Any, List, Optional, Tuple


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    # Lowercase, collapse spaces
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenize(text: str) -> List[str]:
    text = _normalize_text(text)
    # Simple word tokenizer
    return re.findall(r"[a-z0-9_]+", text)


def _approx_token_count(text: str) -> int:
    # Rough heuristic: ~4 chars per token
    return max(1, len(text) // 4)


def _score_text(query_terms: List[str], text: str, weight: float = 1.0) -> float:
    if not text:
        return 0.0
    text_terms = _tokenize(text)
    if not text_terms:
        return 0.0
    term_set = set(text_terms)
    score = sum(1.0 for t in query_terms if t in term_set)
    return score * weight


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _compress_kv(data: Dict[str, Any], include_keys: List[str]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for key in include_keys:
        if key in data and data[key] not in (None, "", []):
            summary[key] = data[key]
    return summary


class ContextRetriever:
    """
    Lightweight, dependency-free contextual memory retriever.
    - Collects candidate snippets from Firestore-derived data structures
    - Scores by simple keyword overlap with the query
    - Assembles a trimmed context within a character/token budget
    """

    def __init__(self, firestore_service):
        self.firestore_service = firestore_service

    async def retrieve(self, patient_id: str, query_text: str, *, max_chars: int = 6000) -> Dict[str, Any]:
        query_terms = _tokenize(query_text)

        # 1) Gather data (best-effort)
        profile = None
        biomarkers = None
        treatments: List[Dict[str, Any]] = []
        conversation: List[Dict[str, Any]] = []
        latest_treatment: Optional[Dict[str, Any]] = None

        try:
            profile = await self.firestore_service.get_patient_data(patient_id)
        except Exception:
            profile = None
        try:
            biomarkers = await self.firestore_service.get_latest_biomarkers(patient_id)
        except Exception:
            biomarkers = None
        try:
            treatments = await self.firestore_service.get_treatment_history(patient_id, limit=10)
        except Exception:
            treatments = []
        try:
            conversation = await self.firestore_service.get_conversation_history(patient_id, limit=10)
        except Exception:
            conversation = []
        # Optional: latest treatment doc if available in your schema (graceful if absent)
        try:
            if hasattr(self.firestore_service, "get_latest_treatment"):
                latest_treatment = await self.firestore_service.get_latest_treatment(patient_id)
        except Exception:
            latest_treatment = None

        # 2) Build candidate snippets with weights
        candidates: List[Tuple[float, str, str]] = []  # (score, section, text)

        # Profile fields of interest (avoid PII besides clinically relevant fields)
        if profile:
            profile_summary = _compress_kv(
                profile,
                [
                    "age",
                    "gender",
                    "bmiIndex",
                    "medicines",
                    "allergies",
                    "history",
                    "goal",
                ],
            )
            profile_text = _normalize_text(str(profile_summary))
            candidates.append((_score_text(query_terms, profile_text, 1.4), "profile", profile_text))

        if biomarkers:
            biomarkers_text = _normalize_text(str(biomarkers))
            candidates.append((_score_text(query_terms, biomarkers_text, 1.3), "biomarkers", biomarkers_text))

        if latest_treatment:
            lt_text = _normalize_text(str(latest_treatment))
            candidates.append((_score_text(query_terms, lt_text, 1.6), "latest_treatment", lt_text))

        # Recent treatment plans (cap to last 3)
        for plan in (treatments or [])[:3]:
            plan_text = _normalize_text(str(plan))
            candidates.append((_score_text(query_terms, plan_text, 1.2), "treatment_plan", plan_text))

        # Recent conversation turns (last 5)
        for msg in (conversation or [])[:5]:
            turn_text = _normalize_text(str(msg))
            candidates.append((_score_text(query_terms, turn_text, 1.0), "conversation", turn_text))

        # 3) Select top snippets until budget
        candidates.sort(key=lambda x: x[0], reverse=True)
        assembled: List[str] = []
        used = 0
        budget_chars = max_chars

        # Always include a compact header
        header = f"patient_id={patient_id}; query='{_truncate(_normalize_text(query_text), 240)}'\n"
        assembled.append(header)
        used += len(header)

        for score, section, text in candidates:
            if score <= 0:
                continue
            if used >= budget_chars:
                break
            # Allocate small per-snippet budget
            allowance = min(800, budget_chars - used)
            snippet = f"[{section}] { _truncate(text, allowance - len(section) - 4) }\n"
            assembled.append(snippet)
            used += len(snippet)

        trimmed_context = "".join(assembled)
        return {
            "patient_id": patient_id,
            "query": query_text,
            "trimmed_context_text": trimmed_context,
            "approx_tokens": _approx_token_count(trimmed_context),
        }


