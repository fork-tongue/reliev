# Mutation Context

Mutations can carry a `context`: a user-defined value attached to the recorded history entry and exposed through the reactive [`undo_context`][reliev.store.Store.undo_context] and [`redo_context`][reliev.store.Store.redo_context] properties. Its typical use is building user-facing labels such as *"Undo Add item"*, but the store attaches no meaning to it — the application decides what a context is.

## Static and callable contexts

```python
from reliev import Store, mutation

class TodoStore(Store):
    # A static context
    @mutation(context="Clear items")
    def clear_items(self):
        self.state["items"].clear()

    # A callable context receives the same arguments as the mutation
    @mutation(context=lambda self, item: f"Add {item}")
    def add_item(self, item):
        self.state["items"].append(item)

store = TodoStore({"items": []})
store.add_item("apple")
assert store.undo_context == "Add apple"
store.undo()
assert store.redo_context == "Add apple"
```

A callable context is invoked right before the mutation runs, with the exact `(self, *args, **kwargs)` of the call, and its return value is stored.

A context can be any (hashable) value, not just a string: a translation key, a tuple like `("added_items", 3)` — whatever gives the application enough to render or act on later.

## Per-call override

Callers can override the context for a single call with the reserved `mutation_context` keyword argument, which is consumed by the decorator and never passed on to the mutation itself:

```python
store.add_item("apple", mutation_context=("add_item", "apple"))
```

## Reading contexts back

`undo_context` is the context of the entry that `undo()` would revert; `redo_context` belongs to the entry that `redo()` would reapply. Both are `None` when there is nothing on the respective stack — or when the entry was recorded without a context. Both properties are backed by the reactive history stacks, so they can be watched like any other reactive value:

```python
from observ import watch

watcher = watch(
    lambda: store.undo_context,
    lambda ctx: undo_action.setText(f"Undo {ctx}" if ctx else "Undo"),
    sync=True,
    immediate=True,
)
```

When mutations call other mutations, the outermost mutation's context wins — see [nested mutations](nested-mutations.md).
