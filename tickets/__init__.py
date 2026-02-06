from . import views
from .main import tickets
from datetime import datetime

async def setup(bot):
    cog = tickets(bot)

    cog.log.info(f"Cog initialized at {datetime.now()}")
    await cog.db.initialize()
    await bot.add_cog(cog)

    bot.add_view(views.SupportPanel())
    bot.add_view(views.AppealPanel())
    bot.add_view(views.Receipt())
    bot.add_view(views.LogsReceipt())
    bot.add_view(views.LogInfo())