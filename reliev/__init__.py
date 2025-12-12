from importlib.metadata import version

__version__ = version("reliev")

from .store import Store, computed, mutation

__all__ = ["Store", "computed", "mutation"]
