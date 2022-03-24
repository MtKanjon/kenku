from io import BytesIO

import discord

from PIL import Image
from redbot.core import commands

WIDE_HEIGHT = 48

class Crow(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def wide(self, ctx, emoji: discord.PartialEmoji, size: int = 3):
        if size < 2 or size > 10:
            await ctx.react_quietly("🚷")
            return

        emoji_data = BytesIO(await emoji.url.read())
        resized_file = self.resize_image(emoji_data, WIDE_HEIGHT * size, WIDE_HEIGHT)
        file = discord.File(resized_file, filename=f"{emoji.name}_wide.png")
        sent = await ctx.send(file=file)
    
    def resize_image(self, image_data: BytesIO, width: int, height: int):
        out = BytesIO()
        with Image.open(image_data) as img:
            resized = img.resize((width, height))
            resized.save(out, format="PNG")
        out.seek(0)
        return out

