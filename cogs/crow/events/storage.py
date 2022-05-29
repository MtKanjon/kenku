import datetime
import logging
import os
from pathlib import Path
import sqlite3
from typing import List, Optional, Union

from .schema import Migrations
from .scoring import Calculator
from .types import Adjustment

log = logging.getLogger("red.kenku")


class EventStorage:
    def __init__(self, path: Union[str, Path]):
        self.path = (
            path if path == ":memory:" else os.path.join(path, "event_storage.sqlite")
        )
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
        end_at: Optional[datetime.datetime] = None,
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
        self, *, channel_id: int, season_id: int, point_value: int = 1
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
        multiplier: int,
        sent_at: datetime.datetime,
    ):
        self.db.execute(
            """
            INSERT INTO event_points (message_id, user_id, channel_id, multiplier, sent_at)
            VALUES (:message_id, :user_id, :channel_id, :multiplier, :sent_at)
            ON CONFLICT (message_id) DO UPDATE SET multiplier=:multiplier
            """,
            dict(
                message_id=message_id,
                user_id=user_id,
                channel_id=channel_id,
                multiplier=multiplier,
                sent_at=sent_at,
            ),
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

    def export_points(self, *, guild_id):
        return self.db.execute(
            """
            SELECT message_id,
                   c.season_id, s.name season_name,
                   p.channel_id, sc.name channel_name,
                   p.user_id, su.name user_name,
                   point_value, sent_at
            FROM event_points p
            LEFT JOIN event_channels c
                ON p.channel_id = c.channel_id
            LEFT JOIN seasons s
                ON c.season_id = s.id
            LEFT OUTER JOIN snowflakes sc
                ON p.channel_id = sc.id
            LEFT OUTER JOIN snowflakes su
                ON p.user_id = su.id
            WHERE s.guild_id = ?
            """,
            (guild_id,),
        ).fetchall()

    def get_season_scores(self, *, season_id: int):
        return self._scoring.get_season_scores(season_id=season_id)

    def get_event_scores(self, *, channel_id: int):
        return self._scoring.get_event_scores(channel_id=channel_id)

    def get_user_season_scores(self, *, season_id: int, user_id: int):
        return self._scoring.get_user_season_scores(
            season_id=season_id, user_id=user_id
        )

    def get_event_points_for_user(self, *, channel_id: int, user_id: int):
        return self._scoring.get_event_points_for_user(
            channel_id=channel_id, user_id=user_id
        )

    def get_adjustments(self, *, channel_id: int):
        return self.db.execute(
            """
            SELECT user_id, s.name user_name, adjustment, note
            FROM event_adjustments a
            LEFT OUTER JOIN snowflakes s
                ON a.user_id = s.id
            WHERE channel_id = ?
            """,
            (channel_id,),
        ).fetchall()

    def replace_adjustments(self, *, channel_id: int, adjustments: List[Adjustment]):
        """Drop all adjustments for the given channel and replace them."""

        def adjustment_generator():
            for adj in adjustments:
                yield (channel_id, adj.user_id, adj.adjustment, adj.note)

        self.db.execute(
            """
            DELETE FROM event_adjustments
            WHERE channel_id = ?
            """,
            (channel_id,),
        )
        self.db.executemany(
            """
            INSERT INTO event_adjustments (channel_id, user_id, adjustment, note)
            VALUES (?, ?, ?, ?)
            """,
            adjustment_generator(),
        )
        self.db.commit()

        # TODO
        # self._scoring.recalculate_event_scores(season_id=season_id, channel_id=channel_id)
