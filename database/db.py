"""Database factory for Market Agent.

Determines the active database engine (SQLite or PostgreSQL) based on environment configuration.
"""

from __future__ import annotations

import os
from database.base import BaseDatabase
from database.sqlite import SQLiteDatabase
from database.postgres import PostgresDatabase


class Database:
    """Database factory wrapper.

    Instantiates and returns the appropriate implementation of BaseDatabase.
    All system modules can import `Database` as usual and get the active driver.
    """

    def __new__(cls, *args, **kwargs) -> BaseDatabase:
        db_type = os.getenv("MA_DATABASE_TYPE", "sqlite").lower().strip()
        if db_type == "postgres":
            return PostgresDatabase(*args, **kwargs)
        return SQLiteDatabase(*args, **kwargs)
