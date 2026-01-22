import discord

from discord import ui
from .helpers import Ticket
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
                accessory=discord.ui.Thumbnail(media="https://cdn.rxtnshi.xyz/u/clipboard.png")
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
    def __init__(self, user: discord.Member, moderated_account: str):
        self.user = user
        
        container = ui.Container(
            ui.Section(
                ui.TextDisplay("## 🚨 New Support Request!")
            ),
        )

        self.add_item(container)

    async def update_status(accepted: bool):
        pass

class SupportPanel(ui.LayoutView):
    def __init__(self, guild: discord.Guild, guidelines: str):
        self.guild = guild
        self.guidelines = guidelines

        container = ui.Container(
            ui.Section(
                ui.TextDisplay(content=f"### ❓ {self.guild}'s Support Center"),
                ui.TextDisplay(content=f"# Guidelines\n{self.guidelines}"),
                accessory=ui.Thumbnail(media="https://cdn.rxtnshi.xyz/u/clipboard.png"),
            ),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay("# Open a Support Request Here!"),
            ui.TextDisplay("-# Disclaimer: Please allow some ample time for server staff to respond to your query."),
            ui.ActionRow(TicketSelectMenu())
        )

        self.add_item(container)

class SettingsPanel(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=180)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user and interaction.user.id == self.author_id:
            return True
        else:
            await send_blocked(interaction, "Only the person who initiated this command can change the settings.", True)
   
    @classmethod
    async def get_settings(cls, cog, interaction: discord.Interaction):
        self = cls.__new__(cls)
        self.cog = cog
        self.data = data

        confg = cog.config.guild(interaction.guild)
        data = await confg.all()

        tickets_enabled = data.get("tickets_enabled")
        appeals_enabled = data.get("appeals_enabled")
        roles = data.get("tickets_roles")
        channels = data.get("ticket_channels")
        panel_cfg = data.get("panel_cfg")
        staff_roles = {}
        for role in roles["staff_roles"]:
            staff_roles.append(f"<@&{role}>")

        is_setup = False
        if all(not item for item in roles and channels and panel_cfg):
            is_setup = True
        else:
            is_setup = False

        ui.LayoutView.__init__(self)
        container = ui.Container(
            ui.Section(
                ui.TextDisplay("## ⚙️ Settings"),
                ui.TextDisplay("Here are your current settings for your server."),
                ui.TextDisplay("# Configuration Status"),
                ui.TextDisplay(f"`{"✅ Configured" if is_setup else "❌ Not fully configured"}`"),
                accessory="https://cdn.rxtnshi.xyz/raw/settings_cog.png"
            ),
            ui.TextDisplay("# __Ticket Statuses__"),
            ui.TextDisplay(
                f"`Tickets Creation`:\n{"✅ Enabled" if tickets_enabled is True else "❌ Disabled"}"
                f"`Appeals Enabled`:\n{"✅ Enabled" if appeals_enabled is True else "❌ Disabled"}"
            ),
            ui.TextDisplay("# __Configured Roles__"),
            ui.TextDisplay(
                f"`Standard access`:\n<@&{roles["modmail_access"] if roles["modmail_access"] else "None set"}>"
                f"`Management access`:\n<@&{roles["modmail_mgmt"] if roles["modmail_mgmt"] else "None set"}>"
                f"`Appeals access`:\n<@&{roles["appeals_access"] if roles["appeals_access"] else "None set"}>"
                f"`Staff Roles`:\n{staff_roles}"
            ),
            ui.TextDisplay("# __Configured Channels__"),
            ui.TextDisplay(
                f"`Ticket Logs`:\n<#{channels['log_channel']}>"
                f"`Appeals`:\n<#{channels["appeal_logs"]}>"
            ),
            ui.TextDisplay("# __Panel Channels__"),
            ui.TextDisplay(f"`Panel Channel`:\n<#{panel_cfg["channel"]}>"),
            ui.TextDisplay(f"`[Link to panel](https://discord.com/channels/{interaction.guild.id}/{panel_cfg["channel"]}/{panel_cfg["message_id"]}`" if panel_cfg["message_id"] else "No panel message set"),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.ActionRow(ConfigChannels(), ConfigRoles(), ConfigFileCheck(), AddCategories(), DelCategories())
        )
        self.add_item(container)
        return self     

