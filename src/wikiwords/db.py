import logging
import os
import sqlite3 as sqlite

from .models import models

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", logging.INFO))

def create_and_connect(db: str, debug: bool = False) -> sqlite.Connection:
    try:
        os.remove(db)
    except FileNotFoundError:
        # save to ignore if db doesn't already exist
        pass

    conn = sqlite.connect(db)

    if debug == True:
        conn.set_trace_callback(lambda stmt: logger.debug(stmt))

    # migrate models
    for m in models():
        m.migrate(conn)

    return conn
