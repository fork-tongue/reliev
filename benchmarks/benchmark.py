"""
Benchmark suite for reliev's store layer using pytest-benchmark.

These benchmarks measure the overhead reliev adds on top of observ and
patchdiff (which have their own benchmark suites): recording a mutation,
walking the undo/redo history, and computed property access.

Run benchmarks:
    uv run pytest benchmarks/benchmark.py --benchmark-only

Save baseline:
    uv run pytest benchmarks/benchmark.py --benchmark-only --benchmark-autosave

Compare against baseline:
    uv run pytest benchmarks/benchmark.py --benchmark-only --benchmark-compare=0001
"""

from reliev import Store, computed, mutation


class BenchStore(Store):
    @mutation
    def bump(self):
        self.state["count"] += 1

    @mutation
    def set_key(self, key, value):
        self.state["map"][key] = value

    @mutation
    def append_item(self, item):
        self.state["items"].append(item)

    @mutation
    def double_bump(self):
        self.bump()
        self.bump()

    @computed
    def double(self):
        return self.state["count"] * 2


def small_state():
    return {"count": 0, "map": {}, "items": []}


def large_state():
    return {
        "count": 0,
        "map": {f"key_{i}": i for i in range(1000)},
        "items": list(range(1000)),
    }


def test_mutation_roundtrip_small_state(benchmark):
    """Record a mutation on a small state and undo it again.

    The undo keeps the history (and thus memory) bounded across
    benchmark rounds; the next mutation clears the redo stack.
    """
    store = BenchStore(small_state())

    def run():
        store.bump()
        store.undo()

    benchmark(run)


def test_mutation_roundtrip_large_state(benchmark):
    """Record a single-key mutation on a large state and undo it."""
    store = BenchStore(large_state())

    def run():
        store.set_key("key_0", 1)
        store.undo()

    benchmark(run)


def test_mutation_append_large_list(benchmark):
    """Append to a large list inside a mutation and undo it."""
    store = BenchStore(large_state())

    def run():
        store.append_item(1)
        store.undo()

    benchmark(run)


def test_nested_mutation_roundtrip(benchmark):
    """A mutation calling nested mutations, recorded as one entry."""
    store = BenchStore(small_state())

    def run():
        store.double_bump()
        store.undo()

    benchmark(run)


def test_undo_redo_cycle(benchmark):
    """Walk one recorded entry back and forth through the history."""
    store = BenchStore(small_state())
    store.bump()

    def run():
        store.undo()
        store.redo()

    benchmark(run)


def test_computed_access_cached(benchmark):
    """Repeated reads of a computed property (nothing invalidated)."""
    store = BenchStore(small_state())
    store.bump()
    assert store.double == 2

    benchmark(lambda: store.double)


def test_computed_access_invalidated(benchmark):
    """Reads of a computed property invalidated by each mutation."""
    store = BenchStore(small_state())

    def run():
        store.bump()
        result = store.double
        store.undo()
        return result

    benchmark(run)


def test_store_creation(benchmark):
    """Construct a store (reactive + readonly proxies) around a state."""
    benchmark(lambda: BenchStore(large_state()))
