import sqlite3


class Calculator:

    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def compute_scores(self, *, season_id: int, channel_id: int):
        points = self.db.execute(
            """
            SELECT message_id, user_id, p.channel_id, point_value
            FROM event_points p
            JOIN event_channels c
                ON p.channel_id = c.channel_id
            WHERE p.season_id = ?
            """,
            (season_id,),
        ).fetchall()

        season_totals = {}
        event_totals = {}
        for point in points:
            # tally all for season total
            user_id = point["user_id"]
            current_season_points = season_totals.get(user_id, 0)
            season_totals[user_id] = current_season_points + point["point_value"]

            # tally channel total if matching
            if point["channel_id"] == channel_id:
                current_event_points = event_totals.get(user_id, 0)
                event_totals[user_id] = current_event_points + point["point_value"]
        
        # TODO: add in adjustments for season and channel

        def season_score_generator():
            for user_id, score in season_totals.items():
                yield (season_id, user_id, score)

        def event_score_generator():
            for user_id, score in event_totals.items():
                yield (channel_id, user_id, score)

        # clear the season scores out first
        # (this is transactional; commit is after insertion)
        self.db.execute(
            """
            DELETE FROM season_scores
            WHERE season_id = ?
            """,
            (season_id,),
        )
        self.db.execute(
            """
            DELETE FROM event_scores
            WHERE channel_id = ?
            """,
            (channel_id,),
        )
        self.db.executemany(
            """
            INSERT INTO season_scores (season_id, user_id, score)
            VALUES (?, ?, ?)
            """,
            season_score_generator(),
        )
        self.db.executemany(
            """
            INSERT INTO event_scores (channel_id, user_id, score)
            VALUES (?, ?, ?)
            """,
            event_score_generator(),
        )
        self.db.commit()

    def update_score(self, *, season_id: int, channel_id: int, user_id: int):
        season_score = self._sum_user_season(season_id=season_id, user_id=user_id)
        event_score = self._sum_user_event(channel_id=channel_id, user_id=user_id)

        self.db.execute(
            """
            INSERT INTO season_scores (season_id, user_id, score)
            VALUES (:season_id, :user_id, :score)
            ON CONFLICT (season_id, user_id) DO UPDATE SET score=:score
            """,
            dict(season_id=season_id, user_id=user_id, score=season_score),
        )
        self.db.execute(
            """
            INSERT INTO event_scores (channel_id, user_id, score)
            VALUES (:channel_id, :user_id, :score)
            ON CONFLICT (channel_id, user_id) DO UPDATE SET score=:score
            """,
            dict(channel_id=channel_id, user_id=user_id, score=event_score),
        )
        self.db.commit()

    def _sum_user_season(self, *, season_id: int, user_id: int):
        """Re-calculate a user's season score based on live point data."""

        points = self.get_season_points_for_user(season_id=season_id, user_id=user_id)
        # TODO
        # adj = self.get_season_adjustments_for_user(season_id=season_id, user_id=user_id)
        return sum(p["point_value"] for p in points)

    def _sum_user_event(self, *, channel_id: int, user_id: int):
        """Re-calculate a user's event/channel score based on live point data."""

        points = self.get_event_points_for_user(channel_id=channel_id, user_id=user_id)
        # TODO
        # adj = self.get_event_adjustments_for_user(channel_id=channel_id, user_id=user_id)
        return sum(p["point_value"] for p in points)

    def get_season_points_for_user(self, *, season_id: int, user_id: int):
        """Fetch all of the points for a user this season."""

        return self.db.execute(
            """
            SELECT message_id, p.channel_id, point_value, sent_at
            FROM event_points p
            JOIN event_channels c
                ON p.channel_id = c.channel_id
            WHERE user_id = ? AND p.season_id = ?
            """,
            (user_id, season_id),
        ).fetchall()

    def get_event_points_for_user(self, *, channel_id: int, user_id: int):
        """Fetch all of the points for a user this event/channel."""

        return self.db.execute(
            """
            SELECT message_id, p.channel_id, point_value, sent_at
            FROM event_points p
            JOIN event_channels c
                ON p.channel_id = c.channel_id
            WHERE user_id = ? AND p.channel_id = ?
            """,
            (user_id, channel_id),
        ).fetchall()
    
    def get_season_adjustments_for_user(self, *, season_id: int, user_id: int):
        """Fetch all of the points for a user this event/channel."""

        return self.db.execute(
            """
            SELECT a.channel_id, adjustment
            FROM event_adjustments a
            JOIN event_channels c
                ON a.channel_id = c.channel_id
            WHERE user_id = ? AND c.season_id = ?
            """,
            (user_id, season_id),
        ).fetchall()
    
    def get_season_scores(self, *, season_id: int):
        return self.db.execute(
            """
            SELECT user_id, score
            FROM season_scores
            INDEXED BY idx_high_scores
            WHERE season_id = ?
            ORDER BY score DESC
            """,
            (season_id,),
        ).fetchall()

    def get_event_scores(self, *, channel_id: int):
        return self.db.execute(
            """
            SELECT user_id, score
            FROM event_scores
            INDEXED BY idx_event_high_scores
            WHERE channel_id = ?
            ORDER BY score DESC
            """,
            (channel_id,),
        ).fetchall()

