# Reliev 

Complementary store library for [observ](https://github.com/fork-tongue/observ). Provides undo/redo functionality.

Leverages [patchdiff](https://github.com/fork-tongue/patchdiff) for constructing patches to apply to state for undo/redo.

## Mutation context

Mutations can carry a `context`, which is attached to the recorded undo entry and exposed through the reactive `undo_context` and `redo_context` properties on the store. This makes it possible, for instance, to build user-facing labels such as "Undo *Add item*".

```python
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

A context can be any (hashable) value, not just a string: for example a translation key, or a tuple like `("added_items", 3)`, giving applications full control over what a context means and how it is used. Callers can also override the context for a single call with the reserved `mutation_context` keyword argument, which is consumed by the decorator and not passed on to the mutation itself:

```python
store.add_item("apple", mutation_context=("add_item", "apple"))
```

When mutations call other mutations, the outermost mutation is the transactional boundary: the whole call records a single undo entry with the outer mutation's context.
