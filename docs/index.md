# Reliev 🩹

Reliev is a small store library on top of [observ](https://github.com/fork-tongue/observ) that adds **undo/redo** to reactive state. You subclass [`Store`][reliev.store.Store], mark the methods that change state with [`@mutation`][reliev.store.mutation], and every call records a history entry that can be undone and redone. Patches are recorded with [patchdiff](https://github.com/fork-tongue/patchdiff), so a mutation costs what it changes, not the size of your state.

```python
from reliev import Store, mutation

class TodoStore(Store):
    @mutation(context=lambda self, item: f"Add {item}")
    def add_item(self, item):
        self.state["items"].append(item)

store = TodoStore({"items": []})
store.add_item("apple")

assert store.state["items"] == ["apple"]
assert store.undo_context == "Add apple"  # e.g. menu item "Undo Add apple"

store.undo()
assert store.state["items"] == []

store.redo()
assert store.state["items"] == ["apple"]
```

Because the state is an observ reactive proxy, everything composes with observ's `watch` and `computed`: watchers see exactly the keys a mutation (or an undo) touched, and the [`@computed`][reliev.store.computed] decorator exposes derived state as store properties.

## Where to start

* The [quick start](getting-started/quick-start.md) walks through a complete store.
* The guide covers [mutations](guide/mutations.md), [undo & redo](guide/undo-redo.md), [mutation context](guide/context.md), [computed properties](guide/computed.md), [nested mutations](guide/nested-mutations.md) and [reactivity](guide/reactivity.md) in more detail.
* The complete public API is documented in the [API reference](reference/api.md).
* The [internals](internals/architecture.md) page describes how everything works under the hood.

## Related projects

* [observ](https://github.com/fork-tongue/observ): the reactivity system reliev's stores are built on.
* [patchdiff](https://github.com/fork-tongue/patchdiff): records the bidirectional patches that make undo/redo possible.
