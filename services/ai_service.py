"""AI chat service with Gemini primary + Groq fallback + streaming."""

from __future__ import annotations

import logging
import random
from collections.abc import AsyncGenerator

from openai import OpenAI as GroqClient
from google import genai
from google.genai import types as gemini_types

from config import settings
from app_state import simulation_engine

logger = logging.getLogger(__name__)

# Groq model rotation state
_groq_index = 0
MAX_HISTORY_CHARS = 4000
SUGGESTION_POOL = [
    "How's my current route looking?",
    "What disruptions are ahead?",
    "Summarize my trip status",
    "Are there any delays on my route?",
    "What's the best next action for me?",
]

def _build_context(vehicle_id: int | None = None) -> str:
    metrics = simulation_engine.current_metrics
    lines = [
        "You are the SOLV Ops Assistant, an expert supply chain AI.",
        "You provide clear, concise, actionable answers to drivers and operators.",
        "Current Status:",
        f"- SLA Compliance: {metrics.on_time_delivery_pct}%",
        f"- Active Vehicles: {metrics.active_trucks}",
        f"- Queued Vehicles: {metrics.queued_trucks}",
        f"- CO2 Saved: {metrics.co2_saved_kg} kg",
        f"- Warehouse Utilization: {metrics.warehouse_utilization_pct}%",
        f"- Reroutes today: {metrics.reroute_count}",
        f"- Stockouts prevented: {metrics.stockouts_prevented}",
    ]

    if vehicle_id is not None:
        vehicle = simulation_engine.vehicles.get(vehicle_id)
        if vehicle:
            lines.extend([
                f"\nYour Vehicle ({vehicle.identifier}):",
                f"- Status: {vehicle.status}",
                f"- Payload: {vehicle.payload_units} units",
                f"- Progress: {vehicle.progress_pct:.1f}%",
                f"- Current Facility: {vehicle.current_facility_id}",
                f"- Driver: {vehicle.driver_name or 'N/A'}",
            ])

    return "\n".join(lines)


def _cap_history(history: list[dict[str, str]] | None) -> list[dict[str, str]]:
    if not history:
        return []
    total = 0
    capped = []
    for msg in reversed(history):
        total += len(msg.get("content", ""))
        if total > MAX_HISTORY_CHARS:
            break
        capped.insert(0, msg)
    return capped


def _pick_suggestions(response_text: str) -> list[str]:
    return random.sample(SUGGESTION_POOL, min(3, len(SUGGESTION_POOL)))


def _next_groq_model() -> str:
    global _groq_index
    models = settings.groq_models
    if not models:
        return "llama-3.3-70b-versatile"
    model = models[_groq_index % len(models)]
    _groq_index += 1
    return model


def _is_rate_limited(err: Exception) -> bool:
    msg = str(err).lower()
    keywords = ["429", "resource exhausted", "rate limit", "too many requests",
                 "quota", "insufficient tokens", "429 too many requests"]
    return any(k in msg for k in keywords)


# ── Gemini (primary) ──

async def _stream_gemini(query: str, history: list[dict[str, str]], context: str
                         ) -> AsyncGenerator[dict, None]:
    client = genai.Client(api_key=settings.gemini_api_key)
    messages = [
        gemini_types.Content(role="user", parts=[gemini_types.Part.from_text(text=context)]),
        gemini_types.Content(role="model", parts=[gemini_types.Part.from_text(
            text="I am ready to assist. What is your question?")]),
    ]
    for msg in history:
        messages.append(gemini_types.Content(
            role=msg.get("role", "user"),
            parts=[gemini_types.Part.from_text(text=msg.get("content", ""))],
        ))
    messages.append(gemini_types.Content(
        role="user", parts=[gemini_types.Part.from_text(text=query)]))

    stream = client.models.generate_content_stream(
        model="gemini-2.5-flash",
        contents=messages,
        config=gemini_types.GenerateContentConfig(temperature=0.3),
    )
    full = ""
    for chunk in stream:
        if chunk.text:
            full += chunk.text
            yield {"type": "chunk", "content": chunk.text}

    yield {"type": "meta", "model": "gemini-2.5-flash", "suggestions": _pick_suggestions(full)}
    yield {"type": "done"}


# ── Groq (fallback) ──

async def _stream_groq(query: str, history: list[dict[str, str]], context: str
                        ) -> AsyncGenerator[dict, None]:
    model = _next_groq_model()
    client = GroqClient(api_key=settings.groq_api_key, base_url="https://api.groq.com/openai/v1")

    messages = [{"role": "system", "content": context}]
    for msg in history:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": query})

    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            stream=True,
        )
        full = ""
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                full += delta
                yield {"type": "chunk", "content": delta}

        yield {"type": "meta", "model": f"groq/{model}", "suggestions": _pick_suggestions(full)}
        yield {"type": "done"}
    except Exception as e:
        logger.warning("Groq model %s failed: %s", model, e)
        raise


# ── Public entry point ──

async def chat_stream(query: str,
                      history: list[dict[str, str]] | None = None,
                      vehicle_id: int | None = None) -> AsyncGenerator[dict, None]:
    """
    Stream a chat response. Yields SSE-serializable dicts:
      {"type": "chunk", "content": "..."}
      {"type": "meta", "model": "...", "suggestions": [...]}
      {"type": "done"}
      {"type": "error", "detail": "..."}
    """
    context = _build_context(vehicle_id)
    capped_history = _cap_history(history)

    # Try Gemini first
    if settings.gemini_api_key:
        try:
            async for event in _stream_gemini(query, capped_history, context):
                yield event
            return
        except Exception as e:
            if _is_rate_limited(e):
                logger.warning("Gemini rate limited, falling back to Groq: %s", e)
            else:
                logger.error("Gemini error (non-rate-limit): %s", e)
                # Non-rate-limit errors from Gemini should still try fallback
                if not settings.groq_api_key:
                    yield {"type": "error", "detail": f"AI service error: {e}"}
                    return

    # Fallback: Groq
    if settings.groq_api_key:
        errors = []
        models_to_try = settings.groq_models or ["llama-3.3-70b-versatile"]
        # Try up to 3 different Groq models
        for attempt in range(min(3, len(models_to_try))):
            try:
                async for event in _stream_groq(query, capped_history, context):
                    yield event
                return
            except Exception as e:
                logger.warning("Groq attempt %d failed: %s", attempt + 1, e)
                errors.append(str(e))
                if not _is_rate_limited(e):
                    break  # non-rate-limit error, don't retry

        yield {"type": "error", "detail": f"All AI providers unavailable. Last error: {errors[-1] if errors else 'Unknown'}"}
        return

    yield {"type": "error", "detail": "No AI providers configured. Set GEMINI_API_KEY or GROQ_API_KEY."}
