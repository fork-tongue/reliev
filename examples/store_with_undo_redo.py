"""
Example that shows how to use the store module
for undo/redo functionality
"""

from observ import watch

from reliev import Store, computed, mutation


class CounterStore(Store):
    @mutation(context="Bump count")
    def bump_count(self):
        """
        Bump counter by one.

        Note: normally self.state is a readonly proxy on the present
        state, but because this method is decorated with `mutation`
        `self.state` is replaced with the mutable `self._present`
        for the scope of this method to record any changes.

        The `context` is attached to the recorded undo entry and can
        be read back through `store.undo_context`/`store.redo_context`,
        for instance to build user-facing undo/redo labels.
        """
        self.state["count"] += 1

    @mutation(context=lambda self, amount: f"Adjust count to {amount}")
    def adjust_count(self, amount):
        self.state["count"] = amount

    @computed
    def count(self):
        """
        Decorating a method with `computed` will create a property
        on the store instance for easy access.
        """
        return self.state["count"]


if __name__ == "__main__":
    store = CounterStore({"count": 0})

    _ = watch(
        lambda: store.state["count"],
        lambda val: print(f"Count is now: {val}"),  # noqa: T201
        sync=True,
        immediate=True,
    )

    # Bump the count by one
    store.bump_count()
    # Current state of the store can be accessed through
    # the `state` property on store
    assert store.state["count"] == 1
    # The count is now also accessible as a property because
    # of the computed `count` method defined on CounterStore
    assert store.count == 1

    # Set the count to 5
    store.adjust_count(5)
    assert store.count == 5

    # The context of the mutation that would be undone/redone is
    # available for building user-facing labels such as menu items
    assert store.undo_context == "Adjust count to 5"

    # Undo last change
    store.undo()
    assert store.count == 1
    assert store.undo_context == "Bump count"
    assert store.redo_context == "Adjust count to 5"

    # Redo undone change
    store.redo()
    assert store.count == 5
