from .TwilightTickets import TwilightTickets
from . import ViewsModals

async def setup(bot):
    await bot.add_cog(TwilightTickets(bot))

async def setup_hook(bot):
    cog = bot.get_cog("TwilightTickets")

    bot.add_view(ViewsModals.TicketView())
    bot.add_view(ViewsModals.CloseTicketView())
    bot.add_view(ViewsModals.AppealView())
    
    cog.ticket_statuses = await cog.config.get_raw("tickets_enabled")
	cog.tickets_enabled = await cog.config.get_raw("ticket_statuses")
