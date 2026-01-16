import discord
import vt

from discord import ui
from .classes import Ticket
from .error_handling import send_blocked, send_error, send_success

def parse_id(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip("'\""))
    except ValueError:
        return None

# -- Views/LayoutViews -- #
class TicketInfo(ui.LayoutView):
    def __init__(self, author: discord.Member | discord.User, title: str, description: str):
        self.author = author
        self.title = title
        self.description = description

        container = ui.Container(
            ui.Section(
                ui.TextDisplay(content=f"## 🛈 Request Information"),
                ui.TextDisplay(content=f"{self.title}\n\n"),
                ui.TextDisplay(content=f"{self.description}"),
                ui.TextDisplay(content=f"-# Thank you for contacting us. A member of our staff team will get to you shortly."),
                accessory=discord.ui.Thumbnail(media="https://cdn.rxtnshi.xyz/u/8bnPxj.gif")
            ),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay(content=f"# Action Center"),
            ui.ActionRow(UploadFile()),
        )

        self.add_item(container)

class LogInfo(ui.LayoutView):
    def __init__(self, author: discord.Member | discord.User, title: str, description: str, ticket_guild: discord.Guild, ticket_channel: discord.TextChannel):
        self.author = author
        self.title = title
        self.description = description
        self.guild = ticket_guild
        self.channel = ticket_channel

        container = ui.Container(
            ui.Section(
                ui.TextDisplay(f"## 🚨 New Support Request!"),
                ui.TextDisplay(content=f"{self.title}\n\n"),
                ui.TextDisplay(content=f"{self.description}"),
                accessory=discord.ui.Thumbnail(media="https://cdn.rxtnshi.xyz/u/5775-applicationpending-ids.png")
            ),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.ActionRow(
                ui.Button(
                    label="Access Ticket",
                    style=discord.ButtonStyle.link(),
                    url=f"https://discord.com/channels/{self.guild}/{self.channel}/",
                )
            )
        )

        self.add_item(container)

class AppealPanel(ui.LayoutView):
    def __init__(self, user: discord.Member):
        pass

class SupportPanel(ui.LayoutView):
    def __init__(self, guild: discord.Guild, guidelines: str):
        self.guild = guild
        self.guidelines = guidelines

        container = ui.Container(
            ui.Section(
                ui.TextDisplay(content=f"### ❓ {self.guild}'s Support Center"),
                ui.TextDisplay(content=f"# Guidelines\n{self.guidelines}"),
                accessory=ui.Thumbnail(media="https://cdn.rxtnshi.xyz/u/559950-clipboard.png"),
            ),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay("# Open a Support Request Here!"),
            ui.TextDisplay("-# Disclaimer: Please allow some ample time for server staff to respond to your query."),
            ui.ActionRow(TicketSelectMenu())
        )

        self.add_item(container)

class SettingsPanel(ui.LayoutView):
    def __init__(self):
        pass

class Receipt(ui.LayoutView):
    def __init__(self, file: discord.File):
        pass

class LogsReceipt(ui.LayoutView):
    def __init__(self, file: discord.File):
        pass

# -- Modals -- #
class TicketQuestionaire(ui.Modal):
    def __init__(self, ticket_type, category, team_id):
        super().__init__(title=f"✍️ Opening a Request", timeout=None)
        self.ticket_type = ticket_type
        self.category = category
        self.team_id = team_id

        self.title = ui.Label(
            text="Request Title",
            description="In short, how can we help you today?",
            component=ui.TextInput(
                placeholder="I need help!",
                max_length=40,
                style=discord.TextStyle.short,
                required=True
            )
        )

        self.description = ui.Label(
            text="Request Description",
            description="Describe your request in a few sentences or so.",
            component=ui.TextInput(
                placeholder="I need help with something!",
                max_length=2000,
                style=discord.TextStyle.paragraph,
                required=True
            )
        )

        self.add_item(self.title)
        self.add_item(self.description)

    async def on_submit(self, interaction):
        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)
        channels = await confg.ticket_channels()
        log_channel_id = channels.get("log_channel")
        log_channel = interaction.guild.get_channel(log_channel_id)

        title = self.title.component.value
        description = self.description.component.value

        ticket = Ticket(self.ticket_type, title, description, self.team_id)
        await ticket.create_ticket(interaction)

