"""Byte caching for audio data."""

from typing import Callable


class BytesCache:
    """Cache for loaded audio bytes."""

    def __init__(self, data_provider: Callable[[str], bytes]):
        self._data_provider = data_provider
        self._cache: dict[str, bytes] = {}

    def get(self, name: str) -> bytes:
        """Get bytes for a name, loading and caching if not already cached."""
        if name not in self._cache:
            self._cache[name] = self._data_provider(name)
        return self._cache[name]

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()
