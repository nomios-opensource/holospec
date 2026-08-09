import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from holospec import main

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "dummy_schema.yaml"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SPEC_DRIVEN_SCHEMA_DIR = REPO_ROOT / "schemas" / "spec-driven"


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path, monkeypatch):
    # find_project_root() looks directly under cwd for openspec/ or
    # holospec/ dirs, and load_schema() falls back to $XDG_DATA_HOME —
    # isolate tests from any such dirs on the real filesystem
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))

    # holospec has no packaged builtin schema — provide a project-local
    # spec-driven schema (tier 1) so the "default schema" tests resolve
    holospec_dir = tmp_path / "holospec"
    schemas_dir = holospec_dir / "schemas" / "spec-driven"
    schemas_dir.mkdir(parents=True)
    shutil.copy(SPEC_DRIVEN_SCHEMA_DIR / "schema.yaml", schemas_dir / "schema.yaml")


def test_given_valid_schema_file_when_schemacheck_run_then_reports_valid():
    # GIVEN a valid schema file
    runner = CliRunner()

    # WHEN running schemacheck
    result = runner.invoke(main, ["schemacheck", str(FIXTURE_PATH)])

    # THEN it reports the schema as valid with exit code 0
    assert result.exit_code == 0
    assert "Valid schema" in result.output


def test_given_valid_schema_file_when_schemacheck_run_with_json_then_reports_valid_json():
    # GIVEN a valid schema file
    runner = CliRunner()

    # WHEN running schemacheck with --json
    result = runner.invoke(main, ["schemacheck", str(FIXTURE_PATH), "--json"])

    # THEN it outputs a JSON object marking the schema valid
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {"valid": True, "errors": []}


def test_given_invalid_schema_file_when_schemacheck_run_then_reports_errors_and_exits_nonzero(
    tmp_path,
):
    # GIVEN a schema file with a broken requires reference
    schema_path = tmp_path / "bad_schema.yaml"
    schema_path.write_text("propose:\n  requires: [does_not_exist]\n")
    runner = CliRunner()

    # WHEN running schemacheck
    result = runner.invoke(main, ["schemacheck", str(schema_path)])

    # THEN it exits non-zero and reports the error
    assert result.exit_code != 0
    assert "does_not_exist" in result.output


def test_given_default_schema_when_workflow_run_then_lists_actions_and_order():
    # GIVEN the default builtin schema
    runner = CliRunner()

    # WHEN running workflow
    result = runner.invoke(main, ["workflow"])

    # THEN it reports the schema name/description, actions topology, and each action
    assert result.exit_code == 0
    assert "# spec-driven Workflow" in result.output
    assert "Holospec implementation of the Openspec default schema" in result.output
    assert "## Stages" in result.output
    assert "Stage 1:" in result.output
    assert "### propose" in result.output
    assert "### apply" in result.output


def test_given_default_schema_when_workflow_run_with_json_then_returns_actions_and_order():
    # GIVEN the default builtin schema
    runner = CliRunner()

    # WHEN running workflow with --json
    result = runner.invoke(main, ["workflow", "--json"])

    # THEN it returns a JSON object with name, description, actions and order
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["name"] == "spec-driven"
    assert payload["description"] == "Holospec implementation of the Openspec default schema"
    assert "actions" in payload
    assert "order" in payload
    assert "propose" in payload["order"][0]


def test_given_diamond_dependency_when_workflow_run_with_tree_then_shared_node_rendered_once_deep():
    # GIVEN a schema where two branches both require an artifact produced by
    # a shared upstream action, and both branches are in turn required by a
    # join action — the join node is reached twice during tree traversal
    schema_path = Path("holospec/schemas/spec-driven/schema.yaml")
    schema_path.write_text(
        """
artifacts:
  - id: root_out
    generates: root.md
    template: root.md
  - id: a_out
    generates: a.md
    template: a.md
  - id: b_out
    generates: b.md
    template: b.md
  - id: join_out
    generates: join.md
    template: join.md

root:
  artifacts: [root_out]
  requires: []

branch_a:
  artifacts: [a_out]
  requires: [root_out]

branch_b:
  artifacts: [b_out]
  requires: [root_out]

join:
  artifacts: [join_out]
  requires: [a_out, b_out]
"""
    )
    runner = CliRunner()

    # WHEN running workflow --tree
    result = runner.invoke(main, ["workflow", "--tree"])

    # THEN it renders without error, following the shared join node twice
    assert result.exit_code == 0
    assert result.output.count("join") == 2


