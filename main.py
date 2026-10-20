"""
main.py — AI Personal Tutor Backend
FastAPI + SQLite + JWT Authentication + OpenRouter AI

Run with: uvicorn main:app --reload
"""

import os
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv as _load_dotenv_early
_load_dotenv_early()

import ai_helper
from services import EvaluationService, MasteryService, RoadmapService, WeakTopicService
from database import get_db, init_db
from auth import create_token, decode_token, get_current_user, require_admin
from models import (
    RegisterRequest,
    LoginRequest,
    ChatRequest,
    HintRequest,
    SummaryRequest,
    EvaluateRequest,
    RoadmapCompleteRequest,
)
import sqlite3
import bcrypt

# ─── Setup ────────────────────────────────────────────────────────────────────

JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

app = FastAPI(title="AI Personal Tutor API", version="1.0.0")

# CORS: allow_origins=["*"] works fine with Bearer token auth (no cookies needed).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Database is now handled by the `database` package (get_db, init_db)


# JWT helpers and Pydantic request models are provided by `auth` and `models` packages.
# They were moved to separate modules during the refactor to keep main.py thin.


# ─── Auth Routes ──────────────────────────────────────────────────────────────

@app.post("/register")
def register(req: RegisterRequest):
    """Register a new student account."""
    if not req.name or not req.email or not req.password:
        raise HTTPException(status_code=400, detail="All fields are required")

    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (req.name, req.email.lower(), hashed, "student", datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    finally:
        conn.close()

    return {"message": "Account created successfully! Please log in."}


@app.post("/login")
def login(req: LoginRequest):
    """Log in and receive a JWT token."""
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", (req.email.lower(),)
    ).fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not bcrypt.checkpw(req.password.encode(), user["password"].encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token(user["id"], user["role"])

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
        },
    }


@app.post("/logout")
def logout():
    """
    Logout is handled client-side by deleting the token.
    This endpoint exists for completeness.
    """
    return {"message": "Logged out successfully"}


# ─── AI Chat Route ────────────────────────────────────────────────────────────

@app.post("/chat")
def chat(req: ChatRequest, user=Depends(get_current_user)):
    """
    Send a message to the AI tutor and get a Socratic response.
    Automatically detects the topic, saves messages, and updates progress.
    """
    user_id = user["id"]
    conn = get_db()

    # 1. Load recent chat history for context
    recent_history = conn.execute(
        "SELECT role, message FROM chat_history WHERE user_id = ? ORDER BY id DESC LIMIT 20",
        (user_id,),
    ).fetchall()
    recent_history = list(reversed([dict(r) for r in recent_history]))

    # 2. Detect topic from the new message (or fall back to recent history)
    topic = ai_helper.detect_topic(req.message)
    if not topic and recent_history:
        # Try to detect from recent messages if current message doesn't reveal topic
        combined = " ".join(m["message"] for m in recent_history[-5:])
        topic = ai_helper.detect_topic(combined)

    # 3. Load memory summary from last session (if any)
    last_session = conn.execute(
        "SELECT summary FROM sessions WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    memory_summary = last_session["summary"] if last_session and last_session["summary"] else ""

    # 4. Call the AI tutor
    ai_response = ai_helper.get_tutor_response(
        user_message=req.message,
        chat_history=recent_history,
        topic=topic,
        memory_summary=memory_summary,
    )

    # 5. Save the student's message and AI response to chat history
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO chat_history (user_id, role, message, timestamp) VALUES (?, ?, ?, ?)",
        (user_id, "user", req.message, now),
    )
    conn.execute(
        "INSERT INTO chat_history (user_id, role, message, timestamp) VALUES (?, ?, ?, ?)",
        (user_id, "assistant", ai_response, now),
    )

    # 6. Ensure a progress row exists for this topic. Actual progress updates
    # are driven by the evaluation engine when the student submits an answer.
    if topic:
        conn.execute(
            "INSERT OR IGNORE INTO progress (user_id, topic, progress, hints_used) VALUES (?, ?, 0, 0)",
            (user_id, topic),
        )

    conn.commit()
    conn.close()

    return {
        "response": ai_response,
        "topic": topic or "General",
    }


# ─── Hint Route ───────────────────────────────────────────────────────────────