class Receipt(ui.LayoutView):
    def __init__(self, file: discord.File, title: str, requester: discord.Member, closer: discord.Member, open_reason: str, close_reason: str, open_time: int, close_time: int):
        self.file = file
        self.title = title
        self.requester = requester
        self.closer = closer
        self.open_reason = open_reason
        self.close_reason = close_reason
        self.open_time = open_time
        self.close_time = close_time

        container = ui.Container(
            ui.Section(
                ui.TextDisplay(content=f"## 🗒️ Transcript for {self.title}"),
                ui.TextDisplay(content=f"Here is the transcript for `{self.title}`. The ticket information can be found below."),
                accessory=ui.Thumbnail(media="https://cdn.rxtnshi.xyz/u/clipboard.png"),
            ),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay(content="# Ticket Information"),
            ui.TextDisplay(content=f"**Requester**: {self.requester.mention} ({self.requester.id})"),
            ui.TextDisplay(content=f"**Closed By**: {self.closer.mention} ({self.closer.id})\n\n"),
            ui.TextDisplay(content=f"**Opened at**: <t:{self.open_reason}:F>"),
            ui.TextDisplay(content=f"**Closed at**: <t:{self.open_reason}:F>\n\n"),
            ui.TextDisplay(content=f"**Request Description**: {self.open_reason}"),
            ui.TextDisplay(content=f"**Close Reason**: {self.close_reason}"),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay("# View Transcript"),
            ui.MediaGallery(ui.MediaGalleryItem(file=self.file))
        )

        self.add_item(container)

class LogsReceipt(ui.LayoutView):
    def __init__(self, file: discord.File, title: str, requester: discord.Member, closer: discord.Member, open_reason: str, close_reason: str, open_time: int, close_time: int):
        self.file = file
        self.title = title
        self.requester = requester
        self.closer = closer
        self.open_reason = open_reason
        self.close_reason = close_reason
        self.open_time = open_time
        self.close_time = close_time

        container = ui.Container(
            ui.Section(
                ui.TextDisplay(content=f"## 🗒️ Transcript for {self.title}"),
                ui.TextDisplay(content=f"Here is the transcript for `{self.title}`. The ticket information can be found below."),
                accessory=ui.Thumbnail(media="https://cdn.rxtnshi.xyz/u/clipboard.png"),
            ),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay(content="# Ticket Information"),
            ui.TextDisplay(content=f"**Requester**: {self.requester.mention} ({self.requester.id})"),
            ui.TextDisplay(content=f"**Closed By**: {self.closer.mention} ({self.closer.id})\n\n"),
            ui.TextDisplay(content=f"**Opened at**: <t:{self.open_reason}:F>"),
            ui.TextDisplay(content=f"**Closed at**: <t:{self.open_reason}:F>\n\n"),
            ui.TextDisplay(content=f"**Request Description**: {self.open_reason}"),
            ui.TextDisplay(content=f"**Close Reason**: {self.close_reason}"),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay("# View Transcript"),
            ui.MediaGallery(ui.MediaGalleryItem(file=self.file))
        )

        self.add_item(container)

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
    def __init__(self, categories: list[dict], appeals_enabled: bool):
        self.map = {c["name"].replace(" ", "-").lower(): c for c in categories}

        options = [
            discord.SelectOption(
                label=c["name"],
                value=c["name"].replace(" ", "-").lower(),
                description=c.get("description" or "No description")
            )
            for c in categories
        ]

        if appeals_enabled:
            options.append(
                discord.SelectOption(
                    label="🔨 Appeals",
                    value="appeals",
                    description="Appeal a moderation here."
                )
            )
            self.map["appeal"] = {"name": "🔨 Appeals"}

        super().__init__(
            placeholder="Select a Category",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        result = self.map.get(self.values[0])
        modal = TicketQuestionaire(result)

        await interaction.response.send_modal(modal)

class FileUploadAnalysisModal(ui.Modal):
    def __init__(self, scans_enabled: bool):
        super().__init__(title="File Uploads", timeout=None)
        self.scans_enabled = scans_enabled

        if self.scans_enabled:
            self.file_upload = ui.Label(
                text = "Upload Your File",
                description = "This file will be analyzed by VirusTotal before being uploaded to the ticket.",
                component= ui.FileUpload(
                    min_values = 1,
                    custom_id = "file-upload-object",
                    required = False
                )
            )
        else:
            self.file_upload = ui.Label(
                text = "Upload Your File",
                description = "Your file will be uploaded to this channel.",
                component= ui.FileUpload(
                    min_values = 1,
                    custom_id = "file-upload-object",
                    required = False
                )
            )

        self.add_item(self.file_upload)

    async def on_submit(self, interaction: discord.Interaction):
        file = self.file_upload.component.values

        if self.scans_enabled:
            import vt
            pass
        else:
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
                default="No reason given.",
                style=discord.TextStyle.paragraph
            )
        )

        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason.component.value
        await Ticket.close_ticket(self, interaction, reason)

