"""The one place PaperCrew talks to an LLM.

There is no demo or simulated mode: without an OpenRouter API key the app
refuses to create companies or run work, and says so. Tests stub the two
functions in this module (and `crew_runner.invoke_crew`) so they never reach
the network while every other code path runs for real.
"""
import json
import os
import re

import httpx

from .db import CompanyRow, SessionLocal, SettingRow

DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
REQUEST_TIMEOUT = 180.0


class LLMNotConfigured(RuntimeError):
    """No OpenRouter API key available."""


class LLMError(RuntimeError):
    """The model call failed or returned something unusable."""


def get_setting(db, key: str, default: str = "") -> str:
    row = db.get(SettingRow, key)
    return row.value if row and row.value else default


def get_api_key(db=None) -> str:
    """Stored key first, then OPENROUTER_API_KEY from the environment."""
    if db is not None:
        stored = get_setting(db, "openrouter_api_key")
        if stored:
            return stored
        return os.getenv("OPENROUTER_API_KEY", "")
    session = SessionLocal()
    try:
        return get_api_key(session)
    finally:
        session.close()


def api_key_configured() -> bool:
    return bool(get_api_key())


def require_api_key(db=None) -> str:
    key = get_api_key(db)
    if not key:
        raise LLMNotConfigured(
            "No OpenRouter API key configured. Add one in Settings "
            "(get a free key at https://openrouter.ai/keys)."
        )
    return key


def resolve_model(db, company_id: int = 0, agent_model: str = "") -> str:
    """Agent override → company override → global default → built-in default."""
    company = db.get(CompanyRow, company_id) if company_id else None
    return (
        agent_model
        or (company.default_model if company and company.default_model else "")
        or get_setting(db, "default_model", "")
        or DEFAULT_MODEL
    )


def call_text(prompt: str, max_tokens: int = 1024, company_id: int = 0) -> str:
    """One completion from OpenRouter. Raises if unconfigured or failing."""
    db = SessionLocal()
    try:
        api_key = require_api_key(db)
        model = resolve_model(db, company_id)
    finally:
        db.close()

    try:
        response = httpx.post(
            f"{OPENROUTER_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            },
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise LLMError(f"Could not reach OpenRouter: {exc}") from exc

    if response.status_code >= 400:
        raise LLMError(f"OpenRouter returned {response.status_code}: {response.text[:300]}")
    try:
        return response.json()["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMError(f"Unexpected OpenRouter response: {response.text[:300]}") from exc


def _strip_fences(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    return fenced.group(1) if fenced else text


def call_json(prompt: str, max_tokens: int = 1500, company_id: int = 0, as_list: bool = False):
    """Completion parsed as JSON. Models often wrap JSON in prose or fences,
    so we strip fences and fall back to the outermost object/array."""
    raw = _strip_fences(call_text(prompt, max_tokens, company_id))
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    pattern = r"\[.*\]" if as_list else r"\{.*\}"
    match = re.search(pattern, raw, re.DOTALL)
    if not match:
        raise LLMError(f"Model did not return JSON: {raw[:300]}")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMError(f"Model returned malformed JSON: {match.group(0)[:300]}") from exc
