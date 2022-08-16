import discord
from redbot.core import commands
from redbot.core.bot import Red

from .crow_events import CrowEvents
from .crow_wide import CrowWide

EVENT_EMOJIS = {"🧩": 1, "🍒": 2, "🚥": 3}


class Crow(CrowEvents, CrowWide, commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.bot.allowed_mentions = discord.AllowedMentions.none()

    async def cog_before_invoke(self, ctx: commands.Context):
        self._init_event_manager()
