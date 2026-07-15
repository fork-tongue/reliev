# Architecture

This page documents how reliev works under the hood. Nothing here is part of the public API; it exists to help contributors understand the single module the library consists of: `store.py`.

## Two views of one state

A [`Store`][reliev.store.Store] holds the same underlying state behind two observ proxies:

* `self._present` — a `reactive` (writable) proxy, the store's private handle for applying changes;
* `self.state` — a `readonly` proxy over the same target, the public handle. Reads through it are dependency-tracked; writes raise.

Both wrap the *same* object, so a change applied through `_present` is immediately visible through `state`, and notifies exactly the watchers that depend on the touched locations.

The undo/redo stacks, `_past` and `_future`, are `shallow_reactive` lists of `HistoryEntry` tuples. Shallow is deliberate: pushes and pops must be observable (they drive `can_undo`, `can_redo` and the context properties), but the patch operations inside an entry are never mutated, so there is no reason to pay for deep proxying them.

## Anatomy of a mutation call

The wrapper installed by [`@mutation`][reliev.store.mutation] runs each call in five steps:

1. **Reentrancy check.** If the store is already inside a mutation (`_in_mutation`), the method body runs directly against the current draft and returns — this is what collapses [nested mutations](../guide/nested-mutations.md) into the outer entry, and why nested `strict` and `context` settings are ignored.
2. **Context resolution.** A `mutation_context` keyword passed by the caller wins; otherwise a callable `context` is invoked with the call's own arguments; otherwise the static `context` value is used as-is.
3. **Recording.** The body is wrapped in a *recipe* and handed to patchdiff's `produce(self._present, recipe=recipe, in_place=True)`. Produce proxies the draft, runs the recipe, and returns the forward and reverse patch lists. For the duration of the recipe, `self.state` is swapped to the writable draft so the method body can write through the same attribute it normally reads from; a `finally` swaps the readonly proxy back even if the body raises. `in_place=True` matters twice: the store wants the real state mutated (not a copy), and it keeps patchdiff writing through the reactive proxy so observ sees every change.
4. **History bookkeeping.** If any patches were recorded, a `HistoryEntry(ops, reverse_ops, context)` is appended to `_past` and `_future` is cleared — a new change invalidates previously undone ones. If nothing was recorded, strict mode (the decorator's setting, falling back to the store's) decides between raising and ignoring.
5. **Restore.** `self.state` points back at the readonly proxy.

## Undo and redo

[`undo()`][reliev.store.Store.undo] pops the newest entry off `_past`, applies its `reverse_ops` to `_present` with patchdiff's `iapply`, and pushes the entry onto `_future`; [`redo()`][reliev.store.Store.redo] mirrors it with `ops`. Since `iapply` writes through the reactive proxy, undo/redo trigger exactly the same fine-grained notifications the original mutation did. Entries keep both patch directions forever, so walking the history any number of times costs only patch application — no diffing, no snapshots.

## Computed properties

[`@computed`][reliev.store.computed] replaces a method with a stdlib `property`. Its getter lazily creates one observ computed expression per instance — `computed_expression(deep=deep)(partial(fn, self))` — and caches it in the instance `__dict__` under a name derived from the method. Later accesses reuse the cached expression, which only re-evaluates when its reactive dependencies changed. Using a plain `property` keeps semantics unsurprising: assignment raises `AttributeError`, `isinstance(cls.__dict__[name], property)` holds, and there is no custom descriptor to learn.

For typing purposes the decorator is declared to return a `ComputedProperty[T]` protocol, so type checkers see attribute access typed as the getter's return type; at runtime the object really is just a `property`.

## Division of labor

Reliev itself is intentionally thin. The heavy lifting lives upstream:

* [observ](https://fork-tongue.github.io/observ/) implements the proxies, dependency tracking and scheduling;
* [patchdiff](https://fork-tongue.github.io/patchdiff/) implements patch recording (`produce`) and application (`iapply`).

What reliev adds is the transactional glue: one decorator that turns method calls into history entries, and a store that knows how to walk them.
