import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from schwab_cli.config import lock_path, local_schwab_dir


class TokenLockError(RuntimeError):
    pass


@contextmanager
def token_lock() -> Iterator[None]:
    local_schwab_dir().mkdir(parents=True, exist_ok=True)
    path = lock_path()
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            msg = (
                "Another Schwab CLI process is refreshing or logging in. "
                "Wait for it to finish, then retry."
            )
            raise TokenLockError(msg) from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.flush()
            os.fsync(handle.fileno())
