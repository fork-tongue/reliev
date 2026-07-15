# Nested Mutations

Mutations can call other mutations. When they do, the **outermost** mutation is the transactional boundary: the whole call records a single undo entry covering all changes, no matter how deep the calls nest.

```python
from reliev import Store, mutation

class CounterStore(Store):
    @mutation(context="inner")
    def inc(self):
        self.state["n"] += 1

    @mutation(context="outer")
    def double_inc(self):
        self.inc()
        self.inc()

store = CounterStore({"n": 0})
store.double_inc()

assert store.state["n"] == 2
assert store.undo_context == "outer"  # one entry, the outer context

store.undo()
assert store.state["n"] == 0          # both increments undone together
```

While the outer mutation is running, nested mutation calls execute directly against the same writable draft, so their changes are recorded into the outer entry. Two decorator settings are consequently ignored on nested calls:

* **`strict`** — only the outer mutation's no-op check applies. A nested call that changes nothing is fine; what matters is whether the transaction as a whole changed anything.
* **`context`** — the outer mutation's context wins, including over a `mutation_context` keyword passed to a nested call.

This makes mutations freely composable: a high-level user action can be built out of smaller mutations that also work standalone, and each entry in the history still corresponds to exactly one user-level action.
