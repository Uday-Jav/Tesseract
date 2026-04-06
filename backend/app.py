"""Main FastAPI application for ResumeRanker."""

from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.services.resume_analysis import analyze_resume_upload

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
uploaded_resumes: list[dict] = []


@app.get("/")
def read_root() -> dict:
    """Health-check endpoint."""
    return {"message": "ResumeRanker API running"}


async def _read_resume_upload(
    upload: UploadFile | None,
    *,
    job_description: str | None,
    field_label: str,
) -> tuple[bytes, str, dict]:
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

        analysis = await analyze_resume_upload(
            file_bytes=file_bytes,
            filename=upload.filename,
            job_description=cleaned_job_description,
        )
    except ImportError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except HTTPException:
        raise
    except Exception as error:  # pragma: no cover - defensive error handling
        raise HTTPException(status_code=500, detail="AI processing failed for the uploaded resume.") from error
    finally:
        await upload.close()

    return file_bytes, cleaned_job_description, analysis


@app.post("/analyze-resume")
async def analyze_resume_endpoint(
    resume: UploadFile | None = File(None),
    job_description: str | None = Form(None),
) -> dict:
    """Analyze an uploaded resume directly from multipart bytes."""
    _, _, analysis = await _read_resume_upload(
        resume,
        job_description=job_description,
        field_label="Resume",
    )
    return analysis


@app.post("/upload-resume")
async def upload_resume(
    file: UploadFile | None = File(None),
    job_description: str | None = Form(None),
) -> dict:
    """
    Upload a PDF resume, analyze it, and keep the result in memory.
    """
    active_job_description = job_description or job_description_text
    _, cleaned_job_description, analysis = await _read_resume_upload(
        file,
        job_description=active_job_description,
        field_label="Resume",
    )

    resume_id = len(uploaded_resumes) + 1
    resume_record = {
        "id": resume_id,
        "filename": file.filename,
        "job_description": cleaned_job_description,
        "analysis": analysis,
    }
    uploaded_resumes.append(resume_record)

    return {
        "resume_id": resume_id,
        "filename": file.filename,
        "message": "Resume uploaded successfully.",
        "analysis": analysis,
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
def rank_resumes() -> dict:
    """Return all uploaded resumes ranked by their AI final score."""
    if not uploaded_resumes:
        raise HTTPException(status_code=404, detail="No resumes have been uploaded yet.")

    ranked_resumes = []
    for resume in uploaded_resumes:
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
def get_analysis(resume_id: int) -> dict:
    """Return detailed analysis for one uploaded resume."""
    resume = next((item for item in uploaded_resumes if item["id"] == resume_id), None)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found.")

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
        "explanation": analysis["explanation"],
    }
