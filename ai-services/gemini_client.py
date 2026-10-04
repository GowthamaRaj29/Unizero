"""Minimal Gemini API client for the AI-service integration points."""

from __future__ import annotations

import os

import requests


class GeminiAPIError(Exception):
    """Raised when a Gemini request cannot be completed or parsed."""


def normalize_model_json(text: str) -> str:
    """Remove optional Markdown fences from a model JSON response."""
    normalized = text.strip()
    if normalized.startswith("```"):
        normalized = normalized.split("\n", 1)[1] if "\n" in normalized else normalized[3:]
        if normalized.rstrip().endswith("```"):
            normalized = normalized.rstrip()[:-3].rstrip()
    return normalized


def generate_text(system_prompt: str, user_prompt: str, max_tokens: int) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise GeminiAPIError("GEMINI_API_KEY is not set in the environment")

    preferred = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
    candidates = [
        preferred,
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
        "gemma-4-26b-a4b-it",
        "gemma-4-31b-it",
    ]
    seen = set()
    models_to_try = [m for m in candidates if not (m in seen or seen.add(m))]

    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    last_error = None
    for model in models_to_try:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        try:
            response = requests.post(
                url,
                params={"key": api_key},
                json=payload,
                timeout=45,
            )
            if response.status_code == 429:
                last_error = f"Model {model} rate-limited (429)"
                continue
            response.raise_for_status()
            data = response.json()
            text = "".join(
                part.get("text", "")
                for part in data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [])
            )
            if text:
                return text
        except (requests.RequestException, ValueError, IndexError, KeyError) as exc:
            last_error = exc
            continue

    raise GeminiAPIError(f"All Gemini models exhausted. Last error: {last_error}")
