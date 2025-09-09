from .TwilightTickets import TwilightTickets
from . import ViewsModals

async def setup(bot):
    await bot.add_cog(TwilightTickets(bot))

async def setup_hook(bot):
    await bot.add_view(ViewsModals.CloseTicketView())
    await bot.add_view(ViewsModals.TicketView())
    await bot.add_view(ViewsModals.AppealView())
    print("views added successfully")