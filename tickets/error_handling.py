import discord
from datetime import datetime

async def send_error(interaction: discord.Interaction, content: str, epheremal: bool = False):
    cog = interaction.client.get_cog("tickets")

    embed = discord.Embed(
        title="⚠️ Error!",
        description="Encountered an error performing this action.",
        color=discord.Color.dark_orange(),
        timestamp=datetime.now()
    )
    
    embed.add_field(name="Error Details", value=content)

    cog.log.error(f"{interaction.user} ran into an error: {content}")
    await interaction.response.send_message(embed=embed, ephemeral=epheremal or False)

async def send_success(interaction: discord.Interaction, content: str, epheremal: bool = False):
    cog = interaction.client.get_cog("tickets")

    embed = discord.Embed(
        title="✅ Success!",
        description="Successfully performed this action!",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )

    embed.add_field(name="Details", value=content)

    cog.log.info(f"{interaction.user} successfully ran something: {content}")
    await interaction.response.send_message(embed=embed, ephemeral=epheremal or False)

async def send_warning(interaction: discord.Interaction, content: str, epheremal: bool = False):
    cog = interaction.client.get_cog("tickets")

    embed = discord.Embed(
        title="⚠️ Warning!",
        description="The action you requested was performed, but encountered a potential issue.",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    
    embed.add_field(name="Details", value=content)

    cog.log.warning(f"{interaction.user} tried to do something but was met with a warning: {content}")
    await interaction.response.send_message(embed=embed, ephemeral=epheremal or False)

async def send_blocked(interaction: discord.Interaction, content: str, epheremal: bool = False):
    cog = interaction.client.get_cog("tickets")

    embed = discord.Embed(
        title="🚫 Prohibited!",
        description="You've been blocked from doing this action.",
        color=discord.Color.dark_orange(),
        timestamp=datetime.now()
    )
    
    embed.add_field(name="Details", value=content)

    cog.log.warning(f"{interaction.user} tried to do something but was blocked: {content}")
    await interaction.response.send_message(embed=embed, ephemeral=epheremal or False)