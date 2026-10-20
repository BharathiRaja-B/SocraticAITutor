"""
ai_helper.py — All AI-related logic: prompts, API calls, topic detection.
This module talks to OpenRouter and returns text responses.
"""

import os
import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Default free model on OpenRouter. Change this to another valid free slug if desired.
# See https://openrouter.ai/models?q=free for supported free endpoints.
MODEL = "openrouter/free"


def call_ai(messages: list, max_tokens: int = 600, temperature: float = 0.7) -> str:
    """
    Send a list of chat messages to OpenRouter and return the reply text.
    messages format: [{"role": "system"|"user"|"assistant", "content": "..."}]
    """
    if not OPENROUTER_API_KEY:
        return "⚠️ AI is not configured. Please set OPENROUTER_API_KEY in your .env file."

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "AI Personal Tutor",
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    try:
        response = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") if isinstance(data, dict) else None
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            return "⚠️ Unexpected response from AI service."

        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            return "⚠️ The AI returned an empty response. Please try again."

        return content.strip()
    except requests.exceptions.Timeout:
        return "⚠️ The AI took too long to respond. Please try again."
    except requests.exceptions.RequestException as e:
        return f"⚠️ Could not reach the AI service: {str(e)}"
    except (KeyError, IndexError):
        return "⚠️ Unexpected response from AI service."


# ─── Prompt Builders ─────────────────────────────────────────────────────────

def build_tutor_system_prompt(topic: str, memory_summary: str) -> str:
    """
    Returns the system prompt for the Socratic tutor.
    The AI guides students with questions instead of handing them answers.
    """
    memory_section = ""
    if memory_summary:
        memory_section = f"\n\nContext from previous sessions:\n{memory_summary}"

    return f"""You are a patient, encouraging AI tutor specializing in {topic or 'general learning'}.
Your teaching style is Socratic — you guide students to discover answers themselves.

Rules you MUST follow:
1. Never give the full answer immediately. Start with a small explanation or analogy.
2. Ask one guiding question to get the student thinking.
3. When they respond, give brief feedback and ask a follow-up question.
4. Only reveal the full answer after at least 2 exchanges, or if the student asks directly.
5. Keep your responses concise and friendly (3–6 sentences max per turn).
6. Use simple language suitable for a beginner.
7. Celebrate small wins ("Great thinking!", "Exactly right!").
8. If the student is stuck, offer a small nudge — not the answer.{memory_section}

Current topic being studied: {topic or 'not yet determined'}"""


def build_hint_prompt(question: str, hint_level: int, topic: str) -> str:
    """
    Returns a prompt for generating a progressive hint.
    hint_level: 1 = concept hint, 2 = method hint, 3 = detailed hint
    """
    level_descriptions = {
        1: "a concept hint — remind them of the core idea or concept involved, without mentioning how to solve it",
        2: "a method hint — suggest the approach or technique they should use, but not the exact steps",
        3: "a detailed hint — walk them through the steps in plain language, but still let them write the final answer",
    }

    description = level_descriptions.get(hint_level, level_descriptions[1])

    return f"""A student is learning about {topic or 'programming'} and needs help with this question:

"{question}"

Give them {description}. Keep the hint to 2–4 sentences. Be encouraging."""


def build_summary_prompt(chat_history: list, topic: str) -> str:
    """
    Returns a prompt to summarize what a student learned in a session.
    chat_history: list of dicts with 'role' and 'message' keys
    """
    # Format the last 20 messages for the summary
    history_text = "\n".join(
        f"{msg['role'].upper()}: {msg['message']}"
        for msg in chat_history[-20:]
    )

    return f"""Here is a tutoring session transcript about {topic or 'various topics'}:

{history_text}

Write a brief session summary with exactly these three sections:
1. Topics Learned: (bullet list of concepts covered)
2. Needs Practice: (bullet list of areas where the student struggled)
3. Recommended Next Topic: (one suggested topic to study next)

Keep the summary concise and helpful. Use plain language."""


# ─── Topic Detection ──────────────────────────────────────────────────────────

