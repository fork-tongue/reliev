from unittest.mock import Mock

import pytest
from observ import watch

from reliev.store import Store, computed, mutation


class CustomStore(Store):
    @mutation
    def bump_count(self):
        self.state["count"] += 1

    @computed
    def double(self):
        return self.state["count"] * 2


def test_store_undo_redo():
    store = CustomStore(state={"count": 0})
    assert store.state["count"] == 0
    assert not store.can_undo
    assert not store.can_redo

    store.bump_count()
    assert store.state["count"] == 1
    assert not store.can_redo

    store.undo()
    assert store.state["count"] == 0
    assert not store.can_undo
    assert store.can_redo

    store.redo()
    assert store.state["count"] == 1
    assert store.can_undo
    assert not store.can_redo

    store.bump_count()
    assert store.state["count"] == 2
    assert store.can_undo
    assert not store.can_redo

    store.undo()
    store.undo()
    assert store.state["count"] == 0
    assert not store.can_undo
    assert store.can_redo

    store.bump_count()
    assert store.can_undo
    assert not store.can_redo


def test_store_computed_methods():
    store = CustomStore(state={"count": 0})

    assert store.state["count"] == 0
    assert store.double == 0

    store.bump_count()

    assert store.state["count"] == 1
    assert store.double == 2


def test_store_undo_redo_unchanged_watcher():
    store = CustomStore(state={"count": 0, "foo": {}})
    watcher = watch(lambda: store.state["foo"], Mock(), sync=True)

    store.bump_count()
    assert store.state["count"] == 1
    watcher.callback.assert_not_called()

    store.undo()
    assert store.state["count"] == 0
    watcher.callback.assert_not_called()


def test_store_computed_deep():
    class DeepStore(Store):
        @computed
        def deep_items(self):
            return self.state["items"]

        @computed(deep=False)
        def shallow_items(self):
            return self.state["items"]

        @mutation
        def add_item(self, item):
            self.state["items"].append(item)

    store = DeepStore({"items": []})
    deep_watcher = watch(lambda: store.deep_items, Mock(), sync=True, deep=True)
    shallow_watcher = watch(lambda: store.shallow_items, Mock(), sync=True)

    store.add_item(3)
    shallow_watcher.callback.assert_not_called()
    deep_watcher.callback.assert_called_once()


def test_store_undo_redo_all_types():
    class SetStore(Store):
        @mutation
        def add(self, item):
            self.state["set"].add(item)

        @mutation
        def append(self, item):
            self.state["list"].append(item)

        @mutation
        def set(self, key, value):
            self.state["dict"][key] = value

    store = SetStore(
        {
            "set": {"a"},
            "list": ["a"],
            "dict": {"a": "b"},
        }
    )
    assert store.state["set"] == {"a"}
    assert store.state["list"] == ["a"]
    assert store.state["dict"] == {"a": "b"}

    store.add("b")
    assert store.state["set"] == {"a", "b"}
    store.undo()
    assert store.state["set"] == {"a"}

    store.append("b")
    assert store.state["list"] == ["a", "b"]
    store.undo()
    assert store.state["list"] == ["a"]

    store.set("b", "c")
    assert store.state["dict"] == {"a": "b", "b": "c"}
    store.undo()
    assert store.state["dict"] == {"a": "b"}


def test_store_empty_mutation_non_strict_store():
    class SimpleStore(Store):
        @mutation
        def update_count(self, count):
            self.state["count"] = count

    # Create a store with strict set to False
    store = SimpleStore({"count": 1}, strict=False)
    assert store.state["count"] == 1
    assert not store.can_undo

    # Update with the same number. This should
    # result in no change being recorded
    store.update_count(1)
    assert not store.can_undo

    # Check that if we do supply another number
    # that a change will actually be recorded
    store.update_count(2)
    assert store.can_undo


def test_store_empty_mutation_strict_store():
    class SimpleStore(Store):
        @mutation
        def update_count(self, count):
            self.state["count"] = count

    # Create a store with strict set to True
    # (is the default value for `strict` argument)
    store = SimpleStore({"count": 1})
    assert store.state["count"] == 1
    assert not store.can_undo

    # Update with the same number. This should
    # trigger a RuntimeError
    with pytest.raises(RuntimeError):
        store.update_count(1)


def test_computed_attribute_rejects_assignment():
    """Computed methods are exposed as property-like descriptors, so direct
    assignment must raise rather than silently shadow the computed value."""
    store = CustomStore(state={"count": 0})
    with pytest.raises(AttributeError):
        store.double = 99


def test_computed_is_installed_as_property():
    """@computed should produce a plain stdlib property on the class, so it
    behaves like any other read-only attribute (and assignment raises by
    virtue of property's built-in setter behavior)."""
    assert isinstance(CustomStore.__dict__["double"], property)


