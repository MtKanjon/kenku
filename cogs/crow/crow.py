from io import BytesIO
from pprint import pformat

import discord
from PIL import Image
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils import chat_formatting

from .event_manager import EventManager

WIDE_HEIGHT = 48
EVENT_EMOJI = "🧩"


class Crow(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.event_manager = EventManager(self)

    @commands.command()
    async def wide(self, ctx, emoji: discord.PartialEmoji, size: int = 3):
        if size < 2 or size > 10:
            await ctx.react_quietly("🚷")
            return

        emoji_data = BytesIO(await emoji.url.read())
        resized_file = self._resize_image(emoji_data, WIDE_HEIGHT * size, WIDE_HEIGHT)
        file = discord.File(resized_file, filename=f"{emoji.name}_wide.png")
        await ctx.send(file=file)

    def _resize_image(self, image_data: BytesIO, width: int, height: int):
        out = BytesIO()
        with Image.open(image_data) as img:
            resized = img.resize((width, height))
            resized.save(out, format="PNG")
        out.seek(0)
        return out

    @commands.Cog.listener("on_raw_reaction_add")
    async def add_event_points(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        if not self.is_event_react(payload.emoji):
            return
        if not await self.can_event_react(payload.member):
            return

        channel = self.bot.get_channel(payload.channel_id)

        partial = discord.PartialMessage(channel=channel, id=payload.message_id)
        message = await partial.fetch()
        self.event_manager.add_point(message)

        await message.add_reaction(EVENT_EMOJI)

        pass

    @commands.Cog.listener("on_raw_reaction_remove")
    async def remove_event_points(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        if not self.is_event_react(payload.emoji):
            return

        channel = self.bot.get_channel(payload.channel_id)
        partial = discord.PartialMessage(channel=channel, id=payload.message_id)
        message = await partial.fetch()
        self.event_manager.remove_point(message)

    def is_event_react(self, emoji: discord.PartialEmoji):
        return emoji.name == EVENT_EMOJI

    async def can_event_react(self, member: discord.Member):
        return await self.bot.is_mod(member)

    def has_mod_reacts(self, message):
        pass

    @commands.command()
    async def eventdebug(self, ctx):
        msg = chat_formatting.box(pformat(self.event_manager.debug()), "python")
        await ctx.send(msg)
