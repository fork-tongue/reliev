# Mutations

A mutation is the only way to change a store's state. Decorating a method with [`@mutation`][reliev.store.mutation] turns each call into a transaction: the method runs against a writable draft of the state, every change it makes is recorded as a pair of forward and reverse patches, and the pair is pushed onto the undo history as a single entry.

```python
from reliev import Store, mutation

class TodoStore(Store):
    @mutation
    def add_item(self, item):
        self.state["items"].append(item)

    @mutation
    def clear(self):
        self.state["items"].clear()
```

Outside of mutations, `self.state` (and `store.state` from the outside) is a **readonly** observ proxy: reads are tracked for reactivity, and any write raises. Inside a mutation, `self.state` is temporarily replaced with a writable draft supplied by patchdiff's `produce`, so the method body reads naturally while every write is recorded. Once the call returns, `self.state` points back at the readonly proxy.

Mutations can take any arguments. Their return value is discarded — a mutation describes a change, not a query.

## Strict mode

Calling a mutation that ends up changing nothing usually indicates a bug, so by default it raises:

```python
store = TodoStore({"items": []})
store.clear()  # RuntimeError: Calling mutation didn't result in any change to state
```

If no-op calls are expected, opt out per store or per mutation:

```python
store = TodoStore({"items": []}, strict=False)  # whole store is lenient

class TodoStore(Store):
    @mutation(strict=False)  # only this mutation is lenient
    def clear(self):
        self.state["items"].clear()
```

A `strict` setting on the decorator wins over the store's setting, in both directions. No-op calls in lenient mode record nothing: they leave the history untouched, so they cannot be undone (there is nothing to undo) and do not clear the redo stack.

## What gets recorded

The recorded patches are [patchdiff](https://fork-tongue.github.io/patchdiff/) operations — RFC 6902 JSON-patch style `add`/`remove`/`replace` — describing exactly the writes the mutation performed, in both directions. This has two practical consequences:

* The cost of a mutation scales with the number of changes it makes, not with the size of the state.
* A history entry is compact: undoing does not restore a snapshot, it applies the reverse patches.

See [undo & redo](undo-redo.md) for how entries move through the history, and [mutation context](context.md) for attaching labels to them.
