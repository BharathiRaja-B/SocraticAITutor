"""
weak_topic_service.py — Weak Topic Detection

Rules (no AI):
- score < 60 => failed evaluation
- hint level 3 used three times for a topic => weak
- three failed evaluations for a topic => weak

This module updates `evaluation_stats` and `user_weak_topics` tables and
provides query methods for the frontend to list weak topics and suggestions.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict
import sqlite3

DB_PATH = "tutor.db"


class WeakTopicService:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def record_evaluation(self, user_id: int, topic: str, score: int, hint_level: Optional[int] = None) -> None:
        """
        Update evaluation_stats for the user/topic and mark weak topic if rules met.
        """
        conn = self._conn()
        cur = conn.cursor()

        # Update or insert stats
        row = cur.execute(
            "SELECT failed_count, total_count FROM evaluation_stats WHERE user_id = ? AND topic = ?",
            (user_id, topic),
        ).fetchone()

        if row is None:
            failed = 1 if score < 60 else 0
            total = 1
            cur.execute(
                "INSERT INTO evaluation_stats (user_id, topic, failed_count, total_count) VALUES (?, ?, ?, ?)",
                (user_id, topic, failed, total),
            )
        else:
            failed = row[0] + (1 if score < 60 else 0)
            total = row[1] + 1
            cur.execute(
                "UPDATE evaluation_stats SET failed_count = ?, total_count = ? WHERE user_id = ? AND topic = ?",
                (failed, total, user_id, topic),
            )

        conn.commit()

        # Check rules
        should_mark = False
        reason = None

        if score < 60:
            # Immediate weak mark on low score
            should_mark = True
            reason = f"Low score ({score})"

        # Check failed_count rule
        stats = cur.execute(
            "SELECT failed_count FROM evaluation_stats WHERE user_id = ? AND topic = ?",
            (user_id, topic),
        ).fetchone()
        if stats and stats[0] >= 3:
            should_mark = True
            reason = f"{stats[0]} failed evaluations"

        # Check hint level 3 usage rule by reading progress.hints_used
        prog = cur.execute(
            "SELECT hints_used FROM progress WHERE user_id = ? AND topic = ?",
            (user_id, topic),
        ).fetchone()
        if prog and prog[0] >= 3:
            should_mark = True
            reason = f"Hint level 3 used {prog[0]} times"

        if should_mark:
            self._mark_weak(conn, user_id, topic, reason)

        conn.close()

    def record_hint(self, user_id: int, topic: str, hint_level: int) -> None:
        """
        Called when a hint is used. If hint_level==3, check whether the count reached 3.
        """
        if hint_level != 3:
            return

        conn = self._conn()
        cur = conn.cursor()
        prog = cur.execute(
            "SELECT hints_used FROM progress WHERE user_id = ? AND topic = ?",
            (user_id, topic),
        ).fetchone()
        if prog and prog[0] >= 3:
            # mark weak
            reason = f"Hint level 3 used {prog[0]} times"
            self._mark_weak(conn, user_id, topic, reason)
        conn.close()

    def _mark_weak(self, conn: sqlite3.Connection, user_id: int, topic: str, reason: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.cursor()
        existing = cur.execute(
            "SELECT id, mark_count FROM user_weak_topics WHERE user_id = ? AND topic = ?",
            (user_id, topic),
        ).fetchone()
        if existing is None:
            cur.execute(
                "INSERT INTO user_weak_topics (user_id, topic, reason, mark_count, created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?)",
                (user_id, topic, reason, now, now),
            )
        else:
            new_count = existing[1] + 1
            cur.execute(
                "UPDATE user_weak_topics SET reason = ?, mark_count = ?, updated_at = ? WHERE id = ?",
                (reason, new_count, now, existing[0]),
            )
        conn.commit()

    def get_user_weak_topics(self, user_id: int) -> List[Dict[str, str]]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT topic, reason, mark_count, created_at, updated_at FROM user_weak_topics WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_suggestions_for_topic(self, topic: str) -> Dict[str, List[str]]:
        """
        Provide simple non-AI suggestions for a weak topic.
        """
        return {
            "need_revision": [f"Review notes on {topic}", f"Re-read examples for {topic}"],
            "suggested_practice": [f"Solve 3 practice problems on {topic}", f"Try flashcards for {topic} terms"],
        }
