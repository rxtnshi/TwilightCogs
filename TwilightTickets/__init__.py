from .TwilightTickets import TwilightTickets
from . import ViewsModals

async def setup(bot):
    await bot.add_cog(TwilightTickets(bot))

async def setup_hook(bot):
    await bot.wait_until_ready()
    cog = bot.get_cog("TwilightTickets")
    guild = bot.get_guild(1341956884059521025)

    cog.tickets_enabled = await cog.config.guild(guild).tickets_enabled()
    cog.tickets_statuses = await cog.config.guild(guild).ticket_statuses()

    bot.add_view(ViewsModals.TicketView())
    bot.add_view(ViewsModals.CloseTicketView())
    bot.add_view(ViewsModals.AppealView())

    
