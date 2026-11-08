"""Single-backend artifact leases. Tombstones never wait for long model work.

All artifact producers register before reading their input. Cleanup waits until
they have left, then excludes new producers until physical cleanup ends. SQLite
still serializes every authority decision; this gate is not an auth boundary.
The supported deployment remains one backend worker per database.
"""
from contextlib import contextmanager
from pathlib import Path
import threading

_registry_lock = threading.Lock()
_registry = {}


def gate(engine):
    key = str(Path(engine.url.database).resolve()).casefold()
    with _registry_lock:
        return _registry.setdefault(key, [threading.Condition(), 0, False])


@contextmanager
def producing(engine):
    state = gate(engine)
    with state[0]:
        state[0].wait_for(lambda: not state[2])
        state[1] += 1
    try:
        yield
    finally:
        with state[0]:
            state[1] -= 1
            state[0].notify_all()


@contextmanager
def cleaning(engine):
    state = gate(engine)
    with state[0]:
        acquired = not state[1] and not state[2]
        if acquired:
            state[2] = True
    try:
        yield acquired
    finally:
        if acquired:
            with state[0]:
                state[2] = False
                state[0].notify_all()
