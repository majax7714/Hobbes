"""The provider layer's own exceptions.

Callers catch these, never the ACP SDK's or any-llm's, so a version bump of
either library stays inside the one module that wraps it (DEC-004).
"""

from __future__ import annotations


class ProviderError(Exception):
    """Base for every error the provider layer raises."""


class UnknownAgentError(ProviderError):
    """No agent of that name is in the registry."""


class AgentError(ProviderError):
    """An ACP agent failed to start, answer, or stay connected.

    ``stderr_tail`` holds the agent's last stderr lines, when it wrote any,
    because that is usually where a harness says what went wrong.
    """

    def __init__(self, message: str, *, stderr_tail: str = "") -> None:
        self.stderr_tail = stderr_tail
        if stderr_tail:
            message = f"{message}\n--- agent stderr (last lines) ---\n{stderr_tail}"
        super().__init__(message)


class CompletionError(ProviderError):
    """A raw model API call failed."""


class MissingKeyError(CompletionError):
    """The provider's API key is not set; ``env_var`` names the variable."""

    def __init__(self, provider: str, env_var: str) -> None:
        self.provider = provider
        self.env_var = env_var
        super().__init__(f"no API key for {provider}: set {env_var} in the environment")
