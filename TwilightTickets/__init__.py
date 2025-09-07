from .TwilightTickets import TwilightTickets

async def setup(bot):
    await bot.add_cog(TwilightTickets(bot))