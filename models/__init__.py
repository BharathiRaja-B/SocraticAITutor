"""
models package — Pydantic request models
"""
from pydantic import BaseModel
from typing import Optional


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[int] = None


class HintRequest(BaseModel):
    question: str
    hint_level: int


class SummaryRequest(BaseModel):
    topic: Optional[str] = None


class EvaluateRequest(BaseModel):
    question: str
    student_answer: str
    topic: Optional[str] = None
    hint_level: Optional[int] = None
    is_explanation: Optional[bool] = False


class RoadmapCompleteRequest(BaseModel):
    roadmap_name: str
    topic_name: str
