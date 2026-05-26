from functools import partial, wraps
from typing import Callable, Generic, TypeVar

import patchdiff
from observ import computed as computed_expression
from observ import (
    reactive,
    readonly,
    shallow_reactive,
)

T = TypeVar("T", bound=Callable)


def mutation(_fn=None, *, strict=None):
    def decorator_mutation(fn: T) -> T:
        @wraps(fn)
        def inner(self, *args, **kwargs):
            # If we're already inside a mutation on this store, run fn directly
            # so the outer mutation's proxy records all nested changes as a
            # single undo entry. The outer mutation is the transactional
            # boundary; any `strict` setting on nested mutations is ignored.
            if getattr(self, "_in_mutation", False):
                fn(self, *args, **kwargs)
                return

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
                    self._past.append((ops, reverse_ops))
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

    def undo(self):
        """
        Undoes the last mutation
        """
        if not self.can_undo:
            return

        ops, reverse_ops = self._past.pop()
        patchdiff.iapply(self._present, reverse_ops)
        self._future.append((ops, reverse_ops))

    def redo(self):
        """
        Redoes the next mutation
        """
        if not self.can_redo:
            return

        ops, reverse_ops = self._future.pop()
        patchdiff.iapply(self._present, ops)
        self._past.append((ops, reverse_ops))