@app.post("/hint")
def hint(req: HintRequest, user=Depends(get_current_user)):
    """
    Get a progressive hint for a question.
    Tracks hint usage per topic.
    """
    user_id = user["id"]

    if req.hint_level not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="hint_level must be 1, 2, or 3")

    # Detect topic from the question
    topic = ai_helper.detect_topic(req.question) or "General"

    # Generate hint using AI
    hint_text = ai_helper.get_hint(req.question, req.hint_level, topic)

    # Track hint usage
    conn = get_db()
    conn.execute(
        """INSERT INTO progress (user_id, topic, progress, hints_used)
           VALUES (?, ?, 0, 1)
           ON CONFLICT(user_id, topic) DO UPDATE SET
           hints_used = hints_used + 1""",
        (user_id, topic),
    )
    conn.commit()
    conn.close()

    # Notify weak topic service about hint usage
    weak_service.record_hint(user_id, topic, req.hint_level)

    level_names = {1: "Concept Hint", 2: "Method Hint", 3: "Detailed Hint"}

    return {
        "hint": hint_text,
        "level": req.hint_level,
        "level_name": level_names[req.hint_level],
        "topic": topic,
    }


# ─── Student Routes ───────────────────────────────────────────────────────────

@app.get("/progress")
def get_progress(user=Depends(get_current_user)):
    """Get the student's topic progress and hint usage."""
    conn = get_db()
    rows = conn.execute(
        "SELECT topic, progress, hints_used FROM progress WHERE user_id = ? ORDER BY progress DESC",
        (user["id"],),
    ).fetchall()
    conn.close()

    return {"progress": [dict(r) for r in rows]}


@app.get("/history")
def get_history(user=Depends(get_current_user)):
    """Get the student's chat history (most recent 50 messages)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT role, message, timestamp FROM chat_history WHERE user_id = ? ORDER BY id DESC LIMIT 50",
        (user["id"],),
    ).fetchall()
    conn.close()

    return {"history": list(reversed([dict(r) for r in rows]))}


@app.get("/summary")
def get_summaries(user=Depends(get_current_user)):
    """Get all session summaries for the student."""
    conn = get_db()
    rows = conn.execute(
        "SELECT topic, summary, hints_used, created_at FROM sessions WHERE user_id = ? ORDER BY id DESC LIMIT 10",
        (user["id"],),
    ).fetchall()
    conn.close()

    return {"summaries": [dict(r) for r in rows]}


@app.post("/summary/generate")
def generate_summary(req: SummaryRequest, user=Depends(get_current_user)):
    """
    Generate and save a session summary for the current chat history.
    Call this when the student ends a session.
    """
    user_id = user["id"]
    conn = get_db()

    # Load today's chat history
    rows = conn.execute(
        "SELECT role, message FROM chat_history WHERE user_id = ? ORDER BY id DESC LIMIT 30",
        (user_id,),
    ).fetchall()
    chat_history = list(reversed([dict(r) for r in rows]))

    if not chat_history:
        raise HTTPException(status_code=400, detail="No chat history to summarize")

    # Detect topic
    combined = " ".join(m["message"] for m in chat_history)
    topic = req.topic or ai_helper.detect_topic(combined) or "General"

    # Count hints used in this session
    hint_count = conn.execute(
        "SELECT COALESCE(SUM(hints_used), 0) FROM progress WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]

    # Generate the summary using AI
    summary_text = ai_helper.generate_session_summary(chat_history, topic)

    # Save session
    conn.execute(
        "INSERT INTO sessions (user_id, topic, summary, hints_used, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, topic, summary_text, hint_count, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()

    return {"summary": summary_text, "topic": topic}


# ─── Admin Routes ─────────────────────────────────────────────────────────────

@app.get("/admin/users")
def admin_get_users(admin=Depends(require_admin)):
    """Get all student accounts."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, email, created_at FROM users WHERE role = 'student' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    return {"users": [dict(r) for r in rows]}


@app.get("/admin/progress")
def admin_get_progress(admin=Depends(require_admin)):
    """Get progress for all students."""
    conn = get_db()
    rows = conn.execute("""
        SELECT u.name, u.email, p.topic, p.progress, p.hints_used
        FROM progress p
        JOIN users u ON u.id = p.user_id
        ORDER BY p.progress DESC
    """).fetchall()
    conn.close()

    return {"progress": [dict(r) for r in rows]}


