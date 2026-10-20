"""
evaluation_service.py — Evaluation Engine service

Provides EvaluationService.evaluate(question, student_answer, topic)
which calls the AI with a strict evaluation prompt, safely parses the returned
JSON, validates fields, and returns a normalized dict the API can use.
"""

import json
import re
from typing import Any, Dict

import ai_helper


class EvaluationService:
    def __init__(self):
        pass

    def _safe_extract_json(self, text: str) -> Any:
        """
        Try to robustly extract a JSON object from model output.
        Strategies:
        - Try json.loads directly
        - Fall back to extracting the first {...} block
        - If still failing, return None
        """
        text = text.strip()

        # 1) Direct parse
        try:
            return json.loads(text)
        except Exception:
            pass

        # 2) Extract first {...} block using regex (handles extra commentary)
        match = re.search(r"\{(?:.|\n)*\}", text)
        if match:
            candidate = match.group(0)
            try:
                return json.loads(candidate)
            except Exception:
                return None

        return None

    def _validate_and_normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure the parsed data contains required fields with safe types and ranges."""
        # Defaults
        out = {
            "score": 0,
            "correct": False,
            "confidence": 0.0,
            "misconceptions": [],
            "feedback": "The evaluation could not be parsed. Please try again.",
            "next_action": "repeat",
            "parsing_error": False,
        }

        if not isinstance(data, dict):
            out["parsing_error"] = True
            return out

        # score
        try:
            score = int(round(float(data.get("score", 0))))
            score = max(0, min(100, score))
            out["score"] = score
        except Exception:
            out["parsing_error"] = True

        # correct
        out["correct"] = bool(data.get("correct", out["correct"]))

        # confidence
        try:
            conf = float(data.get("confidence", out["confidence"]))
            conf = max(0.0, min(1.0, conf))
            out["confidence"] = conf
        except Exception:
            out["parsing_error"] = True

        # misconceptions
        ms = data.get("misconceptions", [])
        if isinstance(ms, list):
            out["misconceptions"] = [str(x) for x in ms][:10]
        else:
            out["misconceptions"] = [str(ms)]
            out["parsing_error"] = True

        # feedback
        fb = data.get("feedback", "")
        out["feedback"] = str(fb) if fb is not None else out["feedback"]

        # next_action
        na = str(data.get("next_action", out["next_action"]))
        if na not in ("advance", "repeat", "practice"):
            out["next_action"] = "repeat"
            out["parsing_error"] = True
        else:
            out["next_action"] = na

        return out

    def evaluate(self, question: str, student_answer: str, topic: str) -> Dict[str, Any]:
        """
        Evaluate the student's answer using the AI and return a normalized dict.
        """
        prompt = ai_helper.build_evaluation_prompt(question, student_answer, topic)

        messages = [{"role": "user", "content": prompt}]

        # Use a deterministic/low-temperature setting to improve JSON stability
        ai_output = ai_helper.call_ai(messages, max_tokens=250, temperature=0.0)

        parsed = self._safe_extract_json(ai_output)

        if parsed is None:
            return {
                "score": 0,
                "correct": False,
                "confidence": 0.0,
                "misconceptions": [],
                "feedback": "Sorry — the evaluation service couldn't parse the model's response.",
                "next_action": "repeat",
                "parsing_error": True,
                "raw_ai_output": ai_output[:1000],
            }

        normalized = self._validate_and_normalize(parsed)
        normalized["raw_ai_output"] = ai_output[:1000]
        return normalized