def test_given_default_schema_when_workflow_run_with_tree_then_renders_tree():
    # GIVEN the default builtin schema
    runner = CliRunner()

    # WHEN running workflow with --tree
    result = runner.invoke(main, ["workflow", "--tree"])

    # THEN it renders a tree with propose at the root
    assert result.exit_code == 0
    assert "propose" in result.output
    assert "└──" in result.output or "├──" in result.output


def test_given_known_action_id_when_action_run_then_returns_instruction_and_checklist():
    # GIVEN the default builtin schema
    runner = CliRunner()

    # WHEN running action for a known action id
    result = runner.invoke(main, ["action", "propose"])

    # THEN it returns the instruction and checklist
    assert result.exit_code == 0
    assert "Instruction" in result.output
    assert "Checklist" in result.output


def test_given_known_action_id_when_action_run_with_json_then_returns_action_metadata():
    # GIVEN the default builtin schema
    runner = CliRunner()

    # WHEN running action with --json for a known action id
    result = runner.invoke(main, ["action", "propose", "--json"])

    # THEN it returns JSON with the action's id and requires
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["id"] == "propose"
    assert payload["requires"] == []


def test_given_unknown_action_id_when_action_run_then_exits_nonzero_with_error():
    # GIVEN the default builtin schema
    runner = CliRunner()

    # WHEN running action for an unknown action id
    result = runner.invoke(main, ["action", "does_not_exist"])

    # THEN it exits non-zero and reports action_not_found
    assert result.exit_code != 0
    assert "action_not_found" in result.output


def test_given_unknown_action_id_when_action_run_with_json_then_returns_error_json():
    # GIVEN the default builtin schema
    runner = CliRunner()

    # WHEN running action with --json for an unknown action id
    result = runner.invoke(main, ["action", "does_not_exist", "--json"])

    # THEN it returns a JSON error payload with code action_not_found
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "action_not_found"


def test_given_config_yaml_with_context_when_action_run_then_context_disclosed():
    # GIVEN a project-local config.yaml with a context field
    Path("holospec/config.yaml").write_text("schema: spec-driven\ncontext: This project prefers uv over pip.\n")
    runner = CliRunner()

    # WHEN running action for a known action id
    result = runner.invoke(main, ["action", "propose", "--json"])

    # THEN the config's context is disclosed in the result
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["context"] == "This project prefers uv over pip."


def test_given_missing_schema_file_when_schemacheck_run_then_reports_schema_not_found():
    # GIVEN a schema file path that does not exist
    runner = CliRunner()

    # WHEN running schemacheck on a missing file
    result = runner.invoke(main, ["schemacheck", "does_not_exist.yaml"])

    # THEN it exits non-zero and reports schema_not_found
    assert result.exit_code != 0
    assert "schema_not_found" in result.output


def test_given_broken_requires_when_workflow_run_then_reports_invalid_schema(tmp_path):
    # GIVEN a project-local schema whose requires references an unknown artifact
    schema_path = Path("holospec/schemas/spec-driven/schema.yaml")
    schema_path.write_text("propose:\n  requires: [does_not_exist]\n")
    runner = CliRunner()

    # WHEN running workflow
    result = runner.invoke(main, ["workflow"])

    # THEN it exits non-zero and reports invalid_schema
    assert result.exit_code != 0
    assert "invalid_schema" in result.output


def test_given_config_yaml_names_custom_schema_when_workflow_run_without_flag_then_uses_it():
    # GIVEN a project-local schema named "custom" and a config.yaml pointing at it
    custom_dir = Path("holospec/schemas/custom")
    custom_dir.mkdir(parents=True)
    shutil.copy(SPEC_DRIVEN_SCHEMA_DIR / "schema.yaml", custom_dir / "schema.yaml")
    Path("holospec/config.yaml").write_text("schema: custom\n")
    runner = CliRunner()

    # WHEN running workflow with no --schema flag
    result = runner.invoke(main, ["workflow"])

    # THEN it resolves the schema named in config.yaml, not the 'spec-driven' default
    assert result.exit_code == 0
    assert "# spec-driven Workflow" in result.output


def test_given_config_yaml_names_custom_schema_when_schema_flag_passed_then_flag_wins():
    # GIVEN a project-local schema named "custom" and a config.yaml pointing at it
    custom_dir = Path("holospec/schemas/custom")
    custom_dir.mkdir(parents=True)
    shutil.copy(SPEC_DRIVEN_SCHEMA_DIR / "schema.yaml", custom_dir / "schema.yaml")
    Path("holospec/config.yaml").write_text("schema: custom\n")
    runner = CliRunner()

    # WHEN running workflow with an explicit --schema overriding config.yaml
    result = runner.invoke(main, ["workflow", "--schema", "spec-driven"])

    # THEN the explicit flag is honored rather than config.yaml's value
    assert result.exit_code == 0
    assert "# spec-driven Workflow" in result.output


