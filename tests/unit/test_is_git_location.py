import pytest

from holospec import _is_git_location


@pytest.mark.parametrize(
    "location",
    [
        "git@github.com:acme/holospec-schemas.git",
        "git@github.com:acme/holospec-schemas",
        "ssh://git@github.com:2222/acme/holospec-schemas",
        "git://example.com/holospec-schemas",
        "https://github.com/acme/holospec-schemas.git",
        "git@github.com:acme/holospec-schemas.git#v1.2.0",
    ],
)
def test_given_git_style_location_when_checked_then_true(location):
    # GIVEN / WHEN / THEN a git-style location is recognised, with or without a #ref
    assert _is_git_location(location) is True


@pytest.mark.parametrize("location", ["https://example.com/schemas", "/local/path", "./schemas/openspec"])
def test_given_non_git_location_when_checked_then_false(location):
    # GIVEN / WHEN / THEN a path or plain URL is not treated as git
    assert _is_git_location(location) is False
