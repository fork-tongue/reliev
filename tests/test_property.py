"""
Property-based tests: random sequences of mutations, undos and redos
are checked against a naive model that keeps full deep-copied
snapshots of the expected state.
"""

from copy import deepcopy

from hypothesis import given
from hypothesis import strategies as st
from observ import to_raw

from reliev import Store, computed, mutation


class PropertyStore(Store):
    # All mutations are non-strict so that actions which happen to be
    # no-ops (setting an existing value, popping from an empty list)
    # simply record nothing instead of raising
    @mutation(strict=False, context=lambda self, key, value: ("set", key))
    def set_value(self, key, value):
        self.state["map"][key] = value

    @mutation(strict=False, context=lambda self, key: ("delete", key))
    def delete_value(self, key):
        self.state["map"].pop(key, None)

    # No context: entries recorded by this mutation carry None
    @mutation(strict=False)
    def append_item(self, item):
        self.state["list"].append(item)

    @mutation(strict=False, context="pop")
    def pop_item(self):
        if self.state["list"]:
            self.state["list"].pop()

    @mutation(strict=False, context="add")
    def add_member(self, member):
        self.state["set"].add(member)

    @computed
    def list_size(self):
        return len(self.state["list"])


def apply_to_model(data, action):
    """Apply an action to a plain-data model of the state."""
    kind, *args = action
    if kind == "set":
        data["map"][args[0]] = args[1]
    elif kind == "delete":
        data["map"].pop(args[0], None)
    elif kind == "append":
        data["list"].append(args[0])
    elif kind == "pop":
        if data["list"]:
            data["list"].pop()
    elif kind == "add":
        data["set"].add(args[0])
    return data


def perform(store, action):
    kind, *args = action
    if kind == "set":
        store.set_value(*args)
    elif kind == "delete":
        store.delete_value(*args)
    elif kind == "append":
        store.append_item(*args)
    elif kind == "pop":
        store.pop_item()
    elif kind == "add":
        store.add_member(*args)


def context_for(action):
    """The context the store should record for an action."""
    kind, *args = action
    if kind in ("set", "delete"):
        return (kind, args[0])
    if kind == "append":
        return None
    return kind


keys = st.sampled_from(["a", "b", "c"])
values = st.integers(min_value=0, max_value=3)

actions = st.lists(
    st.one_of(
        st.tuples(st.just("set"), keys, values),
        st.tuples(st.just("delete"), keys),
        st.tuples(st.just("append"), values),
        st.tuples(st.just("pop")),
        st.tuples(st.just("add"), values),
        st.tuples(st.just("undo")),
        st.tuples(st.just("redo")),
    ),
    max_size=30,
)


@given(actions=actions)
def test_store_matches_model(actions):
    store = PropertyStore({"map": {}, "list": [], "set": set()})

    # The model: deep-copied snapshots of every state the store has
    # been in, the index of the present snapshot, and per-snapshot
    # contexts (contexts[i] belongs to the entry that produced
    # snapshots[i]; snapshot 0 is the initial state)
    snapshots = [{"map": {}, "list": [], "set": set()}]
    contexts = [None]
    index = 0

    for action in actions:
        kind = action[0]
        if kind == "undo":
            store.undo()
            if index > 0:
                index -= 1
        elif kind == "redo":
            store.redo()
            if index < len(snapshots) - 1:
                index += 1
        else:
            perform(store, action)
            expected = apply_to_model(deepcopy(snapshots[index]), action)
            if expected != snapshots[index]:
                # A recorded change truncates the redo tail
                del snapshots[index + 1 :]
                del contexts[index + 1 :]
                snapshots.append(expected)
                contexts.append(context_for(action))
                index += 1

        assert to_raw(store.state) == snapshots[index]
        assert store.can_undo == (index > 0)
        assert store.can_redo == (index < len(snapshots) - 1)
        assert store.undo_context == (contexts[index] if index > 0 else None)
        assert store.redo_context == (
            contexts[index + 1] if index < len(snapshots) - 1 else None
        )
        assert store.list_size == len(snapshots[index]["list"])

    # Unwind the whole history and replay it: both walks must visit
    # exactly the recorded snapshots
    while store.can_undo:
        store.undo()
        index -= 1
        assert to_raw(store.state) == snapshots[index]
    assert index == 0
    assert to_raw(store.state) == snapshots[0]

    while store.can_redo:
        store.redo()
        index += 1
        assert to_raw(store.state) == snapshots[index]
    assert index == len(snapshots) - 1


def test_undo_redo_are_noops_without_history():
    store = PropertyStore({"map": {}, "list": [], "set": set()})

    store.undo()
    store.redo()

    assert to_raw(store.state) == {"map": {}, "list": [], "set": set()}
    assert not store.can_undo
    assert not store.can_redo
