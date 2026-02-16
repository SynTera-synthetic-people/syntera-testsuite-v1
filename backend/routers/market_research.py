"""Market Research Reverse Engineering - Infer research design from report content."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional
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

from config.settings import Settings

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
- Report Output: (numeric values from report: prefer counts e.g. 225, or if only % given use e.g. 45% and we will compute count from n)
  - 225
  - 150
  - 125
- Sample size (n): (integer for this question if stated; else repeat overall n from A if known)
- Target Segment: (e.g. All respondents)
- Expected Output Pattern: (e.g. Bar chart)

Rules: Plain text only. Output numeric counts when the report gives them; if only % is given, output the % and include Sample size (n). List every question."""


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


def _call_openai(report_text: str, api_key: Optional[str] = None) -> str:
    """Call OpenAI API with the reverse-engineering prompt. Returns raw markdown."""
    api_key = (api_key or "").strip() or _get_openai_key()
    if not api_key or not api_key.startswith("sk-"):
        raise ValueError("OPENAI_API_KEY not set.")
    report_to_send, _ = _truncate_report(report_text)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        model = _settings.OPENAI_MODEL or os.getenv("OPENAI_MODEL", "gpt-4o")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": REVERSE_ENGINEER_SYSTEM_PROMPT},
                {"role": "user", "content": f"Input Report:\n\n{report_to_send}"}
            ],
            temperature=0.3,
            max_tokens=8192,
        )
        content = response.choices[0].message.content if response.choices else None
        if isinstance(content, list):
            content = " ".join(
                (p.get("text") if isinstance(p, dict) else str(p) for p in content if p)
            )
        return (content or "").strip()
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
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        model = _settings.ANTHROPIC_MODEL or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        response = client.messages.create(
            model=model,
            max_tokens=8192,
            system=REVERSE_ENGINEER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Input Report:\n\n{report_to_send}"}],
        )
        if response.content:
            parts = []
            for block in response.content:
                text = getattr(block, "text", None) or (block.get("text") if isinstance(block, dict) else None)
                if text:
                    parts.append(str(text).strip())
            if parts:
                return "\n\n".join(parts)
        return ""
    except Exception as e:
        err_str = str(e).lower()
        if "429" in err_str or "rate_limit" in err_str or "overloaded" in err_str:
            raise HTTPException(
                status_code=429,
                detail="Report is too long or API is rate-limited. Shorten the report text or try again in a minute."
            )
        logger.exception("Anthropic (Claude) call failed")
        raise HTTPException(status_code=502, detail=f"LLM processing failed: {str(e)}")


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


def _parse_structured_output(raw: str) -> tuple[list[str], Optional[int], list[dict], list[dict]]:
    """Parse raw markdown into overall_objectives, overall_sample_size_n, section_objectives, reconstructed_questionnaire."""
    overall = []
    overall_n: Optional[int] = None
    sections = []
    questions = []

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
            elif line.startswith("-") and len(line) > 2 and "Overall sample size" not in line:
                overall.append(line[1:].strip())

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
                        opts = [_strip_markdown_bold(o.strip()) for o in re.split(r"[\n-]", val) if o.strip() and o.strip() != "Option"]
                        q[key] = [o for o in opts if o]
                    elif key == "option_values":
                        # Parse lines like "45%" or "- 45%" or "Option A: 45%" -> take the value part
                        lines = [ln.strip() for ln in re.split(r"[\n-]", val) if ln.strip()]
                        values = []
                        for ln in lines:
                            ln = _strip_markdown_bold(ln)
                            if ":" in ln:
                                ln = ln.split(":", 1)[1].strip()
                            if ln:
                                values.append(ln)
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

    return overall, overall_n, sections, questions


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
    no_key_message = (
        "No API key. Set OPENAI_API_KEY or ANTHROPIC_API_KEY in your .env file (see .env.example) "
        "and restart the server to get AI-powered questionnaire reconstruction from your report."
    )
    openai_first = getattr(_settings, "OPENAI_FIRST", True) or (os.getenv("OPENAI_FIRST", "true").lower() in ("1", "true", "yes"))
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
                    overall, overall_n, section_objs, questionnaire = _parse_structured_output(raw_md)
                except Exception as parse_err:
                    logger.warning("Parse of %s output failed, using fallback structure: %s", name, parse_err)
                    h_overall, h_sections, h_questions, _ = _heuristic_reverse_engineer(text)
                    overall, overall_n, section_objs, questionnaire = [], None, h_sections, h_questions
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
    section_objectives = [SectionObjective(section_name=s["section_name"], research_objective=s["research_objective"]) for s in section_objs]
    reconstructed = [ReconstructedQuestion(**q) for q in questionnaire]
    result = {
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


def _merge_chunk_results(results: list[dict]) -> dict:
    """Merge multiple _run_reverse_engineer results into one (dedupe objectives/sections/questions)."""
    if not results:
        return {
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
                "overall_objectives": [],
                "section_objectives": [],
                "reconstructed_questionnaire": [],
                "raw_markdown": "",
                "ai_used": False,
                "message": str(e),
            })
    return _merge_chunk_results(results)


@router.get("/ai-status")
async def ai_status():
    """Return whether OpenAI or Anthropic API keys are configured; provider order and cache size."""
    openai_first = getattr(_settings, "OPENAI_FIRST", True) or (os.getenv("OPENAI_FIRST", "true").lower() in ("1", "true", "yes"))
    return {
        "openai_configured": _get_openai_key() is not None,
        "anthropic_configured": _get_anthropic_key() is not None,
        "openai_first": openai_first,
        "cache_size": len(_reverse_engineer_cache),
        "env_paths_checked": _env_paths,
        "env_file_exists": any(os.path.isfile(p) for p in _env_paths),
    }


@router.post("/reverse-engineer")
async def reverse_engineer_report(
    report_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
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
    return _run_reverse_engineer_maybe_chunked(text, openai_key=openai_key, anthropic_key=anthropic_key)


@router.post("/reverse-engineer/json")
async def reverse_engineer_json(body: ReverseEngineerRequest):
    """Same as reverse-engineer but accepts JSON body with report_text. No length limit; long reports are processed in chunks."""
    openai_key = _get_openai_key()
    anthropic_key = _get_anthropic_key()
    return _run_reverse_engineer_maybe_chunked(body.report_text.strip(), openai_key=openai_key, anthropic_key=anthropic_key)


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
async def reverse_engineer_session(body: ReverseEngineerSessionRequest):
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
    return _run_reverse_engineer_maybe_chunked(full_text, openai_key=openai_key, anthropic_key=anthropic_key)


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
