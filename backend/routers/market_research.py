"""Market Research Reverse Engineering - Infer research design from report content."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel, Field
from typing import Any, Optional
import base64
import hashlib
import logging
import os
import re
import time

# Project root: parent of backend/ (this file is backend/routers/market_research.py)
_project_root = os.path.normpath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
_env_path = os.path.join(_project_root, ".env")
# Also try cwd in case server was started from project root with different module path
_env_paths = [_env_path]
_cwd_env = os.path.join(os.getcwd(), ".env")
if _cwd_env not in _env_paths:
    _env_paths.append(_cwd_env)

if os.path.isfile(_env_path):
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except Exception:
        pass

from sqlalchemy.orm import Session

from config.settings import Settings
from backend.utils.llm_gateway import LlmGateway
from database.connection import get_db
from backend.models.survey import MarketResearchExtraction
from backend.utils.json_helpers import sanitize_for_json

_MAX_RAW_MARKDOWN_PERSIST = 350_000

logger = logging.getLogger(__name__)
router = APIRouter()
_settings = Settings()

# Cap report size per LLM call. Chunked processing uses this for each chunk.
MAX_REPORT_CHARS = 50_000
# Chunk overlap when splitting long reports (chars) to avoid cutting mid-sentence.
CHUNK_OVERLAP = 2_000
# In-memory cache: same report text → skip API call (saves credits).
_reverse_engineer_cache: dict[str, dict] = {}
REVERSE_ENGINEER_CACHE_MAX = 50
# Chunked upload: session_id -> { chunks: {index: str}, total_chunks: int, created_at: float }
_upload_chunks_store: dict[str, dict] = {}
UPLOAD_CHUNKS_TTL_SEC = 3600
UPLOAD_CHUNKS_MAX_SESSIONS = 100
_llm_gateway = LlmGateway(_settings)


def _parse_env_file(path: str) -> tuple[Optional[str], Optional[str]]:
    """Parse a single .env file for API keys. Returns (openai_key, anthropic_key)."""
    openai_key, anthropic_key = None, None
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                line = line.strip().strip("\ufeff")
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key == "OPENAI_API_KEY" and value and (value.startswith("sk-") or value.startswith("sk-proj-")):
                    openai_key = value
                if key == "ANTHROPIC_API_KEY" and value and value.startswith("sk-ant-"):
                    anthropic_key = value
    except Exception as e:
        logger.warning("Could not read .env at %s: %s", path, e)
    return openai_key, anthropic_key


def _read_keys_from_env_file() -> tuple[Optional[str], Optional[str]]:
    """Read API keys from .env; try project-root path and cwd."""
    openai_key, anthropic_key = None, None
    for path in _env_paths:
        if not os.path.isfile(path):
            continue
        o, a = _parse_env_file(path)
        if o:
            openai_key = o
        if a:
            anthropic_key = a
        if openai_key and anthropic_key:
            break
    return openai_key, anthropic_key


def _get_openai_key() -> Optional[str]:
    v = (_settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY") or "").strip()
    if v and (v.startswith("sk-") or v.startswith("sk-proj-")):
        return v
    v, _ = _read_keys_from_env_file()
    return v


def _get_anthropic_key() -> Optional[str]:
    v = (_settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if v and v.startswith("sk-ant-"):
        return v
    _, v = _read_keys_from_env_file()
    return v

# Shorter prompt to reduce input tokens (API cost). Output format must stay for parser.
REVERSE_ENGINEER_SYSTEM_PROMPT = """You are a Market Research Methodologist. Reverse-engineer the research design from the report.

CRITICAL: List EVERY survey question in the report. One block per question. Do not skip or merge. Use short lines so you can fit all questions. Prefer more questions over long text.

Tasks: (1) Infer overall research objectives and overall sample size if stated. (2) Section-wise objectives. (3) For EACH chart/table/finding: one block with survey question, options, and numeric values.

Output exactly this format:

A. Overall Research Objectives
- Geography: (country/region/market inferred from the report; or "Not stated")
- Industry: (sector or vertical; or "Not stated")
- Research scenario: (one line — what is being studied; or "Not stated")
- Overall sample size (n): (integer if report states total respondents anywhere, e.g. 1000; else omit this line)
- Objective 1
- Objective 2

B. Section-wise Objectives
- Section Name: Research Objective

C. Reconstructed Questionnaire
For EVERY question (one block each; be exhaustive):
- Report Reference: (e.g. Figure 4)
- Research Intent: (one line)
- Survey Question: (exact question text)
- Question Type: Single choice / Multiple choice / Likert scale
- Answer Options:
  - Option 1
  - Option 2
- Report Output: (response COUNT only: one integer per option, same order as Answer Options. No percentages, no text. Sum of counts must equal sample size n. Every option must have a number.)
  - 225
  - 150
  - 125
- Sample size (n): (integer for this question if stated; else repeat overall n from A if known)
- Target Segment: (e.g. All respondents)
- Expected Output Pattern: (e.g. Bar chart)

Rules: Plain text only. Report Output must be integers only (counts). No % symbols, no words. Sum of all option counts = n. No blank values. List every question."""

# JSON output schema for cost optimization: predictable structure, server-side validation, cheap repair on failure
REVERSE_ENGINEER_JSON_SYSTEM = """You are a Market Research Methodologist. Reverse-engineer the research design from the report.

Output a single JSON object with exactly these keys (no markdown, no code fence):
- "geography": string or null (country/region/market; null if not inferable)
- "industry": string or null (sector/vertical; null if not inferable)
- "scenario": string or null (one line — study focus; null if not inferable)
- "overall_objectives": array of strings (research objectives)
- "overall_sample_size_n": integer or null (total respondents if stated in report)
- "section_objectives": array of { "section_name": string, "research_objective": string }
- "reconstructed_questionnaire": array of objects, each with:
  "report_reference": string,
  "research_intent": string,
  "survey_question": string,
  "question_type": string (e.g. Single choice),
  "answer_options": array of strings,
  "option_values": array of strings (counts only, e.g. "225", "150"; no %, no blanks; sum = sample_size_n),
  "sample_size_n": integer or null,
  "target_segment": string,
  "expected_output_pattern": string

