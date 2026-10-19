import sqlite3
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"], timeout=20, isolation_level=None
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


def close_db(_=None):
    db = g.pop("db", None)
    if db:
        db.close()


def initialize():
    from pathlib import Path

    get_db().executescript(Path(__file__).with_name("schema.sql").read_text())


def row(sql, args=()):
    r = get_db().execute(sql, args).fetchone()
    return dict(r) if r else None


def rows(sql, args=()):
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


class Transaction:
    def __enter__(self):
        self.db = get_db()
        self.db.execute("BEGIN IMMEDIATE")
        return self.db

    def __exit__(self, kind, value, trace):
        self.db.execute("ROLLBACK" if kind else "COMMIT")
