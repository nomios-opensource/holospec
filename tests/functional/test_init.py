import io
import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

import holospec
from holospec import main

SKILL_SOURCE_PATH = Path(__file__).resolve().parent.parent.parent / "skills" / "holospec" / "SKILL.md"
OPENSPEC_SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / "schemas" / "openspec"


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path, monkeypatch):
    # find_project_root() looks directly under cwd for openspec/ or
    # holospec/ dirs — isolate tests from any such dirs on the real filesystem
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))
    return tmp_path


def test_given_no_existing_root_when_init_run_then_scaffolds_holospec_dir(isolated_cwd):
    # GIVEN a project directory with neither openspec/ nor holospec/
    runner = CliRunner()

    # WHEN running init
    result = runner.invoke(main, ["init", "--schema", "openspec", "--json"])

    # THEN it scaffolds a new holospec/ root and installs the skill file
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["created"] is True
    assert payload["root"] == str(isolated_cwd / "holospec")
    assert (isolated_cwd / "holospec" / "config.yaml").is_file()
    agents_skill_path = isolated_cwd / ".agents" / "skills" / "holospec" / "SKILL.md"
    assert agents_skill_path.is_file()
    assert agents_skill_path.read_text() == SKILL_SOURCE_PATH.read_text()
    claude_skill_path = isolated_cwd / ".claude" / "skills" / "holospec" / "SKILL.md"
    assert claude_skill_path.is_symlink() or claude_skill_path.parent.is_symlink()
    assert claude_skill_path.read_text() == SKILL_SOURCE_PATH.read_text()


def test_given_existing_root_without_config_when_init_run_then_creates_config(isolated_cwd):
    # GIVEN an existing holospec/ root with a schema already present but no config.yaml
    schema_dir = isolated_cwd / "holospec" / "schemas" / "openspec"
    schema_dir.mkdir(parents=True)
    (schema_dir / "schema.yaml").write_text(OPENSPEC_SCHEMA_DIR.joinpath("schema.yaml").read_text())
    runner = CliRunner()

    # WHEN running init and selecting that schema
    result = runner.invoke(main, ["init", "--schema", "openspec", "--json"])

    # THEN config.yaml is created, pointing at the selected schema
    assert result.exit_code == 0
    config_path = isolated_cwd / "holospec" / "config.yaml"
    assert config_path.is_file()
    assert config_path.read_text() == "schema: openspec\n"


def test_given_init_already_run_when_init_run_again_then_symlink_is_recreated(isolated_cwd):
    # GIVEN a project where init has already installed the skill symlink
    runner = CliRunner()
    runner.invoke(main, ["init", "--schema", "openspec", "--json"])

    # WHEN running init again
    result = runner.invoke(main, ["init", "--schema", "openspec", "--json"])

    # THEN the symlink is replaced cleanly rather than erroring or nesting
    assert result.exit_code == 0
    claude_skill_path = isolated_cwd / ".claude" / "skills" / "holospec" / "SKILL.md"
    assert claude_skill_path.read_text() == SKILL_SOURCE_PATH.read_text()


def test_given_real_dir_at_claude_skill_path_when_init_run_then_replaces_it_with_symlink(
    isolated_cwd,
):
    # GIVEN a real (non-symlink) directory already occupying .claude/skills/holospec
    stale_dir = isolated_cwd / ".claude" / "skills" / "holospec"
    stale_dir.mkdir(parents=True)
    (stale_dir / "SKILL.md").write_text("stale content")
    runner = CliRunner()

    # WHEN running init
    result = runner.invoke(main, ["init", "--schema", "openspec", "--json"])

    # THEN the stale directory is replaced with a symlink to the canonical skill
    assert result.exit_code == 0
    claude_skill_path = isolated_cwd / ".claude" / "skills" / "holospec"
    assert claude_skill_path.is_symlink()
    assert (claude_skill_path / "SKILL.md").read_text() == SKILL_SOURCE_PATH.read_text()


