from .Giveaways import Giveaways
from .ViewsModals import GiveawayView

async def setup(bot):
    cog = Giveaways(bot)
    await bot.add_cog(cog)

    bot.add_view(GiveawayView())