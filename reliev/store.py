from __future__ import annotations

from functools import partial, wraps
from typing import TYPE_CHECKING, Any, Generic, NamedTuple, TypeVar, cast, overload

import patchdiff
from observ import computed as computed_expression
from observ import (
    reactive,
    readonly,
    shallow_reactive,
)

T = TypeVar("T")
# A mutation method: any signature, but the recorded wrapper always
# returns None (a mutation's return value would be discarded)
M = TypeVar("M", bound="Callable[..., None]")
S = TypeVar("S")

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable
    from types import FunctionType
    from typing import Protocol

    from observ.watcher import Computed
    from patchdiff.types import Diffable, Operation

    # The context attached to a history entry: any hashable value,
    # or a callable producing one (invoked with the same arguments
    # as the mutation itself)
    Context = Hashable
    ContextArg = Context | Callable[..., Context]

    class ComputedProperty(Protocol[T]):
        """
        The read-only descriptor installed by `computed` (a plain
        stdlib `property` at runtime, typed here so attribute access
        yields the getter's return type and assignment is rejected).
        """

        def __get__(self, obj: Any, objtype: type | None = None) -> T: ...


class HistoryEntry(NamedTuple):
    """A single recorded mutation in the store's undo/redo history."""

    ops: list[Operation]
    reverse_ops: list[Operation]
    context: Context | None


@overload
def mutation(_fn: M) -> M: ...


@overload
def mutation(
    *, strict: bool | None = None, context: ContextArg | None = None
) -> Callable[[M], M]: ...


def mutation(
    _fn: M | None = None,
    *,
    strict: bool | None = None,
    context: ContextArg | None = None,
) -> M | Callable[[M], M]:
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

    def decorator_mutation(fn: M) -> M:
        @wraps(fn)
        def inner(self: Store[Any], *args: Any, **kwargs: Any) -> None:
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
                # The cast pins the callable branch of ContextArg:
                # callable() narrows to an unknown callable signature,
                # which would not be safe to call
                entry_context = cast("Callable[..., Context]", context)(
                    self, *args, **kwargs
                )
            else:
                entry_context = context

            readonly_state = self.state

            def recipe(state: Any) -> None:
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

        # The wrapper keeps fn's (call) signature: it forwards *args and
        # **kwargs unchanged, minus the reserved mutation_context kwarg
        return cast("M", inner)

    if _fn is None:
        return decorator_mutation
    return decorator_mutation(_fn)


@overload
def computed(_fn: Callable[[Any], T]) -> ComputedProperty[T]: ...


@overload
def computed(
    *, deep: bool = True
) -> Callable[[Callable[[Any], T]], ComputedProperty[T]]: ...


def computed(
    _fn: Callable[[Any], T] | None = None, *, deep: bool = True
) -> ComputedProperty[T] | Callable[[Callable[[Any], T]], ComputedProperty[T]]:
    """Expose a method as a read-only, observ-backed reactive property.

    The decorated method must take only ``self``. It is replaced by a
    ``property`` whose getter lazily builds an observ computed expression
    (one per instance, cached in the instance ``__dict__``) and returns
    its current value. Assignment raises ``AttributeError``, since
    ``property`` has no setter.
    """

    def decorator_computed(fn: Callable[[Any], T]) -> ComputedProperty[T]:
        # The cast recovers __name__: the decorated method is always a
        # plain function, but Callable does not carry that attribute
        cache_key = f"_computed_expr_{cast('FunctionType', fn).__name__}"

        @wraps(fn)
        def getter(self: Any) -> T:
            expr: Computed[T] | None = self.__dict__.get(cache_key)
            if expr is None:
                expr = computed_expression(deep=deep)(partial(fn, self))
                self.__dict__[cache_key] = expr
            return expr()

        # At runtime the descriptor is a plain stdlib property; the
        # ComputedProperty protocol narrows attribute access to T and
        # rejects assignment (property has no setter)
        return cast("ComputedProperty[T]", property(getter))

    if _fn is None:
        return decorator_computed
    return decorator_computed(_fn)


class Store(Generic[S]):
    """
    Store that tracks mutations to state in order to enable undo/redo functionality
    """

    state: S

    def __init__(self, state: S, strict: bool = True) -> None:
        """
        Creates a store with the given state as the initial state.
        When `strict` is False, calling mutations that do not result
        in an actual change will be ignored.
        """
        self._strict = strict
        self._present = reactive(state)
        self._past: list[HistoryEntry] = shallow_reactive([])
        self._future: list[HistoryEntry] = shallow_reactive([])
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
    def undo_context(self) -> Context | None:
        """
        Returns the context of the mutation that `undo()` would revert,
        or None when there is nothing to undo (or no context was given)
        """
        if not self._past:
            return None
        return self._past[-1].context

    @property
    def redo_context(self) -> Context | None:
        """
        Returns the context of the mutation that `redo()` would reapply,
        or None when there is nothing to redo (or no context was given)
        """
        if not self._future:
            return None
        return self._future[-1].context

    def undo(self) -> None:
        """
        Undoes the last mutation
        """
        if not self.can_undo:
            return

        entry = self._past.pop()
        # The cast unifies S with the containers patchdiff can patch;
        # the state proxy is a duck-typed container look-alike
        patchdiff.iapply(cast("Diffable", self._present), entry.reverse_ops)
        self._future.append(entry)

    def redo(self) -> None:
        """
        Redoes the next mutation
        """
        if not self.can_redo:
            return

        entry = self._future.pop()
        # See the matching cast in undo()
        patchdiff.iapply(cast("Diffable", self._present), entry.ops)
        self._past.append(entry)
