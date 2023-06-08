import datetime
import io
from typing import Iterator, Optional, Union, cast

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils import menus

from .events import EventManager, EventError

EVENT_EMOJIS = {"🧩": 1, "🍒": 2, "🚥": 3}


class CrowEvents(commands.Cog):
    bot: Red

    def _init_event_manager(self):
        # initialize the event manager lazily, so bugs don't crash startup
        if hasattr(self, "event_manager") and self.event_manager:
            return
        self.event_manager = EventManager(cast(commands.Cog, self))

    @commands.group()
    async def events(self, ctx: commands.Context):
        """
        Event leaderboard and point tracking commands.

        Leaderboards are calculated by adding up points for all members participating in an event. To create an event, use the `setup` command to tell the bot to monitor the event's channel. Then, react to messages with the 🧩 emoji. Any message with a 🧩 react will be counted for that event's score for that person, and can be applied by any mod/admin. The bot will react with 🧩 as an acknowledgement.

        By default, each 🧩 react earns the member 1 point, but each message only counts once, no matter how many people react. To change the point value, use `setup`. Higher point values may be useful for events that require more participation.

        If you need to count _more than one point_ for a message, you can use these reactions in any combination. They'll be added up:

        - 🧩 1 point
        - 🍒 2 points
        - 🚥 3 points

        This bot also tracks seasons of events, however the capability to configure seasons is not yet supported. All events/channels and leaderboards will fall under "Season 1" for now.
        """

    @commands.Cog.listener("on_raw_reaction_add")
    async def event_react_added(self, payload: discord.RawReactionActionEvent):
        self._init_event_manager()
        if not await self.should_handle_react(payload):
            return

        channel = cast(discord.TextChannel, self.bot.get_channel(payload.channel_id))
        partial = discord.PartialMessage(channel=channel, id=payload.message_id)
        message: discord.Message = await partial.fetch()

        # count the mod reacts and add them up
        score, _emojis = await self.score_mod_reacts(message)
        added = self.event_manager.set_points(message, score)

        if added:
            await message.add_reaction(payload.emoji)

    @commands.Cog.listener("on_raw_reaction_remove")
    async def event_react_removed(self, payload: discord.RawReactionActionEvent):
        self._init_event_manager()
        if not await self.should_handle_react(payload):
            return

        channel = cast(discord.TextChannel, self.bot.get_channel(payload.channel_id))
        partial = discord.PartialMessage(channel=channel, id=payload.message_id)
        message: discord.Message = await partial.fetch()

        # count the mod reacts and add them up
        score, emojis = await self.score_mod_reacts(message)
        self.event_manager.set_points(message, score)

        # if there no more mod reacts on this emoji, remove it
        if payload.emoji.name not in emojis:
            await message.remove_reaction(
                payload.emoji, cast(discord.Member, self.bot.user)
            )

    async def should_handle_react(self, payload: discord.RawReactionActionEvent):
        # ignore ourselves
        assert self.bot.user
        if payload.user_id == self.bot.user.id:
            return False

        # make sure it's actually an event reaction
        if not self.is_event_react(payload.emoji):
            return False

        # member is empty on reaction removals, so look it up
        member = payload.member
        if not member:
            guild = self.bot.get_guild(cast(int, payload.guild_id))
            assert guild
            member = guild.get_member(payload.user_id)
            assert member

        # check if the person un/reacting is a mod
        if not await self.bot.is_mod(member):
            return False

        return True

    def is_event_react(self, emoji: Union[str, discord.PartialEmoji, discord.Emoji]):
        if emoji in EVENT_EMOJIS:
            return True
        if isinstance(emoji, str):
            return False
        try:
            return emoji.name in EVENT_EMOJIS
        except AttributeError:
            return False

    async def score_mod_reacts(self, message: discord.Message):
        """Check if a message has any mod event reactions."""

        # find the reaction
        reactions: Iterator[discord.Reaction] = filter(
            lambda r: self.is_event_react(r.emoji), message.reactions
        )

        multiplier = 0
        emojis: set[str] = set()
        for reaction in reactions:
            # async loop reacting users to find mods
            async for user in reaction.users():
                if await self.bot.is_mod(cast(discord.Member, user)):
                    emoji = cast(str, reaction.emoji)
                    multiplier += EVENT_EMOJIS[emoji]
                    emojis.add(emoji)
                    break
        return multiplier, emojis

    @events.command(name="info")
    async def events_info(
        self,
        ctx: commands.Context,
        event: Optional[discord.TextChannel] = None,
        user: Union[discord.User, discord.Member, None] = None,
    ):
        """
        Show your current score in this season.

        If a channel/event name is provided, show a breakdown of your scores for that event.
        """

        # channel breakdown
        if event:
            user = user if user else ctx.message.author
            event_points, event_adj = self.event_manager.user_event_info(user, event)
            desc = []
            for point in event_points:
                score = point["point_value"] * point["multiplier"]
                url = event.get_partial_message(point["message_id"]).jump_url
                sent_at = int(
                    datetime.datetime.fromisoformat(point["sent_at"]).timestamp()
                )
                desc.append(f"[{plural(score)}]({url}) on <t:{sent_at}>")
            for adj in event_adj:
                amount = adj["adjustment"]
                desc.append(f"{plural(amount)} adjusted by staff")
            embed = discord.Embed(
                title=f"{user.name}#{user.discriminator}'s points in {event.name}",
                description="\n".join(desc),
            )
            await ctx.send(embed=embed)

        # general season scores
        else:
            author = cast(discord.Member, ctx.message.author)
            season, scores_by_channel = self.event_manager.user_info(author)
            desc = []
            total = 0
            for score in scores_by_channel:
                total += score["score"]
                desc.append(f"<#{score['channel_id']}>: {plural(score['score'])}")

            embed = discord.Embed(
                title=f"Your points - {season['name']}",
                description=f"__**Total:** {plural(total)}__\n\n" + "\n".join(desc),
            )
            await ctx.send(embed=embed)

    @events.command(name="leaderboard")
    async def events_leaderboard(
        self, ctx: commands.Context, event: Optional[discord.TextChannel] = None
    ):
        """
        Show the season leaderboard.

        If a channel is provided, show that event's leaderboard instead.
        """

        assert ctx.guild

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
        for user_id, points in user_points.items():
            user = await ctx.bot.get_or_fetch_user(user_id)
            desc.append(f"**{place}.** {user} <@{user_id}>: **{plural(points)}**")
            place += 1

        embed_pages = []
        for i in range(0, len(desc), 20):
            page_lines = desc[i : i + 20]
            embed_pages.append(
                discord.Embed(
                    title=f"Leaderboard - {title} - Page {len(embed_pages)+1}",
                    description="\n".join(page_lines),
                )
            )

        await menus.menu(
            ctx,
            embed_pages,
            controls=menus.DEFAULT_CONTROLS,
            message=None,  # type: ignore
            page=0,
            timeout=30.0,
        )

    @commands.admin()
    @events.command(name="setup")
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
            desc.append(f"<#{channel['channel_id']}>: {plural(points)} per submission")

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
            multiplier, _emojis = await self.score_mod_reacts(message)
            if multiplier > 0:
                self.event_manager.set_points(message, multiplier)

        await ctx.send(
            f"Scanning <#{channel.id}> for event data, this may take a while..."
        )
        self.event_manager.clear_channel_points(channel)

        self.event_manager.rescan_channel(ctx, channel, rescan_handler)

    @commands.admin()
    @events.command(name="adjust")
    async def events_adjust(self, ctx: commands.Context, channel: discord.TextChannel):
        """
        Manually adjust scores for an event.

        Provide a channel name and the bot will attach a CSV of manually adjusted scores for you to edit. If no adjustments have been made, it will send a sample. Edit this CSV, run the command again with it attached, and they will be saved.

        You do not need to know Discord user IDs when filling out the spreadsheet. Just fill out `user_name` with a Discord user tag and it'll try to figure it out. Then enter in a score adjustment (positive or negative), and an optional note for your own records.

        If you delete a row from the sheet, that adjustment will be removed.

        Adjusted scores are **not** affected by channel-set multipliers. They'll be added in as-is.
        """
        # replace scores
        if len(ctx.message.attachments) > 0:
            attachment: discord.Attachment = ctx.message.attachments[0]
            bytes = await attachment.read()
            readable = io.StringIO(bytes.decode(encoding="UTF-8"))

            try:
                await self.event_manager.replace_adjustments(ctx, channel.id, readable)
            except EventError as e:
                await ctx.send(str(e))
                return

            await ctx.send("Score adjustments updated.")
            return

        # otherwise, emit scores
        writable = io.StringIO()
        adjs = self.event_manager.get_adjustments(
            channel.id, writable, ctx.message.author
        )
        writable.seek(0)

        if len(adjs) == 0:
            content = "This event does not yet have any adjusted scores. I'm sending you a blank CSV with a sample score adjustment for yourself. "
        else:
            content = "Here are the existing score adjustments for this event."
        content += "\n\nPlease check the `help` for this command for the format and behavior. When you've made your edits, run this command again with your modified CSV attached."

        this_channel = cast(discord.TextChannel, ctx.channel)
        file = discord.File(writable, filename=f"{this_channel.name}_adjustments.csv")  # type: ignore
        await ctx.send(content, file=file)

    @commands.admin()
    @events.command(name="export")
    async def events_export(self, ctx: commands.Context):
        """
        Export all point data to a CSV file for safe-keeping.
        """

        assert ctx.guild

        writable = io.StringIO()
        self.event_manager.export_points(ctx.guild.id, writable)
        writable.seek(0)
        file = discord.File(writable, filename=f"{ctx.guild.id}_points.csv")  # type: ignore
        await ctx.send(file=file)


def plural(points: int):
    word = "point" if points == 1 else "points"
    return f"{points} {word}"
