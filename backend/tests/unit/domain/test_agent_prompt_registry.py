from __future__ import annotations

import pytest

from app.domain.services.agent_prompt_registry import (
    AgentPromptRegistry,
    PromptAssemblyInput,
    PromptFallbackMode,
)
from app.providers.llm.types import LLMCapabilities


def test_prompt_registry_assembles_messages_in_deterministic_order() -> None:
    registry = AgentPromptRegistry()

    assembly = registry.assemble(
        PromptAssemblyInput(
            profile_key="operator",
            project_rules=("Never publish directly.", "Cite artifact IDs."),
            experiment_objective="Improve first two second retention.",
            runtime_context="campaign=neon-relic; artifact=artifact-1",
            user_message="What should I do next?",
        )
    )

    assert [message.role for message in assembly.messages] == [
        "system",
        "system",
        "system",
        "system",
        "system",
        "system",
        "user",
    ]
    assert assembly.messages[0].content.startswith("Global safety:")
    assert assembly.messages[1].content.startswith("Factory Agent:")
    assert "production copilot" in assembly.messages[2].content
    assert assembly.messages[3].content == (
        "Project rules:\n- Never publish directly.\n- Cite artifact IDs."
    )
    assert assembly.messages[4].content == (
        "Experiment objective: Improve first two second retention."
    )
    assert assembly.messages[5].content == (
        "Compact runtime context: campaign=neon-relic; artifact=artifact-1"
    )
    assert assembly.messages[6].content == "What should I do next?"
    assert assembly.prompt_versions == {
        "global_safety": "global-safety.v1",
        "base": "factory-agent.v1",
        "profile": "operator.v1",
    }
    assert assembly.fallback_mode == PromptFallbackMode.NATIVE_TOOL_CALLING
    assert len(assembly.deterministic_fingerprint) == 64


def test_prompt_registry_uses_explicit_empty_context_placeholders() -> None:
    registry = AgentPromptRegistry()

    assembly = registry.assemble(PromptAssemblyInput(profile_key="caption_strategist"))

    assert assembly.messages[3].content == "Project rules: none supplied."
    assert assembly.messages[4].content == "Experiment objective: none supplied."
    assert assembly.messages[5].content == "Compact runtime context: none supplied."
    assert assembly.messages[6].content == ""
    assert assembly.prompt_versions["profile"] == "caption-strategist.v1"


def test_prompt_registry_fingerprint_is_stable_for_same_inputs() -> None:
    registry = AgentPromptRegistry()

    first = registry.assemble(
        PromptAssemblyInput(profile_key="operator", user_message="Check next action")
    )
    second = registry.assemble(
        PromptAssemblyInput(profile_key="operator", user_message="Check next action")
    )

    assert first.deterministic_fingerprint == second.deterministic_fingerprint


def test_prompt_registry_downgrades_assembly_mode_for_weak_provider() -> None:
    registry = AgentPromptRegistry()

    assembly = registry.assemble(
        PromptAssemblyInput(
            profile_key="operator",
            capabilities=LLMCapabilities(
                supports_tools=False,
                supports_vision=False,
                supports_structured_output=True,
            ),
            user_message="Draft safe actions.",
        )
    )

    assert assembly.fallback_mode == PromptFallbackMode.STRUCTURED_JSON_PROPOSALS


@pytest.mark.parametrize(
    ("capabilities", "expected"),
    [
        (LLMCapabilities(True, False, False), PromptFallbackMode.NATIVE_TOOL_CALLING),
        (LLMCapabilities(False, False, True), PromptFallbackMode.STRUCTURED_JSON_PROPOSALS),
        (LLMCapabilities(False, True, False), PromptFallbackMode.ADVISOR_ONLY),
    ],
)
def test_prompt_registry_maps_fallback_modes_from_provider_capabilities(
    capabilities: LLMCapabilities, expected: PromptFallbackMode
) -> None:
    assert AgentPromptRegistry.fallback_mode_for_capabilities(capabilities) == expected


def test_prompt_registry_rejects_unknown_profile() -> None:
    registry = AgentPromptRegistry()

    with pytest.raises(ValueError, match="Unknown agent profile"):
        registry.assemble(PromptAssemblyInput(profile_key="autonomous_publisher"))
