# Undo & Redo

The store keeps two stacks of history entries: the past and the future. Every mutation call that changed something pushes an entry onto the past — and clears the future, because a new change invalidates any previously undone ones (the classic linear-history model).

```python
store.bump_count()   # past: [bump], future: []
store.undo()         # past: [],     future: [bump]
store.redo()         # past: [bump], future: []
```

[`undo()`][reliev.store.Store.undo] pops the most recent entry, applies its reverse patches to the state and pushes the entry onto the future. [`redo()`][reliev.store.Store.redo] does the mirror image. Both are no-ops when their stack is empty, so it is always safe to call them.

## Enabling UI affordances

[`can_undo`][reliev.store.Store.can_undo] and [`can_redo`][reliev.store.Store.can_redo] report whether the respective stack is non-empty. The history stacks are reactive, so these properties can be watched — a menu item or toolbar button stays in sync by itself:

```python
from observ import watch

watcher = watch(
    lambda: store.can_undo,
    lambda enabled: undo_action.setEnabled(enabled),
    sync=True,
    immediate=True,
)
```

For user-facing labels such as *"Undo Add item"*, see [mutation context](context.md).

## Granularity

One mutation call is one undo step. If a user-level action spans several state changes, put them in one mutation — or let one mutation call others: [nested mutations](nested-mutations.md) collapse into a single entry on the outermost call, which is the transactional boundary.
