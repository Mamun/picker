"""
Process-level TTL cache — replaces @st.cache_data in the backend layer.

Usage:
    from stockiq.backend.cache import ttl_cache

    @ttl_cache(60)          # cache for 60 seconds
    def my_fn(arg):
        ...

The store is module-level, so results are shared across all Streamlit sessions
in the same process (same behaviour as @st.cache_data).
"""

import functools
import time


def ttl_cache(ttl_seconds: int):
    """Decorator that caches the return value for ``ttl_seconds`` seconds."""
    def decorator(fn):
        store: dict = {}

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = str(args) + str(sorted(kwargs.items()))
            now = time.time()
            if key in store:
                result, expires = store[key]
                if now < expires:
                    return result
            result = fn(*args, **kwargs)
            store[key] = (result, now + ttl_seconds)
            return result

        wrapper.clear = store.clear  # type: ignore[attr-defined]
        return wrapper
    return decorator
