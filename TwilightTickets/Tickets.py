import discord
import datetime
import sqlite3
import uuid
import io

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
    embed_color: int,
    cog: commands.Cog
):
    from . import ViewsModals

    guild = interaction.guild
    user = interaction.user
    
    category = discord.utils.get(guild.categories, id=category_id)
    if category is None:
        await interaction.response.send_message("Cannot open a ticket right now.", ephemeral=True)
        return

    ticket_id = uuid.uuid4().hex[:6]
    channel_name = f"{ticket_type.lower()}-report-{ticket_id}"

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True),
        discord.utils.get(guild.roles, id=staff_role_id): discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
    }

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        topic=f"ID: {ticket_id} | Issue: {request_description} | Opened by: {user.mention} ({user.id})"
    )
    
    cog.cursor.execute("""
        INSERT INTO tickets (ticket_id, channel_id, opener_id, open_time)
        VALUES (?, ?, ?, ?)
        """, (ticket_id, channel.id, user.id, datetime.now().isoformat()))
    cog.conn.commit()

    embed = discord.Embed(
        title=f"📋 {ticket_type} Ticket Submitted",
        description=f"{user.mention} submitted a ticket.",
        color=embed_color,
        timestamp=datetime.now()
    )
    embed.add_field(name="Issue:", value=request_name, inline=False)
    embed.add_field(name="Description:", value=request_description, inline=False)

    # await channel.send(f"{discord.utils.get(guild.roles, id=staff_role_id).mention}")
    await channel.send(embed=embed, view=ViewsModals.CloseTicketView())
    await interaction.response.send_message(f"✅ Ticket opened! Access it at {channel.mention}", ephemeral=True)

async def close_ticket(channel: discord.TextChannel, closer: discord.Member, close_reason: str, log_message: discord.Message, cog: commands.Cog):
    ticket_id = None
    if channel.topic and "ID:" in channel.topic:
        try:
            ticket_id = channel.topic.split("ID:")[1].split("|")[0].strip()
        except IndexError:
            pass

    if ticket_id:
        try:
            # Add close_reason to the UPDATE query
            cog.cursor.execute("""
                UPDATE tickets
                SET closer_id = ?, close_time = ?, log_message_id = ?, close_reason = ?
                WHERE ticket_id = ?
            """, (closer.id, datetime.now().isoformat(), log_message.id, close_reason, ticket_id))
            cog.conn.commit()
        except Exception as e:
            print(f"Failed to update ticket {ticket_id} in database: {e}")

    await channel.delete()

async def create_transcript(channel: discord.TextChannel, open_reason: str, opener, closer, logs_channel, close_reason: str, cog: commands.Cog):
    ticket_id = None
    if channel.topic and "ID:" in channel.topic:
        try:
            ticket_id = channel.topic.split("ID:")[1].split("|")[0].strip()
        except IndexError:
            pass
    
    open_time_dt = None
    open_time_ts = "N/A"
    cog.cursor.execute("SELECT open_time FROM tickets WHERE ticket_id = ?", (ticket_id,))
    result = cog.cursor.fetchone()
    if result:
        open_time_dt = datetime.fromisoformat(result[0])
        open_time_str = open_time_dt.strftime('%Y-%m-%d %H:%M:%S UTC')
        open_time_ts = f"<t:{int(open_time_dt.timestamp())}:f>"

    close_time_dt = datetime.now()
    close_time_str = close_time_dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    close_time_ts = f"<t:{int(close_time_dt.timestamp())}:f>"

    # header
    transcript = "-" * 40 + "\n"
    transcript += f"Transcript for ticket channel: {channel.name}\n"
    transcript += f"Opened by: {opener} ({opener.id})\n"
    transcript += f"Closed by: {closer} ({closer.id})\n"
    transcript += f"Opened at: {open_time_str}\n"
    transcript += f"Closed at: {close_time_str}\n"
    transcript += f"Ticket issue: {open_reason}\n"
    transcript += f"Close Reason: {close_reason}\n"
    transcript += "-" * 40 + "\n"

    async for msg in channel.history(limit=None, oldest_first=True):
        time = msg.created_at.strftime("%Y-%m-%d %H:%M")
        content = msg.content if msg.content else "[Embed/Attachment]"
        transcript += f"[{time}] {msg.author}: {content}\n"
    
    user_embed = discord.Embed(
        title=f"📫 Ticket Transcript",
        description="Thank you for opening a ticket with us. Your ticket transcript is attached.",
        color=0x00FF00,
        timestamp=close_time_dt
    )
    user_embed.add_field(name="Opened by:", value=f"{opener.mention} ({opener.id})", inline=False)
    user_embed.add_field(name="Closed by:", value=f"{closer.mention} ({closer.id})", inline=False)
    user_embed.add_field(name="Opened at:", value=open_time_ts, inline=False)
    user_embed.add_field(name="Closed at:", value=close_time_ts, inline=False)
    user_embed.add_field(name="Ticket Issue:", value=f"{open_reason}", inline=False)
    user_embed.add_field(name="Close Reason:", value=close_reason, inline=False)

    logs_channel_embed = discord.Embed(
        title=f"📋 Ticket Transcript",
        description=f"Ticket log for {channel.name}",
        color=0x00FF00,
        timestamp=close_time_dt
    )
    logs_channel_embed.add_field(name="Opened by:", value=f"{opener} ({opener.id})", inline=False)
    logs_channel_embed.add_field(name="Closed by:", value=f"{closer} ({closer.id})", inline=False)
    logs_channel_embed.add_field(name="Opened at:", value=open_time_ts, inline=True)
    logs_channel_embed.add_field(name="Closed at:", value=close_time_ts, inline=True)
    logs_channel_embed.add_field(name="Ticket issue:", value=f"{open_reason}", inline=False)
    logs_channel_embed.add_field(name="Close Reason:", value=close_reason, inline=False)

    transcript_text = transcript
    file_user = discord.File(io.StringIO(transcript_text), filename=f"transcript.txt")
    file_logs = discord.File(io.StringIO(transcript_text), filename=f"transcript.txt")

    log_message = await logs_channel.send(embed=logs_channel_embed, file=file_logs)

    try:
        await opener.send(embed=user_embed, file=file_user)
    except (discord.Forbidden, AttributeError):
        await log_message.reply(f"Unable to send transcript to {opener.mention} (DMs may be closed or user not found).")

    return log_message

