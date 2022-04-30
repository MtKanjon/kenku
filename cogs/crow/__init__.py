from .crow import Crow


def setup(bot):
    bot.add_cog(Crow(bot))
