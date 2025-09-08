import discord
import datetime
import uuid
import io
import re

from datetime import datetime
from discord import app_commands, utils
from discord.ext import commands

async def create_ticket(
    interaction,
    ticket_type: str,
    request_name: str,
    request_description: str,
    category_id: int,
    staff_role_id: int,
    embed_color: int
):
    from . import ViewsModals

    guild = interaction.guild
    user = interaction.user
    
    category = discord.utils.get(guild.categories, id=category_id)
    if category is None:
        await interaction.response.send_message("Cannot open a ticket right now.", ephemeral=True)
        return

    ticket_id = uuid.uuid1().hex[:6]
    channel_name = f"{ticket_type.lower()}-report-{ticket_id}"

    for channel in category.text_channels:
        if channel.topic and f"({user.id})" in channel.topic:
            await interaction.response.send_message(f"You already have a ticket open! You can access it here: {channel.mention}", ephermal=True)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True),
        discord.utils.get(guild.roles, id=staff_role_id): discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
    }

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        topic=f"Issue: {request_description} | Opened by: {user.mention} ({user.id})"
    )
    
    embed = discord.Embed(
        title=f"📋 {ticket_type} Ticket Submitted",
        description=f"{user.mention} submitted a ticket.",
        color=embed_color,
        timestamp=datetime.now()
    )
    embed.add_field(name="Description:", value=request_description, inline=False)
    embed.add_field(name="Reported User:", value=request_name, inline=False)

    await channel.send(embed=embed, view=ViewsModals.CloseTicketView())
    await interaction.response.send_message(f"✅ Ticket opened! Access it at {channel.mention}", ephemeral=True)

async def create_transcript(channel: str, open_reason: str, opener, closer, logs_channel):
    transcript = "-" * 40 + "\n"
    transcript += f"Transcript for ticket channel: {channel.name}\n"
    transcript += f"Opened by: {opener} ({opener.id})\n"
    transcript += f"Closed by: {closer} ({closer.id})\n"
    transcript += f"Ticket issue: {open_reason}\n"
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
    user_embed.add_field(name="Opened by:", value=f"{opener} ({opener.id})", inline=False)
    user_embed.add_field(name="Closed by:", value=f"{closer} ({opener.id})", inline=False)
    user_embed.add_field(name="Ticket issue:", value=f"{open_reason}", inline=False)

    logs_channel_embed = discord.Embed(
        title=f"📋 Ticket Transcript",
        description=f"Ticket log for {channel.name}",
        color=0x00FF00,
        timestamp=datetime.now()
    )
    logs_channel_embed.add_field(name="Opened by:", value=f"{opener} ({closer.id})", inline=False)
    logs_channel_embed.add_field(name="Closed by:", value=f"{closer} ({closer.id})", inline=False)
    logs_channel_embed.add_field(name="Ticket issue:", value=f"{open_reason}", inline=False)

    file_data = io.StringIO(transcript)
    file_user = discord.File(io.StringIO(transcript), filename=f"transcript.txt")
    file_data.seek(0)
    file_logs = discord.File(io.StringIO(transcript), filename=f"transcript.txt")

    try:
        await opener.send(embed=user_embed, file=file_user)
        await logs_channel.send(embed=logs_channel_embed, file=file_logs)
    except discord.Forbidden:
        await logs_channel.send(f"Unable to send transcript for {channel.mention}. This may be due to their direct messages turned off.", embed=logs_channel_embed, file=file)