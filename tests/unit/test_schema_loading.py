from pathlib import Path

import pytest

from holospec import (
    HoloSpecError,
    find_project_root,
    load_schema,
    load_schema_file,
    resolve_schema_file,
    resolve_schema_path,
)


def test_given_missing_file_when_loading_schema_file_then_raises_schema_not_found(tmp_path):
    # GIVEN a path that does not exist
    missing = tmp_path / "does_not_exist.yaml"

    # WHEN loading the schema file

    # THEN a schema_not_found error is raised
    with pytest.raises(HoloSpecError) as exc_info:
        load_schema_file(missing)
    assert exc_info.value.code == "schema_not_found"


def test_given_invalid_yaml_when_loading_schema_file_then_raises_invalid_schema(tmp_path):
    # GIVEN a file with malformed YAML
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("propose: [unterminated\n")

    # WHEN loading the schema file

    # THEN an invalid_schema error is raised
    with pytest.raises(HoloSpecError) as exc_info:
        load_schema_file(bad_yaml)
    assert exc_info.value.code == "invalid_schema"


def test_given_empty_file_when_loading_schema_file_then_raises_invalid_schema(tmp_path):
    # GIVEN an empty YAML file
    empty = tmp_path / "empty.yaml"
    empty.write_text("")

    # WHEN loading the schema file

    # THEN an invalid_schema error is raised for the empty file
    with pytest.raises(HoloSpecError) as exc_info:
        load_schema_file(empty)
    assert exc_info.value.code == "invalid_schema"
    assert "empty" in exc_info.value.message


def test_given_no_project_root_when_finding_project_root_then_returns_none(tmp_path, monkeypatch):
    # GIVEN a directory tree with no openspec/ or holospec/ anywhere above it
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)

    # WHEN finding the project root starting from the nested directory
    root = find_project_root("spec-driven", start=nested)

    # THEN no root is found
    assert root is None


def test_given_no_project_root_when_resolving_schema_path_then_returns_none(tmp_path):
    # GIVEN a directory tree with no matching project root
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    # WHEN resolving the schema path
    path = resolve_schema_path("spec-driven", start=nested)

    # THEN no path is resolved
    assert path is None


def test_given_direct_yaml_path_that_exists_when_loading_schema_then_loads_it(tmp_path):
    # GIVEN a direct .yaml path that exists
    schema_path = tmp_path / "custom.yaml"
    schema_path.write_text("propose:\n  requires: []\n")

    # WHEN loading the schema by that direct path
    schema = load_schema(str(schema_path))

    # THEN the schema is loaded from that file
    assert schema == {"propose": {"requires": []}}


def test_given_direct_yaml_path_that_does_not_exist_when_loading_schema_then_raises(tmp_path):
    # GIVEN a name that looks like a direct .yaml path but doesn't exist
    missing = tmp_path / "missing.yaml"

    # WHEN loading the schema by that direct path

    # THEN a schema_not_found error is raised
    with pytest.raises(HoloSpecError) as exc_info:
        load_schema(str(missing))
    assert exc_info.value.code == "schema_not_found"


def test_given_dir_with_no_schema_file_when_resolving_schema_file_then_raises(tmp_path):
    # GIVEN a directory with neither schema.yaml nor schema.yml
    empty_dir = tmp_path / "schemas" / "custom"
    empty_dir.mkdir(parents=True)

    # WHEN resolving the schema file for that directory

    # THEN a schema_not_found error is raised
    with pytest.raises(HoloSpecError) as exc_info:
        resolve_schema_file(empty_dir)
    assert exc_info.value.code == "schema_not_found"


def test_given_schema_yml_extension_when_resolving_schema_file_then_finds_it(tmp_path):
    # GIVEN a directory with only a schema.yml (not .yaml)
    schema_dir = tmp_path / "schemas" / "custom"
    schema_dir.mkdir(parents=True)
    (schema_dir / "schema.yml").write_text("propose:\n  requires: []\n")

    # WHEN resolving the schema file for that directory
    resolved = resolve_schema_file(schema_dir)

    # THEN the schema.yml file is returned
    assert resolved == schema_dir / "schema.yml"


def test_given_project_root_with_yml_extension_when_loading_schema_then_loads_it(tmp_path, monkeypatch):
    # GIVEN a project root whose schema is named schema.yml instead of schema.yaml
    monkeypatch.chdir(tmp_path)
    (tmp_path / "holospec" / "schemas" / "spec-driven").mkdir(parents=True)
    (tmp_path / "holospec" / "schemas" / "spec-driven" / "schema.yml").write_text("propose:\n  requires: []\n")

    # WHEN loading the schema by name

    # THEN it is found and loaded despite the .yml extension
    schema = load_schema("spec-driven")
    assert schema == {"propose": {"requires": []}}


def test_given_unresolvable_schema_name_when_loading_schema_then_raises_not_found(tmp_path, monkeypatch):
    # GIVEN a schema name that cannot be resolved from any tier
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))

    # WHEN loading a schema with an unresolvable name

    # THEN a schema_not_found error is raised
    with pytest.raises(HoloSpecError) as exc_info:
        load_schema("nonexistent-schema")
    assert exc_info.value.code == "schema_not_found"
