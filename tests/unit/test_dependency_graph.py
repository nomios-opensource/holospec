import pytest

from holospec import HoloSpecError, actions_topology, build_producer_map, get_requires


def test_given_linear_chain_when_ordered_then_returns_dependency_order():
    # GIVEN a linear chain a -> b -> c, wired via artifacts each action requires
    schema = {
        "artifacts": [
            {"id": "a_out", "generates": "a.md", "template": "a.md"},
            {"id": "b_out", "generates": "b.md", "template": "b.md"},
        ],
        "a": {"artifacts": ["a_out"], "requires": []},
        "b": {"artifacts": ["b_out"], "requires": ["a_out"]},
        "c": {"requires": ["b_out"]},
    }

    # WHEN computing the actions topology
    order = actions_topology(schema)

    # THEN each action is its own level, in dependency order
    assert order == [["a"], ["b"], ["c"]]


def test_given_parallel_branches_when_ordered_then_branches_share_a_level():
    # GIVEN a root with two independent branches depending on its artifact
    schema = {
        "artifacts": [
            {"id": "root_out", "generates": "root.md", "template": "root.md"},
            {"id": "a_out", "generates": "a.md", "template": "a.md"},
            {"id": "b_out", "generates": "b.md", "template": "b.md"},
        ],
        "root": {"artifacts": ["root_out"], "requires": []},
        "branch_a": {"artifacts": ["a_out"], "requires": ["root_out"]},
        "branch_b": {"artifacts": ["b_out"], "requires": ["root_out"]},
        "join": {"requires": ["a_out", "b_out"]},
    }

    # WHEN computing the actions topology
    order = actions_topology(schema)

    # THEN root is the sole first level, branch_a/branch_b share a level, and
    # join is the sole last level
    assert order[0] == ["root"]
    assert order[1] == ["branch_a", "branch_b"]
    assert order[-1] == ["join"]


def test_given_cycle_when_ordered_then_raises_invalid_schema_error():
    # GIVEN a cycle: a requires b's artifact, b requires a's artifact
    schema = {
        "artifacts": [
            {"id": "a_out", "generates": "a.md", "template": "a.md"},
            {"id": "b_out", "generates": "b.md", "template": "b.md"},
        ],
        "a": {"artifacts": ["a_out"], "requires": ["b_out"]},
        "b": {"artifacts": ["b_out"], "requires": ["a_out"]},
    }

    # WHEN computing the actions topology

    # THEN a cycle error is raised
    with pytest.raises(HoloSpecError) as exc_info:
        actions_topology(schema)
    assert exc_info.value.code == "invalid_schema"
    assert "Cycle detected" in exc_info.value.message


def test_given_no_actions_when_ordered_then_returns_empty_order():
    # GIVEN a schema with only reserved keys and no actions
    schema = {"name": "empty", "version": 1}

    # WHEN computing the actions topology
    order = actions_topology(schema)

    # THEN the order is empty
    assert order == []


def test_given_action_value_is_not_a_mapping_when_getting_requires_then_returns_empty_list():
    # GIVEN an action key whose value is not a mapping
    schema = {"propose": "not a mapping"}

    # WHEN getting its requires
    requires = get_requires(schema, "propose")

    # THEN an empty list is returned rather than raising
    assert requires == []


def test_given_action_value_is_not_a_mapping_when_building_producer_map_then_skipped():
    # GIVEN an action key whose value is not a mapping
    schema = {"propose": "not a mapping"}

    # WHEN building the producer map
    producers = build_producer_map(schema)

    # THEN no producers are recorded for it
    assert producers == {}


def test_given_actions_dict_convention_when_ordered_then_returns_dependency_order():
    # GIVEN a linear chain a -> b, declared under the actions: mapping instead
    # of as bare top-level keys
    schema = {
        "artifacts": [
            {"id": "a_out", "generates": "a.md", "template": "a.md"},
        ],
        "actions": {
            "a": {"artifacts": ["a_out"], "requires": []},
            "b": {"requires": ["a_out"]},
        },
    }

    # WHEN computing the actions topology
    order = actions_topology(schema)

    # THEN each action is resolved from the actions: mapping, in dependency order
    assert order == [["a"], ["b"]]
