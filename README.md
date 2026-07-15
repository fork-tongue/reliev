# Reliev 

Complementary store library for [observ](https://github.com/fork-tongue/observ). Provides undo/redo functionality.

Leverages [patchdiff](https://github.com/fork-tongue/patchdiff) for constructing patches to apply to state for undo/redo.

## Mutation reasons

Mutations can carry a `reason`, which is attached to the recorded undo entry and exposed through the reactive `undo_reason` and `redo_reason` properties on the store. This makes it possible to build user-facing labels such as "Undo *Add item*".

```python
class TodoStore(Store):
    # A static reason
    @mutation(reason="Clear items")
    def clear_items(self):
        self.state["items"].clear()

    # A callable reason receives the same arguments as the mutation
    @mutation(reason=lambda self, item: f"Add {item}")
    def add_item(self, item):
        self.state["items"].append(item)


store = TodoStore({"items": []})
store.add_item("apple")
assert store.undo_reason == "Add apple"
store.undo()
assert store.redo_reason == "Add apple"
```

A reason can be any (hashable) value, not just a string: for example a translation key, or a tuple like `("added_items", 3)`, giving applications full control over how reasons are rendered. Callers can also override the reason for a single call with the reserved `mutation_reason` keyword argument, which is consumed by the decorator and not passed on to the mutation itself:

```python
store.add_item("apple", mutation_reason=("add_item", "apple"))
```

When mutations call other mutations, the outermost mutation is the transactional boundary: the whole call records a single undo entry with the outer mutation's reason.
