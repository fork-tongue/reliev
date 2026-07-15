[![PyPI version](https://badge.fury.io/py/reliev.svg)](https://badge.fury.io/py/reliev)
[![CI status](https://github.com/fork-tongue/reliev/workflows/CI/badge.svg)](https://github.com/fork-tongue/reliev/actions)

# Reliev 🩹

**Undo/redo for observ-based reactive state.**

📖 [Documentation](https://fork-tongue.github.io/reliev/) | [Quick Start](https://fork-tongue.github.io/reliev/getting-started/quick-start/) | [API Reference](https://fork-tongue.github.io/reliev/reference/api/)

Reliev is a complementary store library for [observ](https://github.com/fork-tongue/observ). Subclass `Store`, mark state-changing methods with `@mutation`, and every call records a single undo/redo history entry. [Patchdiff](https://github.com/fork-tongue/patchdiff) records the changes as bidirectional patches, so a mutation costs what it changes — not the size of your state — and undo/redo trigger exactly the fine-grained reactive notifications the original change did.

```python
from reliev import Store, computed, mutation

class TodoStore(Store):
    @mutation(context=lambda self, item: f"Add {item}")
    def add_item(self, item):
        self.state["items"].append(item)

    @computed
    def item_count(self):
        return len(self.state["items"])

store = TodoStore({"items": []})
store.add_item("apple")

assert store.item_count == 1
assert store.undo_context == "Add apple"  # e.g. menu item "Undo Add apple"

store.undo()
assert store.item_count == 0

store.redo()
assert store.item_count == 1
```

## Features

* **Transactional mutations** — one mutation call is one undo step; nested mutation calls collapse into the outermost entry
* **Mutation context** — attach any (hashable) value or a callable to a mutation for user-facing undo/redo labels, and read it back through the reactive `undo_context`/`redo_context` properties
* **Computed properties** — expose derived state as cached, reactive, read-only store properties
* **Strict mode** — mutations that change nothing raise by default; opt out per store or per mutation
* **Fully reactive** — state, history flags and contexts all compose with observ's `watch` and `computed`
* **Typed** — complete type hints, PEP 561 `py.typed`, checked with [ty](https://github.com/astral-sh/ty) in CI
