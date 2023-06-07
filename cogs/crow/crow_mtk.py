from io import BytesIO
from math import floor
from typing import Optional, cast

import aiohttp
import discord
from PIL import Image
from redbot.core import commands, Config
from redbot.core.bot import Red


class CrowMtk(commands.Cog):
    bot: Red
    config: Config
    httpsession: aiohttp.ClientSession

    @commands.mod()
    @commands.group()
    async def mtk(self, ctx: commands.Context):
        """Kanjon's half-assed goodie bag"""

        self.config.register_user(exclaim={"image": "", "x": 0, "y": 0, "scale": 1.0})

    @mtk.command("exclaimset")  # type: ignore
    async def mtk_exclaim_set(
        self, ctx: commands.Context, image: str, x: int, y: int, scale: float
    ):
        """
        Configure a base image / sticker for your Discord account

        Supply a URL, and X, Y coordinates (from top left) for where
        the center of an emoji should go.
        """
        config = self.config.user(ctx.author)
        async with config.exclaim() as exclaim:
            exclaim["image"] = image
            exclaim["x"] = x
            exclaim["y"] = y
            exclaim["scale"] = scale
        await ctx.react_quietly("✅")

    @mtk.command(name="exclaim")  # type: ignore
    async def mtk_exclaim(
        self,
        ctx: commands.Context,
        emoji: discord.PartialEmoji,
        channel: discord.TextChannel,
    ):
        """
        Shout out an emoji on a sticker.

        Use `exclaimset` first! Otherwise this won't work.

        If webhooks were set up on a channel, will attempt to impersonate you.
        """
        config = self.config.user(ctx.author)
        exclaim = await config.exclaim()
        scale: float = exclaim["scale"]

        base_data = BytesIO(await self._mtk_fetch(exclaim["image"]))
        base_img = Image.open(base_data)

        emoji_data = BytesIO(await emoji.read())
        emoji_img = Image.open(emoji_data)
        emoji_resized = emoji_img.resize(
            (floor(emoji_img.width * scale), floor(emoji_img.height * scale))
        )

        box = (
            exclaim["x"] - emoji_resized.width // 2,
            exclaim["y"] - emoji_resized.height // 2,
        )
        base_img.alpha_composite(emoji_resized, box)

        out = BytesIO()
        base_img.save(out, format="PNG")
        out.seek(0)

        file = discord.File(out, filename=f"exclaim_{emoji.name}.png")

        webhook = await self._mtk_exclaim_webhook(channel)
        if webhook:
            author = cast(discord.Member, ctx.author)
            avatar_url = author.avatar.url if author.avatar else None
            await webhook.send(
                file=file,
                username=author.nick or author.name,
                avatar_url=avatar_url,
                wait=True,
            )
        else:
            await channel.send(file=file)

    @mtk.command(name="exclaimwebhook")  # type: ignore
    async def mtk_exclaim_webhook(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
    ):
        """
        Set up webhooks for a channel for impersonation

        Only needs to be set once per channel. If not set up, messages will show as being from the bot.
        """
        existing = await self._mtk_exclaim_webhook(channel)
        if existing:
            await ctx.reply("Webhook already exists for that channel.")
            return
        await channel.create_webhook(name="Kenku Disguise")
        await ctx.react_quietly("✅")

    async def _mtk_exclaim_webhook(
        self, channel: discord.TextChannel
    ) -> Optional[discord.Webhook]:
        try:
            for hook in await channel.webhooks():
                assert hook.user
                assert self.bot.user
                if hook.user.id == self.bot.user.id:
                    return hook
        except discord.Forbidden:
            return None

    async def _mtk_fetch(self, url):
        async with self.httpsession.get(url) as response:
            return await response.read()
