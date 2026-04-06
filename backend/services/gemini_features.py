"""Gemini-powered helpers for JD parsing, summaries, interview questions, and recruiter chat."""

from __future__ import annotations

from io import BytesIO
import json
import os
import re
from typing import Any

from dotenv import load_dotenv
import pdfplumber
from starlette.concurrency import run_in_threadpool


load_dotenv()

COMMON_SKILLS = [
    "python",
    "java",
    "javascript",
    "typescript",
    "sql",
    "react",
    "node.js",
    "fastapi",
    "django",
    "flask",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "machine learning",
    "deep learning",
    "nlp",
    "pandas",
    "numpy",
    "tensorflow",
    "pytorch",
    "scikit-learn",
    "mysql",
    "postgresql",
    "mongodb",
    "git",
]


def _extract_json_object(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}

    try:
        parsed = json.loads(text[start : end + 1])
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from google import genai
    except Exception:
        return None

    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def _generate_json_with_gemini(prompt: str) -> tuple[dict[str, Any], str]:
    client = _get_gemini_client()
    if client is None:
        return {}, "local"

    model_name = os.getenv("GOOGLE_ANALYSIS_MODEL", "gemini-2.5-flash")

    try:
        from google.genai import types

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        text = getattr(response, "text", "") or ""
        return _extract_json_object(text), "google"
    except Exception:
        return {}, "local"


def extract_resume_text_from_bytes(file_bytes: bytes) -> str:
    """Extract text from uploaded PDF bytes for downstream Gemini features."""
    collected_pages: list[str] = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                collected_pages.append(page_text.strip())
    return "\n".join(collected_pages).strip()


def _fallback_parse_jd(job_description: str) -> dict[str, Any]:
    text = job_description.strip()
    lowered = text.lower()

    required_skills = [skill for skill in COMMON_SKILLS if skill in lowered]
    role_title = "General Role"
    for marker in ("developer", "engineer", "analyst", "scientist", "manager", "designer"):
        match = re.search(rf"([A-Za-z /-]+{marker})", text, flags=re.IGNORECASE)
        if match:
            role_title = match.group(1).strip()
            break

    experience_level = "mid-level"
    if "senior" in lowered or "5+" in lowered or "7+" in lowered:
        experience_level = "senior"
    elif "junior" in lowered or "entry" in lowered or "fresher" in lowered:
        experience_level = "junior"

    responsibilities = [
        sentence.strip(" -.")
        for sentence in re.split(r"[.\n]", text)
        if len(sentence.strip()) > 25
    ][:6]

    education = []
    if "bachelor" in lowered or "b.tech" in lowered or "degree" in lowered:
        education.append("Bachelor's degree")
    if "master" in lowered or "m.tech" in lowered:
        education.append("Master's degree")

    return {
        "role_title": role_title,
        "required_skills": required_skills[:10],
        "optional_skills": [],
        "experience_level": experience_level,
        "tools": required_skills[:8],
        "responsibilities": responsibilities,
        "education": education,
        "keywords": required_skills[:12],
        "ai_provider": "local",
    }


async def parse_job_description(job_description: str) -> dict[str, Any]:
    prompt = f"""
You are a recruiter assistant. Parse the following job description and return only JSON
with these keys:
role_title, required_skills, optional_skills, experience_level, tools, responsibilities, education, keywords.

Job description:
{job_description}
"""
    parsed, provider = await run_in_threadpool(_generate_json_with_gemini, prompt)
    if not parsed:
        return _fallback_parse_jd(job_description)

    fallback = _fallback_parse_jd(job_description)
    fallback.update(
        {
            "role_title": str(parsed.get("role_title") or fallback["role_title"]),
            "required_skills": list(parsed.get("required_skills") or fallback["required_skills"]),
            "optional_skills": list(parsed.get("optional_skills") or []),
            "experience_level": str(parsed.get("experience_level") or fallback["experience_level"]),
            "tools": list(parsed.get("tools") or fallback["tools"]),
            "responsibilities": list(parsed.get("responsibilities") or fallback["responsibilities"]),
            "education": list(parsed.get("education") or fallback["education"]),
            "keywords": list(parsed.get("keywords") or fallback["keywords"]),
            "ai_provider": provider,
        }
    )
    return fallback


def _fallback_candidate_summary(analysis: dict[str, Any], parsed_jd: dict[str, Any]) -> dict[str, Any]:
    strengths = list(analysis.get("skills", []))[:5]
    missing_skills = list(analysis.get("missing_skills", []))[:5]
    concerns = list(analysis.get("fraud_reasons", []))[:5]
    role_title = parsed_jd.get("role_title", "the role")

    return {
        "short_summary": (
            f"Candidate appears {'fake/template-based' if analysis.get('is_fake') else 'real'} "
            f"for {role_title} with final score {analysis.get('final_score', 0)}."
        ),
        "fit_explanation": analysis.get("explanation", "No explanation available."),
        "strengths": strengths,
        "missing_skills": missing_skills,
        "concerns": concerns,
        "ai_provider": "local",
    }


