from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib

from app.providers.llm.types import LLMCapabilities, LLMMessage, LLMResponseMode


class PromptFallbackMode(StrEnum):
    NATIVE_TOOL_CALLING = "native_tool_calling"
    STRUCTURED_JSON_PROPOSALS = "structured_json_proposals"
    ADVISOR_ONLY = "advisor_only"


@dataclass(frozen=True)
class AgentProfile:
    key: str
    version: str
    prompt: str
    fallback_mode: PromptFallbackMode = PromptFallbackMode.NATIVE_TOOL_CALLING


@dataclass(frozen=True)
class PromptAssemblyInput:
    profile_key: str
    project_rules: tuple[str, ...] = ()
    experiment_objective: str | None = None
    runtime_context: str | None = None
    user_message: str = ""
    capabilities: LLMCapabilities | None = None


@dataclass(frozen=True)
class PromptAssembly:
    messages: tuple[LLMMessage, ...]
    prompt_versions: dict[str, str]
    fallback_mode: PromptFallbackMode
    deterministic_fingerprint: str


class AgentPromptRegistry:
    global_safety_version = "global-safety.v1"
    base_prompt_version = "factory-agent.v1"

    def __init__(self, profiles: dict[str, AgentProfile] | None = None) -> None:
        self._profiles = profiles or {
            "operator": AgentProfile(
                key="operator",
                version="operator.v1",
                prompt=(
                    "Act as a production copilot for ContentFactory operators. "
                    "Ground claims in provided context, artifacts, tool results, and approvals."
                ),
            ),
            "caption_strategist": AgentProfile(
                key="caption_strategist",
                version="caption-strategist.v1",
                prompt=(
                    "Focus on short-form caption, hashtag, first-comment, "
                    "and edit recommendations. Keep every recommendation tied "
                    "to measurable evidence."
                ),
            ),
        }

    def get_profile(self, key: str) -> AgentProfile:
        try:
            return self._profiles[key]
        except KeyError as exc:
            available = ", ".join(sorted(self._profiles))
            raise ValueError(
                f"Unknown agent profile {key!r}. Available profiles: {available}."
            ) from exc

    @staticmethod
    def fallback_mode_for_capabilities(capabilities: LLMCapabilities) -> PromptFallbackMode:
        mode: LLMResponseMode = capabilities.response_mode()
        return PromptFallbackMode(mode)

    def assemble(self, item: PromptAssemblyInput) -> PromptAssembly:
        profile = self.get_profile(item.profile_key)
        fallback_mode = (
            self.fallback_mode_for_capabilities(item.capabilities)
            if item.capabilities
            else profile.fallback_mode
        )
        messages = (
            LLMMessage(role="system", content=self._global_safety_prompt()),
            LLMMessage(role="system", content=self._base_factory_agent_prompt()),
            LLMMessage(role="system", content=profile.prompt),
            LLMMessage(role="system", content=self._project_rules(item.project_rules)),
            LLMMessage(
                role="system",
                content=self._experiment_objective(item.experiment_objective),
            ),
            LLMMessage(role="system", content=self._runtime_context(item.runtime_context)),
            LLMMessage(role="user", content=item.user_message),
        )
        deterministic_fingerprint = self._fingerprint(
            messages=messages,
            profile=profile,
            fallback_mode=fallback_mode,
        )
        return PromptAssembly(
            messages=messages,
            prompt_versions={
                "global_safety": self.global_safety_version,
                "base": self.base_prompt_version,
                "profile": profile.version,
            },
            fallback_mode=fallback_mode,
            deterministic_fingerprint=deterministic_fingerprint,
        )

    @staticmethod
    def _global_safety_prompt() -> str:
        return (
            "Global safety: never expose provider secrets, never execute shell commands, "
            "and never claim file, render, metric, or artifact facts without supplied evidence."
        )

    @staticmethod
    def _base_factory_agent_prompt() -> str:
        return (
            "Factory Agent: operate through typed backend tools and approval-gated actions. "
            "Prefer read-only inspection before proposing mutations or expensive jobs."
        )

    @staticmethod
    def _project_rules(rules: tuple[str, ...]) -> str:
        if not rules:
            return "Project rules: none supplied."
        normalized = "\n".join(f"- {rule}" for rule in rules)
        return f"Project rules:\n{normalized}"

    @staticmethod
    def _experiment_objective(objective: str | None) -> str:
        return f"Experiment objective: {objective or 'none supplied.'}"

    @staticmethod
    def _runtime_context(context: str | None) -> str:
        return f"Compact runtime context: {context or 'none supplied.'}"

    @staticmethod
    def _fingerprint(
        *,
        messages: tuple[LLMMessage, ...],
        profile: AgentProfile,
        fallback_mode: PromptFallbackMode,
    ) -> str:
        payload_parts = [
            f"profile={profile.key}",
            f"version={profile.version}",
            f"mode={fallback_mode.value}",
        ]
        payload_parts.extend(f"{message.role}:{message.content}" for message in messages)
        payload = "\n".join(payload_parts)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
