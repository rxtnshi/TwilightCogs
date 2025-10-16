from .QOTD import QOTD

async def setup(bot):
    await bot.add_cog(QOTD(bot))