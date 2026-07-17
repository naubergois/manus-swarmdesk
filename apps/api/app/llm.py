"""LLM factory — real providers only (no mocks), with automatic failover."""

from __future__ import annotations

from functools import lru_cache

from fastapi import HTTPException
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings


def _provider_order() -> list[str]:
    preferred = (settings.llm_provider or "auto").lower()
    if preferred != "auto":
        return [preferred]
    order: list[str] = []
    if settings.xai_api_key:
        order.append("xai")
    if settings.gemini_api_key or settings.google_api_key:
        order.append("google")
    if settings.openai_api_key:
        order.append("openai")
    if settings.anthropic_api_key:
        order.append("anthropic")
    return order or ["xai", "google", "openai", "anthropic"]


def _build_provider(name: str) -> BaseChatModel | None:
    if name == "anthropic" and settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.llm_model,
            api_key=settings.anthropic_api_key,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

    if name == "google" and (settings.gemini_api_key or settings.google_api_key):
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.google_model,
            google_api_key=settings.gemini_api_key or settings.google_api_key,
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_tokens,
        )

    if name == "xai" and settings.xai_api_key:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.xai_model,
            api_key=settings.xai_api_key,
            base_url="https://api.x.ai/v1",
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

    if name == "openai" and settings.openai_api_key:
        from langchain_openai import ChatOpenAI

        kwargs: dict = {
            "model": settings.openai_model,
            "api_key": settings.openai_api_key,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
        }
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        return ChatOpenAI(**kwargs)

    return None


def iter_chat_models() -> list[tuple[str, BaseChatModel]]:
    models: list[tuple[str, BaseChatModel]] = []
    for name in _provider_order():
        model = _build_provider(name)
        if model is not None:
            models.append((name, model))
    return models


@lru_cache(maxsize=1)
def get_chat_model() -> BaseChatModel:
    models = iter_chat_models()
    if not models:
        raise HTTPException(
            status_code=503,
            detail=(
                "Nenhuma chave de LLM utilizável. Configure uma de: "
                "XAI_API_KEY, GEMINI_API_KEY/GOOGLE_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY."
            ),
        )
    return models[0][1]


def active_provider_info() -> dict:
    models = iter_chat_models()
    if not models:
        return {"provider": "none", "model": None}
    name, _ = models[0]
    model_name = {
        "google": settings.google_model,
        "anthropic": settings.llm_model,
        "xai": settings.xai_model,
        "openai": settings.openai_model,
    }.get(name, name)
    return {"provider": name, "model": model_name}


def _is_quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "credit balance",
            "resource_exhausted",
            "quota",
            "rate limit",
            "429",
            "insufficient_quota",
            "billing",
        )
    )


async def structured_invoke(schema: type, system: str, human: str):
    """Invoke chat models with structured output, failing over on quota errors."""
    models = iter_chat_models()
    if not models:
        raise HTTPException(
            status_code=503,
            detail="Nenhuma chave de LLM configurada para os agentes.",
        )

    errors: list[str] = []
    for name, llm in models:
        try:
            bound = llm.with_structured_output(schema)
            return await bound.ainvoke(
                [
                    ("system", system),
                    ("human", human),
                ]
            )
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            if _is_quota_error(exc):
                continue
            raise HTTPException(status_code=502, detail=f"Falha LLM ({name}): {exc}") from exc

    raise HTTPException(
        status_code=502,
        detail="Todos os provedores LLM falharam por cota/erro: " + " || ".join(errors[:3]),
    )
