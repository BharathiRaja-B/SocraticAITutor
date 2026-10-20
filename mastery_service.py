"""
mastery_service.py — Mastery Engine

Provides `MasteryService.calculate_delta(score, correct, hint_level, explained_back)`
which returns an integer delta to apply to a student's progress for a topic.

Rules implemented:
- Correct answer: +10
- Partial answer: +5
- Wrong answer: +2
- If the question used a level 3 hint: -2
- If the student successfully "explained back": +8

The service is deterministic and contains no side effects; DB updates are handled
in the API layer (`main.py`).
"""

from typing import Optional


class MasteryService:
    def __init__(self):
        pass

    def calculate_delta(self, score: int, correct: bool, hint_level: Optional[int] = None, explained_back: bool = False) -> int:
        """
        Compute the progress delta based on evaluation score and flags.

        score: 0-100
        correct: boolean
        hint_level: optional int (if 3, apply penalty)
        explained_back: whether the student explained back the concept successfully
        """
        # Base bucket by score
        if score >= 80:
            base = 10
        elif score >= 50:
            base = 5
        else:
            base = 2

        delta = base

        # Explained back bonus
        if explained_back:
            delta += 8

        # Hint level 3 penalty
        if hint_level == 3:
            delta -= 2

        # Ensure at least 0 change (don't subtract below zero)
        # but allow negative if desired; clamp by caller when applying.
        return int(delta)
