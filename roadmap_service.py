"""
roadmap_service.py — Learning Roadmap service

Provides utilities to read predefined roadmaps, track per-user completion,
and compute current/next/completed topics and progress percentage.

This module uses the same SQLite database file `tutor.db` used by the app.
"""

import sqlite3
from typing import List, Dict, Optional
from datetime import datetime, timezone

DB_PATH = "tutor.db"


class RoadmapService:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_roadmap_topics(self, roadmap_name: str) -> List[str]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT topic_name FROM roadmap_topics WHERE roadmap_name = ? ORDER BY topic_order",
            (roadmap_name,),
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]

    def get_user_completed_topics(self, user_id: int, roadmap_name: str) -> List[str]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT topic_name FROM user_roadmap_progress WHERE user_id = ? AND roadmap_name = ? AND completed = 1 ORDER BY topic_name",
            (user_id, roadmap_name),
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]

    def mark_topic_completed(self, user_id: int, roadmap_name: str, topic_name: str) -> None:
        conn = self._conn()
        now = datetime.now(timezone.utc).isoformat()
        try:
            conn.execute(
                "INSERT INTO user_roadmap_progress (user_id, roadmap_name, topic_name, completed, completed_at) VALUES (?, ?, ?, 1, ?)",
                (user_id, roadmap_name, topic_name, now),
            )
        except sqlite3.IntegrityError:
            # row exists — update
            conn.execute(
                "UPDATE user_roadmap_progress SET completed = 1, completed_at = ? WHERE user_id = ? AND roadmap_name = ? AND topic_name = ?",
                (now, user_id, roadmap_name, topic_name),
            )
        finally:
            conn.commit()
            conn.close()

    def get_user_roadmap_status(self, user_id: int, roadmap_name: str) -> Dict[str, Optional[object]]:
        """
        Returns a dict:
        {
          "all_topics": [..],
          "completed_topics": [..],
          "current_topic": str or None,
          "next_topic": str or None,
          "progress_percent": 0-100
        }
        """
        all_topics = self.get_roadmap_topics(roadmap_name)
        completed = set(self.get_user_completed_topics(user_id, roadmap_name))
        total = len(all_topics)

        completed_list = [t for t in all_topics if t in completed]

        # Current is the first topic not completed
        current = None
        next_topic = None
        for idx, t in enumerate(all_topics):
            if t not in completed:
                current = t
                # Next is next in list if exists
                if idx + 1 < total:
                    next_topic = all_topics[idx + 1]
                break

        if total == 0:
            progress = 0
        else:
            progress = round((len(completed_list) / total) * 100, 1)

        return {
            "all_topics": all_topics,
            "completed_topics": completed_list,
            "current_topic": current,
            "next_topic": next_topic,
            "progress_percent": progress,
        }
