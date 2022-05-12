import datetime
import logging
import os
import sqlite3

from .scoring import Calculator


log = logging.getLogger("red.kenku")


class EventStorage:
    def __init__(self, path: str):
        self.path = os.path.join(path, "event_storage.sqlite")
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row

        log.debug(self.path)
        if logging.DEBUG >= log.level:
            self.db.set_trace_callback(log.debug)

        self._scoring = Calculator(self.db)

    def initialize(self):
        migrations = Migrations(self.db)
        migrations.migrate()

    def get_seasons(self, *, guild_id):
        return self.db.execute(
            """
            SELECT * FROM seasons
            WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchall()

    def configure_season(
        self,
        *,
        name: str,
        guild_id: int,
        start_at: datetime.datetime,
        end_at: datetime.datetime = None,
    ):
        """Creates or updates a season with the given name."""

        self.db.execute(
            """
            INSERT INTO seasons (name, guild_id, start_at, end_at)
            VALUES (:name, :guild_id, :start_at, :end_at)
            ON CONFLICT (name, guild_id) DO UPDATE SET start_at=:start_at, end_at=:end_at
            """,
            dict(name=name, guild_id=guild_id, start_at=start_at, end_at=end_at),
        )
        self.db.commit()

    def get_channel(self, channel_id: int):
        return self.db.execute(
            """
            SELECT * from event_channels
            WHERE channel_id = ?
            """,
            (channel_id,),
        ).fetchone()

    def get_season_channels(self, season_id: int):
        return self.db.execute(
            """
            SELECT * from event_channels
            WHERE season_id = ?
            """,
            (season_id,),
        ).fetchall()

    def configure_channel(
        self, *, channel_id: int, season_id: int, point_value: int = None
    ):
        self.db.execute(
            """
            INSERT INTO event_channels (channel_id, season_id, point_value)
            VALUES (:channel_id, :season_id, :point_value)
            ON CONFLICT (channel_id) DO UPDATE SET point_value=:point_value
            """,
            dict(channel_id=channel_id, season_id=season_id, point_value=point_value),
        )
        self.db.commit()
        self._scoring.recalculate_event_scores(
            season_id=season_id, channel_id=channel_id
        )

    def remove_channel(self, *, channel_id: int, season_id: int):
        self.db.execute(
            """
            DELETE FROM event_channels
            WHERE channel_id = ?
            """,
            (channel_id,),
        )
        self.db.commit()
        self._scoring.recalculate_event_scores(
            season_id=season_id, channel_id=channel_id
        )

    def clear_channel_points(self, *, channel_id: int):
        self.db.execute(
            """
            DELETE FROM event_points
            WHERE channel_id = ?
            """,
            (channel_id,),
        )
        self.db.commit()

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
        season_id: int,
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
        self._scoring.recalculate_user_scores(
            season_id=season_id, channel_id=channel_id, user_id=user_id
        )

    def remove_point(
        self, *, message_id: int, user_id: int, season_id: int, channel_id: int
    ):
        self.db.execute(
            """
            DELETE FROM event_points
            WHERE message_id = ?
            """,
            (message_id,),
        )
        self.db.commit()
        self._scoring.recalculate_user_scores(
            season_id=season_id, channel_id=channel_id, user_id=user_id
        )

    def export(self, *, guild_id):
        return self.db.execute(
            """
            SELECT message_id, p.season_id, p.channel_id, point_value, sent_at, sc.name channel, su.name user
            FROM event_points p
            LEFT OUTER JOIN event_channels c
                ON p.channel_id = c.channel_id
            LEFT OUTER JOIN snowflakes sc
                ON p.channel_id = sc.id
            LEFT OUTER JOIN snowflakes su
                ON p.user_id = su.id
            """
        ).fetchall()

    def get_season_scores(self, *, season_id: int):
        return self._scoring.get_season_scores(season_id=season_id)

    def get_event_scores(self, *, channel_id: int):
        return self._scoring.get_event_scores(channel_id=channel_id)

    def get_season_points_for_user(self, *, season_id: int, user_id: int):
        return self._scoring.get_season_points_for_user(
            season_id=season_id, user_id=user_id
        )


SCHEMA_VERSION = 3
SCHEMA = """
    CREATE TABLE IF NOT EXISTS seasons (
        id        INTEGER PRIMARY KEY NOT NULL,
        name      TEXT NOT NULL,
        guild_id  INTEGER NOT NULL,
        start_at  INTEGER NOT NULL,
        end_at    INTEGER,

        UNIQUE (name, guild_id)
    );

    CREATE TABLE IF NOT EXISTS season_scores (
        season_id  INTEGER NOT NULL,
        user_id    INTEGER NOT NULL,
        score      INTEGER NOT NULL,

        PRIMARY KEY (season_id, user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_high_scores ON season_scores (season_id, score DESC);

    CREATE TABLE IF NOT EXISTS event_channels (
        channel_id   INTEGER PRIMARY KEY NOT NULL,
        season_id    INTEGER NOT NULL,
        point_value  INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS event_points (
        message_id  INTEGER PRIMARY KEY NOT NULL,
        user_id     INTEGER NOT NULL,
        channel_id  INTEGER NOT NULL,
        sent_at     INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS event_adjustments (
        id          INTEGER PRIMARY KEY NOT NULL,
        channel_id  INTEGER NOT NULL,
        user_id     INTEGER NOT NULL,
        adjustment  INTEGER NOT NULL,
        note        TEXT
    );

    CREATE TABLE IF NOT EXISTS event_scores (
        channel_id  INTEGER NOT NULL,
        user_id     INTEGER NOT NULL,
        score       INTEGER NOT NULL,

        PRIMARY KEY (channel_id, user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_event_high_scores ON event_scores (channel_id, score DESC);

    CREATE TABLE IF NOT EXISTS snowflakes (
        id         INTEGER PRIMARY KEY NOT NULL,
        name       TEXT,
        cached_at  INTEGER NOT NULL
    );
"""


class Migrations:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.current = self.version()

    def migrate(self):
        # up to date
        if self.current == SCHEMA_VERSION:
            return

        # fresh database
        if self.current == 0:
            # SCHEMA should always represent current state, so skip to that
            self.db.executescript(SCHEMA)
            self.current = SCHEMA_VERSION
            self.version(assign=self.current)
            return

        # roll through each migration
        while self.current < SCHEMA_VERSION:
            target = self.current + 1
            log.warning(f"Processing event storage migration to version {target}")
            migration = getattr(self, f"to_{target}", None)
            if migration:
                migration()
            self.current = target
            self.version(assign=self.current)

        log.info("Migrations complete")

    def version(self, *, assign: int = None):
        if assign:
            # pragma does not support typical parameter substitution
            self.db.execute(f"PRAGMA user_version = {assign:d}").fetchone()
        row = self.db.execute("PRAGMA user_version").fetchone()
        return row[0]

    # MIGRATIONS BELOW
    # If a migration doesn't modify a table/index (for example, it just creates new tables),
    # then just execute SCHEMA. SCHEMA should always be safe to re-run.
    # Otherwise, apply the necessary SQL to migrate.

    def to_2(self):
        self.db.executescript(SCHEMA)

    def to_3(self):
        self.db.executescript(SCHEMA)
