"""Market Research Reverse Engineering - Infer research design from report content."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional
import logging
import os
import re

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

# Keep total request under provider TPM (e.g. OpenAI 30k). System prompt ~2k tokens; reserve for response.
# ~4 chars/token → cap report at ~22k tokens (~88k chars). Use 70k to be safe.
MAX_REPORT_CHARS = 70_000


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

REVERSE_ENGINEER_SYSTEM_PROMPT = """You are a senior Market Research Methodologist and Survey Designer.

You are given a market research report that contains:
- Executive summaries
- Charts and figures with percentages
- Category-wise insights
- Consumer quotes
- Key findings and recommendations

Your task is to reverse-engineer the *original research design* behind the report.

From the report content, you must:

1. Infer the **overall research objective(s)** of the study.
2. Derive **section-wise research objectives** (e.g., motivation, platform preference, payment behavior, category behavior, trust, influencers, etc.).
3. For each chart, insight, or quantitative finding:
   - Identify the **latent research question** that must have been asked.
   - Reconstruct the **exact survey question** in natural market-research language.
   - Provide the **most likely answer options** (MCQ / Likert / multi-select) that could produce the reported outputs.
4. Maintain:
   - Neutral, professional survey tone
   - Clear segmentation logic (Urban vs Rest of India, Gen Z, Millennials, Gen X, etc.)
   - Consistency with the percentages and comparisons shown in the report

Output in the following structured format:

A. Overall Research Objectives
- Objective 1
- Objective 2
- ...

B. Section-wise Objectives
For each section in the report:
- Section Name
- Research Objective

C. Reconstructed Questionnaire

For each inferred question:

- Report Reference:
  (e.g., "Figure 4: Factors leading to stickiness", Page 11)

- Research Intent:
  (What the researchers wanted to understand)

- Survey Question:
  (Exact question as it would appear in a survey)

- Question Type:
  (Single choice / Multiple choice / Likert scale / Ranking)

- Answer Options:
  - Option 1
  - Option 2
  - Option 3
  - ...

- Target Segment:
  (All respondents / Urban / Rest of India / Gen Z / etc.)

- Expected Output Pattern:
  (What kind of chart or insight this question would generate)

