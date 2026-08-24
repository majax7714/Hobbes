"""RepeatGuardAgent — mini-swe-agent's DefaultAgent plus ADR-079's repeat
refusal. Select with `agent.agent_class: hobbesmini.RepeatGuardAgent`
and tune with `agent.max_repeats` (default 3; 0 = refuse but never exit)."""
from hobbesmini.guard import (  # noqa: F401
    REFUSAL, commit_on_exit_command, context_as_tool_exchange, repeat_verdict, split_context,
)

try:
    from minisweagent.agents.default import AgentConfig, DefaultAgent
except ImportError:  # pure-function use outside the container
    AgentConfig = DefaultAgent = None  # type: ignore[assignment]

if DefaultAgent is not None:

    class RepeatGuardConfig(AgentConfig):
        max_repeats: int = 3
        #: "prompt" leaves the aid where Pier rendered it (markers stripped);
        #: "observation" re-shapes it as the agent's first tool exchange (C-56).
        hobbes_context_shape: str = "prompt"

    class RepeatGuardAgent(DefaultAgent):
        def __init__(self, *args, config_class=RepeatGuardConfig, **kwargs):
            super().__init__(*args, config_class=config_class, **kwargs)
            self._last_command: str | None = None
            self._repeat_streak = 0
            self.repeats_refused = 0
            self.commit_on_exit: str | None = None
            self.hobbes_context_shape: str | None = None

        def add_messages(self, *messages: dict) -> list[dict]:
            out = []
            for msg in messages:
                if msg.get("role") == "user" and not getattr(self, "_context_done", False) and "<<<HOBBES_CONTEXT>>>" in (msg.get("content") or ""):
                    self._context_done = True
                    task, aid = split_context(msg["content"])
                    msg = dict(msg, content=task)
                    out.extend(super().add_messages(msg))
                    if aid and self.config.hobbes_context_shape == "observation":
                        native = "textbased" not in type(self.model).__name__.lower()
                        out.extend(super().add_messages(*context_as_tool_exchange(aid, native)))
                        self.hobbes_context_shape = "observation"
                    elif aid:
                        out.extend(super().add_messages({"role": "user", "content": aid, "extra": {"hobbes_context": True}}))
                        self.hobbes_context_shape = "prompt"
                    continue
                out.extend(super().add_messages(msg))
            return out

        def execute_actions(self, message: dict) -> list[dict]:
            actions = message.get("extra", {}).get("actions", [])
            command = actions[0].get("command", "") if len(actions) == 1 else None
            if command is not None:
                refuse, self._repeat_streak, stop = repeat_verdict(
                    self._last_command, command, self._repeat_streak, self.config.max_repeats
                )
                self._last_command = command
                if refuse:
                    self.repeats_refused += 1
                    outputs = [{"output": REFUSAL.format(n=self._repeat_streak), "returncode": 1, "exception_info": ""}]
                    added = self.add_messages(
                        *self.model.format_observation_messages(message, outputs, self.get_template_vars())
                    )
                    if stop:
                        self.add_messages({
                            "role": "exit",
                            "content": "RepeatedActionError",
                            "extra": {"exit_status": "RepeatedActionError", "submission": "",
                                      "repeats_refused": self.repeats_refused},
                        })
                    return added
            return super().execute_actions(message)

        def run(self, *args, **kwargs):
            """DefaultAgent.run plus commit-on-exit (ADR-080): whatever ends
            the loop — submission, limits, a context-window 400 — leftover
            edits are committed so the verifier's collect hook sees them.
            A hard kill from outside (Pier's agent timeout) cannot be caught."""
            try:
                return super().run(*args, **kwargs)
            finally:
                reason = (self.messages[-1].get("extra", {}) if self.messages else {}).get("exit_status", "exit")
                try:
                    result = self.env.execute({"command": commit_on_exit_command(str(reason))})
                    self.commit_on_exit = (result.get("output") or "").strip()[-40:]
                except Exception as exc:  # never mask the run's own outcome
                    self.commit_on_exit = f"failed: {exc}"[:120]
                try:
                    self.save(self.config.output_path)
                except Exception:
                    pass

        def serialize(self, *extra_dicts) -> dict:
            data = super().serialize(*extra_dicts)
            stats = data["info"].setdefault("model_stats", {})
            stats["repeats_refused"] = self.repeats_refused
            stats["commit_on_exit"] = getattr(self, "commit_on_exit", None)
            stats["hobbes_context_shape"] = getattr(self, "hobbes_context_shape", None)
            return data