def test_given_no_existing_root_when_init_run_without_json_then_prints_text_summary(isolated_cwd):
    # GIVEN a project directory with neither openspec/ nor holospec/
    runner = CliRunner()

    # WHEN running init without --json
    result = runner.invoke(main, ["init", "--schema", "openspec"])

    # THEN it prints a human-readable summary
    assert result.exit_code == 0
    assert "Scaffolded root:" in result.output
    assert "Installed skill file:" in result.output


def test_given_existing_holospec_dir_when_init_run_without_json_then_prints_detected_summary(
    isolated_cwd,
):
    # GIVEN an existing holospec/ directory
    (isolated_cwd / "holospec").mkdir()
    runner = CliRunner()

    # WHEN running init without --json
    result = runner.invoke(main, ["init", "--schema", "openspec"])

    # THEN it prints a human-readable summary noting detection, not scaffolding
    assert result.exit_code == 0
    assert "Detected existing root:" in result.output


def test_given_existing_openspec_dir_when_init_run_then_detects_it_without_scaffolding(
    isolated_cwd,
):
    # GIVEN an existing openspec/ directory
    (isolated_cwd / "openspec").mkdir()
    runner = CliRunner()

    # WHEN running init
    result = runner.invoke(main, ["init", "--schema", "openspec", "--json"])

    # THEN it detects the existing openspec/ root and does not scaffold
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["created"] is False
    assert payload["root"] == str(isolated_cwd / "openspec")
    assert (isolated_cwd / ".agents" / "skills" / "holospec" / "SKILL.md").is_file()
    assert not (isolated_cwd / "holospec").exists()


def test_given_existing_holospec_dir_when_init_run_then_detects_it_without_scaffolding(
    isolated_cwd,
):
    # GIVEN an existing holospec/ directory
    (isolated_cwd / "holospec").mkdir()
    runner = CliRunner()

    # WHEN running init
    result = runner.invoke(main, ["init", "--schema", "openspec", "--json"])

    # THEN it detects the existing holospec/ root and does not create a new one
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["created"] is False
    assert payload["root"] == str(isolated_cwd / "holospec")
    assert (isolated_cwd / ".agents" / "skills" / "holospec" / "SKILL.md").is_file()


def test_given_unrelated_openspec_dir_in_ancestor_when_init_run_then_scaffolds_here_instead(isolated_cwd, monkeypatch):
    # GIVEN an unrelated openspec/ directory in an ancestor directory
    (isolated_cwd / "openspec").mkdir()
    nested = isolated_cwd / "some-other-project"
    nested.mkdir()
    monkeypatch.chdir(nested)
    runner = CliRunner()

    # WHEN running init from the nested, unrelated project directory
    result = runner.invoke(main, ["init", "--schema", "openspec", "--json"])

    # THEN it scaffolds a new root here rather than adopting the ancestor's
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["created"] is True
    assert payload["root"] == str(nested / "holospec")


def test_given_both_openspec_and_holospec_dirs_when_init_run_then_holospec_takes_precedence(
    isolated_cwd,
):
    # GIVEN both openspec/ and holospec/ directories exist at the same level
    (isolated_cwd / "openspec").mkdir()
    (isolated_cwd / "holospec").mkdir()
    runner = CliRunner()

    # WHEN running init
    result = runner.invoke(main, ["init", "--schema", "openspec", "--json"])

    # THEN holospec/ is detected as the root, per documented precedence
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["root"] == str(isolated_cwd / "holospec")


def test_given_no_existing_schema_when_init_run_then_fetches_default_schema_from_registry(
    isolated_cwd,
):
    # GIVEN a fresh project directory with no schemas/ content
    runner = CliRunner()

    # WHEN running init with the default schema name
    result = runner.invoke(main, ["init", "--schema", "openspec", "--json"])

    # THEN it copies schema.yaml + templates/ from the registry's local path
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema"] == "openspec"
    assert payload["schema_fetched"] is True
    dest_dir = isolated_cwd / "holospec" / "schemas" / "openspec"
    assert (dest_dir / "schema.yaml").read_text() == (OPENSPEC_SCHEMA_DIR / "schema.yaml").read_text()
    assert (dest_dir / "templates" / "proposal.md").is_file()