List EVERY survey question. option_values must be counts only; sum equals sample_size_n. Output valid JSON only."""


class ReverseEngineerRequest(BaseModel):
    report_text: str = Field(..., min_length=50, description="Full text of the market research report")


class AppendChunkRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    chunk_index: int = Field(..., ge=0)
    total_chunks: int = Field(..., ge=1)
    content: str = Field(..., min_length=1)
    is_file_part: bool = False
    filename: Optional[str] = None


class ReverseEngineerSessionRequest(BaseModel):
    session_id: str = Field(..., min_length=1)


class SectionObjective(BaseModel):
    section_name: str
    research_objective: str


class ReconstructedQuestion(BaseModel):
    report_reference: str = ""
    research_intent: str = ""
    survey_question: str = ""
    question_type: str = ""
    answer_options: list[str] = Field(default_factory=list)
    option_values: list[str] = Field(default_factory=list, description="Quantitative values from report per option (e.g. 45%, n=120)")
    sample_size_n: Optional[int] = Field(None, description="Total respondents for this question when report states it; used to compute counts from %")
    target_segment: str = ""
    expected_output_pattern: str = ""


class ReverseEngineerResponse(BaseModel):
    geography: Optional[str] = None
    industry: Optional[str] = None
    scenario: Optional[str] = None
    overall_objectives: list[str] = Field(default_factory=list)
    overall_sample_size_n: Optional[int] = Field(None, description="Total respondents from report when stated once; used to compute counts from %")
    section_objectives: list[SectionObjective] = Field(default_factory=list)
    reconstructed_questionnaire: list[ReconstructedQuestion] = Field(default_factory=list)
    raw_markdown: Optional[str] = None  # Full AI output when using LLM


def _clean_extracted_text(text: str) -> str:
    """Normalize whitespace and remove control characters from extracted PDF/text."""
    if not text or not text.strip():
        return text
    import re
    # Replace multiple spaces/newlines with single newline, then strip each line
    text = re.sub(r"[\r\n]+", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines)


def _extract_text_from_file(content: bytes, filename: str) -> str:
    """Extract plain text from uploaded file. Supports .txt and .pdf (requires PyMuPDF)."""
    if not filename:
        try:
            return _clean_extracted_text(content.decode("utf-8", errors="replace"))
        except Exception:
            raise HTTPException(status_code=400, detail="Could not decode file as text.")
    lower = filename.lower()
    if lower.endswith(".txt"):
        return _clean_extracted_text(content.decode("utf-8", errors="replace"))

    if lower.endswith(".pdf"):
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=content, filetype="pdf")
            parts = []
            for page in doc:
                # "text" mode gives block order; "blocks" can be used for structured extraction
                parts.append(page.get_text("text", sort=True))
            doc.close()
            raw = "\n".join(parts)
            if not raw or len(raw.strip()) < 20:
                raise HTTPException(
                    status_code=400,
                    detail="PDF appears to be image-based or empty. Use a PDF with selectable text, or paste the report text manually.",
                )
            return _clean_extracted_text(raw)
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail="PDF support requires PyMuPDF. Run: pip install pymupdf. Then restart the server. Alternatively, copy-paste the report text into the text box.",
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("PDF extraction failed")
            raise HTTPException(
                status_code=400,
                detail=f"PDF could not be read: {str(e)}. Try pasting the report text manually.",
            )

    # Unknown type: try decode only for likely text files
    if content[:4] in (b"%PDF",):
        raise HTTPException(status_code=400, detail="PDF parsing failed. Install pymupdf (pip install pymupdf) or paste the report text manually.")
    return _clean_extracted_text(content.decode("utf-8", errors="replace"))


def _truncate_report(report_text: str) -> tuple[str, bool]:
    """Return (text to send, was_truncated)."""
    if len(report_text) <= MAX_REPORT_CHARS:
        return report_text, False
    truncated = report_text[:MAX_REPORT_CHARS]
    suffix = f"\n\n[Report truncated to first {MAX_REPORT_CHARS} characters to stay within API rate limits.]"
    return truncated + suffix, True


def _get_primary_models() -> tuple[str, str]:
    """Return (openai_model, anthropic_model) based on TIER. Basic tier uses cheaper models."""
    tier = (getattr(_settings, "TIER", "pro") or os.getenv("TIER", "pro")).lower()
    if tier == "basic":
        return (
            getattr(_settings, "OPENAI_MODEL_BASIC", None) or os.getenv("OPENAI_MODEL_BASIC", "gpt-4o-mini"),
            getattr(_settings, "ANTHROPIC_MODEL_BASIC", None) or os.getenv("ANTHROPIC_MODEL_BASIC", "claude-3-5-haiku-20241022"),
        )
    return (
        _settings.OPENAI_MODEL or os.getenv("OPENAI_MODEL", "gpt-4o"),
        _settings.ANTHROPIC_MODEL or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
    )


def _optional_context_str(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    return s if s else None


def _parse_json_output(raw: str) -> tuple[list[str], Optional[int], list[dict], list[dict], Optional[str], Optional[str], Optional[str]]:
    """Parse LLM JSON into objectives, questionnaire, and geography/industry/scenario. Raises on invalid."""
    import json
    s = (raw or "").strip()
    # Strip markdown code fence if present
    if s.startswith("```"):
        lines = s.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines)
    data = json.loads(s)
    geography = _optional_context_str(data.get("geography"))
    industry = _optional_context_str(data.get("industry"))
    scenario = _optional_context_str(data.get("scenario"))
    overall = list(data.get("overall_objectives") or [])
    if not isinstance(overall, list):
        overall = [str(overall)] if overall else []
    overall = [str(x).strip() for x in overall if x is not None]
    overall_n = data.get("overall_sample_size_n")
    if overall_n is not None and not isinstance(overall_n, int):
        try:
            overall_n = int(overall_n)
        except (TypeError, ValueError):
            overall_n = None
    sections = []
    for sec in data.get("section_objectives") or []:
        if isinstance(sec, dict) and sec.get("section_name") is not None:
            sections.append({
                "section_name": _strip_markdown_bold(str(sec.get("section_name", "")).strip()),
                "research_objective": _strip_markdown_bold(str(sec.get("research_objective", "")).strip()),
            })
    questions = []
    for q in data.get("reconstructed_questionnaire") or []:
        if not isinstance(q, dict):
            continue
        questions.append({
            "report_reference": _strip_markdown_bold(str(q.get("report_reference", "") or "")),
            "research_intent": _strip_markdown_bold(str(q.get("research_intent", "") or "")),
            "survey_question": _strip_markdown_bold(str(q.get("survey_question", "") or "")),
            "question_type": _strip_markdown_bold(str(q.get("question_type", "") or "")),
            "answer_options": [str(o).strip() for o in (q.get("answer_options") or []) if o is not None],
            "option_values": [str(v).strip() for v in (q.get("option_values") or []) if v is not None],
            "sample_size_n": _int_or_none(q.get("sample_size_n")),
            "target_segment": _strip_markdown_bold(str(q.get("target_segment", "") or "")),
                    "expected_output_pattern": _strip_markdown_bold(str(q.get("expected_output_pattern", "") or "")),
        })
    return overall, overall_n, sections, questions, geography, industry, scenario


def _repair_json(raw: str, openai_key: Optional[str] = None, anthropic_key: Optional[str] = None) -> str:
    """Use a small/cheap model to fix invalid JSON. Returns repaired string or re-raises."""
    repair_prompt = """Fix the following so it is valid JSON. Preserve all content; only fix syntax (missing commas, quotes, brackets). Output nothing but the JSON object, no markdown.

