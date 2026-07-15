from functools import partial, wraps
from typing import Callable, Generic, Hashable, NamedTuple, Optional, TypeVar

import patchdiff
from observ import computed as computed_expression
from observ import (
    reactive,
    readonly,
    shallow_reactive,
)

T = TypeVar("T", bound=Callable)


class HistoryEntry(NamedTuple):
    """A single recorded mutation in the store's undo/redo history."""

    ops: list
    reverse_ops: list
    context: Optional[Hashable]


def mutation(_fn=None, *, strict=None, context=None):
    """Mark a store method as a mutation that records an undo/redo entry.

    `context` attaches a user-defined value to the recorded history
    entry, which can be read back through `Store.undo_context` and
    `Store.redo_context`, for instance to build user-facing undo/redo
    labels. It can be:

    * any (hashable) value, stored as-is — for example a plain string, a
      translation key, or a tuple such as `("added_items", 3)`
    * a callable, invoked with the same `(self, *args, **kwargs)` as the
      mutation itself (before the mutation runs), whose return value is
      stored as the context

    Callers can override the context for a single call by passing the
    reserved keyword argument `mutation_context`, which is consumed by the
    decorator and not passed on to the mutation itself.
    """

    def decorator_mutation(fn: T) -> T:
        @wraps(fn)
        def inner(self, *args, **kwargs):
            call_context = kwargs.pop("mutation_context", None)

            # If we're already inside a mutation on this store, run fn directly
            # so the outer mutation's proxy records all nested changes as a
            # single undo entry. The outer mutation is the transactional
            # boundary; any `strict` setting on nested mutations is ignored,
            # and so is any context: the outer mutation's context wins.
            if getattr(self, "_in_mutation", False):
                fn(self, *args, **kwargs)
                return

            if call_context is not None:
                entry_context = call_context
            elif callable(context):
                entry_context = context(self, *args, **kwargs)
            else:
                entry_context = context

            readonly_state = self.state

            def recipe(state):
                # Set self.state to the proxied version of the state
                # supplied by patchdiff
                self.state = state
                self._in_mutation = True
                try:
                    fn(self, *args, **kwargs)
                finally:
                    self._in_mutation = False

            try:
                # Pass the writable version of the state to the produce method
                # to be proxied and supplied to the recipe
                _, ops, reverse_ops = patchdiff.produce(
                    self._present, recipe=recipe, in_place=True
                )

                if ops or reverse_ops:
                    self._past.append(HistoryEntry(ops, reverse_ops, entry_context))
                    self._future.clear()
                else:
                    strict_mode = strict if strict is not None else self._strict
                    if strict_mode:
                        raise RuntimeError(
                            "Calling mutation didn't result in any change to state"
                        )
            finally:
                self.state = readonly_state

        return inner

    if _fn is None:
        return decorator_mutation
    return decorator_mutation(_fn)


def computed(_fn=None, *, deep=True):
    """Expose a method as a read-only, observ-backed reactive property.

    The decorated method must take only ``self``. It is replaced by a
    ``property`` whose getter lazily builds an observ computed expression
    (one per instance, cached in the instance ``__dict__``) and returns
    its current value. Assignment raises ``AttributeError``, since
    ``property`` has no setter.
    """

    def decorator_computed(fn: T) -> T:
        cache_key = f"_computed_expr_{fn.__name__}"

        @wraps(fn)
        def getter(self):
            expr = self.__dict__.get(cache_key)
            if expr is None:
                expr = computed_expression(partial(fn, self), deep=deep)
                self.__dict__[cache_key] = expr
            return expr()

        return property(getter)

    if _fn is None:
        return decorator_computed
    return decorator_computed(_fn)


S = TypeVar("S")


class Store(Generic[S]):
    """
    Store that tracks mutations to state in order to enable undo/redo functionality
    """

    def __init__(self, state: S, strict=True):
        """
        Creates a store with the given state as the initial state.
        When `strict` is False, calling mutations that do not result
        in an actual change will be ignored.
        """
        self._strict = strict
        self._present = reactive(state)
        self._past = shallow_reactive([])
        self._future = shallow_reactive([])
        self.state = readonly(state)
        self._in_mutation = False

    @property
    def can_undo(self) -> bool:
        """
        Returns whether the store can undo some mutation
        """
        return len(self._past) > 0

    @property
    def can_redo(self) -> bool:
        """
        Returns whether the store can redo some mutation
        """
        return len(self._future) > 0

    @property
    def undo_context(self) -> Optional[Hashable]:
        """
        Returns the context of the mutation that `undo()` would revert,
        or None when there is nothing to undo (or no context was given)
        """
        if not self._past:
            return None
        return self._past[-1].context

    @property
    def redo_context(self) -> Optional[Hashable]:
        """
        Returns the context of the mutation that `redo()` would reapply,
        or None when there is nothing to redo (or no context was given)
        """
        if not self._future:
            return None
        return self._future[-1].context

    def undo(self):
        """
        Undoes the last mutation
        """
        if not self.can_undo:
            return

        entry = self._past.pop()
        patchdiff.iapply(self._present, entry.reverse_ops)
        self._future.append(entry)

    def redo(self):
        """
        Redoes the next mutation
        """
        if not self.can_redo:
            return

        entry = self._future.pop()
        patchdiff.iapply(self._present, entry.ops)
        self._past.append(entry)
