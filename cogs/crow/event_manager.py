import discord
from redbot.core.data_manager import cog_data_path
from redbot.core import commands

from .event_storage import EventStorage


class EventManager:
    
    def __init__(self, cog: commands.Cog):
        self.cog = cog

        # TODO: move this to a lazy-loaded callback that runs before command group invocation
        path = cog_data_path(cog_instance=cog)
        self.storage = EventStorage(path)
        self.storage.initialize()

    def configure_channel(self, channel: discord.TextChannel, multiplier: int = None):
        self.storage.configure_channel(channel_id=channel.id, multiplier=multiplier)
        self.storage.update_snowflake(id=channel.id, name=channel.name)

    def add_point(self, message: discord.Message):
        self.storage.record_point(
            message_id=message.id,
            user_id=message.author.id,
            channel_id=message.channel.id,
            sent_at=message.created_at,
        )
        self.storage.update_snowflake(
            id=message.author.id,
            name=f"{message.author.name}#{message.author.discriminator}",
        )
        self.storage.update_snowflake(id=message.channel.id, name=message.channel.name)

    def remove_point(self, message: discord.Message):
        self.storage.remove_point(message_id=message.id)

    def user_info(self, user: discord.User):
        points = self.storage.get_points_for_user(user_id=user.id)
        point_map = {}
        for point in points:
            channel_id = point["channel_id"]
            current_points = point_map.get(channel_id, 0)
            point_map[channel_id] = current_points + point["multiplier"]
        return point_map

    def compute_leaderboard(self):
        points = self.storage.get_all_points()
        user_points = {}
        for point in points:
            user_id = point["user_id"]
            current_points = user_points.get(user_id, 0)
            user_points[user_id] = current_points + point["multiplier"]
        # TODO: cache this into a leaderboard table that is kept up to date
        tuples = sorted(user_points.items(), key=lambda item: item[1], reverse=True)
        sorted_users = {k: v for k, v in tuples}
        return sorted_users

    def debug(self):
        data = self.storage.export()
        if len(data) == 0:
            return []
        return [data[0].keys()] + [tuple(row) for row in data]