class OpenAppeal(ui.Modal):
    def __init__(self):
        super().__init__(title="Opening Appeal")

class AppealDecision(ui.Modal):
    def __init__(self, decision: str, appeal_id: str):
        super().__init__(title=f"{self.decision}ing Appeal {self.appeal_id}", timeout=None)
        self.decision = decision
        self.appeal_id = appeal_id

        self.prefined_reasons = ui.Label(
            text="Predefined Reasons",
            description="You can select a predefined reason or choose 'Custom Reason' for your own.",
            component=ui.Select(
                max_values=1,
                required=True,
                options=[
                    discord.SelectOption(
                        label="Evidence Supports Decision",
                        description="The evidence provided by the appealer supports this decision. - accept",
                        value="evidence-supports-decision"
                    ),
                    discord.SelectOption(
                        label="Lack of Evidence",
                        description="The evidence provided is not sufficient to make a decision - denial",
                        value="lack-of-evidence"
                    ),
                    discord.SelectOption(
                        label="Non-appealable Offense",
                        description="This offense is non-appealable - denial",
                        value="non-appealable"
                    ),
                    discord.SelectOption(
                        label="Custom Reason",
                        description="The evidence provided by the appealer supports this decision.",
                        value="custom-reason"
                    )
                ]
            )
        )

        self.reason = ui.Label(
            text="Custom Reason",
            description="Please provide any addition info or your own reason for this decision.",
            component=ui.TextInput(
                style=discord.TextStyle.paragraph(),
                min_length=10,
                required=False
            )
        )
        
        self.add_item(self.prefined_reasons)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        pass

class ConfigChannelsModal(ui.Modal):
    pass

class ConfigRolesModal(ui.Modal):
    pass

class AddCatModal(ui.Modal):
    pass

class DelCatModal(ui.Modal):
    pass

class ConfigFileCheckModal(ui.Modal):
    pass

# -- Buttons -- #
class UploadFile(ui.Button):
    def __init__(self):
        super().__init__(label="📂 Upload a File", style=discord.ButtonStyle.green, custom_id="upload-file-button")

    async def callback(self, interaction: discord.Interaction):
        await interaction.send_modal(FileUploadAnalysisModal())

class CloseTicket(ui.Button):
    def __init__(self):
        super().__init__(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id="close-ticket-button")

    async def callback(self, interaction: discord.Interaction):
        await interaction.send_modal(CloseTicketQuestionaire())
        
class ConfigRoles(ui.Button):
    def __init__(self):
        super().__init__(label="⚙️ Configure Roles", style=discord.ButtonStyle.primary, custom_id="config-roles-button")

    async def callback(self, interaction: discord.Interaction):
        await interaction.send_modal(ConfigRolesModal())

class ConfigChannels(ui.Button):
    def __init__(self):
        super().__init__(label="⚙️ Configure Channels", style=discord.ButtonStyle.primary, custom_id="config-roles-button")

    async def callback(self, interaction: discord.Interaction):
        await interaction.send_modal(ConfigChannelsModal())

class ConfigFileCheck(ui.Button):
    def __init__(self):
        super().__init__(label="⚙️ Configure File Checks", style=discord.ButtonStyle.primary, custom_id="config-vt-button")

    async def callback(self, interaction: discord.Interaction):
        await interaction.send_modal(ConfigFileCheckModal())

class AddCategories(ui.Button):
    def __init__(self):
        super().__init__(label="📲 Add Categories", style=discord.ButtonStyle.green, custom_id="add-catg-button")

    async def callback(self, interaction: discord.Interaction):
        await interaction.send_modal(AddCatModal())

class DelCategories(ui.Button):
    def __init__(self):
        super().__init__(label="❌ Delete Categories", style=discord.ButtonStyle.danger, custom_id="del-catg-button")

    async def callback(self, interaction: discord.Interaction):
        await interaction.send_modal(DelCatModal())

class AcceptAppeal(ui.Button):
    def __init__(self):
        super().__init__(label="✅ Accept Appeal", style=discord.ButtonStyle.green, custom_id="accept-appeal-button")