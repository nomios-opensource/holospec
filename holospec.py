"""
Copyright 2026 Nomios UK&I

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import json
import os
import shutil
import sys
import typing as t
import urllib.request
from pathlib import Path
from urllib.error import URLError

import click
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic_core import ErrorDetails, InitErrorDetails, PydanticCustomError

__version__ = "0.0.0"

RESERVED_KEYS = {"name", "version", "description", "artifacts", "context", "constitution", "actions"}
"""Top-level config keys owned by HoloSpec; a schema may not redefine them."""

PROJECT_ROOT_MARKERS: tuple[str, ...] = ("holospec", "openspec")
"""Directory names to look for when adopting an existing project's schema and
files. Order is precedence; if none is found, the first value is used when
scaffolding a new root."""

DEFAULT_SCHEMA = "spec-driven"
"""Schema used when a project doesn't pin one explicitly."""

SCHEMA_REGISTRY: dict[str, str] = {
    "spec-driven": str(Path(__file__).resolve().parent / "schemas" / "spec-driven"),
}
"""Catalog of holospec project maintained schemas."""


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """HoloSpec — The instruction layer for agentic work."""


@main.command()
@click.argument("file", type=click.Path(path_type=Path))
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def schemacheck(file: Path, as_json: bool) -> None:
    """Validate a schema file."""
    try:
        schema = load_schema_file(file)
    except HoloSpecError as exc:
        _emit_error(exc, as_json)

    errors = validate_schema(schema)

    if as_json:
        click.echo(json.dumps({"valid": len(errors) == 0, "errors": errors}, indent=4))
    else:
        if errors:
            click.echo(f"Invalid schema: {file}")
            for err in errors:
                click.echo(f"  - {err}")
            sys.exit(1)
        else:
            click.echo(f"Valid schema: {file}")


@main.command()
@click.option(
    "--schema",
    "schema_name",
    default=None,
    help="Schema name to load (defaults to config.yaml's `schema:`)",
)
@click.option("--tree", is_flag=True, help="Render requires graph as tree/DAG")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def workflow(schema_name: t.Optional[str], tree: bool, as_json: bool) -> None:
    """List all workflow actions."""
    try:
        schema_name = resolve_schema_name(schema_name)
        schema = load_schema(schema_name)
        errors = validate_schema(schema)
        if errors:
            raise HoloSpecError("invalid_schema", "; ".join(errors))
        order = actions_topology(schema)
        root = find_project_root(schema_name)
    except HoloSpecError as exc:
        _emit_error(exc, as_json)

    actions = _build_workflow_actions(schema)

    if as_json:
        click.echo(
            json.dumps(
                {
                    "name": schema.get("name", ""),
                    "description": schema.get("description", ""),
                    "root": str(root) if root else None,
                    "actions": actions,
                    "order": order,
                },
                indent=4,
            )
        )
        return

    if tree:
        _render_tree(schema, order)
        return

    _render_workflow_text(schema, root, order, actions)


def _build_workflow_actions(schema: dict[str, t.Any]) -> list[dict[str, t.Any]]:
    artifact_map = {a["id"]: a for a in schema.get("artifacts", []) if isinstance(a, dict) and "id" in a}

    actions = []
    for aid in get_action_ids(schema):
        action = schema[aid]
        entry = {
            "id": aid,
            "description": action.get("description", ""),
            "requires": action.get("requires", []),
        }
        action_artifact_ids = action.get("artifacts", [])
        if action_artifact_ids:
            entry["generates"] = [artifact_map[a]["generates"] for a in action_artifact_ids if a in artifact_map]
        actions.append(entry)
    return actions


