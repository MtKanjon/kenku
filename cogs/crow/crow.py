from io import BytesIO
from math import floor
from pprint import pformat
from typing import Union

import discord
from PIL import Image
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils import chat_formatting

from .events import EventManager

WIDE_HEIGHT = 48
EVENT_EMOJI = "🧩"


class Crow(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.event_manager = None

    async def cog_before_invoke(self, ctx: commands.Context):
        self._init_event_manager()

    def _init_event_manager(self):
        # initialize the event manager lazily, so bugs don't crash startup
        if self.event_manager:
            return
        self.event_manager = EventManager(self)

    @commands.command()
    async def wide(
        self, ctx: commands.Context, emoji: discord.PartialEmoji, size: float = 3
    ):
        """owo"""

        if size < 0.05 or size > 20:
            await ctx.react_quietly("🚷")
            return

        if size >= 1.0:
            width = floor(WIDE_HEIGHT * size)
            height = WIDE_HEIGHT
        else:
            # 🐇🥚🤫
            width = WIDE_HEIGHT
            height = floor(WIDE_HEIGHT / size)

        emoji_data = BytesIO(await emoji.url.read())
        resized_file = self._resize_image(emoji_data, width, height)
        file = discord.File(resized_file, filename=f"{emoji.name}_wide.png")
        await ctx.send(file=file)

    def _resize_image(self, image_data: BytesIO, width: int, height: int):
        out = BytesIO()
        with Image.open(image_data) as img:
            resized = img.resize((width, height))
            resized.save(out, format="PNG")
        out.seek(0)
        return out

    @commands.group()
    async def events(self, ctx: commands.Context):
        """
        Event leaderboard and point tracking commands.

        Leaderboards are calculated by adding up points for all members participating in an event. To create an event, use the `confchannel` command to tell the bot to monitor the event's channel. Then, react to messages with the 🧩 emoji. Any message with a 🧩 react will be counted for that event's score for that person, and can be applied by any mod/admin. The bot will react with 🧩 as an acknowledgement.

        By default, each 🧩 react earns the member 1 point, but each message only counts once, no matter how many people react. To change the point value, use `confchannel`. Higher point values may be useful for events that require more participation.

        This bot also tracks seasons of events, however the capability to configure seasons is not yet supported. All events/channels and leaderboards will fall under "Season 1" for now.
        """

    @commands.Cog.listener("on_raw_reaction_add")
    async def add_event_points(self, payload: discord.RawReactionActionEvent):
        self._init_event_manager()
        if not await self.should_handle_react(payload):
            return

        channel = self.bot.get_channel(payload.channel_id)
        partial = discord.PartialMessage(channel=channel, id=payload.message_id)
        message: discord.Message = await partial.fetch()

        added = self.event_manager.add_point(message)
        if added:
            await message.add_reaction(EVENT_EMOJI)

    @commands.Cog.listener("on_raw_reaction_remove")
    async def remove_event_points(self, payload: discord.RawReactionActionEvent):
        self._init_event_manager()
        if not await self.should_handle_react(payload):
            return

        channel = self.bot.get_channel(payload.channel_id)
        partial = discord.PartialMessage(channel=channel, id=payload.message_id)
        message: discord.Message = await partial.fetch()

        # if there are still mod reacts, don't remove the point!
        if await self.has_mod_reacts(message):
            return

        self.event_manager.remove_point(message)
        await message.remove_reaction(EVENT_EMOJI, self.bot.user)

    async def should_handle_react(self, payload: discord.RawReactionActionEvent):
        # ignore ourselves
        if payload.user_id == self.bot.user.id:
            return False

        # make sure it's actually an event reaction
        if not self.is_event_react(payload.emoji):
            return False

        # member is empty on reaction removals, so look it up
        member = payload.member
        if not member:
            guild = self.bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)

        # check if the person un/reacting is a mod
        if not await self.bot.is_mod(member):
            return False

        return True

    def is_event_react(self, emoji: Union[str, discord.PartialEmoji]):
        if emoji == EVENT_EMOJI:
            return True
        try:
            return emoji.name == EVENT_EMOJI
        except AttributeError:
            return False

    async def has_mod_reacts(self, message: discord.Message):
        """Check if a message has any mod event reactions."""

        # find the reaction
        try:
            reaction: discord.Reaction = next(
                filter(lambda r: self.is_event_react(r.emoji), message.reactions)
            )
        except StopIteration:
            return False

        # async loop reacting users to find mods
        async for user in reaction.users():
            if await self.bot.is_mod(user):
                return True
        return False

    @events.command(name="info")
    async def events_info(self, ctx: commands.Context):
        """Show your current score in this season."""

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

    @events.command(name="leaderboard")
    async def events_leaderboard(
        self, ctx: commands.Context, event: discord.TextChannel = None
    ):
        """
        Show the season leaderboard.

        If a channel is provided, show that event's leaderboard instead.
        """

        if event:
            user_points = self.event_manager.get_event_leaderboard(event.id)
            if user_points is None:
                # channel not registered for events
                await ctx.react_quietly("🚷")
                return
            title = event.name
        else:
            season, user_points = self.event_manager.get_season_leaderboard(
                ctx.guild.id
            )
            title = season["name"]

        desc = []
        place = 1
        for user, points in user_points.items():
            plural = "point" if points == 1 else "points"
            desc.append(f"**{place}.** <@{user}>: {points} {plural}")
            place += 1

        embed = discord.Embed(
            title=f"Leaderboard - {title}",
            description="\n".join(desc),
        )
        mentions = discord.AllowedMentions(users=False)
        await ctx.send(embed=embed, allowed_mentions=mentions)

    @commands.admin()
    @events.command(name="confchannel")
    async def events_configure_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        point_value: int = 1,
    ):
        """
        Configure a channel to be tracked in the current season.

        If the channel is already tracked, use this command to update the point value.
        Scores will be re-calculated.

        Set to 0 to remove a channel from the season. If you re-add a channel later, or add a channel after 🧩 reactions were already added, use the `rescan` command to update scores.

        The default point value is 1.
        """

        self.event_manager.configure_channel(channel, point_value)
        await ctx.tick()

    @events.command(name="channels")
    async def events_channels(self, ctx: commands.Context):
        """Show all events in the current season."""

        season, channels = self.event_manager.get_season_channels(ctx)

        desc = []
        for channel in channels:
            points = channel["point_value"]
            plural = "point" if points == 1 else "points"
            desc.append(f"<#{channel['channel_id']}>: {points} {plural} per submission")

        embed = discord.Embed(
            title=f"{season['name']} channels", description="\n".join(desc)
        )
        await ctx.send(embed=embed)

    @commands.mod()
    @events.command(name="rescan")
    async def events_rescan(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
    ):
        """
        Scan a channel for reactions and update scores.

        You usually shouldn't need to do this. But if you deleted messages, or the bot was offline
        when reacting, you can run this to clear out points for a channel and re-calculate.
        """

        async def rescan_handler(message):
            if await self.has_mod_reacts(message):
                self.event_manager.add_point(message)

        await ctx.send(
            f"Scanning <#{channel.id}> for event data, this may take a while..."
        )
        self.event_manager.clear_channel_points(channel)

        self.event_manager.rescan_channel(ctx, channel, rescan_handler)

    @commands.admin()
    @events.command(name="debug")
    async def events_debug(self, ctx: commands.Context):
        msg = chat_formatting.box(pformat(self.event_manager.debug()), "python")
        await ctx.send(msg)
