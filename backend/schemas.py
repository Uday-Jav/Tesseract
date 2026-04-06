"""Pydantic schemas for auth endpoints."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=8)
    new_password: str = Field(min_length=8, max_length=128)


class ParseJdRequest(BaseModel):
    job_description: str = Field(min_length=10)


class InterviewQuestionsRequest(BaseModel):
    resume_id: int = Field(gt=0)


class RecruiterChatRequest(BaseModel):
    resume_id: int = Field(gt=0)
    question: str = Field(min_length=2, max_length=2000)