def _render_workflow_text(
    schema: dict[str, t.Any], root: t.Optional[Path], order: list[list[str]], actions: list[dict[str, t.Any]]
) -> None:
    click.echo(f"# {schema.get('name', '')} Workflow\n")
    if schema.get("description"):
        click.echo(f"{schema['description']}\n")
    if root:
        click.echo(f"Root: {root}\n")
    click.echo("## Stages\n")
    click.echo(
        "Stages run in sequence; actions within a stage have no dependency on each other and can run in parallel.\n"
    )
    for i, level in enumerate(order, start=1):
        click.echo(f"Stage {i}: {', '.join(level)}")
    click.echo()
    for entry in actions:
        click.echo(f"### {entry['id']}")
        click.echo(f"\n{entry['description']}")
        if entry["requires"]:
            click.echo(f"\nRequires: {', '.join(entry['requires'])}")
        if entry.get("generates"):
            click.echo(f"\nGenerates: {', '.join(entry['generates'])}")
        click.echo()


def _render_tree(schema: dict[str, t.Any], order: list[list[str]]) -> None:
    action_ids = [aid for level in order for aid in level]
    producers = build_producer_map(schema)
    dependents: dict[str, list[str]] = {aid: [] for aid in action_ids}
    for aid in action_ids:
        for artifact_id in get_requires(schema, aid):
            for producer in producers.get(artifact_id, []):
                if producer in dependents:
                    dependents[producer].append(aid)

    roots = [aid for aid in action_ids if not get_requires(schema, aid)]

    def _print(node: str, prefix: str, is_last: bool, visited: set[str]) -> None:
        connector = "└── " if is_last else "├── "
        click.echo(f"{prefix}{connector}{node}")
        if node in visited:
            return
        visited.add(node)
        children = dependents.get(node, [])
        new_prefix = prefix + ("    " if is_last else "│   ")
        for i, child in enumerate(children):
            _print(child, new_prefix, i == len(children) - 1, visited)

    visited: set[str] = set()
    for i, root in enumerate(roots):
        _print(root, "", i == len(roots) - 1, visited)


@main.command()
@click.argument("action_id")
@click.option(
    "--schema",
    "schema_name",
    default=None,
    help="Schema name to load (defaults to config.yaml's `schema:`)",
)
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def action(action_id: str, schema_name: t.Optional[str], as_json: bool) -> None:
    """Look up an action by id."""
    try:
        schema_name = resolve_schema_name(schema_name)
        schema = load_schema(schema_name)
        errors = validate_schema(schema)
        if errors:
            raise HoloSpecError("invalid_schema", "; ".join(errors))
        root = find_project_root(schema_name)
        config = load_config(root)
        result = lookup_action(schema, action_id, config)
        result["root"] = str(root) if root else None
    except HoloSpecError as exc:
        _emit_error(exc, as_json)

    if as_json:
        click.echo(json.dumps(result, indent=4))
        return

    _render_action_text(result, action_id)


def _render_action_text(result: dict[str, t.Any], action_id: str) -> None:
    click.echo(f"# {result.get('id', action_id)}")
    if result.get("root"):
        click.echo(f"\nRoot: {result['root']}")
    if result.get("description"):
        click.echo(f"\n{result['description']}")
    if result.get("instruction"):
        click.echo(f"\n## Instruction\n\n{result['instruction']}")
    if result.get("checklist"):
        click.echo(f"\n## Checklist\n\n{result['checklist']}")
    if result.get("requires"):
        click.echo(f"\nRequires: {', '.join(result['requires'])}")
    if result.get("_artifacts_detail"):
        for artifact in result["_artifacts_detail"]:
            click.echo(f"\nGenerates: {artifact.get('generates')}")
            click.echo(f"Template: {artifact.get('template')}")
    if result.get("constitution"):
        click.echo(f"\n## Constitution\n\n{result['constitution']}")
    if result.get("context"):
        click.echo(f"\n## Context\n\n{result['context']}")


SKILL_TEMPLATE_PATH = Path(__file__).resolve().parent / "skills" / "holospec" / "SKILL.md"


