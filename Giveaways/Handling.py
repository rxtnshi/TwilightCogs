import discord
from datetime import datetime

async def parse_interaction(interaction: discord.Interaction, embed: discord.Embed, ephemeral: bool):
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

async def send_error(interaction: discord.Interaction, content: str, epheremal: bool = False):
    embed = discord.Embed(
        title="⚠️ Error!",
        description="Giveaways has encountered an error!",
        color=discord.Color.dark_orange(),
        timestamp=datetime.now()
    )
    
    embed.add_field(name="Details", value=content)
    
    await parse_interaction(interaction, embed=embed, ephemeral=epheremal or False)

async def send_success(interaction: discord.Interaction, content: str, epheremal: bool = False):
    embed = discord.Embed(
        title="✅ Success!",
        description=content,
        color=discord.Color.green(),
        timestamp=datetime.now()
    )

    await parse_interaction(interaction, embed=embed, ephemeral=epheremal or False)

async def send_warning(interaction: discord.Interaction, content: str, epheremal: bool = False):
    embed = discord.Embed(
        title="⚠️ Encountered an warning!",
        description="Giveaways has encountered an warning!",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    
    embed.add_field(name="Details", value=content)

    await parse_interaction(interaction, embed=embed, ephemeral=epheremal or False)

async def send_blocked(interaction: discord.Interaction, content: str, epheremal: bool = False):
    embed = discord.Embed(
        title="🚫 Prohibited!",
        description="You've been blocked from doing this action.",
        color=discord.Color.dark_orange(),
        timestamp=datetime.now()
    )
    
    embed.add_field(name="Details", value=content)

    await parse_interaction(interaction, embed=embed, ephemeral=epheremal or False)