Invalid JSON:
"""
    payload = (raw or "")[:15000]
    system_prompt = "Fix invalid JSON syntax only; keep original meaning and fields."
    user_prompt = repair_prompt + payload
    repair_openai = getattr(_settings, "REPAIR_MODEL_OPENAI", None) or os.getenv("REPAIR_MODEL_OPENAI", "gpt-4o-mini")
    repair_anthropic = getattr(_settings, "REPAIR_MODEL_ANTHROPIC", None) or os.getenv("REPAIR_MODEL_ANTHROPIC", "claude-3-5-haiku-20241022")
    if openai_key and (openai_key or "").strip().startswith("sk-"):
        try:
            out = _llm_gateway.complete(
                provider="openai",
                model=repair_openai,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                api_key=openai_key,
                max_tokens=4096,
                temperature=0,
                response_format_json=False,
            )
            if out:
                return out
        except Exception as e:
            logger.warning("JSON repair (OpenAI) failed: %s", e)
    if anthropic_key and (anthropic_key or "").strip().startswith("sk-ant-"):
        try:
            out = _llm_gateway.complete(
                provider="anthropic",
                model=repair_anthropic,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                api_key=anthropic_key,
                max_tokens=4096,
                temperature=0,
                response_format_json=False,
            )
            if out:
                return out
        except Exception as e:
            logger.warning("JSON repair (Anthropic) failed: %s", e)
    raise ValueError("JSON repair failed or no API key available.")


def _call_openai(report_text: str, api_key: Optional[str] = None) -> str:
    """Call OpenAI API with the reverse-engineering prompt. Returns raw markdown."""
    api_key = (api_key or "").strip() or _get_openai_key()
    if not api_key or not api_key.startswith("sk-"):
        raise ValueError("OPENAI_API_KEY not set.")
    report_to_send, _ = _truncate_report(report_text)
    system_prompt = REVERSE_ENGINEER_SYSTEM_PROMPT
    user_prompt = f"Input Report:\n\n{report_to_send}"
    model, _ = _get_primary_models()
    try:
        return _llm_gateway.complete(
            provider="openai",
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            api_key=api_key,
            max_tokens=8192,
            temperature=0.3,
            response_format_json=False,
        )
    except Exception as e:
        err_str = str(e).lower()
        if "429" in err_str or "rate_limit" in err_str or "tokens per min" in err_str:
            raise HTTPException(
                status_code=429,
                detail="Report is too long for the API rate limit (tokens per minute). Shorten the report text (e.g. paste only key sections) or try again in a minute. You can also use a shorter report or split it into parts."
            )
        logger.exception("OpenAI call failed")
        raise HTTPException(status_code=502, detail=f"LLM processing failed: {str(e)}")


def _call_anthropic(report_text: str, api_key: Optional[str] = None) -> str:
    """Call Anthropic (Claude) API with the reverse-engineering prompt. Returns raw markdown."""
    api_key = (api_key or "").strip() or _get_anthropic_key()
    if not api_key or not api_key.startswith("sk-ant-"):
        raise ValueError("ANTHROPIC_API_KEY not set.")
    report_to_send, _ = _truncate_report(report_text)
    system_prompt = REVERSE_ENGINEER_SYSTEM_PROMPT
    user_prompt = f"Input Report:\n\n{report_to_send}"
    _, model = _get_primary_models()
    try:
        return _llm_gateway.complete(
            provider="anthropic",
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            api_key=api_key,
            max_tokens=8192,
            temperature=0.3,
            response_format_json=False,
        )
    except Exception as e:
        err_str = str(e).lower()
        if "429" in err_str or "rate_limit" in err_str or "overloaded" in err_str:
            raise HTTPException(
                status_code=429,
                detail="Report is too long or API is rate-limited. Shorten the report text or try again in a minute."
            )
        logger.exception("Anthropic (Claude) call failed")
        raise HTTPException(status_code=502, detail=f"LLM processing failed: {str(e)}")


def _call_openai_json(report_text: str, api_key: Optional[str] = None) -> str:
    """Call OpenAI requesting JSON output (cost optimization: strict schema, then repair if needed)."""
    api_key = (api_key or "").strip() or _get_openai_key()
    if not api_key or not api_key.startswith("sk-"):
        raise ValueError("OPENAI_API_KEY not set.")
    report_to_send, _ = _truncate_report(report_text)
    system_prompt = REVERSE_ENGINEER_JSON_SYSTEM
    user_prompt = f"Input Report:\n\n{report_to_send}"
    model, _ = _get_primary_models()
    try:
        return _llm_gateway.complete(
            provider="openai",
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            api_key=api_key,
            max_tokens=8192,
            temperature=0.2,
            response_format_json=True,
        )
    except Exception as e:
        err_str = str(e).lower()
        if "429" in err_str or "rate_limit" in err_str:
            raise HTTPException(status_code=429, detail="Report too long or rate limited. Shorten or try again later.")
        logger.exception("OpenAI JSON call failed")
        raise HTTPException(status_code=502, detail=f"LLM processing failed: {str(e)}")


def _call_anthropic_json(report_text: str, api_key: Optional[str] = None) -> str:
    """Call Anthropic requesting JSON output (same schema as OpenAI JSON path)."""
    api_key = (api_key or "").strip() or _get_anthropic_key()
    if not api_key or not api_key.startswith("sk-ant-"):
        raise ValueError("ANTHROPIC_API_KEY not set.")
    report_to_send, _ = _truncate_report(report_text)
    system_prompt = REVERSE_ENGINEER_JSON_SYSTEM + "\n\nOutput only valid JSON, no markdown."
    user_prompt = f"Input Report:\n\n{report_to_send}"
    _, model = _get_primary_models()
    try:
        return _llm_gateway.complete(
            provider="anthropic",
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            api_key=api_key,
            max_tokens=8192,
            temperature=0.2,
            response_format_json=False,
        )
    except Exception as e:
        err_str = str(e).lower()
        if "429" in err_str or "rate_limit" in err_str or "overloaded" in err_str:
            raise HTTPException(status_code=429, detail="Report too long or rate limited. Shorten or try again later.")
        logger.exception("Anthropic JSON call failed")
        raise HTTPException(status_code=502, detail=f"LLM processing failed: {str(e)}")


def _int_or_none(v: Any) -> Optional[int]:
    """Coerce value to int or None."""
    if v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return None


def _strip_markdown_bold(s: str) -> str:
    """Remove markdown ** bold markers from text (e.g. **word** -> word, trailing **)."""
    if not s or not isinstance(s, str):
        return s
    s = s.strip()
    # Replace **content** with content (non-greedy)
    s = re.sub(r"\*\*([^*]*)\*\*", r"\1", s)
    # Remove any remaining stray **
    s = s.replace("**", "").strip()
    return s


def _extract_numeric_from_value(raw: str) -> tuple[Optional[float], bool]:
    """Extract a single number from a string. Returns (number or None, is_percentage). Rejects non-numeric garbage."""
    if not raw or not isinstance(raw, str):
        return None, False
    s = _strip_markdown_bold(raw).strip()
    if ":" in s:
        s = s.split(":", 1)[1].strip()
    # Match integer or decimal, optional % at end; allow leading/trailing whitespace
    m = re.search(r"(\d+(?:\.\d+)?)\s*%?", s)
    if not m:
        return None, False
    try:
        num = float(m.group(1))
        is_pct = "%" in s
        return num, is_pct
    except ValueError:
        return None, False


def _normalize_option_values_to_counts(
    option_values: list[str],
    num_options: int,
    n: Optional[int],
) -> list[str]:
    """
    Ensure option_values are numeric counts only: no %, no blanks, sum <= n.
    - Parse only numbers from each value; if % and n known, convert to count.
    - Pad to num_options with 0; fill single missing as n - sum(others).
    - If sum > n, scale down so total = n.
    Returns list of string integers (counts only).
    """
    if num_options <= 0:
        return []
    counts: list[int] = []
    for v in option_values[:num_options] if option_values else []:
        num, is_pct = _extract_numeric_from_value(str(v) if v else "")
        if num is None:
            counts.append(0)
        elif is_pct and n is not None and n > 0:
            counts.append(round(n * num / 100))
        elif is_pct and (n is None or n <= 0):
            counts.append(0)
        else:
            counts.append(max(0, int(round(num))))
    # Pad to num_options
    while len(counts) < num_options:
        counts.append(0)
    counts = counts[:num_options]
    total = sum(counts)
    if n is not None and n > 0:
        if total > n:
            # Scale down proportionally so sum = n
            if total > 0:
                scale = n / total
                counts = [max(0, int(round(c * scale))) for c in counts]
                # Fix rounding so sum exactly n
                diff = n - sum(counts)
                if diff != 0 and counts:
                    idx = 0
                    while diff > 0 and idx < len(counts):
                        counts[idx] += 1
                        diff -= 1
                        idx += 1
                    while diff < 0 and idx > 0:
                        idx -= 1
                        if counts[idx] > 0:
                            counts[idx] -= 1
                            diff += 1
        elif total < n and counts.count(0) == 1:
            # Single missing: set that option to n - sum(others)
            idx = counts.index(0)
            counts[idx] = n - total
        elif total < n and counts.count(0) > 1:
            # Multiple blanks: put remainder in first zero
            remainder = n - total
            for i in range(len(counts)):
                if remainder <= 0:
                    break
                if counts[i] == 0:
                    counts[i] = min(remainder, n)
                    remainder -= counts[i]
    return [str(c) for c in counts]


def _extract_overall_sample_size(report_text: str) -> Optional[int]:
    """Try to find total sample size from report text (e.g. n=1000, 1,000 respondents)."""
    if not report_text or len(report_text) < 20:
        return None
    # n=1000, n = 1000, N=500, (n=500), sample size 1000, 1,000 respondents, 500 participants
    patterns = [
        r"\bn\s*=\s*([0-9,]+)",
        r"\bN\s*=\s*([0-9,]+)",
        r"\(n\s*=\s*([0-9,]+)\)",
        r"sample\s+size\s+(?:of\s+)?([0-9,]+)",
        r"([0-9,]+)\s+respondents",
        r"([0-9,]+)\s+participants",
        r"total\s+(?:of\s+)?([0-9,]+)\s+(?:respondents|participants|samples)",
    ]
    for pat in patterns:
        m = re.search(pat, report_text[:15000], re.IGNORECASE)
        if m:
            try:
                n = int(m.group(1).replace(",", ""))
                if 10 <= n <= 10000000:
                    return n
            except ValueError:
                continue
    return None


def _split_list_items(text: str) -> list[str]:
    """
    Split list-style text into items by line bullets/newlines while preserving hyphens inside words.
    Examples preserved as single item: "Sugar-free", "Low-fat", "Ready-to-eat".
    """
    if not text:
        return []
    raw = (text or "").strip()
    if not raw:
        return []

    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    items: list[str] = []
    bullet_re = re.compile(r"^\s*(?:[-*•]\s+|\d+[\.\)]\s+)")

    for ln in lines:
        if ln in {"-", "*", "•"}:
            continue
        cleaned = bullet_re.sub("", ln).strip()
        if cleaned and cleaned not in {"-", "*", "•"}:
            items.append(cleaned)

    # Fallback for single-line compact format like: "- A - B - C"
    if len(items) <= 1 and " - " in raw and "\n" not in raw:
        compact = [p.strip() for p in re.split(r"\s+-\s+", raw) if p.strip()]
        compact = [bullet_re.sub("", p).strip() for p in compact if p.strip()]
        if len(compact) > len(items):
            items = compact

    return items


def _parse_structured_output(raw: str) -> tuple[list[str], Optional[int], list[dict], list[dict], Optional[str], Optional[str], Optional[str]]:
    """Parse raw markdown into objectives, questionnaire, and geography/industry/scenario."""
    overall = []
    overall_n: Optional[int] = None
    sections = []
    questions = []
    geography: Optional[str] = None
    industry: Optional[str] = None
    scenario: Optional[str] = None

    # A. Overall Research Objectives (and optional Overall sample size (n):)
    block_a = re.search(r"A\.\s*Overall Research Objectives\s*(.*?)(?=B\.|$)", raw, re.DOTALL | re.IGNORECASE)
    if block_a:
        text = block_a.group(1).strip()
        for line in text.split("\n"):
            line = line.strip()
            if re.match(r"^-\s*Overall sample size\s*\(n\):\s*(\d+)", line, re.IGNORECASE):
                try:
                    overall_n = int(re.search(r"(\d+)", line).group(1))
                except (ValueError, AttributeError):
                    pass
            elif re.match(r"^-\s*Geography:\s*(.+)$", line, re.IGNORECASE):
                geography = _strip_markdown_bold(re.sub(r"^-\s*Geography:\s*", "", line, flags=re.IGNORECASE).strip())
                geography = geography or None
            elif re.match(r"^-\s*Industry:\s*(.+)$", line, re.IGNORECASE):
                industry = _strip_markdown_bold(re.sub(r"^-\s*Industry:\s*", "", line, flags=re.IGNORECASE).strip())
                industry = industry or None
            elif re.match(r"^-\s*Research scenario:\s*(.+)$", line, re.IGNORECASE):
                scenario = _strip_markdown_bold(re.sub(r"^-\s*Research scenario:\s*", "", line, flags=re.IGNORECASE).strip())
                scenario = scenario or None
            elif line.startswith("-") and len(line) > 2 and "Overall sample size" not in line:
                rest = line[1:].strip()
                if not re.match(r"^(Geography|Industry|Research scenario):", rest, re.I):
                    overall.append(rest)

    # B. Section-wise Objectives
    block_b = re.search(r"B\.\s*Section-wise Objectives\s*(.*?)(?=C\.|$)", raw, re.DOTALL | re.IGNORECASE)
    if block_b:
        text = block_b.group(1).strip()
        current_section = None
        current_obj = None
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("-") and ":" in line:
                parts = line[1:].strip().split(":", 1)
                if len(parts) == 2:
                    current_section = parts[0].strip()
                    current_obj = parts[1].strip()
                    if current_section and current_obj:
                        sections.append({"section_name": current_section, "research_objective": current_obj})

    # C. Reconstructed Questionnaire - split by question blocks
    block_c = re.search(r"C\.\s*Reconstructed Questionnaire\s*(.*)$", raw, re.DOTALL | re.IGNORECASE)
    if block_c:
        text = block_c.group(1).strip()
        blocks = re.split(r"\n(?=- Report Reference:|- Research Intent:)", text)
        for blk in blocks:
            blk = blk.strip()
            if not blk or len(blk) < 20:
                continue
            q = {}
            for key, pattern in [
                ("report_reference", r"Report Reference:\s*(.*?)(?=Research Intent:|$)"),
                ("research_intent", r"Research Intent:\s*(.*?)(?=Survey Question:|$)"),
                ("survey_question", r"Survey Question:\s*(.*?)(?=Question Type:|$)"),
                ("question_type", r"Question Type:\s*(.*?)(?=Answer Options:|$)"),
                ("answer_options", r"Answer Options:\s*(.*?)(?=Report Output:|Target Segment:|Expected Output|$)"),
                ("option_values", r"Report Output:\s*(.*?)(?=Sample size|Target Segment:|Expected Output|-\s*Report Reference:|\Z)"),
                ("sample_size_n", r"Sample size\s*\(n\):\s*(\d+)"),
                ("target_segment", r"Target Segment:\s*(.*?)(?=Expected Output|$)"),
                ("expected_output_pattern", r"Expected Output Pattern:\s*(.*?)(?=Report Output:|-\s*Report Reference:|\Z)"),
            ]:
                m = re.search(pattern, blk, re.IGNORECASE | re.DOTALL)
                if m:
                    val = m.group(1).strip()
                    if key == "answer_options":
                        opts = [_strip_markdown_bold(o.strip()) for o in _split_list_items(val) if o.strip() and o.strip() != "Option"]
                        q[key] = [o for o in opts if o]
                    elif key == "option_values":
                        # Parse lines: extract only numeric values (number or number%); reject text/garbage
                        lines = [ln.strip() for ln in _split_list_items(val) if ln.strip()]
                        values = []
                        for ln in lines:
                            num, is_pct = _extract_numeric_from_value(ln)
                            if num is not None:
                                values.append(f"{num}%" if is_pct else str(int(round(num))))
                        q[key] = values
                    elif key == "sample_size_n":
                        try:
                            q[key] = int(val.strip()) if val.strip() else None
                        except ValueError:
                            q[key] = None
                    else:
                        q[key] = _strip_markdown_bold(val)
            if q.get("survey_question") or q.get("research_intent"):
                questions.append({
                    "report_reference": _strip_markdown_bold(q.get("report_reference", "")),
                    "research_intent": _strip_markdown_bold(q.get("research_intent", "")),
                    "survey_question": _strip_markdown_bold(q.get("survey_question", "")),
                    "question_type": _strip_markdown_bold(q.get("question_type", "")),
                    "answer_options": q.get("answer_options", []),
                    "option_values": q.get("option_values", []),
                    "sample_size_n": q.get("sample_size_n"),
                    "target_segment": _strip_markdown_bold(q.get("target_segment", "")),
                    "expected_output_pattern": _strip_markdown_bold(q.get("expected_output_pattern", "")),
                })

    return overall, overall_n, sections, questions, geography, industry, scenario


def _heuristic_reverse_engineer(report_text: str) -> tuple[list[str], list[dict], list[dict], str]:
    """Fallback: build a minimal structured output from report text when no LLM."""
    overall = [
        "Infer overall research objectives from the report executive summary and key findings.",
        "Align section-wise objectives with each major heading or chart section.",
    ]
    sections = []
    questions = []

    # Simple section detection
    lines = report_text.split("\n")
    current_section = None
    for line in lines:
        stripped = line.strip()
        if len(stripped) > 10 and (stripped.isupper() or (len(stripped) < 80 and not stripped.startswith("-"))):
            if "executive" in stripped.lower() or "summary" in stripped.lower() or "introduction" in stripped.lower():
                current_section = stripped
                sections.append({"section_name": current_section, "research_objective": "Understand high-level findings and context."})
            if "figure" in stripped.lower() or "chart" in stripped.lower() or "%" in stripped:
                current_section = stripped[:80]
                sections.append({"section_name": current_section, "research_objective": "Derive survey question that would produce the reported metric."})

    # One placeholder question
    questions.append({
        "report_reference": "Report content (upload full report for AI-powered reconstruction)",
        "research_intent": "Reverse-engineer the survey question that would yield the reported percentages and insights.",
        "survey_question": "Upload the report and set OPENAI_API_KEY for full questionnaire reconstruction.",
        "question_type": "Single choice / Multiple choice / Likert scale (inferred by AI)",
        "answer_options": ["Option 1", "Option 2", "..."],
        "option_values": [],
        "sample_size_n": None,
        "target_segment": "All respondents / Urban / Rest of India / Gen Z / etc.",
        "expected_output_pattern": "Bar chart, pie chart, or insight table matching report.",
    })

    raw = """A. Overall Research Objectives
