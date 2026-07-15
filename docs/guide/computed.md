# Computed Properties

The [`@computed`][reliev.store.computed] decorator exposes derived state as a read-only property on the store, backed by an observ computed expression: the result is cached and only recomputed — lazily — when the reactive state it depends on has changed.

```python
from reliev import Store, computed, mutation

class TodoStore(Store):
    @mutation
    def add_item(self, item):
        self.state["items"].append(item)

    @computed
    def item_count(self):
        return len(self.state["items"])

store = TodoStore({"items": []})
assert store.item_count == 0

store.add_item("apple")
assert store.item_count == 1  # recomputed because items changed
```

The decorated method must take only `self`. It is replaced by a plain stdlib `property`, so assignment raises `AttributeError`, and each store instance gets its own cached expression (created on first access).

## Deep vs. shallow

By default a computed property re-evaluates when anything *inside* the value it depends on changes. Pass `deep=False` when only identity changes matter:

```python
class TodoStore(Store):
    @computed
    def deep_items(self):
        return self.state["items"]      # re-evaluates when items' contents change

    @computed(deep=False)
    def shallow_items(self):
        return self.state["items"]      # only when "items" itself is replaced
```

## Composing with watchers

Computed properties participate in dependency tracking like any reactive value, so they can be watched, and other computed properties can build on them:

```python
from observ import watch

watcher = watch(
    lambda: store.item_count,
    lambda count: print(f"{count} item(s)"),
    sync=True,
)
```

Since undo and redo change the state through the same reactive proxies, computed properties stay correct across history navigation for free.