async def generate_candidate_summary(
    *,
    resume_text: str,
    job_description: str,
    analysis: dict[str, Any],
    parsed_jd: dict[str, Any],
) -> dict[str, Any]:
    prompt = f"""
You are a recruiting assistant. Based on the resume text, parsed job description, and analysis,
return only JSON with these keys:
short_summary, fit_explanation, strengths, missing_skills, concerns.

Resume text:
{resume_text[:6000]}

Job description:
{job_description[:4000]}

Analysis:
{json.dumps(analysis)}

Parsed JD:
{json.dumps(parsed_jd)}
"""
    parsed, provider = await run_in_threadpool(_generate_json_with_gemini, prompt)
    if not parsed:
        return _fallback_candidate_summary(analysis, parsed_jd)

    fallback = _fallback_candidate_summary(analysis, parsed_jd)
    fallback.update(
        {
            "short_summary": str(parsed.get("short_summary") or fallback["short_summary"]),
            "fit_explanation": str(parsed.get("fit_explanation") or fallback["fit_explanation"]),
            "strengths": list(parsed.get("strengths") or fallback["strengths"]),
            "missing_skills": list(parsed.get("missing_skills") or fallback["missing_skills"]),
            "concerns": list(parsed.get("concerns") or fallback["concerns"]),
            "ai_provider": provider,
        }
    )
    return fallback


def _fallback_interview_questions(parsed_jd: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    skills = list(parsed_jd.get("required_skills", [])) or list(analysis.get("skills", []))
    missing = list(analysis.get("missing_skills", []))

    return {
        "technical_questions": [f"Explain your experience with {skill}." for skill in skills[:5]],
        "project_questions": ["Walk me through the most relevant project from your resume."],
        "experience_questions": ["What role did you play in your most recent team or company?"],
        "behavioral_questions": ["Tell me about a time you handled a difficult deadline."],
        "follow_up_questions": [f"How would you close your gap in {skill}?" for skill in missing[:3]],
        "ai_provider": "local",
    }


async def generate_interview_questions(
    *,
    resume_text: str,
    parsed_jd: dict[str, Any],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    prompt = f"""
Generate interview questions for a recruiter. Return only JSON with these keys:
technical_questions, project_questions, experience_questions, behavioral_questions, follow_up_questions.

Resume text:
{resume_text[:6000]}

Parsed JD:
{json.dumps(parsed_jd)}

Analysis:
{json.dumps(analysis)}
"""
    parsed, provider = await run_in_threadpool(_generate_json_with_gemini, prompt)
    if not parsed:
        return _fallback_interview_questions(parsed_jd, analysis)

    fallback = _fallback_interview_questions(parsed_jd, analysis)
    fallback.update(
        {
            "technical_questions": list(parsed.get("technical_questions") or fallback["technical_questions"]),
            "project_questions": list(parsed.get("project_questions") or fallback["project_questions"]),
            "experience_questions": list(parsed.get("experience_questions") or fallback["experience_questions"]),
            "behavioral_questions": list(parsed.get("behavioral_questions") or fallback["behavioral_questions"]),
            "follow_up_questions": list(parsed.get("follow_up_questions") or fallback["follow_up_questions"]),
            "ai_provider": provider,
        }
    )
    return fallback


def _fallback_recruiter_chat(question: str, analysis: dict[str, Any], parsed_jd: dict[str, Any]) -> dict[str, Any]:
    lowered = question.lower()
    if "missing" in lowered:
        answer = f"Missing skills: {', '.join(analysis.get('missing_skills', [])) or 'none detected'}."
    elif "why" in lowered and "low" in lowered:
        answer = f"Candidate ranked low because: {'; '.join(analysis.get('fraud_reasons', [])) or analysis.get('explanation', '')}"
    elif "python" in lowered:
        has_python = "python" in [skill.lower() for skill in analysis.get("skills", [])]
        answer = "Yes, the candidate shows Python in the extracted skills." if has_python else "Python was not found in the extracted skills."
    else:
        answer = analysis.get("explanation", "No answer available from current analysis.")

    return {
        "answer": answer,
        "ai_provider": "local",
        "context_used": {
            "resume_status": analysis.get("resume_status", "unknown"),
            "required_skills": parsed_jd.get("required_skills", []),
        },
    }


async def recruiter_chat(
    *,
    recruiter_message: str,
    resume_text: str,
    job_description: str,
    analysis: dict[str, Any],
    parsed_jd: dict[str, Any],
    chat_history: list[dict[str, Any]],
) -> dict[str, Any]:
    prompt = f"""
You are helping a recruiter chat about a candidate.
Answer the recruiter's question using only the provided resume, JD, analysis, and chat history.
Return only JSON with keys: answer.

Recruiter question:
{recruiter_message}

Resume text:
{resume_text[:5000]}

Job description:
{job_description[:3000]}

Analysis:
{json.dumps(analysis)}

Parsed JD:
{json.dumps(parsed_jd)}

Chat history:
{json.dumps(chat_history[-6:])}
"""
    parsed, provider = await run_in_threadpool(_generate_json_with_gemini, prompt)
    if not parsed:
        return _fallback_recruiter_chat(recruiter_message, analysis, parsed_jd)

    fallback = _fallback_recruiter_chat(recruiter_message, analysis, parsed_jd)
    fallback.update(
        {
            "answer": str(parsed.get("answer") or fallback["answer"]),
            "ai_provider": provider,
        }
    )
    return fallback
