import pytest

from holospec import HoloSpecError, load_config, lookup_action


def test_given_schema_context_only_when_action_looked_up_then_context_included():
    # GIVEN a schema with a context field and no config
    schema = {
        "context": "This is a Python CLI project.",
        "propose": {"requires": []},
    }

    # WHEN looking up the action with no config
    result = lookup_action(schema, "propose")

    # THEN the schema's context is disclosed
    assert result["context"] == "This is a Python CLI project."


def test_given_schema_and_config_context_when_action_looked_up_then_both_included():
    # GIVEN a schema with context and a config with context
    schema = {
        "context": "Schema-level context.",
        "propose": {"requires": []},
    }
    config = {"context": "Config-level context."}

    # WHEN looking up the action with that config
    result = lookup_action(schema, "propose", config)

    # THEN both sources are present in the disclosed context, neither overriding the other
    assert "Schema-level context." in result["context"]
    assert "Config-level context." in result["context"]


def test_given_schema_and_config_constitution_when_action_looked_up_then_both_included():
    # GIVEN a schema with constitution and a config with constitution
    schema = {
        "constitution": "Schema-level constitution.",
        "propose": {"requires": []},
    }
    config = {"constitution": "Config-level constitution."}

    # WHEN looking up the action with that config
    result = lookup_action(schema, "propose", config)

    # THEN both sources are present in the disclosed constitution, neither overriding the other
    assert "Schema-level constitution." in result["constitution"]
    assert "Config-level constitution." in result["constitution"]


def test_given_no_context_or_constitution_when_action_looked_up_then_keys_absent():
    # GIVEN a schema with neither field
    schema = {"propose": {"requires": []}}

    # WHEN looking up the action
    result = lookup_action(schema, "propose")

    # THEN neither key appears in the result
    assert "context" not in result
    assert "constitution" not in result


def test_given_at_include_syntax_when_action_looked_up_then_passed_through_verbatim():
    # GIVEN a schema whose context references a file via @include syntax
    schema = {
        "context": "@include ./docs/house-style.md",
        "propose": {"requires": []},
    }

    # WHEN looking up the action
    result = lookup_action(schema, "propose")

    # THEN the @include reference is disclosed verbatim, never resolved by HoloSpec
    assert result["context"] == "@include ./docs/house-style.md"


def test_given_bare_artifact_id_when_action_looked_up_then_falls_back_to_artifact():
    # GIVEN a schema where the looked-up id is an artifact id, not a top-level action
    schema = {
        "artifacts": [
            {"id": "proposal", "generates": "proposal.md", "template": "proposal.md"},
        ],
        "propose": {"artifacts": ["proposal"], "requires": []},
    }

    # WHEN looking up the artifact id directly
    result = lookup_action(schema, "proposal")

    # THEN the artifact's own fields are returned
    assert result["generates"] == "proposal.md"
    assert result["template"] == "proposal.md"


def test_given_unknown_id_when_action_looked_up_then_raises_action_not_found():
    # GIVEN a schema with no matching action or artifact id
    schema = {"propose": {"requires": []}}

    # WHEN looking up an id that matches neither an action nor an artifact

    # THEN an action_not_found error is raised
    with pytest.raises(HoloSpecError) as exc_info:
        lookup_action(schema, "does_not_exist")
    assert exc_info.value.code == "action_not_found"


def test_given_no_root_when_config_loaded_then_returns_empty_dict():
    # GIVEN no project root
    # WHEN loading config
    config = load_config(None)

    # THEN an empty dict is returned
    assert config == {}


def test_given_root_without_config_file_when_config_loaded_then_returns_empty_dict(tmp_path):
    # GIVEN a root directory with no config.yaml
    # WHEN loading config
    config = load_config(tmp_path)

    # THEN an empty dict is returned
    assert config == {}


def test_given_root_with_config_file_when_config_loaded_then_returns_parsed_fields(tmp_path):
    # GIVEN a root directory with a config.yaml carrying context and constitution
    (tmp_path / "config.yaml").write_text(
        "schema: openspec\ncontext: Project context here.\nconstitution: Always be terse.\n"
    )

    # WHEN loading config
    config = load_config(tmp_path)

    # THEN both fields are parsed
    assert config["context"] == "Project context here."
    assert config["constitution"] == "Always be terse."
