"""Main FastAPI application for ResumeRanker."""

from __future__ import annotations

import json
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.database import Base, engine, ensure_database_ready, get_db
from backend.models import RecruiterChatMessage, ResumeRecord
from backend.schemas import (
    ForgotPasswordRequest,
    InterviewQuestionsRequest,
    LoginRequest,
    ParseJdRequest,
    RecruiterChatRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from backend.services.auth_service import create_password_reset, login_user, register_user, reset_password
from backend.services.gemini_features import (
    extract_resume_text_from_bytes,
    generate_candidate_summary,
    generate_interview_questions,
    parse_job_description,
    recruiter_chat,
)
from backend.services.resume_analysis import analyze_resume_upload

load_dotenv()

app = FastAPI(title="ResumeRanker API")

# Allow frontend apps to connect during local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for hackathon use.
job_description_text = ""
parsed_jd_store: dict[str, dict] = {}


@app.on_event("startup")
def startup_event() -> None:
    """Create database tables when MySQL is available."""
    try:
        ensure_database_ready()
    except SQLAlchemyError:
        # The API can still serve resume analysis while DB setup is in progress.
        pass


@app.get("/")
def read_root() -> dict:
    """Health-check endpoint."""
    return {"message": "ResumeRanker API running"}


def _serialize_payload(payload: dict) -> str:
    return json.dumps(payload)


def _deserialize_payload(payload: str) -> dict:
    return json.loads(payload)


def _resume_to_dict(resume: ResumeRecord) -> dict:
    return {
        "id": resume.id,
        "filename": resume.filename,
        "job_description": resume.job_description,
        "resume_text": resume.resume_text,
        "analysis": _deserialize_payload(resume.analysis_json),
        "parsed_jd": _deserialize_payload(resume.parsed_jd_json),
        "candidate_summary": _deserialize_payload(resume.candidate_summary_json),
    }


async def _read_resume_upload(
    upload: UploadFile | None,
    *,
    job_description: str | None,
    field_label: str,
) -> tuple[bytes, str, str, dict, dict, dict]:
    """Validate an uploaded resume and return its bytes plus analyzed result."""
    if upload is None:
        raise HTTPException(status_code=400, detail=f"{field_label} file is required.")

    if not upload.filename:
        raise HTTPException(status_code=400, detail="Filename is missing.")

    cleaned_job_description = (job_description or "").strip()
    if not cleaned_job_description:
        raise HTTPException(status_code=400, detail="Job description cannot be empty.")

    is_pdf_upload = upload.filename.lower().endswith(".pdf") or upload.content_type == "application/pdf"
    if not is_pdf_upload:
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    try:
        file_bytes = await upload.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        resume_text = extract_resume_text_from_bytes(file_bytes)
        analysis = await analyze_resume_upload(
            file_bytes=file_bytes,
            filename=upload.filename,
            job_description=cleaned_job_description,
        )
        parsed_jd = await parse_job_description(cleaned_job_description)
        candidate_summary = await generate_candidate_summary(
            resume_text=resume_text,
            job_description=cleaned_job_description,
            analysis=analysis,
            parsed_jd=parsed_jd,
        )
    except ImportError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except HTTPException:
        raise
    except Exception as error:  # pragma: no cover - defensive error handling
        raise HTTPException(status_code=500, detail="AI processing failed for the uploaded resume.") from error
    finally:
        await upload.close()

    return file_bytes, cleaned_job_description, resume_text, analysis, parsed_jd, candidate_summary


@app.post("/auth/register")
def register_endpoint(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    """Create a new account in MySQL."""
    try:
        ensure_database_ready()
        return register_user(
            db,
            full_name=payload.full_name,
            email=payload.email,
            password=payload.password,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except SQLAlchemyError as error:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Database error while creating account.") from error


@app.post("/auth/login")
def login_endpoint(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    """Authenticate a user and return a JWT access token."""
    try:
        ensure_database_ready()
        return login_user(db, email=payload.email, password=payload.password)
    except ValueError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    except SQLAlchemyError as error:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Database error while logging in.") from error


@app.post("/auth/forgot-password")
def forgot_password_endpoint(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    """Generate a password reset token for the given email."""
    try:
        ensure_database_ready()
        return create_password_reset(db, email=payload.email)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except SQLAlchemyError as error:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Database error while creating reset token.") from error


@app.post("/auth/reset-password")
def reset_password_endpoint(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict:
    """Reset a user's password using a forgot-password token."""
    try:
        ensure_database_ready()
        return reset_password(db, token=payload.token, new_password=payload.new_password)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except SQLAlchemyError as error:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Database error while resetting password.") from error


@app.post("/parse-jd")
async def parse_jd_endpoint(payload: ParseJdRequest) -> dict:
    """Parse a raw job description into structured recruiter-friendly fields."""
    parsed_jd = await parse_job_description(payload.job_description)
    parsed_jd_store[payload.job_description] = parsed_jd
    return parsed_jd


@app.post("/analyze-resume")
async def analyze_resume_endpoint(
    resume: UploadFile | None = File(None),
    job_description: str | None = Form(None),
) -> dict:
    """Analyze an uploaded resume directly from multipart bytes."""
    _, _, _, analysis, parsed_jd, candidate_summary = await _read_resume_upload(
        resume,
        job_description=job_description,
        field_label="Resume",
    )
    analysis["parsed_jd"] = parsed_jd
    analysis.update(candidate_summary)
    return analysis


@app.post("/upload-resume")
async def upload_resume(
    file: UploadFile | None = File(None),
    job_description: str | None = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    """
    Upload a PDF resume, analyze it, and keep the result in memory.
    """
    ensure_database_ready()
    active_job_description = job_description or job_description_text
    _, cleaned_job_description, resume_text, analysis, parsed_jd, candidate_summary = await _read_resume_upload(
        file,
        job_description=active_job_description,
        field_label="Resume",
    )

    resume_record = ResumeRecord(
        filename=file.filename,
        job_description=cleaned_job_description,
        resume_text=resume_text,
        analysis_json=_serialize_payload(analysis),
        parsed_jd_json=_serialize_payload(parsed_jd),
        candidate_summary_json=_serialize_payload(candidate_summary),
    )
    db.add(resume_record)
    db.commit()
    db.refresh(resume_record)
    parsed_jd_store[cleaned_job_description] = parsed_jd

    return {
        "resume_id": resume_record.id,
        "filename": file.filename,
        "message": "Resume uploaded successfully.",
        "analysis": analysis,
        "parsed_jd": parsed_jd,
        "candidate_summary": candidate_summary,
    }


@app.post("/generate-interview-questions")
async def generate_interview_questions_endpoint(
    payload: InterviewQuestionsRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Generate interview questions using stored resume context plus parsed JD."""
    ensure_database_ready()
    resume_record = db.get(ResumeRecord, payload.resume_id)
    if resume_record is None:
        raise HTTPException(status_code=404, detail="Resume not found.")

    resume = _resume_to_dict(resume_record)

    return await generate_interview_questions(
        resume_text=resume["resume_text"],
        parsed_jd=resume["parsed_jd"],
        analysis=resume["analysis"],
    )


@app.post("/recruiter-chat")
async def recruiter_chat_endpoint(
    payload: RecruiterChatRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Answer recruiter questions over one uploaded resume."""
    ensure_database_ready()
    resume_record = db.get(ResumeRecord, payload.resume_id)
    if resume_record is None:
        raise HTTPException(status_code=404, detail="Resume not found.")

    resume = _resume_to_dict(resume_record)
    chat_history = [
        {"role": message.role, "message": message.message}
        for message in resume_record.chat_messages
    ]
    result = await recruiter_chat(
        recruiter_message=payload.question,
        resume_text=resume["resume_text"],
        job_description=resume["job_description"],
        analysis=resume["analysis"],
        parsed_jd=resume["parsed_jd"],
        chat_history=chat_history,
    )

    db.add(RecruiterChatMessage(resume_id=payload.resume_id, role="recruiter", message=payload.question))
    db.add(RecruiterChatMessage(resume_id=payload.resume_id, role="assistant", message=result["answer"]))
    db.commit()

    updated_history = chat_history + [
        {"role": "recruiter", "message": payload.question},
        {"role": "assistant", "message": result["answer"]},
    ]
    return {
        "resume_id": payload.resume_id,
        "question": payload.question,
        "answer": result["answer"],
        "ai_provider": result["ai_provider"],
        "chat_history": updated_history,
    }


@app.post("/upload-job")
def upload_job(job_description: Annotated[str, Form(...)]) -> dict:
    """Store the latest job description in memory."""
    global job_description_text

    cleaned_text = job_description.strip()
    if not cleaned_text:
        raise HTTPException(status_code=400, detail="Job description cannot be empty.")

    job_description_text = cleaned_text
    return {
        "message": "Job description stored successfully.",
        "job_description_preview": job_description_text[:500],
    }


@app.get("/rank")
def rank_resumes(db: Session = Depends(get_db)) -> dict:
    """Return all uploaded resumes ranked by their AI final score."""
    ensure_database_ready()
    resume_records = db.query(ResumeRecord).order_by(ResumeRecord.id.asc()).all()
    if not resume_records:
        raise HTTPException(status_code=404, detail="No resumes have been uploaded yet.")

    ranked_resumes = []
    for record in resume_records:
        resume = _resume_to_dict(record)
        analysis = resume["analysis"]
        if not analysis["ranked"]:
            continue

        ranked_resumes.append(
            {
                "resume_id": resume["id"],
                "filename": resume["filename"],
                "score": analysis["final_score"],
                "match_score": analysis["match_score"],
                "fraud_score": analysis["fraud_score"],
                "skills": analysis["skills"],
                "missing_skills": analysis["missing_skills"],
                "fraud_reasons": analysis["fraud_reasons"],
                "resume_status": analysis["resume_status"],
            }
        )

    ranked_resumes.sort(key=lambda item: item["score"], reverse=True)
    return {"ranked_resumes": ranked_resumes}


@app.get("/analysis/{resume_id}")
def get_analysis(resume_id: int, db: Session = Depends(get_db)) -> dict:
    """Return detailed analysis for one uploaded resume."""
    ensure_database_ready()
    resume_record = db.get(ResumeRecord, resume_id)
    if resume_record is None:
        raise HTTPException(status_code=404, detail="Resume not found.")

    resume = _resume_to_dict(resume_record)
    analysis = resume["analysis"]
    return {
        "resume_id": resume["id"],
        "filename": resume["filename"],
        "match_score": analysis["match_score"],
        "fraud_score": analysis["fraud_score"],
        "final_score": analysis["final_score"],
        "skills": analysis["skills"],
        "missing_skills": analysis["missing_skills"],
        "fraud_reasons": analysis["fraud_reasons"],
        "authenticity_score": analysis["authenticity_score"],
        "authenticity_reasons": analysis["authenticity_reasons"],
        "quality_score": analysis["quality_score"],
        "quality_warnings": analysis["quality_warnings"],
        "is_fake": analysis["is_fake"],
        "resume_status": analysis["resume_status"],
        "ranked": analysis["ranked"],
        "ai_provider": analysis["ai_provider"],
        "parsed_jd": resume["parsed_jd"],
        "candidate_summary": resume["candidate_summary"],
        "explanation": analysis["explanation"],
    }
