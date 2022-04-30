import datetime
import os
import sqlite3


class EventStorage:
    def __init__(self, path: str):
        self.path = os.path.join(path, "event_storage.sqlite")
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row

        # XXX
        print(self.path)

        def debug(s):
            print(s)

        self.db.set_trace_callback(debug)

    def initialize(self):
        if self._version() == SCHEMA_VERSION:
            return
        self.db.executescript(SCHEMA)
        self._version(assign=SCHEMA_VERSION)

    def _version(self, *, assign: int = None):
        if assign:
            # pragma does not support typical parameter substitution
            self.db.execute(f"PRAGMA user_version = {assign:d}").fetchone()
        row = self.db.execute("PRAGMA user_version").fetchone()
        return row[0]

    def configure_channel(self, *, channel_id: int, multiplier: int = None):
        pass  # TODO

    def remove_channel(self, *, channel_id: int):
        pass  # TODO

    def update_snowflake(self, *, id, name):
        self.db.execute(
            """
            INSERT INTO snowflakes (id, name, cached_at)
            VALUES (:id, :name, :now)
            ON CONFLICT (id) DO UPDATE SET name=:name, cached_at=:now
            """,
            dict(id=id, name=name, now=datetime.datetime.now()),
        )
        self.db.commit()

    def record_point(
        self,
        *,
        message_id: int,
        user_id: int,
        channel_id: int,
        sent_at: datetime.datetime,
    ):
        self.db.execute(
            """
            INSERT INTO event_points (message_id, user_id, channel_id, sent_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (message_id) DO NOTHING
            """,
            (message_id, user_id, channel_id, sent_at),
        )
        self.db.commit()

    def remove_point(self, *, message_id):
        self.db.execute(
            """
            DELETE FROM event_points
            WHERE message_id = ?
            """,
            (message_id,),
        )
        self.db.commit()

    def get_channel(self, channel_id):
        rows = self.db.execute(
            """
            SELECT * from event_channels
            WHERE channel_id = ?
            """,
            (channel_id,),
        ).fetchall()

    def get_points_for_user(self, user_id):
        rows = self.db.execute(
            """
            SELECT message_id, channel_id, multiplier, sent_at
            FROM event_points p
            JOIN event_channels c
                ON p.channel_id = c.channel_id
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchall()

    def export(self):
        return self.db.execute(
            """
            SELECT message_id, p.channel_id, multiplier, sent_at, sc.name channel, sc.name user
            FROM event_points p
            LEFT OUTER JOIN event_channels c
                ON p.channel_id = c.channel_id
            LEFT OUTER JOIN snowflakes sc
                ON p.channel_id = sc.id
            LEFT OUTER JOIN snowflakes su
                ON p.user_id = su.id
            """
        ).fetchall()


SCHEMA_VERSION = 1
SCHEMA = """
    CREATE TABLE event_channels(
        channel_id  INTEGER PRIMARY KEY NOT NULL,
        multiplier  INTEGER DEFAULT 1
    );

    CREATE TABLE event_points(
        message_id  INTEGER PRIMARY KEY NOT NULL,
        user_id     INTEGER NOT NULL,
        channel_id  INTEGER NOT NULL,
        sent_at     INTEGER NOT NULL
    );

    CREATE TABLE snowflakes(
        id         INTEGER PRIMARY KEY NOT NULL,
        name       TEXT,
        cached_at  INTEGER NOT NULL
    );
"""