- Infer overall research objectives from the report.
- Align section-wise objectives with each major section.

B. Section-wise Objectives
- See parsed sections above.

C. Reconstructed Questionnaire
Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env and re-run to get AI-generated questionnaire from your report.
"""
    return overall, sections, questions, raw


def _run_reverse_engineer(
    text: str,
    openai_key: Optional[str] = None,
    anthropic_key: Optional[str] = None,
    use_cache: bool = True,
) -> dict:
    """Core logic: take report text, return structured output. Uses OpenAI first by default. When use_cache=False (chunked flow), skips cache."""
    if use_cache:
        norm_text = (text or "").strip()[:MAX_REPORT_CHARS]
        cache_key = hashlib.sha256(norm_text.encode("utf-8")).hexdigest()
        if cache_key in _reverse_engineer_cache:
            return _reverse_engineer_cache[cache_key]
    else:
        cache_key = None

    raw_md = None
    ai_used = False
    geography: Optional[str] = None
    industry: Optional[str] = None
    scenario: Optional[str] = None
    no_key_message = (
        "No API key. Set OPENAI_API_KEY or ANTHROPIC_API_KEY in your .env file (see .env.example) "
        "and restart the server to get AI-powered questionnaire reconstruction from your report."
    )
    use_json = getattr(_settings, "USE_JSON_OUTPUT", False) or (os.getenv("USE_JSON_OUTPUT", "false").lower() in ("1", "true", "yes"))
    openai_first = getattr(_settings, "OPENAI_FIRST", True) or (os.getenv("OPENAI_FIRST", "true").lower() in ("1", "true", "yes"))
    if use_json:
        json_providers = [
            ("OpenAI", _call_openai_json, openai_key),
            ("Anthropic", _call_anthropic_json, anthropic_key),
        ] if openai_first else [
            ("Anthropic", _call_anthropic_json, anthropic_key),
            ("OpenAI", _call_openai_json, openai_key),
        ]
        for name, call_llm, key in json_providers:
            try:
                raw_md = call_llm(text, api_key=key)
                if raw_md and len(raw_md.strip()) > 0:
                    try:
                        overall, overall_n, section_objs, questionnaire, geography, industry, scenario = _parse_json_output(
                            raw_md
                        )
                        ai_used = True
                        break
                    except Exception as json_err:
                        logger.debug("JSON parse failed, trying repair: %s", json_err)
                        try:
                            repaired = _repair_json(raw_md, openai_key=openai_key, anthropic_key=anthropic_key)
                            overall, overall_n, section_objs, questionnaire, geography, industry, scenario = _parse_json_output(
                                repaired
                            )
                            ai_used = True
                            break
                        except Exception:
                            pass
                        try:
                            overall, overall_n, section_objs, questionnaire, geography, industry, scenario = _parse_structured_output(
                                raw_md
                            )
                            ai_used = True
                            break
                        except Exception:
                            logger.warning("JSON and markdown parse failed for %s, trying next provider", name)
            except ValueError:
                continue
            except HTTPException:
                raise
    if not ai_used:
        providers = [
            ("OpenAI", _call_openai, openai_key),
            ("Anthropic", _call_anthropic, anthropic_key),
        ] if openai_first else [
            ("Anthropic", _call_anthropic, anthropic_key),
            ("OpenAI", _call_openai, openai_key),
        ]
        for name, call_llm, key in providers:
            try:
                raw_md = call_llm(text, api_key=key)
                if raw_md and len(raw_md.strip()) > 0:
                    try:
                        overall, overall_n, section_objs, questionnaire, geography, industry, scenario = _parse_structured_output(
                            raw_md
                        )
                    except Exception as parse_err:
                        logger.warning("Parse of %s output failed, using fallback structure: %s", name, parse_err)
                        h_overall, h_sections, h_questions, _ = _heuristic_reverse_engineer(text)
                        overall, overall_n, section_objs, questionnaire = [], None, h_sections, h_questions
                        geography = industry = scenario = None
                    ai_used = True
                    break
            except ValueError as e:
                logger.debug("No %s key or key invalid: %s", name, e)
                continue
            except HTTPException:
                raise
    if not ai_used:
        logger.info(
            "Market Research: no API key used (both providers raised ValueError). openai_key_provided=%s anthropic_key_provided=%s",
            bool(openai_key and openai_key.strip().startswith("sk-")),
            bool(anthropic_key and anthropic_key.strip().startswith("sk-ant-")),
        )
        overall, section_objs, questionnaire, raw_md = _heuristic_reverse_engineer(text)
        overall_n = None
    # Use overall n from parser, or extract from report text when LLM didn't return it
    if overall_n is None and text:
        overall_n = _extract_overall_sample_size(text)
    # Fill per-question sample_size_n when missing but we have overall n and question has % values
    _pct_re = re.compile(r"^\s*\d+(?:\.\d+)?\s*%\s*$")
    for q in questionnaire:
        if q.get("sample_size_n") is None and overall_n is not None:
            vals = q.get("option_values") or []
            if vals and any(_pct_re.match(str(v).strip()) for v in vals):
                q["sample_size_n"] = overall_n
    # Normalize option_values: counts only, no blanks, sum <= n, no text/%
    num_opts_key = "answer_options"
    for q in questionnaire:
        opts = q.get(num_opts_key) or []
        n_q = q.get("sample_size_n") or overall_n
        q["option_values"] = _normalize_option_values_to_counts(
            q.get("option_values") or [], len(opts), n_q
        )
    section_objectives = [SectionObjective(section_name=s["section_name"], research_objective=s["research_objective"]) for s in section_objs]
    reconstructed = [ReconstructedQuestion(**q) for q in questionnaire]
    result = {
        "geography": geography,
        "industry": industry,
        "scenario": scenario,
        "overall_objectives": overall,
        "overall_sample_size_n": overall_n,
        "section_objectives": [s.model_dump() for s in section_objectives],
        "reconstructed_questionnaire": [q.model_dump() for q in reconstructed],
        "raw_markdown": raw_md,
        "ai_used": ai_used,
        "message": None if ai_used else no_key_message,
    }
    if use_cache and cache_key is not None:
        if len(_reverse_engineer_cache) >= REVERSE_ENGINEER_CACHE_MAX:
            _reverse_engineer_cache.pop(next(iter(_reverse_engineer_cache)))
        _reverse_engineer_cache[cache_key] = result
    return result


def _split_into_chunks(text: str, chunk_size: int = MAX_REPORT_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks for chunked LLM processing."""
    text = (text or "").strip()
    if len(text) <= chunk_size:
        return [text] if text else []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start = end - overlap
        if start >= len(text):
            break
    return chunks


