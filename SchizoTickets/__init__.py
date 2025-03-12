from .SchizoTickets import SchizoTickets


async def setup(bot):
    await bot.add_cog(SchizoTickets(bot))