def test_store_nested_mutations_collapse_to_single_entry():
    """A mutation that calls another mutation should produce one undo entry
    covering all of the changes, not raise and not produce multiple entries."""

    class NestedStore(Store):
        @mutation
        def inc(self):
            self.state["n"] += 1

        @mutation
        def double_inc(self):
            self.inc()
            self.inc()

    store = NestedStore({"n": 0})
    store.double_inc()
    assert store.state["n"] == 2
    # Both inner inc() calls must collapse into a single undo entry on the
    # outer double_inc() mutation.
    assert len(store._past) == 1

    store.undo()
    assert store.state["n"] == 0
    assert not store.can_undo
    assert store.can_redo

    store.redo()
    assert store.state["n"] == 2


def test_mutation_reason():
    class ReasonStore(Store):
        @mutation(reason="Increment counter")
        def bump(self):
            self.state["count"] += 1

        @mutation(reason=lambda self, amount: ("adjusted_count", amount))
        def adjust(self, amount):
            self.state["count"] = amount

        @mutation
        def reset(self):
            self.state["count"] = 0

    store = ReasonStore({"count": 0})
    assert store.undo_reason is None
    assert store.redo_reason is None

    # Static reason
    store.bump()
    assert store.undo_reason == "Increment counter"
    assert store.redo_reason is None

    # Callable reason receives the same arguments as the mutation
    # and can return any (hashable) value, such as a tuple
    store.adjust(5)
    assert store.undo_reason == ("adjusted_count", 5)

    # Mutations without a reason record None
    store.reset()
    assert store.undo_reason is None

    # Reasons move along with undo/redo
    store.undo()
    assert store.undo_reason == ("adjusted_count", 5)
    assert store.redo_reason is None
    store.undo()
    assert store.undo_reason == "Increment counter"
    assert store.redo_reason == ("adjusted_count", 5)
    store.redo()
    assert store.undo_reason == ("adjusted_count", 5)
    assert store.redo_reason is None

    # New mutations clear the redo stack and its reasons
    store.undo()
    store.bump()
    assert store.redo_reason is None


def test_mutation_reason_call_override():
    class ReasonStore(Store):
        @mutation(reason="Increment counter")
        def bump(self):
            self.state["count"] += 1

        @mutation
        def adjust(self, amount):
            self.state["count"] = amount

    store = ReasonStore({"count": 0})

    # `mutation_reason` overrides the reason from the decorator
    # and is not passed on to the mutation itself
    store.bump(mutation_reason="Increment counter (override)")
    assert store.undo_reason == "Increment counter (override)"

    # It also works for mutations without a decorator reason
    store.adjust(3, mutation_reason=("adjusted_count", 3))
    assert store.undo_reason == ("adjusted_count", 3)


def test_mutation_reason_nested_mutations():
    class NestedStore(Store):
        @mutation(reason="inner")
        def inc(self):
            self.state["n"] += 1

        @mutation(reason="outer")
        def double_inc(self):
            self.inc()
            self.inc(mutation_reason="inner override")

    store = NestedStore({"n": 0})
    store.double_inc()
    assert store.state["n"] == 2
    # The outer mutation is the transactional boundary,
    # so its reason wins over any nested reasons
    assert store.undo_reason == "outer"


def test_mutation_reason_is_reactive():
    class ReasonStore(Store):
        @mutation(reason="Increment counter")
        def bump(self):
            self.state["count"] += 1

    store = ReasonStore({"count": 0})
    watcher = watch(lambda: store.undo_reason, Mock(), sync=True)

    store.bump()
    watcher.callback.assert_called_once()
    assert store.undo_reason == "Increment counter"

    watcher.callback.reset_mock()
    store.undo()
    watcher.callback.assert_called_once()
    assert store.undo_reason is None


def test_mutation_strict_keyword_argument():
    class SimpleStore(Store):
        @mutation
        def update_count(self, count):
            self.state["count"] = count

        @mutation(strict=False)
        def update_count_non_strict(self, count):
            self.state["count"] = count

        @mutation(strict=True)
        def update_count_strict(self, count):
            self.state["count"] = count

    # Create a store with strict set to True (default)
    store = SimpleStore({"count": 1})
    assert store.state["count"] == 1
    assert not store.can_undo

    # Update with the same number using non-strict mutation
    # This should NOT raise an error and should NOT record a change
    store.update_count_non_strict(1)
    assert not store.can_undo

    # Update with a different number to verify store still works
    store.update_count(2)
    assert store.can_undo
    assert store.state["count"] == 2

    # Now create a non-strict store
    store2 = SimpleStore({"count": 5}, strict=False)
    assert store2.state["count"] == 5
    assert not store2.can_undo

    # Update with the same number using strict mutation decorator
    # This should raise an error even though the store is non-strict
    with pytest.raises(RuntimeError):
        store2.update_count_strict(5)

    # Verify the store still works normally with default behavior
    store2.update_count(5)
    assert not store2.can_undo  # No change recorded in non-strict mode

    store2.update_count(6)
    assert store2.can_undo  # Change recorded
    assert store2.state["count"] == 6
