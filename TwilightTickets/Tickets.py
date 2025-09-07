import discord
import datetime

from datetime import datetime
from discord import app_commands, utils
from discord.ext import commands

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
            modal = GameModal()

        await interaction.response.send_modal(modal)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

class DiscordModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Discord Help Request", timeout=None)
        self.discord_report_name = discord.ui.TextInput(label="Who are you reporting? If nobody, you can put 'NONE'.", required=True, style=discord.TextStyle.short)
        self.discord_request = discord.ui.TextInput(label="Describe the issue", required=True, style=discord.TextStyle.paragraph)
        self.add_item(self.discord_report_name)
        self.add_item(self.discord_request)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user

        ticket_category = "Support"
        category = discord.utils.get(guild.categories, name=ticket_category)

        if category is None:
            await interaction.response.send_message("I cannot open a ticket at the moment. Please contact Discord Bot staff.", ephemeral=True)

        existing_channel = discord.utils.get(guild.text_channels, name=f"{interaction.user}-discord-report")

        if existing_channel:
            await interaction.response.send_message("You already have an active ticket open.", ephemeral=True)

        overwrites = {
			guild.default_role: discord.PermissionOverwrite(view_channel=False),
			user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True),  
			discord.utils.get(guild.roles, id=1009509393609535548): discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
		}

        channel = await guild.create_text_channel(
			name = f"{interaction.user}-discord-report",
			category=category,
			overwrites=overwrites
		)

        await interaction.response.send_message("✅ Discord ticket sucessfully opened! You can access your ticket at {channel.mention}", ephemeral=True)

        embed = discord.Embed(
			title = "⚠️ New Player Report submitted",
			description = f"{interaction.user.mention} submitted a player report, please check it out!",
			color = 0xFF5733,
			timestamp=datetime.now()
		)
        embed.add_field(name="Description of the rule violation:",
			value = self.report_reason.value,
			inline=False
		)
        embed.add_field(name="Who broke it:",
			value = self.player_name.value,
			inline=False
		)
        
        await channel.send(embed=embed)