Rules:
- Use plain text only for Survey Question and Answer Options (no markdown: no ** for bold).
- Do NOT copy sentences from the report as questions.
- Convert insights and charts into *original survey questions*.
- Ensure that each reconstructed question logically explains the reported percentages.
- Where multiple charts stem from the same construct (e.g., trust, value, convenience), group them under a common research theme.
- If qualitative quotes exist, infer the *open-ended* question that could have generated them.
"""


class ReverseEngineerRequest(BaseModel):
    report_text: str = Field(..., min_length=50, description="Full text of the market research report")


class SectionObjective(BaseModel):
    section_name: str
    research_objective: str


class ReconstructedQuestion(BaseModel):
    report_reference: str = ""
    research_intent: str = ""
    survey_question: str = ""
    question_type: str = ""
    answer_options: list[str] = Field(default_factory=list)
    target_segment: str = ""
    expected_output_pattern: str = ""


class ReverseEngineerResponse(BaseModel):
    overall_objectives: list[str] = Field(default_factory=list)
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
            max_tokens=4096,
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
            max_tokens=4096,
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


def _parse_structured_output(raw: str) -> tuple[list[str], list[dict], list[dict]]:
    """Parse raw markdown into overall_objectives, section_objectives, reconstructed_questionnaire."""
    overall = []
    sections = []
    questions = []

    # A. Overall Research Objectives
    block_a = re.search(r"A\.\s*Overall Research Objectives\s*(.*?)(?=B\.|$)", raw, re.DOTALL | re.IGNORECASE)
    if block_a:
        text = block_a.group(1).strip()
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("-") and len(line) > 2:
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
                ("report_reference", r"Report Reference:\s*(.*?)(?=Research Intent:|$)", re.DOTALL),
                ("research_intent", r"Research Intent:\s*(.*?)(?=Survey Question:|$)", re.DOTALL),
                ("survey_question", r"Survey Question:\s*(.*?)(?=Question Type:|$)", re.DOTALL),
                ("question_type", r"Question Type:\s*(.*?)(?=Answer Options:|$)", re.DOTALL),
                ("answer_options", r"Answer Options:\s*(.*?)(?=Target Segment:|Expected Output|$)", re.DOTALL),
                ("target_segment", r"Target Segment:\s*(.*?)(?=Expected Output|$)", re.DOTALL),
                ("expected_output_pattern", r"Expected Output Pattern:\s*(.*?)(?=Report Output:|-\s*Report Reference:|\Z)", re.DOTALL),
            ]:
                m = re.search(pattern, blk, re.IGNORECASE)
                if m:
                    val = m.group(1).strip()
                    if key == "answer_options":
                        opts = [_strip_markdown_bold(o.strip()) for o in re.split(r"[\n-]", val) if o.strip() and o.strip() != "Option"]
                        q[key] = [o for o in opts if o]
                    else:
                        q[key] = _strip_markdown_bold(val)
            if q.get("survey_question") or q.get("research_intent"):
                questions.append({
                    "report_reference": _strip_markdown_bold(q.get("report_reference", "")),
                    "research_intent": _strip_markdown_bold(q.get("research_intent", "")),
                    "survey_question": _strip_markdown_bold(q.get("survey_question", "")),
                    "question_type": _strip_markdown_bold(q.get("question_type", "")),
                    "answer_options": q.get("answer_options", []),
                    "target_segment": _strip_markdown_bold(q.get("target_segment", "")),
                    "expected_output_pattern": _strip_markdown_bold(q.get("expected_output_pattern", "")),
                })

    return overall, sections, questions


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
) -> dict:
    """Core logic: take report text, return structured output. Uses Anthropic (Claude) first, then OpenAI, then heuristic.
    Keys can be passed in so the same values resolved in the request handler are used for the LLM calls."""
    raw_md = None
    ai_used = False
    no_key_message = (
        "No API key. Set OPENAI_API_KEY or ANTHROPIC_API_KEY in your .env file (see .env.example) "
        "and restart the server to get AI-powered questionnaire reconstruction from your report."
    )
    # Try Anthropic (Claude, claude-sonnet-4-20250514) first, then OpenAI; use passed-in keys
    for name, call_llm, key in [
        ("Anthropic", _call_anthropic, anthropic_key),
        ("OpenAI", _call_openai, openai_key),
    ]:
        try:
            raw_md = call_llm(text, api_key=key)
            if raw_md and len(raw_md.strip()) > 0:
                try:
                    overall, section_objs, questionnaire = _parse_structured_output(raw_md)
                except Exception as parse_err:
                    logger.warning("Parse of %s output failed, using fallback structure: %s", name, parse_err)
                    h_overall, h_sections, h_questions, _ = _heuristic_reverse_engineer(text)
                    overall, section_objs, questionnaire = h_overall, h_sections, h_questions
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
    section_objectives = [SectionObjective(section_name=s["section_name"], research_objective=s["research_objective"]) for s in section_objs]
    reconstructed = [ReconstructedQuestion(**q) for q in questionnaire]
    return {
        "overall_objectives": overall,
        "section_objectives": [s.model_dump() for s in section_objectives],
        "reconstructed_questionnaire": [q.model_dump() for q in reconstructed],
        "raw_markdown": raw_md,
        "ai_used": ai_used,
        "message": None if ai_used else no_key_message,
    }


@router.get("/ai-status")
async def ai_status():
    """Return whether OpenAI or Anthropic API keys are configured (for debugging)."""
    return {
        "openai_configured": _get_openai_key() is not None,
        "anthropic_configured": _get_anthropic_key() is not None,
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
    # Resolve keys once in request context (same as ai-status) and pass into runner
    openai_key = _get_openai_key()
    anthropic_key = _get_anthropic_key()
    return _run_reverse_engineer(text, openai_key=openai_key, anthropic_key=anthropic_key)


@router.post("/reverse-engineer/json")
async def reverse_engineer_json(body: ReverseEngineerRequest):
    """Same as reverse-engineer but accepts JSON body with report_text."""
    openai_key = _get_openai_key()
    anthropic_key = _get_anthropic_key()
    return _run_reverse_engineer(body.report_text.strip(), openai_key=openai_key, anthropic_key=anthropic_key)


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
