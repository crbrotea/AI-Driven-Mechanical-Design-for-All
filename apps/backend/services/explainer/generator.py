"""Streaming generator that turns AnalysisResult into NaturalReport via Gemma."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from services.explainer.cache import ExplainerCache
from services.explainer.domain.errors import (
    ExplainError,
    ExplainErrorCode,
)
from services.explainer.domain.models import NaturalReport
from services.explainer.facts import build_facts
from services.explainer.prompt import build_strict_retry_prompt, build_user_prompt
from services.interpreter.agent.gemma_client import VertexRateLimited, VertexTimeout
from services.interpreter.domain.intent import DesignIntent
from services.physics.domain.models import AnalysisResult


class GemmaTextClient(Protocol):
    def generate_text_streaming(
        self, *, system_prompt: str, user_prompt: str
    ) -> AsyncIterator[str]: ...


class ExplainEvent(BaseModel):
    event: str       # "progress" | "chunk" | "final" | "error"
    data: dict[str, Any]


class Explainer:
    def __init__(
        self,
        *,
        gemma: GemmaTextClient,
        cache: ExplainerCache,
        system_prompt: str,
    ) -> None:
        self._gemma = gemma
        self._cache = cache
        self._system = system_prompt

    async def explain_streaming(
        self, intent: DesignIntent, result: AnalysisResult
    ) -> AsyncIterator[ExplainEvent]:
        key = self._cache.key_for(intent, result)
        cached = self._cache.get(key)
        if cached is not None:
            yield ExplainEvent(
                event="final",
                data={"report": cached.model_dump(), "cache_hit": True, "cache_key": key},
            )
            return

        facts = build_facts(intent, result)
        yield ExplainEvent(event="progress", data={"step": "generating"})

        accumulated = ""
        try:
            async for chunk in self._gemma.generate_text_streaming(
                system_prompt=self._system,
                user_prompt=build_user_prompt(facts),
            ):
                accumulated += chunk
                yield ExplainEvent(event="chunk", data={"text": chunk})
        except VertexTimeout as exc:
            ExplainError(
                code=ExplainErrorCode.GEMMA_TIMEOUT,
                message="Vertex AI streaming timed out",
                retry_after=5,
            ).raise_as()
            raise AssertionError("unreachable") from exc
        except VertexRateLimited as exc:
            ExplainError(
                code=ExplainErrorCode.GEMMA_RATE_LIMITED,
                message=str(exc),
                retry_after=30,
            ).raise_as()
            raise AssertionError("unreachable") from exc
        except Exception as exc:
            ExplainError(
                code=ExplainErrorCode.GEMMA_FAILED,
                message=f"Vertex AI call failed: {exc!r}",
                retry_after=10,
                details={"exception_type": type(exc).__name__},
            ).raise_as()
            raise AssertionError("unreachable") from exc

        yield ExplainEvent(event="progress", data={"step": "parsing"})

        report = await self._parse_or_retry(accumulated, facts)

        self._cache.put(key, report)
        yield ExplainEvent(
            event="final",
            data={"report": report.model_dump(), "cache_hit": False, "cache_key": key},
        )

    async def _parse_or_retry(
        self, first_text: str, facts: dict[str, str]
    ) -> NaturalReport:
        first = _try_parse(first_text)
        if first is not None:
            return first

        retry_text = ""
        try:
            async for chunk in self._gemma.generate_text_streaming(
                system_prompt=self._system,
                user_prompt=build_strict_retry_prompt(facts),
            ):
                retry_text += chunk
        except (VertexTimeout, VertexRateLimited, Exception) as exc:
            ExplainError(
                code=ExplainErrorCode.REPORT_PARSE_FAILED,
                message=f"Retry stream failed: {exc!r}",
                details={"first_text": first_text[:500]},
            ).raise_as()
            raise AssertionError("unreachable") from exc

        second = _try_parse(retry_text)
        if second is not None:
            return second

        ExplainError(
            code=ExplainErrorCode.REPORT_PARSE_FAILED,
            message="Gemma returned malformed JSON twice",
            details={"first_text": first_text[:500], "retry_text": retry_text[:500]},
        ).raise_as()
        raise AssertionError("unreachable")


def _try_parse(text: str) -> NaturalReport | None:
    stripped = _strip_codefence(text)
    try:
        return NaturalReport.model_validate_json(stripped)
    except (ValidationError, json.JSONDecodeError):
        return None


def _strip_codefence(text: str) -> str:
    """Strip ```json ... ``` if the model wrapped JSON in a code fence."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
    if s.startswith("json\n"):
        s = s[5:]
    if s.endswith("```"):
        s = s.rsplit("```", 1)[0]
    return s.strip()
