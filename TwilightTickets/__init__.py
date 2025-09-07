from .TwilightTickets import SchizoTickets

async def setup(bot):
    await bot.add_cog(TwilightTickets(bot))