from pathlib import Path

from holospec import load_schema_file, validate_schema

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "dummy_schema.yaml"


def test_given_dummy_schema_file_when_loaded_then_generates_field_survives_verbatim():
    # GIVEN a dummy schema file with glob-based generates fields

    # WHEN loading the schema file
    schema = load_schema_file(FIXTURE_PATH)

    # THEN the generates field on each artifact survives unchanged
    generates_by_id = {a["id"]: a["generates"] for a in schema["artifacts"]}
    assert generates_by_id == {
        "proposal": "proposal.md",
        "specs": "specs/**/*.md",
        "design": "design.md",
        "tasks": "tasks.md",
    }


def test_given_dummy_schema_file_when_validated_then_no_errors():
    # GIVEN a dummy schema file
    schema = load_schema_file(FIXTURE_PATH)

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN there are no errors
    assert errors == []
