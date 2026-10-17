"""LLM access (xAI Grok via the OpenAI-compatible API). Optional: every caller has a deterministic fallback,
so the graph features never depend on the LLM being up (and the demo never stalls)."""
from __future__ import annotations

import json
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@lru_cache(maxsize=1)
def _client():
    key = os.getenv("XAI_API_KEY")
    if not key:
        return None
    from openai import OpenAI
    return OpenAI(api_key=key, base_url=os.getenv("XAI_BASE_URL", "https://api.x.ai/v1"), timeout=30)


def available() -> bool:
    return _client() is not None


def chat(system: str, user: str, max_tokens: int = 500, temperature: float = 0.3) -> str | None:
    c = _client()
    if c is None:
        return None
    try:
        r = c.chat.completions.create(model=os.getenv("XAI_MODEL", "grok-4-fast-non-reasoning"),
                                      messages=[{"role": "system", "content": system},
                                                {"role": "user", "content": user}],
                                      max_tokens=max_tokens, temperature=temperature)
        return (r.choices[0].message.content or "").strip() or None
    except Exception as e:
        print("llm error:", str(e)[:200])
        return None


def chat_json(system: str, user: str, max_tokens: int = 900) -> dict | None:
    out = chat(system + "\nRespond with a single JSON object only, no prose, no code fences.", user, max_tokens, 0.2)
    if not out:
        return None
    out = out.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(out)
    except Exception:
        start, end = out.find("{"), out.rfind("}")
        try:
            return json.loads(out[start:end + 1]) if start >= 0 else None
        except Exception:
            return None