def test_given_existing_schema_when_init_run_then_fetch_is_skipped(isolated_cwd):
    # GIVEN a schemas/openspec/schema.yaml already present under the root
    dest_dir = isolated_cwd / "holospec" / "schemas" / "openspec"
    dest_dir.mkdir(parents=True)
    (dest_dir / "schema.yaml").write_text("name: custom-existing\n")
    runner = CliRunner()

    # WHEN running init
    result = runner.invoke(main, ["init", "--schema", "openspec", "--json"])

    # THEN the existing schema is left untouched and not re-fetched
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_fetched"] is False
    assert (dest_dir / "schema.yaml").read_text() == "name: custom-existing\n"


def test_given_unknown_schema_name_without_schema_url_when_init_run_then_errors(isolated_cwd):
    # GIVEN a schema name with no registry entry and no --schema-url override
    runner = CliRunner()

    # WHEN running init
    result = runner.invoke(main, ["init", "--schema", "does-not-exist", "--json"])

    # THEN it errors rather than silently skipping schema setup
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "schema_not_found"


def test_given_schema_url_local_dir_when_init_run_then_copies_from_it(isolated_cwd, tmp_path):
    # GIVEN a custom local schema directory outside the registry
    custom_source = tmp_path / "custom-schema"
    (custom_source / "templates").mkdir(parents=True)
    (custom_source / "schema.yaml").write_text("name: custom\nartifacts: []\n")
    (custom_source / "templates" / "custom.md").write_text("template body")
    runner = CliRunner()

    # WHEN running init with --schema-url pointing at that directory
    result = runner.invoke(main, ["init", "--schema", "custom", "--schema-url", str(custom_source), "--json"])

    # THEN it copies schema.yaml + templates/ from the custom source, not the registry
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_fetched"] is True
    dest_dir = isolated_cwd / "holospec" / "schemas" / "custom"
    assert (dest_dir / "schema.yaml").read_text() == "name: custom\nartifacts: []\n"
    assert (dest_dir / "templates" / "custom.md").read_text() == "template body"


def test_given_schema_url_local_dir_missing_schema_yaml_when_init_run_then_reports_schema_fetch_failed(
    isolated_cwd, tmp_path
):
    # GIVEN a --schema-url local directory that lacks schema.yaml
    broken_source = tmp_path / "broken-schema"
    broken_source.mkdir()
    runner = CliRunner()

    # WHEN running init pointed at that broken directory
    result = runner.invoke(main, ["init", "--schema", "custom", "--schema-url", str(broken_source), "--json"])

    # THEN the copy failure is surfaced as schema_fetch_failed, not an unhandled crash
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "schema_fetch_failed"


def test_given_schema_url_http_when_init_run_then_fetches_over_network(isolated_cwd, monkeypatch):
    # GIVEN a --schema-url pointing at a (mocked) HTTP source
    schema_bytes = b"name: custom\nartifacts:\n  - id: a\n    generates: a.md\n    template: a.md\n"
    template_bytes = b"template body"

    def fake_urlopen(url):
        if url.endswith("schema.yaml"):
            return io.BytesIO(schema_bytes)
        return io.BytesIO(template_bytes)

    monkeypatch.setattr(holospec.urllib.request, "urlopen", lambda url: _FakeResponse(fake_urlopen(url)))
    runner = CliRunner()

    # WHEN running init with an http --schema-url
    result = runner.invoke(
        main,
        ["init", "--schema", "custom", "--schema-url", "http://example.invalid/schemas/custom", "--json"],
    )

    # THEN it fetches schema.yaml and referenced templates over "the network"
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_fetched"] is True
    dest_dir = isolated_cwd / "holospec" / "schemas" / "custom"
    assert (dest_dir / "schema.yaml").read_bytes() == schema_bytes
    assert (dest_dir / "templates" / "a.md").read_bytes() == template_bytes


