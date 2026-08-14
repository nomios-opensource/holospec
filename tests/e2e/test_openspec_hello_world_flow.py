"""
Live-agent e2e test: costs real API usage, never runs by default.

See AGENTS.md for why this suite is opt-in only. Run explicitly with:
    uv run pytest -m e2e tests/e2e --no-cov

Uses a test class (breaking the repo's usual "no test classes" convention)
specifically because pytest runs a class's methods in definition order and
lets them share instance state (self.project) — each stage here depends on
artifacts the previous stage's agent call left on disk.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

claude_agent_sdk = pytest.importorskip(
    "claude_agent_sdk", reason="e2e deps not installed - see AGENTS.md, run `uv sync --group e2e`"
)
AssistantMessage = claude_agent_sdk.AssistantMessage
ClaudeAgentOptions = claude_agent_sdk.ClaudeAgentOptions
TextBlock = claude_agent_sdk.TextBlock
ToolUseBlock = claude_agent_sdk.ToolUseBlock
query = claude_agent_sdk.query

# Matches a `holospec` invocation's subcommand and, for `action`, the
# action id that follows it, e.g. "holospec action propose --json" ->
# "action propose"; "holospec workflow --json" -> "workflow".
HOLOSPEC_CALL_RE = re.compile(r"\bholospec\s+(action\s+\S+|\S+)")

pytestmark = [pytest.mark.e2e, pytest.mark.asyncio]

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OPENSPEC_SCHEMA_DIR = REPO_ROOT / "schemas" / "openspec"
SKILL_SOURCE_PATH = REPO_ROOT / "skills" / "holospec" / "SKILL.md"

TASK_BRIEF = """\
Build a Python script `hello.py` in the current directory that, when run,
prints "Hello, world!" followed by the current date and time.
"""

STAGE_PROMPT = """\
This is an automated test run - be concise and token/cost economic. Keep
every artifact minimal and skip anything not strictly necessary.

This project uses HoloSpec for openspec development. Work through the
"{action}" HoloSpec action only, for this change:

{task_brief}
Do not run any other HoloSpec action - stop once "{action}"'s checklist is
satisfied.
"""


async def _run_agent(cwd: Path, action: str) -> list[str]:
    """Drive one HoloSpec action and return the `holospec` subcommands invoked, in order."""
    options = ClaudeAgentOptions(
        cwd=str(cwd),
        model="sonnet",
        effort="low",
        permission_mode="acceptEdits",
        allowed_tools=["Read", "Write", "Bash", "Glob"],
        skills=["holospec"],
        max_turns=40,
    )
    prompt = STAGE_PROMPT.format(action=action, task_brief=TASK_BRIEF)

    holospec_calls: list[str] = []
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock) and block.name == "Bash":
                    command = block.input.get("command", "")
                    holospec_calls.extend(HOLOSPEC_CALL_RE.findall(command))
    return holospec_calls


class TestOpenSpecHelloWorldFlow:
    """Drives one HoloSpec change through propose, ff (plan), apply, archive."""

    @staticmethod
    @pytest.fixture(scope="class")
    def project(tmp_path_factory):  # noqa: D102
        project_dir = tmp_path_factory.mktemp("openspec_project")

        # Install the real HoloSpec openspec schema and skill file exactly
        # as `holospec init` would, so the agent discovers the protocol
        # itself via the installed skill rather than being told about it.
        shutil.copytree(OPENSPEC_SCHEMA_DIR, project_dir / "holospec" / "schemas" / "openspec")
        (project_dir / "holospec" / "config.yaml").write_text("schema: openspec\n")

        installed_skill_dir = project_dir / ".claude" / "skills" / "holospec"
        installed_skill_dir.mkdir(parents=True)
        shutil.copy(SKILL_SOURCE_PATH, installed_skill_dir / "SKILL.md")

        return project_dir

    async def test_given_new_change_when_propose_run_then_proposal_exists(self, project):  # noqa: D102
        # GIVEN a project with the real HoloSpec openspec schema and skill installed

        # WHEN a real Claude agent works the "propose" action only
        calls = await _run_agent(project, "propose")

        # THEN a proposal document exists under the change's own directory
        assert list(project.glob("holospec/changes/*/proposal.md"))

        # AND the agent discovered the workflow before acting on it, and
        # looked up "propose" specifically rather than some other action
        assert "workflow" in calls
        assert calls.index("workflow") < calls.index("action propose")

    async def test_given_proposal_when_ff_run_then_plan_artifacts_exist(self, project):  # noqa: D102
        # GIVEN a proposal from the previous stage

        # WHEN a real Claude agent fast-forwards through the remaining
        # planning artifacts (specs, design, tasks)
        calls = await _run_agent(project, "ff")

        # THEN specs and a tasks breakdown exist (design is conditional and
        # may legitimately be skipped for a change this small)
        assert list(project.glob("holospec/changes/*/specs/**/*.md"))
        assert list(project.glob("holospec/changes/*/tasks.md"))

        # AND the agent looked up the workflow before running "ff"
        assert "workflow" in calls
        assert "action ff" in calls
        assert calls.index("workflow") < calls.index("action ff")

    async def test_given_plan_when_apply_run_then_script_works_and_tasks_complete(self, project):  # noqa: D102
        # GIVEN a completed plan from the previous stage

        # WHEN a real Claude agent works the "apply" action only
        calls = await _run_agent(project, "apply")

        # THEN the CLI was consulted before applying, and "apply" was the
        # action looked up
        assert "workflow" in calls
        assert calls.index("workflow") < calls.index("action apply")

        # AND every task is checked off
        tasks_files = list(project.glob("holospec/changes/*/tasks.md"))
        assert tasks_files
        tasks_text = tasks_files[0].read_text()
        assert "[ ]" not in tasks_text

        # AND the resulting hello-world script runs and prints a greeting
        # with a timestamp
        script = project / "hello.py"
        assert script.exists()

        result = subprocess.run(  # noqa: S603
            [sys.executable, str(script)],
            cwd=project,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        assert "Hello, world!" in result.stdout

    async def test_given_applied_change_when_archive_run_then_change_filed_away(self, project):  # noqa: D102
        # GIVEN an applied change with completed tasks from the previous stage

        # WHEN a real Claude agent works the "archive" action only
        calls = await _run_agent(project, "archive")

        # THEN the CLI was consulted before archiving
        assert "workflow" in calls
        assert calls.index("workflow") < calls.index("action archive")

        # AND the change's artifacts are no longer in the active location
        active_changes = [p for p in project.glob("holospec/changes/*") if p.is_dir() and p.name != "archive"]
        assert not active_changes

        # AND an archive directory was created to file the change away
        archive_dirs = [p for p in project.glob("**/*") if p.is_dir() and "archive" in p.name.lower()]
        assert archive_dirs, "expected an archive directory to be created"
