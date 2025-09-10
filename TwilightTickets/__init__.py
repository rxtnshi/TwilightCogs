from .TwilightTickets import TwilightTickets
from . import ViewsModals

async def setup(bot):
    await bot.add_cog(TwilightTickets(bot))

async def setup_hook(bot):
    await bot.wait_until_ready()
    bot.add_view(ViewsModals.TicketView())
    bot.add_view(ViewsModals.CloseTicketView())
    bot.add_view(ViewsModals.AppealView())

    cog = bot.get_cog("TwilightTickets")
    if not cog:
        return
    
    guild = cog.bot.get_guild(1341956884059521025)
    if guild:
        cog.tickets_enabled = await cog.config.guild(guild).tickets_enabled()
        cog.ticket_statuses = await cog.config.guild(guild).ticket_statuses()