@main.command()
@click.option("--schema", "schema_name", default=DEFAULT_SCHEMA, help="Schema name to fetch")
@click.option("--schema-url", "schema_url", default=None, help="Override schema source (path or URL)")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def init(schema_name: str, schema_url: t.Optional[str], as_json: bool) -> None:
    """Initialize a new project or detect an existing one."""
    root = find_any_project_root()
    created = False

    if root is None:
        root = Path.cwd() / PROJECT_ROOT_MARKERS[0]
        root.mkdir(parents=True, exist_ok=True)
        (root / "schemas").mkdir(exist_ok=True)
        config_path = root / "config.yaml"
        if not config_path.exists():
            config_path.write_text("schema: spec-driven\n")
        created = True

    skill_paths = _install_skill(Path.cwd())

    dest_dir = root / "schemas" / schema_name
    schema_fetched = False
    if not (dest_dir / "schema.yaml").is_file():
        location = schema_url or SCHEMA_REGISTRY.get(schema_name)
        if location is None:
            _emit_error(
                HoloSpecError(
                    "schema_not_found",
                    f"No known source for schema '{schema_name}'; pass --schema-url",
                ),
                as_json,
            )
        try:
            fetch_schema(schema_name, location, dest_dir)
        except HoloSpecError as exc:
            _emit_error(exc, as_json)
        schema_fetched = True

    result = {
        "root": str(root),
        "created": created,
        "skills_installed": skill_paths,
        "schema": schema_name,
        "schema_fetched": schema_fetched,
    }

    if as_json:
        click.echo(json.dumps(result, indent=4))
    else:
        action_word = "Scaffolded" if created else "Detected existing"
        click.echo(f"{action_word} root: {root}")
        schema_word = "Fetched" if schema_fetched else "Using existing"
        click.echo(f"{schema_word} schema: {schema_name}")
        for path in skill_paths:
            click.echo(f"Installed skill file: {path}")


def _install_skill(cwd: Path) -> list[str]:
    """
    Write the harness-agnostic canonical skill and symlink it for Claude Code.

    Written to .agents/skills/; Claude Code only reads .claude/skills/, so
    that path is symlinked to it instead.
    """
    agents_skill_dir = cwd / ".agents" / "skills" / "holospec"
    agents_skill_dir.mkdir(parents=True, exist_ok=True)
    (agents_skill_dir / "SKILL.md").write_text(SKILL_TEMPLATE_PATH.read_text())

    claude_skills_dir = cwd / ".claude" / "skills"
    claude_skills_dir.mkdir(parents=True, exist_ok=True)
    link_path = claude_skills_dir / "holospec"
    if link_path.is_symlink() or link_path.exists():
        if link_path.is_symlink():
            link_path.unlink()
        else:
            shutil.rmtree(link_path)
    link_path.symlink_to(os.path.relpath(agents_skill_dir, claude_skills_dir), target_is_directory=True)

    return [str(agents_skill_dir / "SKILL.md"), str(link_path / "SKILL.md")]


def _fetch_url(url: str, dest: Path) -> None:
    try:
        with urllib.request.urlopen(url) as response:  # noqa: S310
            dest.write_bytes(response.read())
    except (URLError, OSError) as exc:
        raise HoloSpecError("schema_fetch_failed", f"Failed to fetch {url}: {exc}") from exc


def fetch_schema(name: str, base_location: str, dest_dir: Path) -> None:
    """Populate dest_dir with schema.yaml + templates/ from a local path or URL."""
    source = Path(base_location)
    dest_dir.mkdir(parents=True, exist_ok=True)

    if source.is_dir():
        try:
            shutil.copy2(source / "schema.yaml", dest_dir / "schema.yaml")
            shutil.copytree(source / "templates", dest_dir / "templates", dirs_exist_ok=True)
        except OSError as exc:
            raise HoloSpecError("schema_fetch_failed", f"Failed to copy schema '{name}' from {source}: {exc}") from exc
        return

    schema_dest = dest_dir / "schema.yaml"
    _fetch_url(f"{base_location}/schema.yaml", schema_dest)

    schema = yaml.safe_load(schema_dest.read_text()) or {}
    templates = {
        artifact["template"]
        for artifact in schema.get("artifacts", [])
        if isinstance(artifact, dict) and artifact.get("template")
    }

    templates_dir = dest_dir / "templates"
    templates_dir.mkdir(exist_ok=True)
    for template_name in templates:
        _fetch_url(f"{base_location}/templates/{template_name}", templates_dir / template_name)