def _payload_for_db(result: dict) -> dict:
    """Copy of reverse-engineer API payload; truncate huge raw_markdown for DB."""
    out = {k: v for k, v in result.items() if k not in ("extraction_id", "persisted_at")}
    raw = out.get("raw_markdown")
    if isinstance(raw, str) and len(raw) > _MAX_RAW_MARKDOWN_PERSIST:
        out["raw_markdown"] = (
            raw[:_MAX_RAW_MARKDOWN_PERSIST]
            + "\n\n[Truncated for storage. Run reverse-engineer again for full raw output in memory.]"
        )
    return sanitize_for_json(out)


def _persist_market_research_result(db: Session, result: dict) -> Optional[str]:
    """
    Persist full extraction (objectives, questionnaire, geography/industry/scenario, flags).
    Always inserts a new row per run so history is kept; latest is loaded by GET /latest-extraction.
    """
    payload = _payload_for_db(result)
    geo = payload.get("geography")
    ind = payload.get("industry")
    scen = payload.get("scenario")
    row = MarketResearchExtraction(
        geography=(str(geo)[:512] if geo else None),
        industry=(str(ind)[:200] if ind else None),
        scenario=(str(scen)[:8000] if scen else None),
        result_data=payload,
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    except Exception as e:
        logger.warning("Persist market research extraction failed: %s", e)
        db.rollback()
        return None


def _merge_extraction_row_to_response(row: MarketResearchExtraction) -> dict:
    base = row.result_data if isinstance(row.result_data, dict) else {}
    out = dict(base)
    out["geography"] = row.geography or out.get("geography")
    out["industry"] = row.industry or out.get("industry")
    out["scenario"] = row.scenario or out.get("scenario")
    out["extraction_id"] = row.id
    out["persisted_at"] = row.created_at.isoformat() if row.created_at else None
    return sanitize_for_json(out)


def _first_non_empty_context(results: list[dict], key: str) -> Optional[str]:
    for r in results:
        v = r.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def _merge_chunk_results(results: list[dict]) -> dict:
    """Merge multiple _run_reverse_engineer results into one (dedupe objectives/sections/questions)."""
    if not results:
        return {
            "geography": None,
            "industry": None,
            "scenario": None,
            "overall_objectives": [],
            "overall_sample_size_n": None,
            "section_objectives": [],
            "reconstructed_questionnaire": [],
            "raw_markdown": "",
            "ai_used": False,
            "message": None,
        }
    if len(results) == 1:
        return results[0]
    seen_overall = set()
    overall = []
    for r in results:
        for o in r.get("overall_objectives") or []:
            k = (o or "").strip().lower()[:200]
            if k and k not in seen_overall:
                seen_overall.add(k)
                overall.append(o)
    seen_section = set()
    sections = []
    for r in results:
        for s in r.get("section_objectives") or []:
            name = (s.get("section_name") or "").strip()
            if name and name not in seen_section:
                seen_section.add(name)
                sections.append(s)
    # Dedupe by report_reference + survey_question so we keep all distinct questions (different ref or different text)
    seen_question = set()
    questions = []
    for r in results:
        for q in r.get("reconstructed_questionnaire") or []:
            ref = (q.get("report_reference") or "").strip()[:100]
            sq = (q.get("survey_question") or "").strip()
            key = (ref + "\n" + sq).lower()[:500]
            if key and key not in seen_question:
                seen_question.add(key)
                questions.append(q)
    raw_parts = [r.get("raw_markdown") or "" for r in results if r.get("raw_markdown")]
    ai_used = any(r.get("ai_used") for r in results)
    raw_merged = "\n\n".join(f"--- Part {i+1} ---\n\n{p}" for i, p in enumerate(raw_parts)) if raw_parts else ""
    overall_n = next((r.get("overall_sample_size_n") for r in results if r.get("overall_sample_size_n") is not None), None)
    return {
        "geography": _first_non_empty_context(results, "geography"),
        "industry": _first_non_empty_context(results, "industry"),
        "scenario": _first_non_empty_context(results, "scenario"),
        "overall_objectives": overall,
        "overall_sample_size_n": overall_n,
        "section_objectives": sections,
        "reconstructed_questionnaire": questions,
        "raw_markdown": raw_merged,
        "ai_used": ai_used,
        "message": None if ai_used else (results[0].get("message") or None),
    }


def _run_reverse_engineer_maybe_chunked(
    text: str,
    openai_key: Optional[str] = None,
    anthropic_key: Optional[str] = None,
) -> dict:
    """Run reverse engineer on full text; if text exceeds MAX_REPORT_CHARS, process in chunks and merge."""
    text = (text or "").strip()
    if not text or len(text) < 50:
        return _run_reverse_engineer("", openai_key=openai_key, anthropic_key=anthropic_key, use_cache=False)
    if len(text) <= MAX_REPORT_CHARS:
        return _run_reverse_engineer(text, openai_key=openai_key, anthropic_key=anthropic_key)
    chunks = _split_into_chunks(text)
    if not chunks:
        return _run_reverse_engineer(text[:MAX_REPORT_CHARS], openai_key=openai_key, anthropic_key=anthropic_key)
    logger.info("Processing report in %d chunks (total %d chars)", len(chunks), len(text))
    results = []
    for i, chunk in enumerate(chunks):
        try:
            r = _run_reverse_engineer(chunk, openai_key=openai_key, anthropic_key=anthropic_key, use_cache=False)
            results.append(r)
        except Exception as e:
            logger.warning("Chunk %s failed: %s", i + 1, e)
            results.append({
                "geography": None,
                "industry": None,
                "scenario": None,
                "overall_objectives": [],
                "overall_sample_size_n": None,
                "section_objectives": [],
                "reconstructed_questionnaire": [],
                "raw_markdown": "",
                "ai_used": False,
                "message": str(e),
            })
    return _merge_chunk_results(results)


@router.get("/latest-extraction")
async def get_latest_market_research_extraction(db: Session = Depends(get_db)):
    """
    Return the most recently persisted reverse-engineer result for the UI (same shape as POST reverse-engineer).
    """
    row = (
        db.query(MarketResearchExtraction)
        .order_by(MarketResearchExtraction.created_at.desc())
        .first()
    )
    if not row:
        return {"has_extraction": False}
    return {"has_extraction": True, "data": _merge_extraction_row_to_response(row)}


@router.get("/ai-status")
async def ai_status():
    """Return provider config + runtime optimization status (cache, budget, throttling)."""
    openai_first = getattr(_settings, "OPENAI_FIRST", True) or (os.getenv("OPENAI_FIRST", "true").lower() in ("1", "true", "yes"))
    return {
        "openai_configured": _get_openai_key() is not None,
        "anthropic_configured": _get_anthropic_key() is not None,
        "openai_first": openai_first,
        "cache_size": len(_reverse_engineer_cache),
        "deterministic_cache_enabled": True,
        "near_duplicate_cache": bool(getattr(_settings, "LLM_ALLOW_NEAR_DUPLICATE_CACHE", True)),
        "daily_budget_tokens_max": int(getattr(_settings, "LLM_DAILY_TOKEN_BUDGET", 50_000_000)),
        "daily_budget_tokens_used": _llm_gateway.budget.used_tokens,
        "max_concurrent_heavy_calls": int(getattr(_settings, "LLM_MAX_CONCURRENT_HEAVY_CALLS", 3)),
        "env_paths_checked": _env_paths,
        "env_file_exists": any(os.path.isfile(p) for p in _env_paths),
    }


@router.post("/reverse-engineer")
async def reverse_engineer_report(
    report_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """
    Reverse-engineer the original research design from a market research report.
    Provide either report_text (plain text) or upload a file (.txt or .pdf).
    """
    text = (report_text or "").strip()
    if file and file.filename:
        content = await file.read()
        text = _extract_text_from_file(content, file.filename)
    if not text or len(text) < 50:
        raise HTTPException(status_code=400, detail="Provide report_text (min 50 chars) or upload a .txt/.pdf file.")
    openai_key = _get_openai_key()
    anthropic_key = _get_anthropic_key()
    result = _run_reverse_engineer_maybe_chunked(text, openai_key=openai_key, anthropic_key=anthropic_key)
    eid = _persist_market_research_result(db, result)
    out = dict(result)
    if eid:
        out["extraction_id"] = eid
    return out


@router.post("/reverse-engineer/json")
async def reverse_engineer_json(body: ReverseEngineerRequest, db: Session = Depends(get_db)):
    """Same as reverse-engineer but accepts JSON body with report_text. No length limit; long reports are processed in chunks."""
    openai_key = _get_openai_key()
    anthropic_key = _get_anthropic_key()
    result = _run_reverse_engineer_maybe_chunked(
        body.report_text.strip(), openai_key=openai_key, anthropic_key=anthropic_key
    )
    eid = _persist_market_research_result(db, result)
    out = dict(result)
    if eid:
        out["extraction_id"] = eid
    return out


def _evict_upload_sessions():
    """Remove expired sessions from chunk store."""
    now = time.time()
    expired = [sid for sid, data in _upload_chunks_store.items() if (now - data.get("created_at", 0)) > UPLOAD_CHUNKS_TTL_SEC]
    for sid in expired:
        _upload_chunks_store.pop(sid, None)
    while len(_upload_chunks_store) > UPLOAD_CHUNKS_MAX_SESSIONS:
        _upload_chunks_store.pop(next(iter(_upload_chunks_store)))


@router.post("/append-chunk")
async def append_chunk(body: AppendChunkRequest):
    """Upload one chunk of a long report (for chunked upload). Call reverse-engineer-session when complete."""
    _evict_upload_sessions()
    sid = body.session_id
    if sid not in _upload_chunks_store:
        _upload_chunks_store[sid] = {
            "chunks": {},
            "total_chunks": body.total_chunks,
            "created_at": time.time(),
            "is_file": bool(body.is_file_part),
            "filename": body.filename if body.is_file_part else None,
        }
    store = _upload_chunks_store[sid]
    if store["total_chunks"] != body.total_chunks:
        raise HTTPException(status_code=400, detail="total_chunks mismatch for this session")
    if body.is_file_part and body.filename:
        store["filename"] = body.filename
    store["chunks"][body.chunk_index] = body.content
    received = len(store["chunks"])
    complete = received == body.total_chunks
    return {"session_id": sid, "received": received, "total": body.total_chunks, "complete": complete}


@router.post("/reverse-engineer-session")
async def reverse_engineer_session(body: ReverseEngineerSessionRequest, db: Session = Depends(get_db)):
    """Run reverse-engineer on the report assembled from append-chunk uploads. No length limit; processed in chunks if long."""
    _evict_upload_sessions()
    sid = body.session_id
    if sid not in _upload_chunks_store:
        raise HTTPException(status_code=404, detail="Session not found or expired. Upload chunks first.")
    store = _upload_chunks_store[sid]
    total = store["total_chunks"]
    chunks = store["chunks"]
    if len(chunks) != total:
        raise HTTPException(status_code=400, detail=f"Missing chunks: have {len(chunks)}, need {total}. Send all chunks first.")
    parts = [chunks[i] for i in range(total)]
    _upload_chunks_store.pop(sid, None)

    if store.get("is_file") and store.get("filename"):
        try:
            assembled = b"".join(base64.b64decode(p) for p in parts)
            full_text = _extract_text_from_file(assembled, store["filename"]).strip()
        except Exception as e:
            logger.exception("Assemble/decode file chunks failed")
            raise HTTPException(status_code=400, detail=f"File assembly or extraction failed: {e}")
    else:
        full_text = "".join(parts).strip()

    if len(full_text) < 50:
        raise HTTPException(status_code=400, detail="Assembled report has fewer than 50 characters.")
    openai_key = _get_openai_key()
    anthropic_key = _get_anthropic_key()
    result = _run_reverse_engineer_maybe_chunked(full_text, openai_key=openai_key, anthropic_key=anthropic_key)
    eid = _persist_market_research_result(db, result)
    out = dict(result)
    if eid:
        out["extraction_id"] = eid
    return out


# Sample PDF for testing: place a file named "sample_market_research_report.pdf" in project root
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SAMPLE_PDF_PATH = os.path.join(_PROJECT_ROOT, "sample_market_research_report.pdf")


@router.get("/sample-pdf-text")
async def get_sample_pdf_text():
    """
    For testing: extract text from sample_market_research_report.pdf in project root.
    Place your test PDF there and call this to prefill the report text.
    """
    if not os.path.isfile(_SAMPLE_PDF_PATH):
        raise HTTPException(
            status_code=404,
            detail=f"Sample PDF not found. Place a file named 'sample_market_research_report.pdf' in the project root: {_PROJECT_ROOT}",
        )
    try:
        with open(_SAMPLE_PDF_PATH, "rb") as f:
            content = f.read()
        text = _extract_text_from_file(content, "sample_market_research_report.pdf")
        if not text or len(text.strip()) < 50:
            raise HTTPException(status_code=400, detail="Sample PDF has no extractable text (image-only or empty).")
        return {"report_text": text, "source": "sample_market_research_report.pdf"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Sample PDF read failed")
        raise HTTPException(status_code=500, detail=str(e))
