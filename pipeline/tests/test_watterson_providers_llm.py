"""Tests for the raw-API path (``hobbes.watterson.providers.llm``) with any-llm faked.

``any_llm.completion`` is replaced by a fake returning any-llm's own
response types, so no request leaves the machine. The missing-key test runs
the real any-llm path: it fails on the absent key before any client exists.
"""

from __future__ import annotations

import any_llm
import pytest
from any_llm.types.completion import ChatCompletion, ChatCompletionChunk

from hobbes.watterson.providers import Completion, CompletionError, MissingKeyError, Usage, complete, stream


def _completion(text: str) -> ChatCompletion:
    return ChatCompletion.model_validate({
        "id": "c1", "object": "chat.completion", "created": 0, "model": "fake-model",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    })


def _chunk(text: str | None) -> ChatCompletionChunk:
    return ChatCompletionChunk.model_validate({
        "id": "c1", "object": "chat.completion.chunk", "created": 0, "model": "fake-model",
        "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
    })


@pytest.fixture
def fake(monkeypatch):
    calls = []

    def completion(model, messages, **kwargs):
        calls.append({"model": model, "messages": messages, **kwargs})
        if kwargs.get("stream"):
            return iter([_chunk("Hel"), _chunk(None), _chunk("lo")])
        return _completion("Hello")

    monkeypatch.setattr(any_llm, "completion", completion)
    return calls


class TestComplete:
    def test_returns_text_finish_reason_and_usage(self, fake):
        result = complete("anthropic:some-model", "hi")
        assert result == Completion("Hello", "fake-model", "stop", Usage(3, 2))
        (call,) = fake
        assert call["model"] == "anthropic:some-model" and call["stream"] is False
        assert call["messages"] == [{"role": "user", "content": "hi"}]

    def test_system_and_set_options_are_passed_and_unset_ones_omitted(self, fake):
        complete("openai:m", "hi", system="be brief", max_tokens=10)
        (call,) = fake
        assert call["messages"][0] == {"role": "system", "content": "be brief"}
        assert call["max_tokens"] == 10
        assert "temperature" not in call and "timeout" not in call

    def test_a_chat_history_is_sent_as_given(self, fake):
        history = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"},
                   {"role": "user", "content": "c"}]
        complete("openai:m", history)
        assert fake[0]["messages"] == history


class TestStream:
    def test_yields_text_deltas_and_skips_empty_ones(self, fake):
        assert list(stream("openai:m", "hi")) == ["Hel", "lo"]
        assert fake[0]["stream"] is True

    def test_an_error_mid_stream_is_ours(self, monkeypatch):
        def chunks():
            yield _chunk("a")
            raise any_llm.RateLimitError("slow down", provider_name="openai")

        monkeypatch.setattr(any_llm, "completion", lambda *a, **k: chunks())
        out = []
        with pytest.raises(CompletionError, match="slow down"):
            for text in stream("openai:m", "hi"):
                out.append(text)
        assert out == ["a"]


class TestErrors:
    @pytest.mark.parametrize(
        "model, env_var",
        [("anthropic:some-model", "ANTHROPIC_API_KEY"), ("openai:some-model", "OPENAI_API_KEY")],
    )
    def test_a_missing_key_names_the_variable(self, monkeypatch, model, env_var):
        monkeypatch.delenv(env_var, raising=False)
        with pytest.raises(MissingKeyError) as info:
            complete(model, "hi")
        assert info.value.env_var == env_var
        assert str(info.value) == f"no API key for {model.split(':')[0]}: set {env_var} in the environment"
        with pytest.raises(MissingKeyError):
            list(stream(model, "hi"))

    def test_a_model_without_a_provider_is_refused(self):
        with pytest.raises(CompletionError, match="Expected 'provider:model'"):
            complete("just-a-model", "hi")

    def test_an_unknown_provider_is_refused(self):
        with pytest.raises(CompletionError, match="not a supported provider"):
            complete("no-such-provider:m", "hi")