@app.get("/admin/sessions")
def admin_get_sessions(admin=Depends(require_admin)):
    """Get all tutoring sessions."""
    conn = get_db()
    rows = conn.execute("""
        SELECT u.name, s.topic, s.hints_used, s.created_at, s.summary
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        ORDER BY s.created_at DESC
        LIMIT 50
    """).fetchall()
    conn.close()

    return {"sessions": [dict(r) for r in rows]}


@app.get("/admin/analytics")
def admin_get_analytics(admin=Depends(require_admin)):
    """Get high-level statistics for the admin dashboard."""
    conn = get_db()

    total_students = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'student'"
    ).fetchone()[0]

    total_sessions = conn.execute(
        "SELECT COUNT(*) FROM sessions"
    ).fetchone()[0]

    total_questions = conn.execute(
        "SELECT COUNT(*) FROM chat_history WHERE role = 'user'"
    ).fetchone()[0]

    avg_progress_row = conn.execute(
        "SELECT AVG(progress) FROM progress"
    ).fetchone()[0]
    avg_progress = round(avg_progress_row or 0, 1)

    # Popular topics
    popular_topics = conn.execute(
        "SELECT topic, COUNT(*) as count FROM progress GROUP BY topic ORDER BY count DESC LIMIT 5"
    ).fetchall()

    conn.close()

    return {
        "total_students": total_students,
        "total_sessions": total_sessions,
        "total_questions": total_questions,
        "avg_progress": avg_progress,
        "popular_topics": [dict(r) for r in popular_topics],
    }


@app.get("/admin/stats")
def admin_stats(admin=Depends(require_admin)):
    """Return extended admin statistics for dashboards and charts."""
    conn = get_db()

    # Average mastery across all students (avg progress)
    avg_mastery = conn.execute("SELECT AVG(progress) FROM progress").fetchone()[0] or 0

    # Most difficult topics: topics with lowest average progress
    difficult = conn.execute(
        "SELECT topic, AVG(progress) as avg_progress, COUNT(*) as users FROM progress GROUP BY topic ORDER BY avg_progress ASC LIMIT 10"
    ).fetchall()

    # Top performing students: users with highest avg progress
    top_students = conn.execute(
        "SELECT u.id, u.name, u.email, AVG(p.progress) as avg_progress FROM users u JOIN progress p ON p.user_id = u.id WHERE u.role = 'student' GROUP BY u.id ORDER BY avg_progress DESC LIMIT 10"
    ).fetchall()

    # Weak topic distribution
    weak_dist = conn.execute(
        "SELECT topic, COUNT(*) as count FROM user_weak_topics GROUP BY topic ORDER BY count DESC LIMIT 20"
    ).fetchall()

    # Average hint usage per student
    avg_hint = conn.execute(
        "SELECT AVG(hints) FROM (SELECT user_id, SUM(hints_used) as hints FROM progress GROUP BY user_id)"
    ).fetchone()[0] or 0

    # Sessions per day (last 30 days)
    sessions_days = conn.execute(
        "SELECT date(created_at) as day, COUNT(*) as count FROM sessions WHERE created_at >= date('now','-30 days') GROUP BY day ORDER BY day"
    ).fetchall()

    # Most studied topics by number of users in progress
    most_studied = conn.execute(
        "SELECT topic, COUNT(*) as users FROM progress GROUP BY topic ORDER BY users DESC LIMIT 10"
    ).fetchall()

    # Learning statistics summary
    total_students = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'student'").fetchone()[0]
    total_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    total_questions = conn.execute("SELECT COUNT(*) FROM chat_history WHERE role = 'user'").fetchone()[0]

    conn.close()

    return {
        "avg_mastery": round(avg_mastery, 1),
        "most_difficult_topics": [dict(r) for r in difficult],
        "top_performing_students": [dict(r) for r in top_students],
        "weak_topic_distribution": [dict(r) for r in weak_dist],
        "avg_hint_usage": round(avg_hint, 1),
        "sessions_per_day": [dict(r) for r in sessions_days],
        "most_studied_topics": [dict(r) for r in most_studied],
        "learning_statistics": {
            "total_students": total_students,
            "total_sessions": total_sessions,
            "total_questions": total_questions,
        },
    }


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "AI Personal Tutor API is running!", "docs": "/docs"}


# ─── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    init_db()


# Instantiate evaluation service
eval_service = EvaluationService()
mastery_service = MasteryService()
roadmap_service = RoadmapService()
weak_service = WeakTopicService()

