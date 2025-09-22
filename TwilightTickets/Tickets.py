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
    ticket_type_request: str,
    request_title: str,
    request_description: str,
    category_id: int,
    staff_role_id: int,
    embed_color: int,
    cog: commands.Cog
):
    from . import ViewsModals

    guild = interaction.guild
    user = interaction.user
    sconfg = cog.config.guild(guild)

    ticket_statuses = await sconfg.ticket_statuses()
    ticket_log_channel_id = await sconfg.ticket_log_channel()
    ticket_log_channel = interaction.guild.get_channel(ticket_log_channel_id)
    staff_ping_enabled = ticket_statuses.get("staffping", True)

    category = discord.utils.get(guild.categories, id=category_id)
    if category is None:
        await interaction.response.send_message("**`⚠️ Error!`** Cannot open a request right now.", ephemeral=True)
        return

    ticket_id = uuid.uuid4().hex[:6]
    channel_name = f"{ticket_type.lower()}-request-{ticket_id}"

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
    
    try:
        cog.cursor.execute(
            "INSERT OR IGNORE INTO tickets (ticket_id, channel_id, opener_id, open_time, ticket_type) VALUES (?, ?, ?, ?, ?)",
            (ticket_id, channel.id, user.id, datetime.now().isoformat(), ticket_type_request),
        )
        cog.conn.commit()
    except Exception as e:
        print(f"[Ticket Creation] DB insert failed for {ticket_id}: {e}")

    embed = discord.Embed(
        title=f"📋 {ticket_type} Request Submitted",
        description=f"{user.mention} submitted a new request. Please take a look at the details and notify appropriate staff members if necessary.",
        color=embed_color,
        timestamp=datetime.now()
    )
    embed.add_field(name="Request Type", value=ticket_type_request, inline=False)
    embed.add_field(name="Request Title", value=request_title, inline=False)
    embed.add_field(name="Request Description", value=request_description, inline=False)

    ticket_type_desc = f"{ticket_type.lower()}.{ticket_type_request.replace(' ', '-').lower()}"

    created_ticket_embed = discord.Embed(
        title=f"📩 New Support Request!",
        description=f"Request opened by {user.mention} ({user.id}) for `{ticket_type_desc}`",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    created_ticket_embed.add_field(name="Link to channel", value=f"{channel.mention}")
    created_ticket_embed.set_thumbnail(url="https://cdn.rxtnshi.xyz/u/8bnPxj.gif")
    created_ticket_embed.set_footer(text=f"Ticket ID: {ticket_id}")

    ping_message = f"<@&{staff_role_id}>" if (staff_ping_enabled and staff_role_id) else None

    await channel.send(ping_message, embed=embed, view=ViewsModals.CloseTicketView(), allowed_mentions=discord.AllowedMentions.all())
    await ticket_log_channel.send(embed=created_ticket_embed)
    await interaction.response.send_message(f"**`✅ Success!`** Ticket opened! Access it at {channel.mention}", ephemeral=True)

async def close_ticket(channel: discord.TextChannel, closer: discord.Member, close_reason: str, log_message: discord.Message, cog: commands.Cog):
    ticket_id = None
    if channel.topic and "ID:" in channel.topic:
        try:
            ticket_id = channel.topic.split("ID:")[1].split("|")[0].strip()
        except IndexError:
            pass

    if ticket_id:
        try:
            cog.cursor.execute("""
                UPDATE tickets
                SET closer_id = ?, close_time = ?, log_message_id = ?, close_reason = ?
                WHERE ticket_id = ?
            """, (closer.id, datetime.now().isoformat(), log_message.id, close_reason, ticket_id))
            cog.conn.commit()
        except Exception as e:
            print(f"[Ticket Closing] Failed to update ticket {ticket_id} in database: {e}")

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
    open_time_str = "N/A"
    ticket_type = "Unknown"

    # Get info from DB
    try:
        cog.cursor.execute("SELECT open_time, ticket_type, opener_id FROM tickets WHERE ticket_id = ?", (ticket_id,))
        result = cog.cursor.fetchone()
        open_user_id = None
        if result:
            open_time_iso, db_ticket_type, open_user_id = result
            open_user_id = None
            if open_time_iso:
                open_time_dt = datetime.fromisoformat(open_time_iso)
                open_time_str = open_time_dt.strftime('%Y-%m-%d %H:%M:%S UTC')
                open_time_ts = f"<t:{int(open_time_dt.timestamp())}:f>"
            if ticket_type:
                ticket_type = db_ticket_type
    except Exception as e:
        print(f"[Ticket Transcripts] DB read failed for ticket id = {ticket_id}") 
        open_user_id = None

    opener_user = "Unknown"
    if isinstance(opener, (discord.Member, discord.User)):
        opener_user = f"{opener} ({opener.id})"
    elif open_user_id:
        opener_user = f"<@{open_user_id}> ({open_user_id})"

    closer_user = "Unknown"
    closer_id = None
    if isinstance(closer, (discord.Member, discord.User)):
        closer_id = closer.id
        closer_user = f"{closer} ({closer_id})"

    close_time_dt = datetime.now()
    close_time_str = close_time_dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    close_time_ts = f"<t:{int(close_time_dt.timestamp())}:f>"

    # header
    transcript = "-" * 40 + "\n"
    transcript += f"Transcript for ticket channel: {channel.name}\n"
    transcript += f"Opened by: {opener_user}\n"
    transcript += f"Closed by: {closer_user}\n"
    transcript += f"Opened at: {open_time_str}\n"
    transcript += f"Closed at: {close_time_str}\n"
    transcript += f"Request Type: {ticket_type}\n"
    transcript += f"Request Issue: {open_reason}\n"
    transcript += f"Close Reason: {close_reason}\n"
    transcript += "-" * 40 + "\n"

    async for msg in channel.history(limit=None, oldest_first=True):
        time = msg.created_at.strftime("%Y-%m-%d %H:%M")
        content = msg.content if msg.content else "[Embed/Attachment]"
        transcript += f"[{time}] {msg.author}: {content}\n"
    
    user_embed = discord.Embed(
        title=f"📫 Ticket Transcript for `{channel.name}`",
        description="Thank you for opening a ticket with us. Your ticket transcript is attached.",
        color=discord.Color.lighter_gray(),
        timestamp=close_time_dt
    )
    user_embed.add_field(name="Opened by", value=opener_user, inline=False)
    user_embed.add_field(name="Closed by", value=closer_user, inline=False)
    user_embed.add_field(name="Opened at", value=open_time_ts, inline=True)
    user_embed.add_field(name="Closed at", value=close_time_ts, inline=True)
    user_embed.add_field(name="Request Type", value=ticket_type, inline=False)
    user_embed.add_field(name="Request Issue", value=f"{open_reason}", inline=False)
    user_embed.add_field(name="Close Reason", value=close_reason, inline=False)

    logs_channel_embed = discord.Embed(
        title=f"📋 Ticket Transcript",
        description=f"Ticket transcript for `{channel.name}`",
        color=discord.Color.lighter_gray(),
        timestamp=close_time_dt
    )
    logs_channel_embed.add_field(name="Opened by", value=opener_user, inline=False)
    logs_channel_embed.add_field(name="Closed by", value=closer_user, inline=False)
    logs_channel_embed.add_field(name="Opened at", value=open_time_ts, inline=True)
    logs_channel_embed.add_field(name="Closed at", value=close_time_ts, inline=True)
    logs_channel_embed.add_field(name="Request Type", value=ticket_type, inline=False)
    logs_channel_embed.add_field(name="Request Issue", value=f"{open_reason}", inline=False)
    logs_channel_embed.add_field(name="Close Reason", value=close_reason, inline=False)

    transcript_text = transcript
    file_user = discord.File(io.StringIO(transcript_text), filename=f"transcript.txt")
    file_logs = discord.File(io.StringIO(transcript_text), filename=f"transcript.txt")

    log_message = await logs_channel.send(embed=logs_channel_embed, file=file_logs)

    try:
        await opener.send(embed=user_embed, file=file_user)
    except (discord.Forbidden, AttributeError):
        await log_message.reply(f"**`⚠️ Error!`** Unable to send transcript to {opener.mention} (DMs may be closed).")

    return log_message

async def create_ban_appeal(interaction, banned_user: str, appeal_platform: str, appeal_request: str, cog: commands.Cog):
    from . import ViewsModals
    
    sconfg = cog.config.guild(interaction.guild)
    user = interaction.user
    guild = interaction.guild
    
    appeal_id = uuid.uuid4().hex[:8]

    time_sent = datetime.fromisoformat(datetime.now().isoformat())
    time_sent_ts = f"<t:{int(time_sent.timestamp())}:f>"

    ticket_statuses = await sconfg.ticket_statuses()
    staff_ping_enabled = ticket_statuses.get("staffping", True)

    cog.cursor.execute("""
        INSERT INTO appeals (appeal_id, user_id, ban_platform, ban_appeal_reason, appeal_status, timestamp)
        VALUES (?, ?, ?, ?, 'pending', ?)
    """, (appeal_id, user.id, appeal_platform, appeal_request, datetime.now().isoformat()))
    cog.conn.commit()

    appeals_channel_id = await sconfg.appeal_log_channel()
    appeal_team_id = await sconfg.appeal_team_role()
    appeals_channel = guild.get_channel(appeals_channel_id)

    if not appeals_channel:
        print(f"[Appeals] Could not find the appeals channel with ID {appeals_channel_id}")
        await interaction.response.send_message("**`⚠️ Error!`** The appeal system is misconfigured. Please contact an administrator.", ephemeral=True)
        return
    
    appeals_embed = discord.Embed(
        title="📥 Appeal Submitted", 
        description=f"Appeal request by {user.mention}. Please investigate the details and select a decision when ready.", 
        color=0xffa500
    )
    appeals_embed.add_field(name="Platform", value=appeal_platform, inline=False)
    appeals_embed.add_field(name="Account ID (User ID)", value=banned_user, inline=False)
    appeals_embed.add_field(name="Appeal Description", value=appeal_request, inline=False)
    appeals_embed.add_field(name="Time Submitted", value=time_sent_ts, inline=False)
    appeals_embed.set_footer(text=f"User ID: {user.id} | Appeal ID: {appeal_id}")

    user_embed = discord.Embed(
        title="📥 Appeal Received",
        description="Thank you for submitting an appeal. Your appeal will be looked at within the next 48 hours.",
        color=0xffa500
    )
    user_embed.add_field(name="Platform", value=appeal_platform, inline=False)
    user_embed.add_field(name="Account ID (User ID)", value=banned_user, inline=False)
    user_embed.add_field(name="Appeal Description", value=appeal_request, inline=False)
    user_embed.add_field(name="Time Submitted", value=time_sent_ts, inline=False)
    user_embed.set_footer(text=f"User ID: {user.id} | Appeal ID: {appeal_id}")

    ping_message = f"<@&{appeal_team_id}>" if (staff_ping_enabled and appeal_team_id) else None

    appeals_message = await appeals_channel.send(ping_message, embed=appeals_embed, view=ViewsModals.AppealView(), allowed_mentions=discord.AllowedMentions.all())
    try:
        await user.send(embed=user_embed)
    except discord.Forbidden:
        await appeals_message.reply(f"**`⚠️ Error!`** Unable to send appeal confirmation to {user.mention} (DMs may be closed).")
        await interaction.response.send_message(f"**`⚠️ Success!`** However, your message requests were turned off so I was unable to send you a confirmation. You may check your appeal status by using `/appeal status {appeal_id}`.", ephemeral=True)
        return
    
    await interaction.response.send_message(f"**`✅ Success!`** Your appeal has been submitted for review and a receipt has been sent to you. Appeal ID: `{appeal_id}`", ephemeral=True)

async def finalize_appeal(opener_id: int, appeal_id: str, decision: str, reason: str, staff_member: discord.Member, cog: commands.Cog):
    status = "accepted" if decision == "accept" else "denied"
    
    cog.cursor.execute("UPDATE appeals SET appeal_status = ? WHERE appeal_id = ?", (status, appeal_id))
    cog.conn.commit()

    time_final_str = datetime.now().isoformat()
    time_final = datetime.fromisoformat(time_final_str)
    time_final_ts = f"<t:{int(time_final.timestamp())}:f>"

    guild = staff_member.guild
    sconfg = cog.config.guild(guild)
    appeals_channel_id = await sconfg.appeal_log_channel()
    appeals_channel = guild.get_channel(appeals_channel_id)

    user = await cog.bot.fetch_user(opener_id)
    if not user:
        print(f"[Direct Messages] Could not find user {opener_id} to DM appeal result.")
        return

    if status == "accepted":
        embed_color = discord.Color.green()
        title = "✅ Appeal Accepted"
        description = "Your appeal has been accepted. Apologies for the inconvenience."
    else:
        embed_color = discord.Color.red()
        title = "🚫 Appeal Rejected"
        description = "Unfortunately, your appeal has been rejected. Please check below for details."

    dm_embed = discord.Embed(title=title, description=description, color=embed_color)
    dm_embed.add_field(name="Reason from Staff", value=reason, inline=False)
    dm_embed.add_field(name="Decision Time", value=time_final_ts, inline=False)
    dm_embed.set_footer(text=f"TWZ Management")

    try:
        await user.send(embed=dm_embed)
    except discord.Forbidden:
        await appeals_channel.send(f"**`⚠️ Error!`** Unable to send the decision to {user.mention}. This may be due to their message requests turned off. (AID: `{appeal_id}`)")