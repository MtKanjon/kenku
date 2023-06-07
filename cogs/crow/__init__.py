from .crow import Crow


async def setup(bot):
    await bot.add_cog(Crow(bot))
