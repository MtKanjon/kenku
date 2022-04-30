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

    def add_point(self, message: discord.Message):
        self.storage.record_point(
            message_id=message.id,
            user_id=message.author.id,
            channel_id=message.channel.id,
            sent_at=message.created_at,
        )
        self.storage.update_snowflake(id=message.author.id, name=message.author.name)
        self.storage.update_snowflake(id=message.channel.id, name=message.channel.name)

    def remove_point(self, message: discord.Message):
        self.storage.remove_point(message_id=message.id)

    def debug(self):
        data = self.storage.export()
        if len(data) == 0:
            return []
        return data[0].keys() + [tuple(row) for row in data]

    # TODO: discord-related event/leaderboard calculations
