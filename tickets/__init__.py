from .main import tickets
from datetime import datetime

async def setup(bot):
    cog = tickets(bot)

    cog.log.info(f"Cog initialized at {datetime.now()}")
    await cog.db.initialize()
    await bot.add_cog(cog)