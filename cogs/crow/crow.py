from io import BytesIO

import discord

from PIL import Image
from redbot.core import commands

class Crow(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    WIDE_HEIGHT = 48
    WIDE_WIDTH_MUL = 3

    @commands.command()
    async def wide(self, ctx, emoji: discord.PartialEmoji):
        emoji_data = BytesIO(await emoji.url.read())

        resized_file = BytesIO()
        with Image.open(emoji_data) as img:
            img_resized = img.resize((self.WIDE_HEIGHT * self.WIDE_WIDTH_MUL, self.WIDE_HEIGHT))
            img_png = img_resized.save(resized_file, format="PNG")

        resized_file.seek(0)
        file = discord.File(resized_file, filename=f"{emoji.name}_wide.png")
        sent = await ctx.send(file=file)

