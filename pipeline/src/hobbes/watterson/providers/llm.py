"""Plain calls to raw model APIs through any-llm: one completion, or a stream.

The only module that imports any-llm (``any-llm-sdk``, pinned in pyproject
per DEC-004). Models are named ``provider:model`` (``anthropic:…``,
``openai:…``); keys come from the provider's usual environment variable
(``ANTHROPIC_API_KEY``, ``OPENAI_API_KEY``). There are no tools and no loop:
one request in, text out (DEC-004).

Only the anthropic and openai SDK extras are installed; another provider
fails with a ``CompletionError`` naming the missing extra.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import any_llm

from hobbes.watterson.providers.errors import CompletionError, MissingKeyError

#: A prompt is either the user's text or a full chat history of
#: ``{"role": ..., "content": ...}`` messages.
Prompt = str | Sequence[Mapping[str, str]]


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class Completion:
    """A finished reply. ``finish_reason`` is the provider's, normalized by
    any-llm to OpenAI's names (stop, length, …)."""

    text: str
    model: str
    finish_reason: str | None
    usage: Usage | None


def _messages(prompt: Prompt, system: str | None) -> list[dict[str, str]]:
    history = [{"role": "user", "content": prompt}] if isinstance(prompt, str) else [dict(m) for m in prompt]
    return ([{"role": "system", "content": system}] if system else []) + history


def _call(model: str, prompt: Prompt, *, stream: bool, system: str | None, **params: Any) -> Any:
    """Call any-llm, turning its failures into ours."""
    options = {k: v for k, v in params.items() if v is not None}
    try:
        return any_llm.completion(model, _messages(prompt, system), stream=stream, **options)
    except Exception as exc:  # noqa: BLE001 — every failure leaves as ours
        raise _translate(exc, model) from exc


def _translate(exc: Exception, model: str) -> CompletionError:
    if isinstance(exc, any_llm.MissingApiKeyError):
        return MissingKeyError(exc.provider_name or model.split(":", 1)[0], exc.env_var_name)
    if isinstance(exc, CompletionError):
        return exc
    if isinstance(exc, ImportError):
        provider = model.split(":", 1)[0]
        return CompletionError(
            f"{model}: the {provider!r} provider's SDK is not installed "
            f"(only the anthropic and openai extras are): {exc}"
        )
    if isinstance(exc, any_llm.AnyLLMError | ValueError):
        return CompletionError(f"{model}: {exc}")
    return CompletionError(f"{model}: {type(exc).__name__}: {exc}")


def complete(
    model: str,
    prompt: Prompt,
    *,
    system: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    timeout: float | None = None,
) -> Completion:
    """Send *prompt* to *model* (``provider:model``) and return the reply."""
    response = _call(
        model, prompt, stream=False, system=system,
        max_tokens=max_tokens, temperature=temperature, timeout=timeout,
    )
    choice = response.choices[0] if response.choices else None
    usage = response.usage
    return Completion(
        text=(choice.message.content or "") if choice else "",
        model=response.model,
        finish_reason=choice.finish_reason if choice else None,
        usage=Usage(usage.prompt_tokens, usage.completion_tokens) if usage else None,
    )


def stream(
    model: str,
    prompt: Prompt,
    *,
    system: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    timeout: float | None = None,
) -> Iterator[str]:
    """Send *prompt* to *model* and yield the reply's text as it arrives."""
    chunks = _call(
        model, prompt, stream=True, system=system,
        max_tokens=max_tokens, temperature=temperature, timeout=timeout,
    )
    try:
        for chunk in chunks:
            for choice in chunk.choices:
                if choice.delta and choice.delta.content:
                    yield choice.delta.content
    except Exception as exc:  # noqa: BLE001
        raise _translate(exc, model) from exc
    finally:
        close = getattr(chunks, "close", None)
        if close is not None:
            close()
