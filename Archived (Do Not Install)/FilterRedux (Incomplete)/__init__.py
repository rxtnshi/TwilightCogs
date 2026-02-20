from .FilterRedux import FilterRedux

async def setup(bot):
    cog = FilterRedux(bot)
    await bot.add_cog(cog)