async def create_ban_appeal(interaction, banned_user: str, appeal_request: str, cog: commands.Cog):
    from . import ViewsModals

    user = interaction.user
    guild = interaction.guild
    
    cog.cursor.execute(("SELECT appeal_id FROM appeals WHERE user_id = ? AND appeal_status = 'pending'"), (user.id))
    result = cog.cursor.fetchone()

    fetched_appeal_id = result
    if result:
        await interaction.response.send_message(f"You already have a pending appeal. Please wait for staff to review it. (Reference AID: `{fetched_appeal_id}`)", ephemeral=True)
        return

    appeal_id = uuid.uuid4().hex[:8]

    try:
        cog.cursor.execute("""
            INSERT INTO appeals (appeal_id, user_id, ban_appeal_reason, appeal_status, timestamp)
            VALUES (?, ?, ?, 'pending', ?)
        """, (appeal_id, user.id, appeal_request, datetime.now().isoformat()))
    except sqlite3.IntegrityError:
        cog.cursor.execute("""
            UPDATE appeals SET ban_appeal_reason = ?, appeal_status = 'pending', timestamp = ? WHERE user_id = ?
        """, (appeal_request, datetime.now().isoformat(), user.id))
    cog.conn.commit()

    appeals_channel_id = 1414770277782392993
    appeals_channel = guild.get_channel(appeals_channel_id)

    if not appeals_channel:
        print(f"ERROR: Could not find the appeals channel with ID {appeals_channel_id}")
        await interaction.response.send_message("The appeal system is misconfigured. Please contact an administrator.", ephemeral=True)
        return
    
    embed = discord.Embed(title="📥 Ban Appeal Submitted", description=f"Submitted by {user.mention}", color=0xffa500)
    embed.add_field(name="Platform and AccountID", value=banned_user, inline=False)
    embed.add_field(name="Appeal Description", value=appeal_request, inline=False)
    embed.set_footer(text=f"User ID: {user.id} | Appeal ID: {appeal_id}")

    user_embed = discord.Embed(
        title="📥 Ban Appeal Received",
        description="Thank you for submitted a ban appeal. Your appeal will be looked at within the next 48 hours.",
    )
    user_embed.add_field(name="Platform and AccountID", value=banned_user, inline=False)
    user_embed.add_field(name="Appeal Description", value=appeal_request, inline=False)
    user_embed.set_footer(text=f"User ID: {user.id} | Appeal ID: {appeal_id}")

    await appeals_channel.send(embed=embed, view=ViewsModals.AppealView(), description=f"Submitted by {user.mention}", color=0xffa500)
    await user.send(embed=user_embed)
    
    await interaction.response.send_message(f"✅ Your appeal has been submitted for review. Appeal ID: `{appeal_id}`", ephemeral=True)


async def finalize_appeal(opener_id: int, appeal_id: str, decision: str, reason: str, staff_member: discord.Member, cog: commands.Cog):
    status = "accepted" if decision == "accept" else "denied"
    
    # Use the specific appeal_id to update the correct record.
    cog.cursor.execute("UPDATE appeals SET appeal_status = ? WHERE appeal_id = ?", (status, appeal_id))
    cog.conn.commit()

    user = await cog.bot.fetch_user(opener_id)
    if not user:
        print(f"Could not find user {opener_id} to DM appeal result.")
        return

    if status == "accepted":
        embed_color = discord.Color.green()
        title = "✅ Ban Appeal Accepted"
        description = "Your appeal has been accepted. Apologies for the inconvenience."
    else:
        embed_color = discord.Color.red()
        title = "🚫 Ban Appeal Rejected"
        description = "Unfortunately, your appeal has been rejected. Please check below for details."

    dm_embed = discord.Embed(title=title, description=description, color=embed_color)
    dm_embed.add_field(name="Reason from Staff", value=reason, inline=False)
    dm_embed.set_footer(text=f"TWZ Management")

    try:
        await user.send(embed=dm_embed)
    except discord.Forbidden:
        print(f"Could not DM appeal result to user {opener_id} (DMs closed).")