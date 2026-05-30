"""
Models package initializer.

This module imports all model modules to ensure SQLAlchemy's class registry
is populated when the package is imported. This prevents mapper initialization
errors caused by models being defined in separate modules but not imported
before mappers are configured.
"""

# Import model modules to ensure they are registered with SQLAlchemy
from . import project  # noqa: F401
from . import clip     # noqa: F401
from . import collection  # noqa: F401
from . import task     # noqa: F401
from . import enums    # noqa: F401

__all__ = [
    "project",
    "clip",
    "collection",
    "task",
    "enums",
]
