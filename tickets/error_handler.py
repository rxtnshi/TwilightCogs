import discord
from datetime import datetime

async def parse_interaction(interaction: discord.Interaction, embed: discord.Embed, ephemeral: bool):
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

async def send_error(interaction: discord.Interaction, content: str, epheremal: bool = False):
    cog = interaction.client.get_cog("tickets")

    embed = discord.Embed(
        title="⚠️ Error!",
        description="Encountered an error performing this action.",
        color=discord.Color.dark_orange(),
        timestamp=datetime.now()
    )
    
    embed.add_field(name="Error Details", value=content)

    await parse_interaction(interaction, embed=embed, ephemeral=epheremal or False)

async def send_success(interaction: discord.Interaction, content: str, epheremal: bool = False):
    embed = discord.Embed(
        title="✅ Success!",
        description="Successfully performed this action!",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )

    embed.add_field(name="Details", value=content)
    await parse_interaction(interaction, embed=embed, ephemeral=epheremal or False)

async def send_blocked(interaction: discord.Interaction, content: str, epheremal: bool = False):
    cog = interaction.client.get_cog("tickets")

    embed = discord.Embed(
        title="🚫 Prohibited!",
        description="You've been blocked from doing this action.",
        color=discord.Color.dark_orange(),
        timestamp=datetime.now()
    )
    
    embed.add_field(name="Details", value=content)
    cog.log.warning(f"{interaction.user} tried to do something but was blocked from doing so: {content}")
    await parse_interaction(interaction, embed=embed, ephemeral=epheremal or False)