# Mount RAG router (document RAG features are additive and do not affect normal chat)
try:
    from routers.rag import router as rag_router
    app.include_router(rag_router, prefix="/rag")
except Exception:
    # If router import fails (missing deps), continue without RAG mounted
    pass


@app.post("/evaluate")
def evaluate(req: EvaluateRequest, user=Depends(get_current_user)):
    """
    Evaluate a student's answer using the EvaluationService, update progress,
    and return a friendly response for the frontend.
    """
    user_id = user["id"]
    topic = req.topic or ai_helper.detect_topic(req.question) or "General"

    # Call evaluation service
    result = eval_service.evaluate(req.question, req.student_answer, topic)

    # Compute mastery delta using the mastery engine and apply to progress table
    conn = get_db()
    try:
        score = int(result.get("score", 0))
        correct = bool(result.get("correct", False))

        hint_level = req.hint_level

        # Determine if this submission is an "explain-back" and whether it succeeded.
        # If `is_explanation` is true, we infer success from the evaluation score/confidence.
        if getattr(req, "is_explanation", False):
            # Threshold for considering an explanation successful: score >= 75 OR (correct and confidence >= 0.7)
            explained_back = (score >= 75) or (bool(result.get("correct")) and float(result.get("confidence", 0.0)) >= 0.7)
        else:
            explained_back = False

        # If this is an explanation submission, persist it to the explanations table
        # and also append it to chat_history so the front-end chat UI can display it.
        if getattr(req, "is_explanation", False):
            try:
                conn.execute(
                    "INSERT INTO explanations (user_id, topic, explanation, evaluation, score, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        user_id,
                        topic,
                        req.student_answer,
                        json.dumps(result),
                        score,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )

                # Save the student's explanation as a chat entry and the AI feedback as assistant reply
                now_ts = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "INSERT INTO chat_history (user_id, role, message, timestamp) VALUES (?, ?, ?, ?)",
                    (user_id, "user", req.student_answer, now_ts),
                )
                # Use the evaluation feedback text as assistant message
                feedback_text = result.get("feedback") or ""
                conn.execute(
                    "INSERT INTO chat_history (user_id, role, message, timestamp) VALUES (?, ?, ?, ?)",
                    (user_id, "assistant", feedback_text, now_ts),
                )
            except Exception:
                # Do not fail the whole request if logging the explanation fails; continue
                pass

        delta = mastery_service.calculate_delta(score=score, correct=correct, hint_level=hint_level, explained_back=explained_back)

        # Ensure progress row exists
        existing_row = conn.execute(
            "SELECT progress, hints_used FROM progress WHERE user_id = ? AND topic = ?",
            (user_id, topic),
        ).fetchone()

        if existing_row is None:
            new_progress = max(0, min(100, delta))
            hints_used = 1 if hint_level == 3 else 0
            conn.execute(
                "INSERT INTO progress (user_id, topic, progress, hints_used) VALUES (?, ?, ?, ?)",
                (user_id, topic, new_progress, hints_used),
            )
        else:
            current = existing_row[0]
            hints_used = existing_row[1]
            # If hint_level==3 and it's a fresh use, increment hints_used
            if hint_level == 3:
                hints_used = hints_used + 1

            new_progress = current + delta
            new_progress = max(0, min(100, new_progress))
            conn.execute(
                "UPDATE progress SET progress = ?, hints_used = ? WHERE user_id = ? AND topic = ?",
                (new_progress, hints_used, user_id, topic),
            )

        conn.commit()
    finally:
        conn.close()

    # After updating progress, notify weak topic service of the evaluation
    try:
        weak_service.record_evaluation(user_id, topic, score, hint_level)
    except Exception:
        # Do not fail the request if weak-topic logging fails
        pass

    # Build friendly response for frontend
    friendly = {
        "evaluation": {
            "score": result.get("score"),
            "correct": result.get("correct"),
            "confidence": result.get("confidence"),
            "misconceptions": result.get("misconceptions"),
            "feedback": result.get("feedback"),
            "next_action": result.get("next_action"),
            "parsing_error": result.get("parsing_error", False),
        },
        "message": "Evaluation complete.",
        "topic": topic,
    }

    # If parsing failed, include a short note and the raw AI snippet (truncated)
    if result.get("parsing_error"):
        friendly["message"] = "Evaluation completed but the AI output could not be fully parsed."
        friendly["debug"] = {"raw_ai_output": result.get("raw_ai_output")}

    return friendly


