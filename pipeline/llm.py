"""Provider-flexible LLM helper used across pipeline stages.

Picks a backend based on which key is present in .env:
  * GROQ_API_KEY      -> Groq (OpenAI-compatible API; default model llama-3.3-70b)
  * ANTHROPIC_API_KEY -> Claude

Both return plain text via a single `complete()` call, so classify.py / filter_relevant.py
don't care which provider is active. Override models with GROQ_MODEL / ANTHROPIC_MODEL.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"


def active_provider() -> str:
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    raise SystemExit(
        "No LLM key found. Add GROQ_API_KEY (or ANTHROPIC_API_KEY) to .env."
    )


def model_name() -> str:
    if active_provider() == "groq":
        return os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    return os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)


def complete(
    prompt: str,
    max_tokens: int = 1024,
    temperature: float = 0.0,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> str:
    """Send a single user prompt, return the model's text response.

    `model` overrides the env default for this call (lets each pipeline stage pick a
    model — e.g. a stronger one for theme coding). `reasoning_effort` ("low"/"medium"/
    "high") applies to Groq reasoning models like gpt-oss to cap thinking-token spend.
    """
    provider = active_provider()
    chosen = model or model_name()

    if provider == "groq":
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("GROQ_API_KEY"), base_url=GROQ_BASE_URL)
        # reasoning_effort is only valid for reasoning models (gpt-oss); ignore otherwise
        extra = (
            {"reasoning_effort": reasoning_effort}
            if reasoning_effort and "gpt-oss" in chosen
            else {}
        )
        resp = client.chat.completions.create(
            model=chosen,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
            extra_body=extra,
        )
        return resp.choices[0].message.content or ""

    import anthropic

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    resp = client.messages.create(
        model=chosen if model else DEFAULT_ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text
