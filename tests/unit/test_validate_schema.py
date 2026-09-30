from pathlib import Path

import pytest

from holospec import load_schema_file, validate_schema

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_FILES = sorted(REPO_ROOT.glob("schemas/*/schema.yaml"))


@pytest.mark.parametrize("schema_path", SCHEMA_FILES, ids=lambda p: p.parent.name)
def test_given_a_real_shipped_schema_when_validated_then_no_errors(schema_path):
    # GIVEN a real shipped schema.yaml under schemas/<name>/
    schema = load_schema_file(schema_path)

    # WHEN validating it
    errors = validate_schema(schema)

    # THEN there are no errors
    assert errors == []


def test_given_minimal_valid_schema_when_validated_then_no_errors():
    # GIVEN a minimal schema with one action
    schema = {
        "name": "test",
        "propose": {"requires": []},
    }

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN there are no errors
    assert errors == []


def test_given_actions_dict_convention_when_validated_then_no_errors():
    # GIVEN a minimal schema declaring its action under the actions: mapping
    schema = {
        "name": "test",
        "actions": {"propose": {"requires": []}},
    }

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN there are no errors
    assert errors == []


def test_given_both_bare_action_keys_and_actions_dict_when_validated_then_error_reported():
    # GIVEN a schema mixing bare top-level action keys with the actions: field
    schema = {
        "name": "test",
        "propose": {"requires": []},
        "actions": {"apply": {"requires": []}},
    }

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN a mixed-convention error is reported
    assert any("mixes bare top-level action keys" in e for e in errors)


def test_given_action_references_unknown_artifact_when_validated_then_error_reported():
    # GIVEN an action referencing an artifact id that doesn't exist
    schema = {
        "artifacts": [
            {"id": "proposal", "generates": "proposal.md", "template": "proposal.md"},
        ],
        "propose": {"artifacts": ["missing_artifact"], "requires": []},
    }

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN an unknown-artifact error is reported
    assert any("unknown artifact id 'missing_artifact'" in e for e in errors)


def test_given_requires_references_unknown_artifact_when_validated_then_error_reported():
    # GIVEN an action whose requires references a nonexistent artifact
    schema = {
        "propose": {"requires": ["does_not_exist"]},
    }

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN an unknown-artifact error is reported
    assert any("unknown artifact id 'does_not_exist'" in e for e in errors)


def test_given_requires_is_not_a_list_when_validated_then_error_reported():
    # GIVEN an action whose requires field is a string instead of a list
    schema = {
        "propose": {"requires": "propose"},
    }

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN a type error is reported
    assert any("requires" in e and "valid list" in e for e in errors)


def test_given_duplicate_artifact_ids_when_validated_then_error_reported():
    # GIVEN two artifacts sharing the same id
    schema = {
        "artifacts": [
            {"id": "proposal", "generates": "a.md", "template": "a.md"},
            {"id": "proposal", "generates": "b.md", "template": "b.md"},
        ],
    }

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN a duplicate-id error is reported
    assert any("Duplicate artifact id: proposal" in e for e in errors)


def test_given_artifact_missing_generates_when_validated_then_error_reported():
    # GIVEN an artifact without a generates field
    schema = {
        "artifacts": [
            {"id": "proposal", "template": "a.md"},
        ],
    }

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN a missing-field error is reported
    assert any("artifacts.0.generates" in e and "required" in e for e in errors)


def test_given_top_level_schema_is_not_a_mapping_when_validated_then_single_error_reported():
    # GIVEN a schema that is a list instead of a mapping
    schema = ["not", "a", "dict"]

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN a single top-level type error is reported
    assert errors == ["Schema must be a mapping at the top level"]


def test_given_action_value_is_not_a_mapping_when_validated_then_error_reported():
    # GIVEN an action key whose value is a string instead of a mapping
    schema = {"propose": "not a mapping"}

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN a type error is reported for that action
    assert any("Action 'propose'" in e and "valid dictionary" in e for e in errors)


def test_given_string_context_and_constitution_when_validated_then_no_errors():
    # GIVEN a schema with string context and constitution fields
    schema = {
        "context": "This is a Python CLI project.",
        "constitution": "Never diff-patch a MODIFIED block.",
        "propose": {"requires": []},
    }

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN there are no errors, and neither key is treated as an action
    assert errors == []


def test_given_non_string_context_when_validated_then_error_reported():
    # GIVEN a schema whose context field is not a string
    schema = {"context": ["not", "a", "string"]}

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN a type error is reported
    assert any("context" in e and "valid string" in e for e in errors)


def test_given_non_string_constitution_when_validated_then_error_reported():
    # GIVEN a schema whose constitution field is not a string
    schema = {"constitution": {"nested": "mapping"}}

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN a type error is reported
    assert any("constitution" in e and "valid string" in e for e in errors)


def test_given_artifacts_is_not_a_list_when_validated_then_error_reported():
    # GIVEN a schema whose artifacts field is a mapping instead of a list
    schema = {"artifacts": {"id": "proposal"}}

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN a type error is reported
    assert any("artifacts" in e and "valid list" in e for e in errors)


def test_given_artifact_entry_is_not_a_mapping_when_validated_then_error_reported():
    # GIVEN an artifacts list containing a non-mapping entry
    schema = {"artifacts": ["not a mapping"]}

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN a type error is reported for that entry
    assert any("artifacts.0" in e and "valid dictionary" in e for e in errors)


def test_given_artifact_missing_id_when_validated_then_error_reported():
    # GIVEN an artifact entry without an id field
    schema = {"artifacts": [{"generates": "a.md", "template": "a.md"}]}

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN a missing-field error is reported
    assert any("artifacts.0.id" in e and "required" in e for e in errors)


def test_given_artifact_missing_template_when_validated_then_error_reported():
    # GIVEN an artifact without a template field
    schema = {"artifacts": [{"id": "proposal", "generates": "a.md"}]}

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN a missing-field error is reported
    assert any("artifacts.0.template" in e and "required" in e for e in errors)


def test_given_action_artifacts_field_is_not_a_list_when_validated_then_error_reported():
    # GIVEN an action whose artifacts field is a string instead of a list
    schema = {"propose": {"artifacts": "proposal", "requires": []}}

    # WHEN validating the schema
    errors = validate_schema(schema)

    # THEN a type error is reported
    assert any("Action 'propose': artifacts" in e and "valid list" in e for e in errors)
