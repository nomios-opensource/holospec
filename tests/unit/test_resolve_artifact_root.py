from pathlib import Path

from holospec import resolve_artifact_root


def test_given_no_root_override_when_resolved_then_returns_default_root():
    # GIVEN an artifact without a root override
    artifact = {"id": "a", "generates": "a.md"}

    # WHEN resolving its root against a default
    result = resolve_artifact_root(artifact, Path("/project/holospec"))

    # THEN the default root passes through unchanged
    assert result == Path("/project/holospec")


def test_given_relative_root_override_when_resolved_then_joins_cwd():
    # GIVEN an artifact with a relative root override
    artifact = {"id": "a", "generates": "a.md", "root": "."}

    # WHEN resolving its root
    result = resolve_artifact_root(artifact, Path("/project/holospec"))

    # THEN it resolves relative to the current working directory, not the default root
    assert result == Path.cwd() / "."


def test_given_absolute_root_override_when_resolved_then_used_as_is():
    # GIVEN an artifact with an absolute root override
    artifact = {"id": "a", "generates": "a.md", "root": "/shared/implementation-reports"}

    # WHEN resolving its root
    result = resolve_artifact_root(artifact, Path("/project/holospec"))

    # THEN the absolute path is used as-is
    assert result == Path("/shared/implementation-reports")
