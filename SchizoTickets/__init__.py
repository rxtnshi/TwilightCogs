from .SchizoTickets import SchizoTickets


def setup(bot):
    bot.add_cog(SchizoTickets(bot))