def test_given_url_fetch_failure_when_init_run_then_reports_schema_fetch_failed(isolated_cwd, monkeypatch):
    # GIVEN a --schema-url that raises on fetch
    def raising_urlopen(url):
        raise OSError("boom")

    monkeypatch.setattr(holospec.urllib.request, "urlopen", raising_urlopen)
    runner = CliRunner()

    # WHEN running init with that schema-url
    result = runner.invoke(
        main,
        ["init", "--schema", "custom", "--schema-url", "http://example.invalid/schemas/custom", "--json"],
    )

    # THEN it surfaces schema_fetch_failed rather than crashing
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "schema_fetch_failed"


def test_given_no_schema_flag_and_noninteractive_input_when_init_run_then_errors(isolated_cwd):
    # GIVEN no --schema flag and non-interactive stdin (the CliRunner default)
    runner = CliRunner()

    # WHEN running init
    result = runner.invoke(main, ["init", "--json"])

    # THEN it errors rather than silently picking a schema
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "schema_not_specified"
    assert "openspec" in payload["error"]["message"]


def test_given_no_schema_flag_and_interactive_input_when_init_run_then_prompts_and_uses_selection(
    isolated_cwd, monkeypatch
):
    # GIVEN interactive stdin and no --schema flag
    monkeypatch.setattr(holospec, "_stdin_isatty", lambda: True)
    runner = CliRunner()

    # WHEN running init and answering the prompt with the default selection
    result = runner.invoke(main, ["init", "--json"], input="\n")

    # THEN it prompts for a schema choice and proceeds with the selected one
    assert result.exit_code == 0
    assert "Select a schema:" in result.output
    payload = json.loads(result.output[result.output.index("{") :])
    assert payload["schema"] == "openspec"


def test_given_local_project_schema_when_init_run_interactively_then_offered_first(isolated_cwd, monkeypatch):
    # GIVEN a project with a local schema already present under holospec/schemas/
    local_dir = isolated_cwd / "holospec" / "schemas" / "mine"
    local_dir.mkdir(parents=True)
    (local_dir / "schema.yaml").write_text("name: mine\nartifacts: []\n")
    monkeypatch.setattr(holospec, "_stdin_isatty", lambda: True)
    runner = CliRunner()

    # WHEN running init and selecting the first offered choice
    result = runner.invoke(main, ["init", "--json"], input="1\n")

    # THEN the local schema is listed first and marked as local, and gets selected
    assert result.exit_code == 0
    assert "1. mine (local)" in result.output
    payload = json.loads(result.output[result.output.index("{") :])
    assert payload["schema"] == "mine"


def test_given_discover_local_schemas_when_root_is_none_then_returns_empty_list():
    # GIVEN no project root
    # WHEN discovering local schemas
    # THEN an empty list is returned without touching the filesystem
    assert holospec._discover_local_schemas(None) == []


def test_given_root_without_schemas_dir_when_discover_local_schemas_then_returns_empty_list(tmp_path):
    # GIVEN a root directory with no schemas/ subdirectory
    # WHEN discovering local schemas
    # THEN an empty list is returned
    assert holospec._discover_local_schemas(tmp_path) == []


class _FakeResponse:
    def __init__(self, buf):
        self._buf = buf

    def __enter__(self):
        return self._buf

    def __exit__(self, *exc_info):
        return False


def _git(repo: Path, *args: str) -> None:
    ident = ["-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", *ident, "-C", str(repo), *args], check=True)  # noqa: S603, S607


def _commit_all(repo: Path) -> None:
    """Turn `repo` into a git repository with everything committed."""
    for args in (["init", "-q"], ["add", "."], ["commit", "-qm", "init"]):
        _git(repo, *args)


