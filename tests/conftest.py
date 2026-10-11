"""Configuración común de tests."""

from __future__ import annotations

import weakref

import pytest

from api.security import rate_limit

# El limitador de peticiones guarda los contadores en memoria y la app de tests es única:
# sin vaciarlos, el número de tests que llaman a rutas de cálculo acaba dando 429 a los últimos.
_stores: weakref.WeakSet[rate_limit.RateLimitStore] = weakref.WeakSet()
_original_init = rate_limit.RateLimitStore.__init__


def _tracking_init(self: rate_limit.RateLimitStore) -> None:
    _original_init(self)
    _stores.add(self)


rate_limit.RateLimitStore.__init__ = _tracking_init  # type: ignore[method-assign]


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> None:
    for store in list(_stores):
        store.reset()
