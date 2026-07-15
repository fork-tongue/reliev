# Reactivity

A store's state is an [observ](https://github.com/fork-tongue/observ) reactive proxy, which means the store plugs into everything observ offers: `watch`, `watch_effect`, `computed`, and UI bindings built on them. Reliev adds no reactivity of its own — it routes all changes (mutations, undos, redos) through the same proxies.

## Watching state

```python
from observ import watch

from reliev import Store, mutation

class CounterStore(Store):
    @mutation
    def bump(self):
        self.state["count"] += 1

store = CounterStore({"count": 0})

watcher = watch(
    lambda: store.state["count"],
    lambda value: print(f"Count is now: {value}"),
    sync=True,
    immediate=True,
)

store.bump()   # prints "Count is now: 1"
store.undo()   # prints "Count is now: 0"
```

## Fine-grained notifications

Undo and redo apply patches that touch exactly the locations the original mutation changed — not the whole state. Watchers of unrelated parts of the state therefore stay quiet:

```python
from unittest.mock import Mock

store = CounterStore({"count": 0, "foo": {}})
foo_watcher = watch(lambda: store.state["foo"], Mock(), sync=True)

store.bump()
store.undo()

foo_watcher.callback.assert_not_called()  # "foo" was never touched
```

## Reactive history

The undo/redo stacks themselves are (shallow) reactive, so everything derived from them can be watched too: [`can_undo`][reliev.store.Store.can_undo], [`can_redo`][reliev.store.Store.can_redo], [`undo_context`][reliev.store.Store.undo_context] and [`redo_context`][reliev.store.Store.redo_context]. A typical desktop app binds its Edit-menu entries to these four properties and never updates them manually again.

## Readonly outside mutations

Because `store.state` is a readonly proxy outside of mutations, accidental writes from UI code raise immediately instead of silently bypassing the history. Every change is forced through a [mutation](mutations.md) — which is exactly what keeps undo/redo trustworthy.
