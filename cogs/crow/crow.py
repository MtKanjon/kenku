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
    async def wide(
        self, ctx: commands.Context, emoji: discord.PartialEmoji, size: int = 3
    ):
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
        pass  # TODO

    @commands.command()
    async def eventdebug(self, ctx: commands.Context):
        msg = chat_formatting.box(pformat(self.event_manager.debug()), "python")
        await ctx.send(msg)

    @commands.command()
    async def mypoints(self, ctx: commands.Context):
        season, point_map = self.event_manager.user_info(ctx.message.author)

        desc = []
        for channel, points in point_map.items():
            plural = "point" if points == 1 else "points"
            desc.append(f"<#{channel}>: {points} {plural}")

        embed = discord.Embed(
            title=f"Your points - {season['name']}",
            description="\n".join(desc),
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def leaderboard(self, ctx: commands.Context):
        season, user_points = self.event_manager.compute_leaderboard(ctx.guild.id)

        desc = []
        place = 1
        for user, points in user_points.items():
            plural = "point" if points == 1 else "points"
            desc.append(f"**{place}.** <@{user}>: {points} {plural}")
            place += 1

        embed = discord.Embed(
            title=f"Leaderboard - {season['name']}",
            description="\n".join(desc),
        )
        mentions = discord.AllowedMentions(users=False)
        await ctx.send(embed=embed, allowed_mentions=mentions)

    @commands.command()
    async def confchannel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        point_value: int = None,
    ):
        self.event_manager.configure_channel(channel, point_value)
        await ctx.tick()