class TicketSelectMenu(ui.Select):
    def __init__(self, categories: list[dict]):
        self.map = {c["name"].replace(" ", "-").lower(): c for c in categories}

        options = [
            discord.SelectOption(
                label=c["name"],
                value=c["name"].replace(" ", "-").lower(),
                description=c.get("description" or "No description")
            )
            for c in categories
        ]

        super().__init__(
            placeholder="Select a Category",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        result = self.map.get(self.values[0])
        modal = TicketQuestionaire(result)

        await interaction.send_modal(modal)

class FileUploadAnalysisModal(ui.Modal):
    def __init__(self, scans_enabled: bool):
        super().__init__(title="File Uploads", timeout=None)

        if scans_enabled:
            self.file_upload = ui.Label(
                text = "Upload Your File",
                description = "This file will be analyzed by VirusTotal before being uploaded to the ticket.",
                component= ui.FileUpload(
                    max_values = 1,
                    custom_id = "file-upload-object",
                    required = False
                )
            )
        else:
            self.file_upload = ui.Label(
                text = "Upload Your File",
                description = "Your file will be uploaded to this channel.",
                component= ui.FileUpload(
                    max_values = 1,
                    custom_id = "file-upload-object",
                    required = False
                )
            )

        self.add_item(self.file_upload)

    async def on_submit(self, interaction):
        file = self.file_upload.component.values

        if file:
            pass

class CloseTicketQuestionaire(ui.Modal):
    def __init__(self, channel: discord.Channel):
        super().__init__(title=f"🔒 Closing Ticket")

        self.channel = channel
        self.reason = ui.Label(
            text="Why are you closing this ticket?",
            description=f"You are closing {self.channel.name}. Please give a reason why otherwise no reason will be given.",
            component=ui.TextInput(
                label="Enter a reason",
                style=discord.TextStyle.paragraph,
                required=True
            )
        )

        self.add_item(self.reason)

    async def on_submit(self, interaction):
        reason = self.reason.component.value
        await Ticket.close_ticket(self, interaction, reason)

# -- Buttons -- #
class UploadFile(ui.Button):
    def __init__(self):
        super().__init__(label="📂 Upload a File", style=discord.ButtonStyle.green, custom_id="upload-file-button")

    async def callback(self, interaction):
        await interaction.send_modal(FileUploadAnalysisModal())

class CloseTicket(ui.Button):
    def __init__(self):
        super().__init__(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id="close-ticket-button")

    async def callback(self, interaction):
        await interaction.send_modal(FileUploadAnalysisModal())
        
class ConfigRoles(ui.Button):
    def __init__(self):
        super().__init__(label="⚙️ Configure Roles", style=discord.ButtonStyle.primary, custom_id="config-roles-button")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("tickets")
        if not cog:
            await send_error(interaction, "TicketSystem not loaded.", True)
            return
        
        await interaction.response.send_modal(SetupChannelsModal(interaction.message))

        message = await interaction.original_response()
        view = discord.ui.View.from_message(message)
        view.message = message

class ConfigChannels(ui.Button):
    def __init__(self):
        super().__init__(label="⚙️ Configure Channels", style=discord.ButtonStyle.primary, custom_id="config-roles-button")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("tickets")
        if not cog:
            await send_error(interaction, "TicketSystem not loaded.", True)
            return
        
        await interaction.response.send_modal(SetupChannelsModal(interaction.message))

        message = await interaction.original_response()
        view = discord.ui.View.from_message(message)
        view.message = message