EXPLAIN_OVERVIEW = """\
# HoloSpec

HoloSpec is a stateless instruction layer for spec-driven workflows: it reads
a schema and a project config, then discloses prose instructions/context to an
agent per `action <id>` call rather than executing the workflow itself.

## Project root

A project root is a directory named one of {markers}, directly under the
current directory (earlier names in that list win if more than one exists at
the same level; ancestor directories are never searched). config.yaml and
schemas/ both live directly inside that root directory, not at the
filesystem/repo root.

## schema.yaml and config.yaml

schema.yaml and config.yaml together configure one project. schema.yaml lives at
<root>/schemas/<name>/schema.yaml and defines a workflow made of two kinds of
entries: file-generating `artifacts:` (what gets written, and from which
template) and actions — a schema is free to name and define whatever actions
its workflow needs; none are hardcoded by HoloSpec. Actions are declared
either as bare top-level keys (e.g. `propose:`, `apply:`) or nested under a
single `actions:` mapping — a schema must use exactly one of these two
conventions, never both.
config.yaml lives at `<root>/config.yaml` and selects which schema to use plus
project-specific additions:

- config.yaml's `schema:` names the default schema (schemas/<name>/schema.yaml) to
  resolve; an explicit `--schema` flag on any command overrides it; '{default_schema}' is
  used if neither is set.
- `context:`/`constitution:` may appear in both files: `context` is domain/background
  knowledge (facts to know), `constitution` is behavior (conventions, best practices, and
  rules to follow). Because the schema is forked into the project to be customised,
  schema.yaml's values are what every project on this schema begins with; config.yaml's
  values are this project's own additions on top. Both files' values are concatenated
  (schema first) and neither overrides the other.

## Actions

An action is the unit an agent invokes, via `action <id>`, once per workflow
step. Calling it discloses that action's `instruction` (prose guidance for
performing the step) and `checklist` (completion criteria) — HoloSpec never
executes anything itself, it only discloses text. An action may list zero or
more `artifacts:` (ids of file-generating units it produces, defined in the
schema's top-level `artifacts:` list) and zero or more `requires:` (artifact
ids that must already exist before the action is ready). `requires:` across
all actions forms a dependency graph, not a strict sequence: actions whose
`requires:` are satisfied by the same existing artifacts are independent of
each other and can be run in parallel or in either order.
"""


@main.command()
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def explain(as_json: bool) -> None:
    """Explain the tool and a project's configuration files."""
    overview = EXPLAIN_OVERVIEW.format(
        markers=", ".join(f"`{marker}/`" for marker in PROJECT_ROOT_MARKERS), default_schema=DEFAULT_SCHEMA
    )
    payload = {
        "overview": overview,
        "schema_yaml": Schema.model_json_schema(),
        "config_yaml": Config.model_json_schema(by_alias=True),
    }

    if as_json:
        click.echo(json.dumps(payload, indent=4))
        return

    click.echo(overview)
    click.echo("## schema.yaml field reference\n")
    click.echo("```json")
    click.echo(json.dumps(payload["schema_yaml"], indent=4))
    click.echo("```")
    click.echo("\n## config.yaml field reference\n")
    click.echo("```json")
    click.echo(json.dumps(payload["config_yaml"], indent=4))
    click.echo("```")


def _emit_error(err: "HoloSpecError", as_json: bool) -> t.NoReturn:
    if as_json:
        click.echo(json.dumps(err.to_dict(), indent=4))
    else:
        click.echo(f"Error [{err.code}]: {err.message}", err=True)
    sys.exit(1)


