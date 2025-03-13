import discord, os
from datetime import datetime
from discord import app_commands, utils
from discord.ext import commands

#######
# MODALS
#######
class BugReportModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Bug Report")
        self.bug_description = discord.ui.TextInput(label="Describe the bug in a few sentences", required=True, style=discord.TextStyle.short)
        self.bug_reproduce = discord.ui.TextInput(label="Reproduction Steps", required=True, style=discord.TextStyle.paragraph)
        self.add_item(self.bug_description)
        self.add_item(self.bug_reproduce)

    async def on_submit(self, interaction: discord.Interaction):
        bug_reportchannel_id = 1348781470264590499
        bug_report_channel = interaction.guild.get_channel(bug_reportchannel_id)

        if not bug_report_channel:
            return await interaction.response.send_message("❌ Bug report failed to send. Please contact a developer.", ephemeral=True)

        embed = discord.Embed(
            title="⚠️ New Bug Report Submitted",
            description=f"{interaction.user.mention} submitted a bug report, please check it out!",
            color=0xFF5733,
            timestamp=datetime.now()
        )
        embed.add_field(name="Status", value="🔴 Untested", inline=False)
        embed.add_field(name="Description of the bug:", value=self.bug_description.value, inline=False)
        embed.add_field(name="Reproduction Steps:", value=self.bug_reproduce.value, inline=False)
        embed.add_field(name="Status last changed by", value="NOBODY", inline=False)

        await bug_report_channel.send(embed=embed, view=BugReportStatusView())
        await interaction.response.send_message("✅ Bug report submitted!", ephemeral=True)

        # ✅ Reopen a fresh modal after submission
        await interaction.followup.send_modal(BugReportModal())  


class DiscordHelpModal(discord.ui.Modal):
	def __init__(self):
		super().__init__(title="Discord Help Request")
		self.discord_report_name = discord.ui.TextInput(label="Who are you reporting? If nobody, you can put 'NONE'.", required=True, style=discord.TextStyle.short)
		self.discord_request = discord.ui.TextInput(label="Describe the issue", required=True, style=discord.TextStyle.paragraph)
		self.add_item(discord_report_name)
		self.add_item(discord_request)

	async def on_submit(self, interaction: discord.Interaction):
		guild = interaction.guild
		user = interaction.user

		ticket_category_name = "Support"

		category = discord.utils.get(guild.categories, name=ticket_category_name)
		if category is None:
			await interaction.response.send_message("Sorry, I had trouble opening a ticket inside an non-existent category")

		existing_channel = discord.utils.get(guild.text_channels, name=f"{interaction.user}-discord-report")
		if existing_channel:
			await interaction.response.send_message("Sorry, you already have an open ticket.")

		overwrites = {
			guild.default_role: discord.PermissionOverwrite(view_channel=False),
			user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True),  
			discord.utils.get(guild.roles, name="guh"): discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
		}

		channel = await guild.create_text_channel(
			name = f"{interaction.user}-discord-report",
			category=category,
			overwrites=overwrites
		)

		await interaction.response.send_message("✅ Discord report submitted! You can access your ticket at {channel.mention}", ephemeral=True)

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

#######
# DROPDOWNS
#######

class TicketDropdown(discord.ui.Select):
	def __init__(self):
		options = [
			discord.SelectOption(label="🛠️ Bug Report", description="Report a plugin bug."),
			#discord.SelectOption(label="⚠️ Discord Help", description="Request help for Discord-related issues."),
		]

		super().__init__(placeholder="Select a category...", options=options)

	async def callback(self, interaction: discord.Interaction):
		"""Handles the dropdown selection."""
		if self.values[0] == "🛠️ Bug Report":
			modal = BugReportModal()
		#elif self.values[0] == "⚠️ Discord Help":
		#	modal = DiscordHelpModal()

		await interaction.response.send_modal(modal)

class BugReportStatuses(discord.ui.Select):
	def __init__(self):
		options = [
			discord.SelectOption(label="🔴 Untested"),
			discord.SelectOption(label="🟠 Confirmed"),
			discord.SelectOption(label="🟢 Fixed"),
			discord.SelectOption(label="👎 Not a bug")
		]

		super().__init__(placeholder="Edit Bug Report Status", options=options)

	async def callback(self, interaction: discord.Interaction):
		dev_role_ids = {1348781920787501077}

		if not any(role.id in dev_role_ids for role in interaction.user.roles):
			await interaction.response.send_message("❌ You do not have sufficient permissions to edit the status. Please contact bot owner to fix this.")
			return

		# CHANGES REPORT STATUS
		message = interaction.message
		embed = message.embeds[0]

		new_status = self.values[0]
		embed.set_field_at(0, name="Status", value=new_status, inline=True)
		embed.set_field_at(3, name="Status last changed by", value=f"{interaction.user.mention}", inline=True)
		await message.edit(embed=embed)

		# SENDS CONFIRMATION OF CHANGE
		await interaction.response.send_message(f"Succssfully changed the status to: {new_status}", ephemeral=True)


#######
# VIEWS
#######

class TicketView(discord.ui.View):
	def __init__(self, bot: commands.Bot) -> None:
		super().__init__()
		self.add_item(TicketDropdown())
		self.bot = bot

class BugReportStatusView(discord.ui.View):
	def __init__(self):
		super().__init__()
		self.add_item(BugReportStatuses())