def test_given_config_yaml_names_custom_schema_when_action_run_without_flag_then_uses_it():
    # GIVEN a project-local schema named "custom" and a config.yaml pointing at it
    custom_dir = Path("holospec/schemas/custom")
    custom_dir.mkdir(parents=True)
    shutil.copy(SPEC_DRIVEN_SCHEMA_DIR / "schema.yaml", custom_dir / "schema.yaml")
    Path("holospec/config.yaml").write_text("schema: custom\n")
    runner = CliRunner()

    # WHEN running action for a known action id with no --schema flag
    result = runner.invoke(main, ["action", "propose", "--json"])

    # THEN it resolves the action from the schema named in config.yaml
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["id"] == "propose"


def test_given_no_config_yaml_when_workflow_run_without_flag_then_falls_back_to_spec_driven():
    # GIVEN no config.yaml at all (the autouse fixture only provides the schema dir)
    runner = CliRunner()

    # WHEN running workflow with no --schema flag
    result = runner.invoke(main, ["workflow"])

    # THEN it falls back to the 'spec-driven' default
    assert result.exit_code == 0
    assert "# spec-driven Workflow" in result.output


def test_given_broken_requires_when_action_run_then_reports_invalid_schema():
    # GIVEN a project-local schema whose requires references an unknown artifact
    schema_path = Path("holospec/schemas/spec-driven/schema.yaml")
    schema_path.write_text("propose:\n  requires: [does_not_exist]\n")
    runner = CliRunner()

    # WHEN running action
    result = runner.invoke(main, ["action", "propose"])

    # THEN it exits non-zero and reports invalid_schema
    assert result.exit_code != 0
    assert "invalid_schema" in result.output


def test_given_action_with_requires_and_context_when_action_run_then_text_output_shows_both():
    # GIVEN a project-local schema/config with requires, constitution, and context
    schema_path = Path("holospec/schemas/spec-driven/schema.yaml")
    schema_path.write_text(schema_path.read_text() + "\nconstitution: Never diff-patch a MODIFIED block.\n")
    Path("holospec/config.yaml").write_text("schema: spec-driven\ncontext: This project prefers uv over pip.\n")
    runner = CliRunner()

    # WHEN running action for an action with a non-empty requires list, in text mode
    result = runner.invoke(main, ["action", "specs"])

    # THEN the text output includes the requires line, constitution, and context
    assert result.exit_code == 0
    assert "Requires: proposal" in result.output
    assert "Constitution" in result.output
    assert "Context" in result.output


def test_given_explain_run_then_reports_overview_and_config_json_schema():
    # GIVEN no particular project state (explain is a static reference command)
    runner = CliRunner()

    # WHEN running explain
    result = runner.invoke(main, ["explain"])

    # THEN it reports a markdown overview plus root detection, the
    # schema.yaml/config.yaml relationship, and field references
    assert result.exit_code == 0
    assert "# HoloSpec" in result.output
    assert "## Project root" in result.output
    assert "named one of `holospec/`, `openspec/`" in result.output
    assert "config.yaml's `schema:`" in result.output
    assert "## schema.yaml field reference" in result.output
    assert "## config.yaml field reference" in result.output
    assert '"Artifact"' in result.output
    assert '"Action"' in result.output


def test_given_explain_run_with_json_then_returns_structured_json_schema():
    # GIVEN no particular project state
    runner = CliRunner()

    # WHEN running explain with --json
    result = runner.invoke(main, ["explain", "--json"])

    # THEN it returns a JSON object with the overview plus both JSON Schemas
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "overview" in payload
    assert "schema_yaml" in payload
    assert "config_yaml" in payload
    assert payload["schema_yaml"]["title"] == "Schema"
    assert payload["config_yaml"]["title"] == "Config"
    assert "schema" in payload["config_yaml"]["properties"]
    assert "Action" in payload["schema_yaml"]["$defs"]


def test_given_schema_and_config_constitution_when_action_run_then_both_disclosed():
    # GIVEN a schema with a constitution field and a config.yaml with its own constitution
    schema_path = Path("holospec/schemas/spec-driven/schema.yaml")
    schema_path.write_text(schema_path.read_text() + "\nconstitution: Never diff-patch a MODIFIED block.\n")
    Path("holospec/config.yaml").write_text("schema: spec-driven\nconstitution: Always ask before force-pushing.\n")
    runner = CliRunner()

    # WHEN running action for a known action id
    result = runner.invoke(main, ["action", "propose", "--json"])

    # THEN both constitutions are present, neither overriding the other
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "Never diff-patch a MODIFIED block." in payload["constitution"]
    assert "Always ask before force-pushing." in payload["constitution"]