class HoloSpecError(Exception):
    """Indicates that a HoloSpec operation failed."""

    def __init__(self, code: str, message: str):
        """Initialize with an error code and message."""
        self.code = code
        self.message = message
        super().__init__(message)

    def to_dict(self) -> dict[str, t.Any]:
        """Return the error as a JSON-serializable dict."""
        return {"error": {"code": self.code, "message": self.message}}


class Artifact(BaseModel):
    """An agent-maintained document referenced by an action's `artifacts:` list.

    Not a general file-precondition mechanism — a step that merely depends on
    a file existing belongs in that action's own instruction/checklist
    prose instead.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        description="Unique id other actions reference in their own `artifacts:` list.", examples=["proposal"]
    )
    generates: str = Field(
        description="Path (or glob, e.g. 'specs/**/*.md') this artifact writes, relative to the project root.",
        examples=["proposal.md", "specs/**/*.md"],
    )
    template: str = Field(
        description="Template filename under schemas/<name>/templates/ to draft this artifact from.",
        examples=["proposal.md"],
    )
    description: str | None = Field(
        default=None,
        description="Short human-readable summary of this artifact.",
        examples=["Initial proposal document outlining the change"],
    )
    instruction: str | None = Field(
        default=None, description="Prose guidance for drafting this artifact, disclosed verbatim by `action <id>`."
    )


class Action(BaseModel):
    """A top-level workflow action key (e.g. `propose`, `apply`) in schema.yaml."""

    model_config = ConfigDict(extra="forbid")

    artifacts: list[str] = Field(
        default=[],
        description="Artifact ids (from the schema's top-level `artifacts:` list) this action produces.",
        examples=[["proposal"]],
    )
    requires: list[str] = Field(
        default=[],
        description="Artifact ids that must exist before this action can run; drives the derived dependency graph.",
        examples=[["design"], []],
    )
    instruction: str | None = Field(default=None, description="Prose guidance for performing this action.")
    checklist: str | None = Field(
        default=None, description="Prose completion criteria for this action, disclosed to the agent."
    )
    description: str | None = Field(
        default=None,
        description="Short human-readable summary of this action.",
        examples=["Establish the why before diving into specs or design"],
    )


class Schema(BaseModel):
    """The shape of a `schema.yaml` file. Any key not listed below is treated as an action id (see Action)."""

    model_config = ConfigDict(extra="allow")

    name: str | None = Field(
        default=None,
        description="Schema name, matched against `--schema`/config.yaml's `schema:`.",
        examples=["spec-driven"],
    )
    version: int | None = Field(default=None, description="Schema version number, informational only.", examples=[1])
    description: str | None = Field(
        default=None,
        description="Short human-readable summary of this schema.",
        examples=["A workflow for drafting and applying spec changes"],
    )
    context: str | None = Field(
        default=None,
        description=(
            "Domain/background knowledge every project starting from this schema begins with — facts about "
            "the subject matter, not instructions for behavior. Concatenated with config.yaml's own `context` "
            "(schema value first, neither overrides the other) and disclosed on every `action <id>` lookup."
        ),
    )
    constitution: str | None = Field(
        default=None,
        description=(
            "Behavior every project starting from this schema begins with — conventions, best practices, and "
            "rules the agent must follow, regardless of which action is running. Concatenated with config.yaml's "
            "own `constitution` (schema value first, neither overrides the other) and disclosed on every "
            "`action <id>` lookup."
        ),
    )
    artifacts: list[Artifact] = Field(
        default=[], description="File-generating units that actions reference by id in their own `artifacts:` list."
    )
    actions: dict[str, Action] = Field(
        default={},
        description=(
            "Actions keyed by id. A schema must use either this field or bare top-level action "
            "keys (e.g. `propose:`, `apply:`), never both in the same file."
        ),
    )

    def _duplicate_artifact_errors(self) -> list[str]:
        errors: list[str] = []
        seen: set[str] = set()
        for artifact in self.artifacts:
            if artifact.id in seen:
                errors.append(f"Duplicate artifact id: {artifact.id}")
            seen.add(artifact.id)
        return errors

    def _resolve_actions(self, bare_actions: dict[str, t.Any]) -> tuple[dict[str, Action], list[str]]:
        errors: list[str] = []
        actions: dict[str, Action] = dict(self.actions)
        for key, value in bare_actions.items():
            try:
                actions[key] = Action.model_validate(value)
            except ValidationError as exc:
                for err in exc.errors():
                    errors.append(f"Action '{key}': {_format_pydantic_error(err)}")
        return actions, errors

    def _unknown_reference_errors(self, actions: dict[str, Action], artifact_ids: set[str]) -> list[str]:
        errors: list[str] = []
        for key, action in actions.items():
            for aid in action.artifacts:
                if aid not in artifact_ids:
                    errors.append(f"Action '{key}': artifacts references unknown artifact id '{aid}'")
            for req in action.requires:
                if req not in artifact_ids:
                    errors.append(f"Action '{key}': requires references unknown artifact id '{req}'")
        return errors

    @model_validator(mode="after")
    def _check_cross_references(self) -> "Schema":
        errors = self._duplicate_artifact_errors()
        artifact_ids = {artifact.id for artifact in self.artifacts}

        bare_actions = dict(self.model_extra or {})
        if bare_actions and self.actions:
            errors.append("Schema mixes bare top-level action keys with the `actions:` field; use only one convention")
        else:
            actions, resolve_errors = self._resolve_actions(bare_actions)
            errors.extend(resolve_errors)
            errors.extend(self._unknown_reference_errors(actions, artifact_ids))

        if errors:
            raise ValidationError.from_exception_data(
                "Schema",
                [InitErrorDetails(type=PydanticCustomError("value_error", e), loc=(), input=None) for e in errors],
            )
        return self


class Config(BaseModel):
    """The shape of a `config.yaml` file, which lives at the project root alongside schemas/<name>/schema.yaml."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str | None = Field(
        default=None,
        alias="schema",
        description=(
            "Name of the schema to resolve by default (looked up at schemas/<name>/schema.yaml). "
            f"Overridden by an explicit `--schema` flag; falls back to '{DEFAULT_SCHEMA}' if neither is set."
        ),
        examples=[DEFAULT_SCHEMA],
    )
    context: str | None = Field(
        default=None,
        description=(
            "Domain/background knowledge this project adds on top of the schema's own `context` — facts about "
            "this project, not instructions for behavior. Concatenated with it (schema value first) and "
            "disclosed on every `action <id>` lookup."
        ),
    )
    constitution: str | None = Field(
        default=None,
        description=(
            "Behavior this project adds on top of the schema's own `constitution` — conventions, best practices, "
            "and rules the agent must follow here, beyond the schema's own rules. Concatenated with it (schema "
            "value first) and disclosed on every `action <id>` lookup."
        ),
    )


