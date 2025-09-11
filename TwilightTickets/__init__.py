from .TwilightTickets import TwilightTickets
from . import ViewsModals

async def setup(bot):
    await bot.add_cog(TwilightTickets(bot))

    

async def setup_hook(bot):
    cog = bot.get_cog("TwilightTickets")
    guild = bot.get_guild(1341956884059521025)

    bot.add_view(ViewsModals.TicketView())
    bot.add_view(ViewsModals.CloseTicketView())
    bot.add_view(ViewsModals.AppealView())
    
    cog.ticket_statuses = await cog.config.guild(guild).get_raw("ticket_statuses")
    cog.tickets_enabled = await cog.config.guild(guild).get_raw("tickets_enabled")