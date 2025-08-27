from .reaperstatisticcog import ReaperStatisticCog


def setup(bot):
    bot.add_cog(ReaperStatisticCog(bot))