def validate_schema(schema: dict[str, t.Any]) -> list[str]:
    """Validate a loaded schema dict. Returns a list of error strings (empty if valid)."""
    if not isinstance(schema, dict):
        return ["Schema must be a mapping at the top level"]

    try:
        Schema.model_validate(schema)
    except ValidationError as exc:
        return [_format_pydantic_error(err) for err in exc.errors()]

    return []


def _format_pydantic_error(err: "ErrorDetails") -> str:
    if err["loc"] == ():
        return str(err["msg"])
    location = ".".join(str(p) for p in err["loc"])
    return f"{location}: {err['msg']}"


def load_schema_file(path: Path) -> dict[str, t.Any]:
    """Load and parse a schema YAML file from disk."""
    try:
        with open(path, "r") as f:
            schema = yaml.safe_load(f)
    except FileNotFoundError as exc:
        raise HoloSpecError("schema_not_found", f"Schema file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise HoloSpecError("invalid_schema", f"Failed to parse schema YAML: {exc}") from exc

    if schema is None:
        raise HoloSpecError("invalid_schema", f"Schema file is empty: {path}")

    return t.cast(dict[str, t.Any], schema)


def find_any_project_root(start: t.Optional[Path] = None) -> t.Optional[Path]:
    """
    Look for a project root marker directory directly under start (or cwd).

    See PROJECT_ROOT_MARKERS. Regardless of what schemas it carries.
    Used only for root detection (e.g. `init`), where there's no schema name
    to qualify against yet. Does not walk up ancestor directories: the
    project root is always directly under the current directory. Markers
    are checked in PROJECT_ROOT_MARKERS order; the first match wins if more
    than one exists at the same level.
    """
    current = (start or Path.cwd()).resolve()
    for marker in PROJECT_ROOT_MARKERS:
        candidate_root = current / marker
        if candidate_root.is_dir():
            return candidate_root
    return None


def find_project_root(name: str, start: t.Optional[Path] = None) -> t.Optional[Path]:
    """
    Look for a project root marker directory with schemas/<name>/schema.yaml under it.

    See PROJECT_ROOT_MARKERS. Directly under start (or cwd).
    Markers are checked in PROJECT_ROOT_MARKERS order; the first match wins
    if more than one exists at the same level. Does not walk up ancestor
    directories: the project root is always directly under the current
    directory.
    """
    current = (start or Path.cwd()).resolve()
    for marker in PROJECT_ROOT_MARKERS:
        candidate_root = current / marker
        if (candidate_root / "schemas" / name / "schema.yaml").is_file():
            return candidate_root
    return None


def resolve_schema_path(name: str, start: t.Optional[Path] = None) -> t.Optional[Path]:
    """Project-local resolution: qualifying project root directly under start (or cwd)."""
    root = find_project_root(name, start)
    if root is not None:
        return root / "schemas" / name / "schema.yaml"
    return None


def load_schema(name: str, start: t.Optional[Path] = None) -> dict[str, t.Any]:
    """Resolve a schema by name (project-local lookup) or by direct filepath."""
    direct = Path(name)
    if direct.suffix in (".yaml", ".yml") or os.sep in name:
        if direct.is_file():
            return load_schema_file(direct)
        raise HoloSpecError("schema_not_found", f"Schema file not found: {direct}")

    path = resolve_schema_path(name, start)
    if path is not None:
        return load_schema_file(path)

    raise HoloSpecError("schema_not_found", f"Schema '{name}' not found in any resolution tier")


def load_config(root: t.Optional[Path]) -> dict[str, t.Any]:
    """Load <root>/config.yaml if present. Returns {} if root or the file is absent."""
    if root is None:
        return {}
    config_path = root / "config.yaml"
    if not config_path.is_file():
        return {}
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config if isinstance(config, dict) else {}


def resolve_schema_name(schema_name: t.Optional[str]) -> str:
    """Explicit --schema wins; otherwise use config.yaml's `schema:`, else DEFAULT_SCHEMA."""
    if schema_name is not None:
        return schema_name
    config = load_config(find_any_project_root())
    return config.get("schema") or DEFAULT_SCHEMA


def get_action_ids(schema: dict[str, t.Any]) -> list[str]:
    """List action ids, from either bare top-level keys or `actions:`."""
    actions = schema.get("actions")
    if isinstance(actions, dict) and actions:
        return list(actions)
    return [k for k in schema if k not in RESERVED_KEYS]


def get_action(schema: dict[str, t.Any], action_id: str) -> t.Any:
    """Look up a single action's raw definition, from either bare top-level keys or `actions:`."""
    actions = schema.get("actions")
    if isinstance(actions, dict) and actions:
        return actions.get(action_id)
    return schema.get(action_id)


def get_requires(schema: dict[str, t.Any], action_id: str) -> list[str]:
    """List artifact ids an action's `requires:` names."""
    action = get_action(schema, action_id)
    if not isinstance(action, dict):
        return []
    return action.get("requires", []) or []


def build_producer_map(schema: dict[str, t.Any]) -> dict[str, list[str]]:
    """Map each artifact id to the action id(s) whose `artifacts:` list produces it."""
    producers: dict[str, list[str]] = {}
    for aid in get_action_ids(schema):
        action = get_action(schema, aid)
        if not isinstance(action, dict):
            continue
        for artifact_id in action.get("artifacts", []) or []:
            producers.setdefault(artifact_id, []).append(aid)
    return producers


def actions_topology(schema: dict[str, t.Any]) -> list[list[str]]:
    """
    Order actions into dependency levels.

    Each level's actions are only blocked by prior levels, so actions within
    the same level can run in parallel.
    """
    action_ids = get_action_ids(schema)
    producers = build_producer_map(schema)
    in_degree = dict.fromkeys(action_ids, 0)
    dependents: dict[str, list[str]] = {aid: [] for aid in action_ids}

    # Build the dependency graph: edges point from a producer action to the
    # action(s) that require the artifact it produces
    for aid in action_ids:
        for artifact_id in get_requires(schema, aid):
            for producer in producers.get(artifact_id, []):
                if producer in dependents:
                    dependents[producer].append(aid)
                    in_degree[aid] += 1

    # Kahn's algorithm, peeling one whole level (all currently-ready actions) at a time
    level = sorted([aid for aid in action_ids if in_degree[aid] == 0])
    order: list[list[str]] = []

    while level:
        order.append(level)
        next_level: list[str] = []
        for current in level:
            for dependent in dependents[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    next_level.append(dependent)
        level = sorted(next_level)

    # If not all actions were ordered, a cycle is keeping some in_degree above 0
    ordered_ids = {aid for level in order for aid in level}
    if len(ordered_ids) != len(action_ids):
        remaining = set(action_ids) - ordered_ids
        raise HoloSpecError("invalid_schema", f"Cycle detected in requires graph among: {sorted(remaining)}")

    return order


def _merge_always_on(schema: dict[str, t.Any], config: dict[str, t.Any], result: dict[str, t.Any]) -> None:
    """Concatenate schema- and config-level context/constitution into result. Neither source overrides the other."""
    for key in ("context", "constitution"):
        parts = [v for v in (schema.get(key), config.get(key)) if v]
        if parts:
            result[key] = "\n\n".join(parts)


def lookup_action(
    schema: dict[str, t.Any], action_id: str, config: t.Optional[dict[str, t.Any]] = None
) -> dict[str, t.Any]:
    """Look up an action by id across artifacts[].id and top-level action keys."""
    config = config or {}
    action_ids = get_action_ids(schema)

    if action_id in action_ids:
        action = get_action(schema, action_id)
        result = dict(action) if isinstance(action, dict) else {}
        result["id"] = action_id

        # Resolve artifact metadata (generates/template) for referenced artifacts
        artifacts = schema.get("artifacts", [])
        artifact_map = {a["id"]: a for a in artifacts if isinstance(a, dict) and "id" in a}
        referenced = result.get("artifacts", [])
        resolved_artifacts = []
        for aid in referenced:
            if aid in artifact_map:
                resolved_artifacts.append(artifact_map[aid])
        if resolved_artifacts:
            result["_artifacts_detail"] = resolved_artifacts

        _merge_always_on(schema, config, result)
        return result

    # Fall back: bare artifact id lookup (not a top-level action, but still identifiable)
    artifacts = schema.get("artifacts", [])
    for artifact in artifacts:
        if isinstance(artifact, dict) and artifact.get("id") == action_id:
            result = dict(artifact)
            _merge_always_on(schema, config, result)
            return result

    raise HoloSpecError("action_not_found", f"No action or artifact found with id '{action_id}'")


if __name__ == "__main__":
    main()
