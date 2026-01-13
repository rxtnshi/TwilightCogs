import discord

from discord import ui
from .databases import TicketCategory, CreateTicket

class TicketPanel(ui.LayoutView):
    def __init__(self, author: discord.Member | discord.User):
        self.author = author
        self.description = f"{self.author.mention}"

        container = ui.Container(
            ui.TextDisplay(content=f"## 📝 New Request Submitted!"),
            ui.TextDisplay(content=f"{self.author.mention} submitted a support request. A member of our staff team will get to you shortly."),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),

        )



class AppealPanel(ui.LayoutView):
    pass

class NewTicket(ui.LayoutView):
    pass

class OpenTicketModal(ui.Modal):
    pass