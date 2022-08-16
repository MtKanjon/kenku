from io import BytesIO
from math import floor

import discord
from PIL import Image
from redbot.core import commands

WIDE_HEIGHT = 48


class CrowWide:
    @commands.command()
    async def wide(
        self,
        ctx: commands.Context,
        emoji: discord.PartialEmoji,
        size: float = 3,
        channel: discord.TextChannel = None,
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

        if channel:
            await channel.send(file=file)
        else:
            await ctx.send(file=file)

    def _resize_image(self, image_data: BytesIO, width: int, height: int):
        out = BytesIO()
        with Image.open(image_data) as img:
            resized = img.resize((width, height))
            resized.save(out, format="PNG")
        out.seek(0)
        return out
