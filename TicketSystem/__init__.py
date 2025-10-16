from .TicketSystem import TicketSystem
from . import ViewsModals

async def setup(bot):
    cog = TicketSystem(bot)
    await bot.add_cog(cog)

    bot.add_view(ViewsModals.TicketView())
    bot.add_view(ViewsModals.CloseTicketView())
    bot.add_view(ViewsModals.AppealView())
