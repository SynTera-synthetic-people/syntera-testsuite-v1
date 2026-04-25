"""Align synthetic vs human survey questions when IDs or file order differ."""
from __future__ import annotations

import math
import re
from difflib import SequenceMatcher
from typing import Any, Optional

__all__ = [
    "normalize_survey_question_id",
    "pair_survey_questions_for_comparison",
    "pair_categorical_response_options",
]


def normalize_survey_question_id(q_id: Any) -> str:
    """
    Canonical id for matching, e.g. 1, 1.0, 'Q1', 'q 1' -> 'Q1'.
    Unknown shapes are uppercased and stripped.
    """
    if q_id is None:
        return ""
    if isinstance(q_id, float) and math.isnan(q_id):
        return ""
    s = str(q_id).strip()
    if not s or s.lower() == "nan":
        return ""
    s_up = s.upper().replace(" ", "")
    if s_up.startswith("Q"):
        tail = s_up[1:].lstrip(":-._")
        m = re.match(r"^(\d+)", tail)
        if m:
            return f"Q{int(m.group(1))}"
        return s_up
    try:
        n = int(float(s))
        return f"Q{n}"
    except (TypeError, ValueError):
        return s_up


def _norm_question_text(text: Any) -> str:
    t = str(text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def _name_similarity(name_a: Any, name_b: Any) -> float:
    a = _norm_question_text(name_a)
    b = _norm_question_text(name_b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _option_label_jaccard(syn: dict[str, Any], real: dict[str, Any]) -> float:
    def keys(d: dict[str, Any]) -> set[str]:
        out: set[str] = set()
        for k in (d or {}):
            kk = _norm_question_text(k)
            if kk and kk not in {"mean", "median", "std", "total_responses"}:
                out.add(kk)
        return out

    sa = keys(syn.get("response_counts") or {})
    rb = keys(real.get("response_counts") or {})
    if not sa or not rb:
        return 0.0
    inter = len(sa & rb)
    union = len(sa | rb)
    return inter / union if union else 0.0


def _norm_option_label(text: Any) -> str:
    t = str(text or "").strip().lower()
    t = t.replace("\u2013", "-").replace("\u2014", "-")
    t = re.sub(r"\s+", " ", t)
    return t


def _satisfaction_polarity_opposed(a: str, b: str) -> bool:
    """True if two labels look like opposite ends of a agree/satisfy scale (avoid wrong fuzzy pairs)."""
    neg = ("dissatisf", "disagree", "negative", "unlikely", "not likely", "poor", "worse")
    pos = ("satisf", "agree", "positive", "likely", "good", "excellent", "strongly agree")
    a_neg = any(x in a for x in neg)
    b_neg = any(x in b for x in neg)
    a_pos = any(x in a for x in pos) and not a_neg
    b_pos = any(x in b for x in pos) and not b_neg
    return (a_neg and b_pos) or (a_pos and b_neg)


def _option_pair_similarity(syn_label: str, human_label: str) -> float:
    """Similarity for matching one synthetic option label to one human option label."""
    a = _norm_option_label(syn_label)
    b = _norm_option_label(human_label)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if _satisfaction_polarity_opposed(a, b):
        return 0.0
    if a.isdigit() and b.isdigit():
        return 1.0 if a == b else 0.0
    r = SequenceMatcher(None, a, b).ratio()
    if len(a) >= 4 and len(b) >= 4 and (a in b or b in a):
        r = max(r, 0.88)
    return float(r)


def _string_key_counts(raw: dict[str, Any] | None) -> dict[str, float]:
    """Coerce dict keys to trimmed strings so lookups stay consistent (JSON may use int keys)."""
    out: dict[str, float] = {}
    for k, v in (raw or {}).items():
        key = str(k).strip()
        try:
            out[key] = float(v or 0)
        except (TypeError, ValueError):
            out[key] = 0.0
    return out


def pair_categorical_response_options(
    syn_counts: dict[str, Any],
    human_counts: dict[str, Any],
    *,
    min_score: float = 0.52,
) -> list[dict[str, Any]]:
    """
    Align synthetic vs human option labels for one question (wording may differ).

    Returns rows with: option, synthetic_option, human_option, synthetic_count, real_count.
    """
    syn_m = _string_key_counts(syn_counts)
    hum_m = _string_key_counts(human_counts)
    syn_keys = list(syn_m.keys())
    hum_keys = list(hum_m.keys())

    def sval(k: str) -> float:
        return float(syn_m.get(k, 0.0))

    def hval(k: str) -> float:
        return float(hum_m.get(k, 0.0))

    if not syn_keys or not hum_keys:
        return []

    candidates: list[tuple[float, int, int]] = []
    for i, sk in enumerate(syn_keys):
        for j, hk in enumerate(hum_keys):
            sim = _option_pair_similarity(sk, hk)
            if sim >= min_score:
                candidates.append((sim, i, j))

    candidates.sort(key=lambda t: t[0], reverse=True)
    used_s: set[int] = set()
    used_h: set[int] = set()
    paired: list[tuple[str, str, float, float]] = []

    for sim, i, j in candidates:
        if i in used_s or j in used_h:
            continue
        used_s.add(i)
        used_h.add(j)
        sk, hk = syn_keys[i], hum_keys[j]
        paired.append((sk, hk, sval(sk), hval(hk)))

    index_h = {hk: idx for idx, hk in enumerate(hum_keys)}
    index_s = {sk: idx for idx, sk in enumerate(syn_keys)}
    paired.sort(key=lambda t: (index_h.get(t[1], 999), index_s.get(t[0], 999)))

    rows: list[dict[str, Any]] = []

    def display_option(sk: str, hk: str) -> str:
        if sk == hk:
            return sk
        return f"{hk} ↔ {sk}"

    for sk, hk, sv, rv in paired:
        rows.append(
            {
                "option": display_option(sk, hk),
                "synthetic_option": sk,
                "human_option": hk,
                "synthetic_count": float(sv),
                "real_count": float(rv),
            }
        )

    for i, sk in enumerate(syn_keys):
        if i in used_s:
            continue
        sv = sval(sk)
        rows.append(
            {
                "option": f"{sk} (synthetic only)",
                "synthetic_option": sk,
                "human_option": None,
                "synthetic_count": float(sv),
                "real_count": 0.0,
            }
        )

    for j, hk in enumerate(hum_keys):
        if j in used_h:
            continue
        rv = hval(hk)
        rows.append(
            {
                "option": f"{hk} (human only)",
                "synthetic_option": None,
                "human_option": hk,
                "synthetic_count": 0.0,
                "real_count": float(rv),
            }
        )

    return rows


def pair_survey_questions_for_comparison(
    syn_q_data: list[dict[str, Any]],
    real_q_data: list[dict[str, Any]],
    min_score: float = 0.48,
) -> list[tuple[dict[str, Any], dict[str, Any], float]]:
    """
    Greedy many-to-one matching: each synthetic question pairs with at most one real question.

    Scores combine question-text similarity and option-label overlap so different Q-numbers
    for the same wording still align.
    """
    if not syn_q_data or not real_q_data:
        return []

    candidates: list[tuple[float, int, int]] = []
    for i, sq in enumerate(syn_q_data):
        sid = normalize_survey_question_id(sq.get("question_id"))
        for j, rq in enumerate(real_q_data):
            rid = normalize_survey_question_id(rq.get("question_id"))
            name = _name_similarity(sq.get("question_name", ""), rq.get("question_name", ""))
            jac = _option_label_jaccard(sq, rq)
            score = min(1.0, 0.58 * name + 0.42 * jac)
            if sid and rid and sid == rid:
                score = min(1.0, score + 0.12)
            # Avoid pairing on option overlap alone when stems are unrelated (common with Likert scales).
            if name < 0.32 and jac < 0.55:
                continue
            # Medium fuzzy text + weak option overlap often means different questions (e.g. two 5-point scales).
            if jac < 0.48 and name < 0.75:
                continue
            if score >= min_score:
                candidates.append((score, i, j))

    candidates.sort(key=lambda t: t[0], reverse=True)
    used_s: set[int] = set()
    used_r: set[int] = set()
    out: list[tuple[dict[str, Any], dict[str, Any], float]] = []
    for score, i, j in candidates:
        if i in used_s or j in used_r:
            continue
        used_s.add(i)
        used_r.add(j)
        out.append((syn_q_data[i], real_q_data[j], score))

    return out
