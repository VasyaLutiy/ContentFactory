from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class WorkflowValidationIssue:
    code: str
    message: str
    node_id: str | None = None


@dataclass(frozen=True)
class WorkflowValidationResult:
    valid: bool
    issues: list[WorkflowValidationIssue] = field(default_factory=list)


def validate_workflow(
    workflow: dict[str, Any],
    object_info: dict[str, Any] | None = None,
) -> WorkflowValidationResult:
    issues: list[WorkflowValidationIssue] = []
    node_ids = set(workflow)

    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            issues.append(
                WorkflowValidationIssue(
                    code="INVALID_NODE",
                    node_id=node_id,
                    message="Workflow node must be an object.",
                )
            )
            continue

        class_type = node.get("class_type")
        if not isinstance(class_type, str) or not class_type:
            issues.append(
                WorkflowValidationIssue(
                    code="MISSING_CLASS_TYPE",
                    node_id=node_id,
                    message="Workflow node is missing class_type.",
                )
            )
        elif object_info is not None and class_type not in object_info:
            issues.append(
                WorkflowValidationIssue(
                    code="UNKNOWN_CLASS_TYPE",
                    node_id=node_id,
                    message=f"ComfyUI does not expose node class {class_type}.",
                )
            )

        inputs = node.get("inputs", {})
        if inputs is None:
            inputs = {}
        if not isinstance(inputs, dict):
            issues.append(
                WorkflowValidationIssue(
                    code="INVALID_INPUTS",
                    node_id=node_id,
                    message="Workflow node inputs must be an object.",
                )
            )
            continue

        for input_name, value in inputs.items():
            if _is_link(value):
                target_node_id = str(value[0])
                if target_node_id == node_id:
                    issues.append(
                        WorkflowValidationIssue(
                            code="SELF_REFERENCE",
                            node_id=node_id,
                            message=f"Input {input_name} references the same node.",
                        )
                    )
                elif target_node_id not in node_ids:
                    issues.append(
                        WorkflowValidationIssue(
                            code="BROKEN_LINK",
                            node_id=node_id,
                            message=f"Input {input_name} references missing node {target_node_id}.",
                        )
                    )
                if not isinstance(value[1], int) or value[1] < 0:
                    issues.append(
                        WorkflowValidationIssue(
                            code="INVALID_OUTPUT_INDEX",
                            node_id=node_id,
                            message=f"Input {input_name} has invalid output index.",
                        )
                    )

    issues.extend(_cycle_issues(workflow))
    return WorkflowValidationResult(valid=not issues, issues=issues)


def _is_link(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], (str, int))
    )


def _cycle_issues(workflow: dict[str, Any]) -> list[WorkflowValidationIssue]:
    graph: dict[str, set[str]] = {node_id: set() for node_id in workflow}
    for node_id, node in workflow.items():
        inputs = node.get("inputs", {}) if isinstance(node, dict) else {}
        if not isinstance(inputs, dict):
            continue
        for value in inputs.values():
            if _is_link(value):
                source_id = str(value[0])
                if source_id in graph:
                    graph[node_id].add(source_id)

    visiting: set[str] = set()
    visited: set[str] = set()
    issues: list[WorkflowValidationIssue] = []

    def visit(node_id: str, path: tuple[str, ...]) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            cycle = " -> ".join((*path, node_id))
            issues.append(
                WorkflowValidationIssue(
                    code="CYCLE",
                    node_id=node_id,
                    message=f"Workflow contains a cycle: {cycle}.",
                )
            )
            return

        visiting.add(node_id)
        for dependency_id in graph[node_id]:
            visit(dependency_id, (*path, node_id))
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in graph:
        visit(node_id, ())

    return issues