def test_given_schema_url_git_repo_when_init_run_then_clones_and_copies_schemas_subdir(isolated_cwd, tmp_path):
    # GIVEN a git repo laid out as holospec-schemas/schemas/<name>/
    repo = tmp_path / "holospec-schemas.git"
    schema_dir = repo / "schemas" / "custom"
    (schema_dir / "templates").mkdir(parents=True)
    (schema_dir / "schema.yaml").write_text("name: custom\nartifacts: []\n")
    (schema_dir / "templates" / "custom.md").write_text("template body")
    _commit_all(repo)
    runner = CliRunner()

    # WHEN running init with the repo as --schema-url (.git suffix marks it as git)
    result = runner.invoke(main, ["init", "--schema", "custom", "--schema-url", f"file://{repo}", "--json"])

    # THEN schemas/custom is copied out of the clone
    assert result.exit_code == 0, result.output
    dest_dir = isolated_cwd / "holospec" / "schemas" / "custom"
    assert (dest_dir / "schema.yaml").read_text() == "name: custom\nartifacts: []\n"
    assert (dest_dir / "templates" / "custom.md").read_text() == "template body"


def test_given_schema_url_git_repo_without_schema_when_init_run_then_reports_schema_fetch_failed(
    isolated_cwd, tmp_path
):
    # GIVEN a git repo containing no schema.yaml
    repo = tmp_path / "empty.git"
    repo.mkdir()
    (repo / "README.md").write_text("x")
    _commit_all(repo)

    # WHEN running init against it
    result = CliRunner().invoke(main, ["init", "--schema", "custom", "--schema-url", f"file://{repo}", "--json"])

    # THEN a schema_fetch_failed error is reported
    assert result.exit_code == 1
    assert json.loads(result.output)["error"]["code"] == "schema_fetch_failed"


def test_given_unreachable_git_url_when_init_run_then_reports_schema_fetch_failed(isolated_cwd, tmp_path):
    # GIVEN a git URL that does not exist
    missing = tmp_path / "missing.git"

    # WHEN running init against it
    result = CliRunner().invoke(main, ["init", "--schema", "custom", "--schema-url", f"file://{missing}", "--json"])

    # THEN the clone failure is surfaced, not an unhandled crash
    assert result.exit_code == 1
    assert json.loads(result.output)["error"]["code"] == "schema_fetch_failed"


def test_given_git_not_installed_when_init_run_then_reports_schema_fetch_failed(isolated_cwd, monkeypatch):
    # GIVEN git is not on PATH
    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(holospec.subprocess, "run", no_git)

    # WHEN running init with a git --schema-url
    result = CliRunner().invoke(
        main, ["init", "--schema", "custom", "--schema-url", "git@example.invalid:org/schemas.git", "--json"]
    )

    # THEN the missing dependency is reported clearly
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "schema_fetch_failed"
    assert "git is not installed" in payload["error"]["message"]


def test_given_schema_url_git_repo_with_ref_when_init_run_then_copies_that_tag(isolated_cwd, tmp_path):
    # GIVEN a git repo whose tag v1 differs from HEAD
    repo = tmp_path / "holospec-schemas.git"
    (repo / "templates").mkdir(parents=True)
    (repo / "templates" / "t.md").write_text("t")
    (repo / "schema.yaml").write_text("name: v1\n")
    _commit_all(repo)
    _git(repo, "tag", "v1")
    (repo / "schema.yaml").write_text("name: head\n")
    _git(repo, "commit", "-qam", "2")

    # WHEN running init with a #v1 ref (schema.yaml at the repo root)
    result = CliRunner().invoke(main, ["init", "--schema", "custom", "--schema-url", f"file://{repo}#v1", "--json"])

    # THEN the tagged content is copied, not HEAD
    assert result.exit_code == 0, result.output
    assert (isolated_cwd / "holospec" / "schemas" / "custom" / "schema.yaml").read_text() == "name: v1\n"
