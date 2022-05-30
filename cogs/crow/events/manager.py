import asyncio
import csv
import datetime
import logging
from typing import IO, Optional

import discord
from discord.ext.commands.converter import UserConverter
from redbot.core.data_manager import cog_data_path
from redbot.core import commands

from .storage import EventStorage
from .types import Adjustment

log = logging.getLogger("red.kenku")


class EventError(Exception):
    pass


class EventManager:
    def __init__(self, cog: commands.Cog, *, storage_path: Optional[str] = None):
        self.cog = cog

        path = storage_path if storage_path else cog_data_path(cog_instance=cog)
        self.storage = EventStorage(path)
        self.storage.initialize()

        self.active_task = None

    def rescan_channel(
        self, ctx: commands.Context, channel: discord.TextChannel, handler
    ):
        self.active_task = asyncio.create_task(self._rescan_task(ctx, channel, handler))

    async def _rescan_task(
        self, ctx: commands.Context, channel: discord.TextChannel, handler
    ):
        async with ctx.typing():
            await asyncio.sleep(1.0)
            status_message: discord.Message = await ctx.send(
                f"⏳ Scan task started. Watch this space..."
            )

            # scan channel history (how far back?)
            count = 0
            flip = False
            async for message in channel.history(limit=1000):
                await handler(message)

                count += 1
                if count % 100 == 0:
                    await asyncio.sleep(2.0)
                    emoji = "🎶" if flip else "🎵"
                    flip = not flip
                    await status_message.edit(
                        content=f"{emoji} Scanned {count} messages so far..."
                    )

            await status_message.edit(
                content=f"🏁 Scan complete. Checked {count} messages."
            )
            self.active_task = None

    def _default_season(self, guild_id):
        # FUTURE: multi-season support; for now just use the first/default
        seasons = self.storage.get_seasons(guild_id=guild_id)
        if len(seasons) > 0:
            return seasons[0]
        else:
            self.storage.configure_season(
                name="Season 1", guild_id=guild_id, start_at=datetime.datetime.now()
            )
            seasons = self.storage.get_seasons(guild_id=guild_id)
            return seasons[0]

    def configure_channel(self, channel: discord.TextChannel, point_value: int = 1):
        season_id = self._default_season(channel.guild.id)["id"]

        if point_value == 0:
            self.storage.remove_channel(season_id=season_id, channel_id=channel.id)
            return

        self.storage.configure_channel(
            season_id=season_id, channel_id=channel.id, point_value=point_value
        )
        self.storage.update_snowflake(id=channel.id, name=channel.name)

    def clear_channel_points(self, channel: discord.TextChannel):
        self.storage.clear_channel_points(channel_id=channel.id)

    def get_season_channels(self, ctx: commands.Context):
        season = self._default_season(ctx.guild.id)
        return season, self.storage.get_season_channels(season["id"])

    def set_points(self, message: discord.Message, score: int):
        season_id = self._default_season(message.guild.id)["id"]

        # always remove points if set to zero
        if score == 0:
            self.storage.remove_point(
                message_id=message.id,
                season_id=season_id,
                channel_id=message.channel.id,
                user_id=message.author.id,
            )
            return

        # only record a point if the channel was configured
        if not self.storage.get_channel(message.channel.id):
            return False
        self.storage.record_point(
            message_id=message.id,
            user_id=message.author.id,
            season_id=season_id,
            channel_id=message.channel.id,
            sent_at=message.created_at,
            multiplier=score,
        )
        self.storage.update_snowflake(
            id=message.author.id,
            name=f"{message.author.name}#{message.author.discriminator}",
        )
        self.storage.update_snowflake(id=message.channel.id, name=message.channel.name)
        return True

    def user_info(self, user: discord.User):
        season = self._default_season(user.guild.id)

        return season, self.storage.get_user_season_scores(
            season_id=season["id"], user_id=user.id
        )

    def user_event_info(self, user: discord.User, channel: discord.TextChannel):
        points = self.storage.get_event_points_for_user(
            channel_id=channel.id, user_id=user.id
        )
        adjustments = self.storage.get_event_adjustments_for_user(
            channel_id=channel.id, user_id=user.id
        )
        return points, adjustments

    def get_season_leaderboard(self, guild_id):
        season = self._default_season(guild_id)

        sorted_scores = self.storage.get_season_scores(season_id=season["id"])
        score_map = {s["user_id"]: s["score"] for s in sorted_scores}
        return season, score_map

    def get_event_leaderboard(self, channel_id):
        if not self.storage.get_channel(channel_id):
            return None
        sorted_scores = self.storage.get_event_scores(channel_id=channel_id)
        score_map = {s["user_id"]: s["score"] for s in sorted_scores}
        return score_map

    def get_adjustments(self, channel_id: int, file: IO, sample_user: discord.Member):
        rows = self.storage.get_adjustments(channel_id=channel_id)
        writer = csv.DictWriter(
            file,
            [
                "user_id",
                "user_name",
                "adjustment",
                "note",
            ],
            extrasaction="ignore",
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()

        # write a sample row
        if len(rows) == 0:
            writer.writerow(
                dict(
                    user_id=None,
                    user_name=f"{sample_user.name}#{sample_user.discriminator}",
                    adjustment=10,
                    note=f"Adding 10 points for {sample_user.display_name} because reasons",
                )
            )
        else:
            for row in rows:
                flattened = dict(row)
                writer.writerow(flattened)

        return rows

    async def replace_adjustments(
        self, ctx: commands.Context, channel_id: int, file: IO
    ):
        season = self._default_season(ctx.guild.id)

        reader = csv.DictReader(file)
        user_lookup = UserConverter()
        adjustments = []
        errors = []
        for row in reader:
            user_id = int(row["user_id"]) if row["user_id"] else None
            adjustment = int(row["adjustment"]) if row["adjustment"] else 0

            # attempt to look up user by name
            if not user_id:
                try:
                    user: discord.User = await user_lookup.convert(
                        ctx, row["user_name"]
                    )
                except:
                    errors.append(row["user_name"])
                    continue
                user_id = user.id
            user = await ctx.bot.get_or_fetch_user(user_id)
            self.storage.update_snowflake(
                id=user_id, name=f"{user.name}#{user.discriminator}"
            )
            adj = Adjustment(user_id=user_id, adjustment=adjustment, note=row["note"])
            adjustments.append(adj)

        if errors:
            raise EventError("Couldn't figure out these users: " + ", ".join(errors))

        self.storage.replace_adjustments(
            season_id=season["id"], channel_id=channel_id, adjustments=adjustments
        )

    def export_points(self, guild_id: int, file: IO):
        rows = self.storage.export_points(guild_id=guild_id)
        writer = csv.DictWriter(
            file,
            [
                "message_id",
                "season_id",
                "season_name",
                "channel_id",
                "channel_name",
                "user_id",
                "user_name",
                "point_value",
                "sent_at",
            ],
            extrasaction="ignore",
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        for row in rows:
            flattened = dict(row)
            writer.writerow(flattened)
