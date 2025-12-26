import importlib.metadata

__version__ = importlib.metadata.distribution(__name__).version

from .extension import PhpBB3

__all__ = (
    'PhpBB3',
)
