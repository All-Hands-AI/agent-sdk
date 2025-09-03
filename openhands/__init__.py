import os
import pkgutil


# Make openhands a namespace package and prefer this repo's path first
__path__ = pkgutil.extend_path(__path__, __name__)
try:
    this_dir = os.path.dirname(__file__)
    if this_dir in __path__:
        # Prefer this repository's openhands path
        __path__.insert(0, __path__.pop(__path__.index(this_dir)))
except Exception:
    # Be forgiving if pkgutil changes type; it's fine to proceed without reordering
    pass
