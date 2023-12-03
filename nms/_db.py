import logging
import sqlite3
import threading
import os

from functools import wraps
from typing import Callable

from ._loggable import Loggable


def connected(func):
    @wraps(func)
    def connected_func(self, *args, **kwargs):
        return func(self, self.connection(), *args, **kwargs)

    return connected_func


class DB(Loggable):
    def __init__(
        self, dbname: str, do_setup: Callable[[sqlite3.Connection], None] = None
    ) -> None:
        super().__init__(logging.getLogger("db"))
        self.log_debug(f"Open database {dbname}")
        self.dbname_ = dbname
        self.conn_ = {}
        self.ensure_dir_exists()
        self.setup(do_setup)

    def ensure_dir_exists(self) -> None:
        if not os.path.exists(self.dbname_):
            dir = "/".join(self.dbname_.split("/")[:-1])
            if dir:
                os.makedirs(dir, exist_ok=True)

    def connection(self) -> sqlite3.Connection:
        thread_id = threading.current_thread().ident
        if not thread_id in self.conn_:
            self.conn_[thread_id] = sqlite3.connect(
                self.dbname_,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
        return self.conn_[thread_id]

    @connected
    def setup(
        self, conn: sqlite3.Connection, do_setup: Callable[[sqlite3.Connection], None]
    ) -> None:
        sqlite3.register_adapter(bool, int)
        sqlite3.register_converter("boolean", lambda v: bool(int(v)))

        if do_setup is None:
            return
        do_setup(conn)
        conn.commit()
