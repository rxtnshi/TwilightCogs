from .TwilightTickets import TwilightTickets
from . import ViewsModals

async def setup(bot):
    await bot.add_cog(TwilightTickets(bot))
    
    
    