# Quick Start

A store wraps a piece of state — any structure of dicts, lists and sets — and tracks every change made through its mutations.

## Define a store

Subclass [`Store`][reliev.store.Store] and decorate the methods that change state with [`@mutation`][reliev.store.mutation]. Inside a mutation, `self.state` is writable; everywhere else it is a readonly proxy.

```python
from reliev import Store, computed, mutation

class CounterStore(Store):
    @mutation(context="Bump count")
    def bump_count(self):
        self.state["count"] += 1

    @mutation(context=lambda self, amount: f"Adjust count to {amount}")
    def adjust_count(self, amount):
        self.state["count"] = amount

    @computed
    def count(self):
        return self.state["count"]

store = CounterStore({"count": 0})
```

## Mutate, undo, redo

Every mutation call records one history entry:

```python
store.bump_count()
assert store.count == 1

store.adjust_count(5)
assert store.count == 5

store.undo()
assert store.count == 1

store.redo()
assert store.count == 5
```

[`can_undo`][reliev.store.Store.can_undo] and [`can_redo`][reliev.store.Store.can_redo] tell you whether there is anything to walk back or forward — for instance to enable or disable menu items. The `context` values passed to the decorators come back through [`undo_context`][reliev.store.Store.undo_context] and [`redo_context`][reliev.store.Store.redo_context], so building a label like *"Undo Adjust count to 5"* is a string format away.

## React to changes

The state is an observ reactive proxy, so watchers pick up changes made by mutations — and by undo/redo — automatically:

```python
from observ import watch

watcher = watch(
    lambda: store.state["count"],
    lambda value: print(f"Count is now: {value}"),
    sync=True,
)

store.bump_count()  # prints "Count is now: 6"
store.undo()        # prints "Count is now: 5"
```

That's the whole model. The [guide](../guide/mutations.md) covers each piece in depth, starting with what exactly a mutation records.
