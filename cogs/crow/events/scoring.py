import sqlite3


class Calculator:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def recalculate_event_scores(self, *, season_id: int, channel_id: int):
        """
        Re-compute scores for an entire event, and update that event and season.

        Useful if an event/channel's configuration was modified. If only a user's score
        needs to be updated, use `recalculate_user_scores`.
        """
        season_totals = {}
        event_totals = {}

        # tally up all points
        points = self.db.execute(
            """
            SELECT message_id, user_id, p.channel_id, point_value, multiplier
            FROM event_points p
            JOIN event_channels c
                ON p.channel_id = c.channel_id
            WHERE c.season_id = ?
            """,
            (season_id,),
        ).fetchall()

        for point in points:
            # tally all for season total
            user_id = point["user_id"]
            current_season_points = season_totals.get(user_id, 0)
            season_totals[user_id] = (
                current_season_points + point["point_value"] * point["multiplier"]
            )

            # tally channel total if matching
            if point["channel_id"] == channel_id:
                current_event_points = event_totals.get(user_id, 0)
                event_totals[user_id] = (
                    current_event_points + point["point_value"] * point["multiplier"]
                )

        # and then similarly tally up all adjustments
        adjustments = self.db.execute(
            """
            SELECT user_id, a.channel_id, adjustment
            FROM event_adjustments a
            JOIN event_channels c
                ON a.channel_id = c.channel_id
            WHERE c.season_id = ?
            """,
            (season_id,),
        ).fetchall()

        for adj in adjustments:
            # tally all for season total
            user_id = adj["user_id"]
            current_season_points = season_totals.get(user_id, 0)
            season_totals[user_id] = current_season_points + adj["adjustment"]

            # tally channel total if matching
            if adj["channel_id"] == channel_id:
                current_event_points = event_totals.get(user_id, 0)
                event_totals[user_id] = current_event_points + adj["adjustment"]

        def season_score_generator():
            for user_id, score in season_totals.items():
                yield (season_id, user_id, score)

        def event_score_generator():
            for user_id, score in event_totals.items():
                yield (channel_id, user_id, score)

        # clear the season + event scores out first
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

    def recalculate_user_scores(self, *, season_id: int, channel_id: int, user_id: int):
        """
        Insert or update the event and season score for a user.

        This re-calculates scores for the specified event/channel as well as the season.
        """
        season_points = self.get_season_points_for_user(
            season_id=season_id, user_id=user_id
        )
        season_adj = self.get_season_adjustments_for_user(
            season_id=season_id, user_id=user_id
        )
        season_score = sum(
            p["point_value"] * p["multiplier"] for p in season_points
        ) + sum(a["adjustment"] for a in season_adj)

        event_points = self.get_event_points_for_user(
            channel_id=channel_id, user_id=user_id
        )
        event_adj = self.get_event_adjustments_for_user(
            channel_id=channel_id, user_id=user_id
        )
        event_score = sum(
            p["point_value"] * p["multiplier"] for p in event_points
        ) + sum(a["adjustment"] for a in event_adj)

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

    def get_season_points_for_user(self, *, season_id: int, user_id: int):
        """Fetch all of the points for a user this season."""

        return self.db.execute(
            """
            SELECT message_id, p.channel_id, point_value, multiplier, sent_at
            FROM event_points p
            JOIN event_channels c
                ON p.channel_id = c.channel_id
            WHERE user_id = ? AND c.season_id = ?
            """,
            (user_id, season_id),
        ).fetchall()

    def get_event_points_for_user(self, *, channel_id: int, user_id: int):
        """Fetch all of the points for a user this event/channel."""

        return self.db.execute(
            """
            SELECT message_id, p.channel_id, point_value, multiplier, sent_at
            FROM event_points p
            JOIN event_channels c
                ON p.channel_id = c.channel_id
            WHERE user_id = ? AND c.channel_id = ?
            """,
            (user_id, channel_id),
        ).fetchall()

    def get_season_adjustments_for_user(self, *, season_id: int, user_id: int):
        """Fetch all of the adjustments for a user for this season."""

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

    def get_event_adjustments_for_user(self, *, channel_id: int, user_id: int):
        """Fetch all of the adjustments for a user for this event/channel."""

        return self.db.execute(
            """
            SELECT channel_id, adjustment
            FROM event_adjustments
            WHERE user_id = ? AND channel_id = ?
            """,
            (user_id, channel_id),
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

    def get_user_season_scores(self, *, season_id: int, user_id: int):
        return self.db.execute(
            """
            SELECT s.channel_id, score
            FROM event_scores s
            JOIN event_channels c
                ON s.channel_id = c.channel_id
            WHERE c.season_id = ? AND s.user_id = ?
            ORDER BY s.channel_id DESC
            """,
            (season_id, user_id),
        ).fetchall()
