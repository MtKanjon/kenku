import sqlite3
import logging

log = logging.getLogger("red.kenku")

SCHEMA_VERSION = 4
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
SCHEMA_3_TO_4 = """
BEGIN TRANSACTION;
    CREATE TEMPORARY TABLE event_points_bak (
        message_id  INTEGER PRIMARY KEY NOT NULL,
        user_id     INTEGER NOT NULL,
        channel_id  INTEGER NOT NULL,
        sent_at     INTEGER NOT NULL
    );
    INSERT INTO event_points_bak SELECT message_id, user_id, channel_id, sent_at FROM event_points;
    DROP TABLE event_points;
    CREATE TABLE event_points (
        message_id  INTEGER PRIMARY KEY NOT NULL,
        user_id     INTEGER NOT NULL,
        channel_id  INTEGER NOT NULL,
        sent_at     INTEGER NOT NULL
    );
    INSERT INTO event_points SELECT message_id, user_id, channel_id, sent_at FROM event_points_bak;
    DROP TABLE event_points_bak;
COMMIT;
VACUUM;
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
    
    def to_4(self):
        self.db.executescript(SCHEMA_3_TO_4)
