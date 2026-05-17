from app.providers.comfy.workflow_validator import validate_workflow


def test_validates_simple_workflow_links() -> None:
    result = validate_workflow(
        {
            "1": {"class_type": "LoadImage", "inputs": {}},
            "2": {"class_type": "PreviewImage", "inputs": {"images": ["1", 0]}},
        },
        object_info={"LoadImage": {}, "PreviewImage": {}},
    )

    assert result.valid
    assert result.issues == []


def test_reports_broken_link_and_unknown_class_type() -> None:
    result = validate_workflow(
        {
            "1": {"class_type": "UnknownNode", "inputs": {"image": ["404", 0]}},
        },
        object_info={"LoadImage": {}},
    )

    assert not result.valid
    assert {issue.code for issue in result.issues} == {"UNKNOWN_CLASS_TYPE", "BROKEN_LINK"}


def test_reports_cycles() -> None:
    result = validate_workflow(
        {
            "1": {"class_type": "A", "inputs": {"input": ["2", 0]}},
            "2": {"class_type": "B", "inputs": {"input": ["1", 0]}},
        }
    )

    assert not result.valid
    assert "CYCLE" in {issue.code for issue in result.issues}
