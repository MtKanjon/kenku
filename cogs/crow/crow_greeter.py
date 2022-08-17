from typing import List
import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.utils.predicates import MessagePredicate

# pyright: reportGeneralTypeIssues=false


class CrowGreeter:
    bot: Red
    config: Config

    @commands.admin()
    @commands.group()
    async def greeter(self, ctx: commands.Context):
        """
        Configure welcome messages and images.
        """

        defaults = {
            "message": "Welcome $USER to our server!",
            "channel": 0,
            "images": [],
            "next_image": 0,
        }
        self.config.register_guild(greeter=defaults)

    @commands.admin()
    @greeter.command(name="config")
    async def greeter_config(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
    ):
        """Set up a greeting channel."""

        await ctx.reply(
            f"Configuring channel <#{channel.id}> to be used for new member greetings. You can enter a greeting message that will be sent when someone joins the server. Use `$USER` to mention them. For example, 'Welcome $USER to our server!'.\n"
            + "Enter your greeting message now (or type `cancel`):"
        )

        message: discord.Message = await self.bot.wait_for(
            "message", check=MessagePredicate.same_context(ctx)
        )

        config = self.config.guild(ctx.guild)
        await config.greeter.message.set(message.content)
        await config.greeter.channel.set(channel.id)

        await ctx.reply(
            "Done! To change the message, run this command again, or use other greeter commands to further customize the greeting (like adding images)."
        )

    @commands.admin()
    @greeter.command(name="banneradd")
    async def greeter_add_banner(
        self,
        ctx: commands.Context,
        url: str,
    ):
        """Add a banner image to the greeter rotation."""

        config = self.config.guild(ctx.guild)
        async with config.greeter.images() as images:
            images.append(url)
        await ctx.react_quietly("✅")

    @commands.admin()
    @greeter.command(name="bannerlist")
    async def greeter_list_banner(
        self,
        ctx: commands.Context,
    ):
        """List all active banner images."""

        config = self.config.guild(ctx.guild)
        images = await config.greeter.images()
        image_text = [f"<{i}>" for i in images]
        images = "\n".join(image_text)
        await ctx.reply(images)

    @commands.admin()
    @greeter.command(name="bannerremove")
    async def greeter_remove_banner(
        self,
        ctx: commands.Context,
        url: str,
    ):
        """Remove a banner image from the greeter rotation."""

        config = self.config.guild(ctx.guild)
        async with config.greeter.images() as images:
            images.remove(url)
        await ctx.react_quietly("✅")

    @greeter.command(name="test")
    async def greeter_test(self, ctx: commands.Context):
        await self.greeter_member_joined(ctx.author)

    @commands.Cog.listener("on_member_update")
    async def greeter_member_verified(self, before: discord.Member, after: discord.Member):
        # we don't use on_member_joined because that'll trigger immediately on join, where we want
        # people to "complete a few more steps before you can start talking" and get verified
        # first. so wait for pending state to change to False
        print(before, before.pending, after, after.pending)
        if before.pending == after.pending:
            return
        if after.pending:
            return
        member = after

        config = self.config.guild(member.guild)
        message = await config.greeter.message()
        channel_id = await config.greeter.channel()

        if channel_id == 0:
            return

        channel: discord.TextChannel = member.guild.get_channel(channel_id)
        formatted = message.replace("$USER", f"<@{member.id}>")

        image_url = await self._greeter_next_image(member.guild)

        embed = discord.Embed(
            description=formatted,
        )
        embed.set_image(url=image_url)
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.all())

    async def _greeter_next_image(self, guild: discord.Guild):
        config = self.config.guild(guild)
        images: List[str] = await config.greeter.images()
        index: int = await config.greeter.next_image()

        # wrap around at the start, instead of afterwards, so we can still show images recently
        # added at the end (if the pointer was already at the end)
        if index >= len(images):
            index = 0
        url = images[index]

        await config.greeter.next_image.set(index + 1)

        return url
