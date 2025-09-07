import discord
import datetime
import io

from datetime import datetime
from discord import app_commands, utils
from discord.ext import commands

async def create_ticket(
    interaction,
    ticket_type: str,
    report_name: str,
    request_description: str,
    category_id: int,
    staff_role_id: int,
    embed_color: int
):
    guild = interaction.guild
    user = interaction.user

    category = discord.utils.get(guild.categories, id=category_id)
    if category is None:
        await interaction.response.send_message("Cannot open a ticket right now.", ephemeral=True)
        return

    channel_name = f"{user}-{ticket_type.lower()}-report"
    existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
    if existing_channel:
        await interaction.response.send_message(f"You already have an active ticket open. {existing_channel.mention}", ephemeral=True)
        return

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True),
        discord.utils.get(guild.roles, id=staff_role_id): discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
    }

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites
        topic=f"Ticket opener: {user.id}"
    )

    embed = discord.Embed(
        title=f"📋 {ticket_type} Ticket Submitted",
        description=f"{user.mention} submitted a ticket.",
        color=embed_color,
        timestamp=datetime.now()
    )
    embed.add_field(name="Description:", value=request_description, inline=False)
    embed.add_field(name="Reported User:", value=report_name, inline=False)

    await channel.send(embed=embed)
    await interaction.response.send_message(f"✅ Ticket opened! Access it at {channel.mention}", ephemeral=True)

async def create_transcript(channel, user, logs_channel):
    transcript = f"Transcript for ticket channel: {channel.mention}"
    transcript += f"Closed by: {user}\n"
    transcript += "-" * 40 + "\n"

    async for msg in channel.history(limit=None, oldest_first=True):
        time = msg.created_at.strftime("%Y-%m-%d %H:%M")
        content = msg.content if msg.content else "[Embed/Attachment]"
        transcript += f"[{time}] {msg.author}: {content}\n"
    
    user_embed = discord.Embed(
        title=f"📋 Ticket Transcript",
        description="Thank you for opening a ticket with us. Your ticket transcript is attached below.",
        color=0x00FF00,
        timestamp=datetime.now()
    )
    user_embed.add_field(name="Opened by:", value="", inline=False)
    user_embed.add_field(name="Closed by:", value="", inline=False)
    

    logs_channel_embed = discord.Embed(
        title=f"📋 Ticket Transcript",
        description=f"Ticket log for {channel.mention}",
        color=0x00FF00,
        timestamp=datetime.now()
    )
    logs_channel_embed.add_field(name="Opened by:", value="", inline=False)
    logs_channel_embed.add_field(name="Closed by:", value="", inline=False)

    file = discord.File(io.StringIO(transcript), filename=f"transcript.txt")

    try:
        await user.send(embed=user_embed, file=file)
    except discord.Forbidden:
        await logs_channel.send(f"Unable to send transcript for {channel.mention}. This may be due to their direct messages turned off.", embed=logs_channel_embed, file=file)
    
class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="⚠️ Discord Staff", description="Contact Discord staff"),
            discord.SelectOption(label="🎮 Game Staff", description="Contact SCP:SL staff")
        ]

        super().__init__(placeholder="Select a category...", options=options)

    async def callback(self, interaction = discord.Interaction):
        if self.values[0] == "⚠️ Discord Staff":
            modal = DiscordModal()
        elif self.values[0] == "🎮 Game Staff":
            # modal = GameModal()
            await interaction.response.send_message("This option is currently disabled.")

        await interaction.response.send_modal(modal)
        await interaction.message.edit(view=TicketView())

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

class CloseTicket(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Close Ticket", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        channel = interaction.channel
        closing_user = interaction.user

        opening_user = None
        if channel.topic and "Ticket opener:" in channel.topic:
            opening_user = int(channel.topic.split("Ticket opener:")[1].strip())
        opener = channel.guild.get_member(opening_user) if opening_user else None

        await create_transcript(channel, opener or closing_user, self.logs_channel, closed_by=closer)
        await interaction.response.send_message("Closing ticket...", ephemeral=True)
        await interaction.channel.delete()

class DiscordModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Discord Help Request", timeout=None)
        self.discord_report_name = discord.ui.TextInput(label="What is your issue?", required=True, style=discord.TextStyle.short)
        self.discord_request = discord.ui.TextInput(label="Describe the issue", required=True, style=discord.TextStyle.paragraph)
        self.add_item(self.discord_report_name)
        self.add_item(self.discord_request)

    async def on_submit(self, interaction: discord.Interaction):
        await create_ticket(
            interaction,
            ticket_type="Discord",
            report_name=self.discord_report_name.value,
            request_description=self.discord_request.value,
            category_name="Support",
            staff_role_id=1009509393609535548, #set whenever testing or when active
            embed_color=0xFF5733
        )

class GameModal(discord.ui.Modal):
    async def on_submit(self, interaction: discord.Interaction):
        await create_ticket(
            interaction,
            ticket_type="SCP:SL",
            report_name=self.game_report_name.value,
            request_description=self.game_request.value,
            category_name="Game Support",
            staff_role_id=1009509393609535548, #set whenever testing or when active
            embed_color=0x3498db
        )