@app.get("/roadmap")
def get_roadmap(roadmap_name: Optional[str] = None, user=Depends(get_current_user)):
    """
    Return the user's roadmap status for `roadmap_name` (defaults to 'React').
    """
    name = roadmap_name or "React"
    status = roadmap_service.get_user_roadmap_status(user["id"], name)
    return {"roadmap": name, "status": status}


@app.get("/weak-topics")
def get_weak_topics(user=Depends(get_current_user)):
    """Return the user's weak topics and simple suggestions."""
    weak = weak_service.get_user_weak_topics(user["id"])
    # Attach suggestions
    for w in weak:
        sugg = weak_service.get_suggestions_for_topic(w["topic"]) if w.get("topic") else {}
        w["need_revision"] = sugg.get("need_revision", [])
        w["suggested_practice"] = sugg.get("suggested_practice", [])

    return {"weak_topics": weak}


@app.get("/dashboard/overview")
def dashboard_overview(user=Depends(get_current_user)):
    """Return aggregated metrics for the student dashboard."""
    user_id = user["id"]
    conn = get_db()

    # Mastery score: average progress across topics
    avg_row = conn.execute(
        "SELECT AVG(progress) as avg_progress FROM progress WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    mastery_score = round(avg_row[0] or 0, 1)

    # Hints used total
    hints_row = conn.execute(
        "SELECT COALESCE(SUM(hints_used),0) FROM progress WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    hints_used = hints_row[0] or 0

    # Sessions completed
    sessions_count = conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]

    # Strong topics (progress >= 80)
    strong_rows = conn.execute(
        "SELECT topic, progress FROM progress WHERE user_id = ? AND progress >= 80 ORDER BY progress DESC",
        (user_id,),
    ).fetchall()
    strong_topics = [dict(r) for r in strong_rows]

    # Weak topics from weak_topic_service
    weak_topics = weak_service.get_user_weak_topics(user_id)

    # Roadmap status (default to React)
    roadmap_name = "React"
    roadmap_status = roadmap_service.get_user_roadmap_status(user_id, roadmap_name)

    # Current topic: prefer roadmap current_topic, else last session topic
    current_topic = roadmap_status.get("current_topic") or (
        conn.execute("SELECT topic FROM sessions WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone() or {"topic": None}
    )
    current_topic = current_topic if isinstance(current_topic, str) else (current_topic[0] if current_topic and current_topic[0] else None)

    # Recommended next topic from roadmap
    recommended_next = roadmap_status.get("next_topic")

    # Learning streak: count consecutive days with chat activity up to today
    days = conn.execute(
        "SELECT DISTINCT date(timestamp) as day FROM chat_history WHERE user_id = ? ORDER BY day DESC",
        (user_id,),
    ).fetchall()
    conn.close()

    day_set = set(r[0] for r in days if r[0])
    from datetime import datetime, timedelta, timezone
    today = datetime.now(timezone.utc).date()
    streak = 0
    cursor_day = today
    while True:
        if cursor_day.isoformat() in day_set:
            streak += 1
            cursor_day = cursor_day - timedelta(days=1)
        else:
            break

    return {
        "current_topic": current_topic or "General",
        "mastery_score": mastery_score,
        "learning_progress": mastery_score,
        "weak_topics": weak_topics,
        "strong_topics": strong_topics,
        "learning_roadmap": {"name": roadmap_name, "status": roadmap_status},
        "current_stage": roadmap_status.get("current_topic"),
        "hints_used": hints_used,
        "sessions_completed": sessions_count,
        "learning_streak": streak,
        "recommended_next": recommended_next,
    }


@app.post("/roadmap/complete")
def complete_roadmap_topic(req: RoadmapCompleteRequest, user=Depends(get_current_user)):
    """
    Mark a topic complete for the user's roadmap and return updated status.
    The backend controls progression; this endpoint can be called after evaluation
    determines the student should advance.
    """
    roadmap_service.mark_topic_completed(user["id"], req.roadmap_name, req.topic_name)
    status = roadmap_service.get_user_roadmap_status(user["id"], req.roadmap_name)
    return {"roadmap": req.roadmap_name, "status": status}
