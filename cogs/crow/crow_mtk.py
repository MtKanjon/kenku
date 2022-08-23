from io import BytesIO
from math import floor
from urllib.request import urlopen

import discord
from PIL import Image
from redbot.core import commands, Config
from redbot.core.bot import Red


class CrowMtk:
    bot: Red
    config: Config

    @commands.is_owner()
    @commands.group()
    async def mtk(self, ctx: commands.Context):
        self.config.register_user(exclaim={"image": "", "x": 0, "y": 0})

    @mtk.command("exclaimset")
    async def mtk_exclaim_set(self, ctx: commands.Context, image: str, x: int, y: int):
        config = self.config.user(ctx.author)
        async with config.exclaim() as exclaim:
            exclaim["image"] = image
            exclaim["x"] = x
            exclaim["y"] = y
        await ctx.react_quietly("✅")

    @mtk.command(name="exclaim")
    async def mtk_exclaim(
        self,
        ctx: commands.Context,
        emoji: discord.PartialEmoji,
        channel: discord.TextChannel,
    ):
        config = self.config.user(ctx.author)
        exclaim = await config.exclaim()

        base_data = BytesIO(urlopen(exclaim["image"]).read())
        base_img = Image.open(base_data)

        emoji_data = BytesIO(await emoji.url.read())
        emoji_img = Image.open(emoji_data)

        box = (
            exclaim["x"] - emoji_img.width // 2,
            exclaim["y"] - emoji_img.height // 2,
        )
        base_img.alpha_composite(emoji_img, box)

        out = BytesIO()
        base_img.save(out, format="PNG")
        out.seek(0)

        file = discord.File(out, filename=f"exclaim_{emoji.name}.png")

        webhook = await self._mtk_exclaim_webhook(channel)
        if webhook:
            await webhook.send(
                file=file,
                username=ctx.author.nick or ctx.author.name,
                avatar_url=ctx.author.avatar_url,
                wait=True,
            )
        else:
            await channel.send(file=file)

    @mtk.command(name="exclaimwebhook")
    async def mtk_exclaim_webhook(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
    ):
        existing = await self._mtk_exclaim_webhook(channel)
        if existing:
            await ctx.reply("Webhook already exists for that channel.")
            return
        await channel.create_webhook(name="Kenku Disguise")
        await ctx.react_quietly("✅")

    async def _mtk_exclaim_webhook(
        self, channel: discord.TextChannel
    ) -> discord.Webhook:
        try:
            for hook in await channel.webhooks():
                if hook.user.id == self.bot.user.id:
                    return hook
        except discord.Forbidden:
            return None
