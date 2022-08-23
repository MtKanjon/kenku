import discord
from redbot.core import commands, Config
from redbot.core.bot import Red

from .crow_events import CrowEvents
from .crow_greeter import CrowGreeter
from .crow_mtk import CrowMtk
from .crow_wide import CrowWide

EVENT_EMOJIS = {"🧩": 1, "🍒": 2, "🚥": 3}


class Crow(CrowEvents, CrowGreeter, CrowMtk, CrowWide, commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.bot.allowed_mentions = discord.AllowedMentions.none()
        self.config = Config.get_conf(self, identifier=8703465)

    async def cog_before_invoke(self, ctx: commands.Context):
        self._init_event_manager()
