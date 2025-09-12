from .TwilightTickets import TwilightTickets
from . import ViewsModals

async def setup(bot):
    cog = TwilightTickets(bot)
    await bot.add_cog(cog)

    bot.add_view(ViewsModals.TicketView())
    bot.add_view(ViewsModals.CloseTicketView())
    bot.add_view(ViewsModals.AppealView())
