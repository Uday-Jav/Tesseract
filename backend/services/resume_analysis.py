"""Helpers for integrating the AI resume analyzer with FastAPI routes."""

from __future__ import annotations

from dotenv import load_dotenv
from starlette.concurrency import run_in_threadpool

load_dotenv()


def empty_analysis_result(explanation: str = "Unable to analyze resume.") -> dict:
    """Return a stable empty payload for callers that need a default shape."""
    return {
        "match_score": 0.0,
        "fraud_score": 0,
        "final_score": 0.0,
        "skills": [],
        "missing_skills": [],
        "fraud_reasons": [],
        "authenticity_score": 0,
        "authenticity_reasons": [],
        "quality_score": 0,
        "quality_warnings": [],
        "is_fake": False,
        "resume_status": "unknown",
        "ranked": False,
        "ai_provider": "local",
        "explanation": explanation,
    }


async def analyze_resume_upload(file_bytes: bytes, filename: str, job_description: str) -> dict:
    """
    Analyze an uploaded PDF using the AI package's byte-friendly API.

    The AI call runs in a threadpool because it performs blocking work.
    """
    analysis = await run_in_threadpool(
        _run_ai_analysis_bytes,
        file_bytes,
        job_description,
        filename,
    )
    return normalize_analysis_result(analysis)


def _run_ai_analysis_bytes(file_bytes: bytes, job_description: str, filename: str) -> dict:
    try:
        from ai.ai_pipeline import analyze_resume_bytes
    except ModuleNotFoundError as error:
        raise ImportError(
            "The AI pipeline module could not be imported. Install the dependencies or sync the AI files."
        ) from error

    return analyze_resume_bytes(file_bytes, job_description, filename)


def normalize_analysis_result(analysis: dict | None) -> dict:
    """Keep the API response shape stable for frontend consumers."""
    payload = empty_analysis_result()
    if analysis is None:
        return payload

    payload.update(
        {
            "match_score": float(analysis.get("match_score", 0.0)),
            "fraud_score": int(analysis.get("fraud_score", 0)),
            "final_score": float(analysis.get("final_score", 0.0)),
            "skills": list(analysis.get("skills", [])),
            "missing_skills": list(analysis.get("missing_skills", [])),
            "fraud_reasons": list(analysis.get("fraud_reasons", [])),
            "authenticity_score": int(analysis.get("authenticity_score", 0)),
            "authenticity_reasons": list(analysis.get("authenticity_reasons", [])),
            "quality_score": int(analysis.get("quality_score", 0)),
            "quality_warnings": list(analysis.get("quality_warnings", [])),
            "is_fake": bool(analysis.get("is_fake", False)),
            "resume_status": str(analysis.get("resume_status", "unknown")),
            "ranked": bool(analysis.get("ranked", False)),
            "ai_provider": str(analysis.get("ai_provider", "local")),
            "explanation": str(analysis.get("explanation", payload["explanation"])),
        }
    )

    if payload["is_fake"]:
        payload["final_score"] = 0.0
        payload["ranked"] = False
        payload["resume_status"] = "fake"

    if payload["resume_status"] == "real":
        payload["ranked"] = True

    return payload