# Simple keyword-based topic detector — no AI needed for this
TOPIC_KEYWORDS = {
    "Python": ["python", "def ", "list", "dictionary", "loop", "function", "class", "import", "pip", "pandas", "numpy"],
    "JavaScript": ["javascript", "js", "const ", "let ", "var ", "arrow function", "promise", "async", "dom", "react", "node"],
    "HTML/CSS": ["html", "css", "div", "span", "flexbox", "grid", "selector", "tag", "element", "style"],
    "SQL": ["sql", "select", "insert", "update", "delete", "join", "table", "database", "query", "where"],
    "Data Structures": ["array", "linked list", "stack", "queue", "tree", "graph", "hash", "binary search", "sorting", "algorithm"],
    "Machine Learning": ["machine learning", "ml", "neural network", "model", "training", "dataset", "classification", "regression"],
    "DBMS": ["dbms", "database management", "normalization", "er diagram", "acid", "transaction", "index"],
    "Java": ["java", "public class", "main method", "jvm", "spring", "maven"],
    "C/C++": ["c++", "c language", "pointer", "malloc", "struct", "#include", "iostream"],
    "React": ["react", "component", "props", "state", "hook", "usestate", "useeffect", "jsx"],
    "Math": ["calculus", "algebra", "geometry", "equation", "derivative", "integral", "matrix", "probability"],
}


def detect_topic(text: str) -> str:
    """
    Detect the topic from a piece of text using keyword matching.
    Returns the detected topic name, or empty string if nothing matched.
    """
    text_lower = text.lower()
    scores = {}

    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[topic] = score

    if not scores:
        return ""

    # Return the topic with the highest keyword match score
    return max(scores, key=scores.get)


# ─── Main AI Functions ────────────────────────────────────────────────────────

def get_tutor_response(user_message: str, chat_history: list, topic: str, memory_summary: str) -> str:
    """
    Get a Socratic tutor response for a student's message.

    user_message: the student's latest message
    chat_history: list of previous messages [{"role": "user"|"assistant", "content": "..."}]
    topic: current detected topic
    memory_summary: summary from the last session (if any)
    """
    system_prompt = build_tutor_system_prompt(topic, memory_summary)

    # Build the messages list: system + recent history + new message
    messages = [{"role": "system", "content": system_prompt}]

    # Include last 10 chat messages for context (to stay within token limits)
    for msg in chat_history[-10:]:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["message"]})

    messages.append({"role": "user", "content": user_message})

    return call_ai(messages, max_tokens=500)


def get_hint(question: str, hint_level: int, topic: str) -> str:
    """
    Get a progressive hint for a student's question.
    hint_level: 1, 2, or 3
    """
    prompt = build_hint_prompt(question, hint_level, topic)
    messages = [{"role": "user", "content": prompt}]
    return call_ai(messages, max_tokens=200)


def generate_session_summary(chat_history: list, topic: str) -> str:
    """
    Generate a session summary from the chat history.
    Returns the summary as a plain text string.
    """
    if not chat_history:
        return "No messages in this session to summarize."

    prompt = build_summary_prompt(chat_history, topic)
    messages = [{"role": "user", "content": prompt}]
    return call_ai(messages, max_tokens=300)


def build_evaluation_prompt(question: str, student_answer: str, topic: str) -> str:
    """
    Build a strict evaluation prompt that instructs the model to return ONLY JSON
    with the following schema:

    {
        "score": 0-100,
        "correct": true|false,
        "confidence": 0-1,
        "misconceptions": [...],
        "feedback": "",
        "next_action": "advance|repeat|practice"
    }

    The prompt emphasizes strict JSON-only output and provides a short example.
    """
    return f"""You are an objective grading assistant for student answers in the topic '{topic or 'General'}'.

Evaluate the student's answer to the question and produce ONLY a single valid JSON object (no extra text).

Required JSON schema:
{{
  "score": integer (0-100),
  "correct": boolean,
  "confidence": number (0.0-1.0),
  "misconceptions": array of short strings describing any incorrect beliefs (empty array if none),
  "feedback": short constructive feedback for the student (1-3 sentences),
  "next_action": one of "advance", "repeat", or "practice"
}}

Be concise. Do NOT include any commentary or markdown. Only return the JSON object.

Question: "{question}"
Student Answer: "{student_answer}"

Example output:
{{"score":85,"correct":true,"confidence":0.82,"misconceptions":[],"feedback":"Good work — you used the right method. Clarify the edge case where x=0.","next_action":"advance"}}
"""
