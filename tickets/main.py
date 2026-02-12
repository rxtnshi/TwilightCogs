import discord
import logging

from . import views
from .error_handler import send_blocked, send_success, send_error
from .creation_handler import Blacklist
from .db_handler import db
from datetime import datetime
from redbot.core import commands, app_commands, Config
from redbot.core.data_manager import cog_data_path

class tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.log = logging.getLogger("twilightcogs.ticketsv2")
        self.path = cog_data_path(self)
        self.db = db(self.path) # in case if need to make db entries/searches

        self.config = Config.get_conf(self, identifier=1, force_registration=True)
        default_guild = {
			"tickets_enabled": True,
            "appeals_enabled": True,
            "pings_enabled": True,
			"ticket_roles": {
				"modmail_access": None,
				"modmail_mgmt": None,
				"appeals_access": None,
                "staff_roles": []
			},
			"ticket_channels": {
				"log_channel": None,
				"appeal_logs": None,
			},
			"panel_cfg": {
				"channel": None,
                "description": None,
				"message_id": None,
			}
		}
        self.config.register_guild(**default_guild)

    async def staff_check(self, interaction: discord.Interaction):
        confg = self.config.guild(interaction.guild)
        ticket_roles = await confg.ticket_roles()
        modmail_access = ticket_roles['modmail_access']
        modmail_mgmt = ticket_roles['modmail_mgmt']

        check = {rid for rid in (modmail_access, modmail_mgmt) if rid}
        if not check:
            return False
        
        return any(role.id in check for role in interaction.user.roles)

    async def elevated_check(self, interaction: discord.Interaction):
        confg = self.config.guild(interaction.guild)
        ticket_roles = await confg.ticket_roles()
        modmail_mgmt = ticket_roles['modmail_mgmt']

        if interaction.user.guild_permissions.administrator:
            return True
        
        if not modmail_mgmt:
            return False
        
        return any(role.id == modmail_mgmt for role in interaction.user.roles) 

    async def blacklist_check(self, user: discord.Member):
        return await self.db.fetch_blacklist(user.id)
    
    async def load_views(self):
        self.log.info("Loading views...")

        saved_views = await self.db.fetch_views()
        if saved_views:
            for view in saved_views:
                view_type = view.get('view_type')
                view_channel_id = view.get('channel_id')
                view_id = int(view.get('message_id'))

                match view_type:
                    case 'support-panel':
                        channel = await self.bot.fetch_channel(view_channel_id)
                        confg = self.config.guild(channel.guild)
                        panel_cfg = await confg.panel_cfg()
                        tickets_enabled = await confg.tickets_enabled()
                        appeals_enabled = await confg.appeals_enabled()
                        categories = await self.db.list_categories() or []
                        description = panel_cfg.get("description")

                        vieww = views.SupportPanel().generate(
                            channel.guild,
                            description,
                            categories,
                            appeals_enabled,
                            tickets_enabled,
                            view_channel_id
                        )
                    case 'appeal-panel':
                        appeal_id = view.get('appeal_id')
                        if not appeal_id:
                            continue
                        
                        appeal = await self.db.fetch_appeal(appeal_id)
                        channel = await self.bot.fetch_channel(view_channel_id)
                        appeal_user = await self.bot.fetch_user(appeal.get('appealer_id'))
                        moderated_account = appeal.get('account')
                        moderated_platform = appeal.get('platform')
                        moderated_reason = appeal.get('reason')
                        appeal_info = appeal.get('appeal_info')

                        try:
                            await channel.fetch_message(view_id)
                        except discord.NotFound:
                            await self.db.delete_view(view_id)
                            self.log.info(f"Deleted {view_type} view with message ID {view_id} as it doesn't exist anymore.")
                            continue

                        vieww = views.AppealPanel().generate(
                            'log',
                            appeal_id,
                            appeal_user,
                            moderated_account,
                            moderated_platform,
                            moderated_reason,
                            appeal_info
                        )
                    case 'ticket-view':
                        ticket = await self.db.fetch_ticket(view_channel_id)
                        if not ticket:
                            continue
                        
                        try:
                            channel = await self.bot.fetch_channel(view_channel_id)
                        except discord.NotFound:
                            await self.db.delete_view(view_id)
                            self.log.info(f"Deleted {view_type} view with message ID {view_id} as it doesn't exist anymore.")
                            continue
                        
                        ticket_user = await self.bot.fetch_user(ticket.get('ticket_user'))

                        vieww = views.TicketInfo().set_data(
                            ticket_user,
                            ticket.get('title'),
                            ticket.get('description'),
                            ticket.get('ticket_id')
                        )
                try:
                    self.bot.add_view(vieww, message_id=view_id)
                    self.log.info(f"Loaded {view_type} view from message {view_id}")
                except Exception as e:
                    self.log.error(f"Unable to load view with message id {view_id}: {e}")

    staff = app_commands.Group(name="staff", description="Staff commands", guild_only=True)
    ticket = app_commands.Group(name="ticket", description="Ticket commands", guild_only=True)
    appeal = app_commands.Group(name="appeal", description="Appeal commands", guild_only=True)
        
    @staff.command(name="register", description="Allows your staff to gain access to use the ticket system.")
    async def register_staff(self, interaction: discord.Interaction, user: discord.Member = None):
        confg = self.config.guild(interaction.guild)
        ticket_roles = await confg.ticket_roles()
        staff_roles = ticket_roles.get("staff_roles")
        access_id = ticket_roles.get("modmail_access")
        mgmt_id = ticket_roles.get("modmail_mgmt")

        access_role = interaction.guild.get_role(access_id)
        access_roles = {rid for rid in (access_id, mgmt_id) if rid}
        mgmt_role = interaction.guild.get_role(mgmt_id)
        user_check = any(r.id in staff_roles for r in interaction.user.roles)
        existing_check = bool(access_roles and any(r.id in access_roles for r in interaction.user.roles))

        if not user_check:
            return await send_blocked(interaction, "You're not permitted to run this command.", True)
        
        if user:
            if not await self.elevated_check(interaction):
                return await send_blocked(interaction, "You're not permitted to register other users.", True)
            
            check = bool(access_roles and any(r.id in access_roles for r in user.roles))
            if check:
                return await send_blocked(interaction, f"{user.mention} is already registered to the ticket system.", True)
            
            await user.add_roles(access_role, reason="Registered user to ticket system as staff")
            return await send_success(interaction, f"Successfully registered {user.mention} to the ticket system.", True)
        
        try:
            if await self.elevated_check(interaction):
                if existing_check:
                    return await send_blocked(interaction, "You're already registered to the ticket system.", True)
                
                await interaction.user.add_roles(mgmt_role, reason="Registered user to ticket system as management")
                return await send_success(interaction, "You've been successfully registered to the system! You've been given elevated level access due to having Administrator permissions.", True)
            else:
                if existing_check:
                    return await send_blocked(interaction, "You're already registered to the ticket system.", True)
                
                await interaction.user.add_roles(access_role, reason="Registered user to ticket system as staff")
                return await send_success(interaction, "You've been successfully registered to the system! You've been given standard level access. If you are someone that needs to be registered as management, please reach out to someone with Administrator permissions.", True)
        except Exception as e:
            return await send_error(interaction, f"Unable to register to the system: `{e}`")

    @staff.command(name="deregister", description="Remove a staff member from being able to access the ticket system.")
    @app_commands.describe(member="The staff member you want to deregister from the system.")
    async def deregister_staff(self, interaction: discord.Interaction, member: discord.Member):
        if not await self.elevated_check(interaction):
            return await send_blocked(interaction, "You are unable to run this command.", True)
        
        confg = self.config.guild(interaction.guild)
        roles = await confg.ticket_roles()
        standard = interaction.guild.get_role(roles.get('modmail_access')) if roles.get('modmail_access') else None

        if standard not in member.roles:
            return await send_error(interaction, f"{member.mention} is already de-registered from the system or wasn't in the first place!", True)

        try:
            await member.remove_roles(standard, reason="User was deregistered from the ticket system.")
            return await send_success(interaction, f"{member.mention} was de-registered from the ticket system.", True)
        except Exception as e:
            return await send_error(interaction, f"Something went wrong trying to deregister {member.mention}: `{e}`", True)

    @staff.command(name="blacklist", description="Blacklist server members from using the ticket system.")
    @app_commands.describe(
        option="Add, remove, or fetch blacklist information for a user", 
        member="The member you want to blacklist from using the ticket system.", 
        reason="The reason you're blacklisting them for."
    )
    @app_commands.choices(
        option=[
            app_commands.Choice(name="add", value="add"),
            app_commands.Choice(name="delete", value="delete"),
            app_commands.Choice(name="fetch", value="fetch")
        ]
    )
    async def blacklist_member(self, interaction: discord.Interaction, option: str, member: discord.Member, reason: str = None):
        if not await self.elevated_check(interaction):
            return await send_blocked(interaction, "You cannot run this command!", True)
        
        target = member
        staff = interaction.user
        if reason is None:
            reason = "No reason provided."

        blacklist = Blacklist(target, staff, reason)
        match option:
            case "add":
                check = await blacklist.fetch(interaction)
                if check:
                    text = (
                        f"{target.mention} is already in the blacklist!\n"
                        f"**Added by**: {interaction.guild.get_member(check.get('staff_member')).mention}"
                        f"**Reason**: {check.get('reason')}"
                    )
                    return await send_error(interaction, text, True)
                
                return await blacklist.add(interaction)
            case "delete":
                check = await blacklist.fetch(interaction)
                if check:
                    modal = views.BlacklistInfo(False, member, check.get("reason"))
                    await interaction.response.send_modal(modal)
                else:
                    return await send_error(interaction, "User was not found in blacklist!", True)
            case "fetch":
                check = await blacklist.fetch(interaction)
                if check:
                    modal = views.BlacklistInfo(True, member, check.get("reason"))
                    return await interaction.response.send_modal(modal)
                return await send_error(interaction, "No blacklist was found for this member.", True)

    @staff.command(name="set", description="Enables/disables ticket creation or appeals")
    @app_commands.describe(
        option="Enable/disable ticket creations or appeals",
        type="Choose either tickets or appeals to enable/disable"
    )
    @app_commands.choices(
        option=[
            app_commands.Choice(name="Enable", value="enable"),
            app_commands.Choice(name="Disable", value="disable")
        ],
        type=[
            app_commands.Choice(name="Tickets", value="tickets"),
            app_commands.Choice(name="Appeals", value="appeals"),
            app_commands.Choice(name="Staff Pings", value="staff-pings")
        ]
    )
    async def statuses(self, interaction: discord.Interaction, option: str, type: str):
        confg = self.config.guild(interaction.guild)
        tickets_status = await confg.tickets_enabled()
        appeals_status = await confg.appeals_enabled()
        pings_status = await confg.pings_enabled()

        match option:
            case "enable":
                match type:
                    case "tickets":
                        if not tickets_status:
                            new_tickets_status = not tickets_status
                            await confg.tickets_enabled.set(new_tickets_status)

                            return await send_success(interaction, f"The ticket system is now **`enabled`**! Please resend the support panel using `/ticket setup` to close tickets.")
                        else:
                            return await send_blocked(interaction, "This option is already enabled!", True)
                    case "appeals":
                        if not appeals_status:
                            new_appeals_status = not appeals_status
                            await confg.appeals_enabled.set(new_appeals_status)

                            return await send_success(interaction, f"The appeal system is now **`enabled`**! Please resend the support panel using `/ticket setup` to close appeals.")
                        else:
                            return await send_blocked(interaction, "This option is already enabled!", True)
                    case "staff-pings":
                        if not pings_status:
                            new_ping_status = not pings_status
                            await confg.pings_enabled.set(new_ping_status)

                            return await send_success(interaction, f"Staff pings is now **`enabled`**!.")
                        else:
                            return await send_blocked(interaction, "This option is already enabled!", True)
            case "disable":
                match type:
                    case "tickets":
                        if tickets_status:
                            new_tickets_status = not tickets_status
                            await confg.tickets_enabled.set(new_tickets_status)

                            return await send_success(interaction, f"The ticket system is now **`disabled`**! Please resend the support panel using `/ticket setup` to close tickets.")
                        else:
                            return await send_blocked(interaction, "This option is already disabled!", True)
                    case "appeals":
                        if appeals_status:
                            new_appeals_status = not appeals_status
                            await confg.appeals_enabled.set(new_appeals_status)

                            return await send_success(interaction, f"The appeal system is now **`disabled`**! Please resend the support panel using `/ticket setup` to close appeals.")
                        else:
                            return await send_blocked(interaction, "This option is already disabled!", True)
                    case "staff-pings":
                        if pings_status:
                            new_ping_status = not pings_status
                            await confg.pings_enabled.set(new_ping_status)

                            return await send_success(interaction, f"Staff pings is now **`disabled`**!")
                        else:
                            return await send_blocked(interaction, "This option is already disabled!", True)
                        
    @staff.command(name="history", description="Fetch ticket history for a user")
    async def ticket_history(self, interaction: discord.Interaction, user: discord.User | discord.Member):
        confg = self.config.guild(interaction.guild)
        channels = await confg.ticket_channels()
        log_ch_id = channels.get('log_channel')
        log_ch = interaction.guild.get_channel(log_ch_id)

        history = await self.db.fetch_ticket_history(user.id) or None
        history_text = ""

        if history:
            ticket_history = []
            for ticket in history:
                ticket_id = ticket.get('ticket_id')
                ticket_channel_id = ticket.get('ticket_channel')
                log_message_id = ticket.get('log_message_id')
                status = ticket.get('is_open')
                status_txt = 'Open' if status else 'Closed'

                channel = interaction.guild.get_channel(ticket_channel_id) or None
                ch_url = channel.jump_url if channel else None

                if status:
                    ticket_history.append(f"[`{ticket_id} - {status_txt}`]({ch_url})")
                else:
                    log_msg = await log_ch.fetch_message(log_message_id)
                    msg_link = log_msg.jump_url
                    ticket_history.append(f"[`{ticket_id} - {status_txt}`]({msg_link})")

            history_text = ", ".join(ticket_history)
        else:
            history_text = "No ticket history was found for this user!"

        embed = discord.Embed(
            title=f"📋 Ticket History for {user}",
            description=f"This is the list of tickets opened by {user.mention}.",
            color=discord.Color.blue()
        )

        embed.add_field(name="List of Tickets", value=history_text)

        await interaction.response.send_message(embed=embed)

    @staff.command(name="list", description="Get a list of users registered to the ticket system.")
    async def get_staff_list(self, interaction: discord.Interaction):
        confg = self.config.guild(interaction.guild)
        roles = await confg.ticket_roles()

        mgmt_id = roles.get('modmail_mgmt')
        stdrd_id = roles.get('modmail_access')

        mgmt = interaction.guild.get_role(mgmt_id)
        stdrd = interaction.guild.get_role(stdrd_id)

        mgmt_members = mgmt.members if mgmt else []
        stdrd_members = stdrd.members if stdrd else []
        mgmt_team = "\n".join(m.mention for m in mgmt_members) or "`No staff`"
        modmail_team = "\n".join(m.mention for m in stdrd_members) or "`No staff`"

        embed = discord.Embed(
			title="🛠️ Ticket System Staff",
			description="Here is a list of all staff with ticket system access!",
			color=discord.Color.blue(),
			timestamp=datetime.now()
		)
        
        embed.add_field(name="Ticket Management", value=mgmt_team, inline=False)
        embed.add_field(name="Ticket Staff", value=modmail_team, inline=False)
        
        await interaction.response.send_message(embed=embed)

    @ticket.command(name="help", description="Display all commands and their usage.")
    async def commands_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="ⓘ Ticket Commands Help Menu",
            description="Here is an overview of commands and functionality for the ticket system.",
            timestamp=datetime.now(),
            color=discord.Color.purple()
        )
        overview = (
            "Most ticket functionality rests in buttons in the ticket channels and log channels. You should be able to operate using the buttons with no errors, although if there are any please contact the cog developer with your RedBot logs.\n\n"
            "Here is a legend for each command and its level of access:\n"
            "🛡️ - Management/Adminstrator access needed\n"
            "🛠️ - Standard access needed\n"
            "👥 - Regular server members have access\n"
        )
        cmds = (
            "🛡️ `/ticket setup`: Interactive setup process for the ticket system. Can configure options here.\n"
            "👥 `/ticket help`: Returns this help menu.\n"
            "🛡️ `/staff panic`: Enables or disables ticket creation.\n"
            "🛠️ `/staff register [member - can be used if you are a person with management access]`: Registers server staff to the ticket system. Staff members must run this command themselves.\n"
            "🛡️ `/staff deregister [member]`: Deregister a specified member from the ticket system and removes standard access from them.\n"
            "🛡️ `/staff blacklist [add/remove/fetch] [member] [reason - optional but recommended]`: Blacklist feature for the ticket system.\n"
            "🛠️ `/staff history [member]`: Fetch ticket history for a user.\n"
            "🛠️ `/staff list`: Fetch users that are registered with the ticket system.\n"
            "👥 `/appeal status [appeal id]`: Check an appeal's status via its ID.\n"
        )
        embed.add_field(name="Overview", value=overview, inline=False)
        embed.add_field(name="Commands", value=cmds, inline=False)

        await interaction.response.send_message(embed=embed)

    @ticket.command(name="setup", description="Set up the ticket system for your server.")
    async def setup_tickets(self, interaction: discord.Interaction):
        if not await self.elevated_check(interaction):
            return await send_blocked(interaction, "You cannot run this command!", True)
        
        view = await views.SettingsPanel(interaction, interaction.user, interaction.message).get_settings(interaction)
        await interaction.response.send_message(view=view)
        view.message = await interaction.original_response()

    @appeal.command(name="status", description="Get the status of an appeal made with the ticket system.")
    @app_commands.describe(id="The appeal id given to you after an appeal has been made.")
    async def appeal_status(self, interaction: discord.Interaction, id: str):
        info = await self.db.fetch_appeal(id)
        if info:
            account = info.get("account")
            platform = info.get("platform")
            mod_reason = info.get("reason")
            appeal_info = info.get("appeal_info")
            decision_time = info.get("decision_time")
            decision_option = info.get("decision_option")
            decision_reason = info.get("decision_reason")
            appeal_id = info.get("appeal_id")

            embed = discord.Embed(
                title=f"Status for Appeal `{appeal_id}`",
                description="Here is the information regarding this appeal.",
                timestamp=datetime.now()
            )

            if decision_option == 'accepted':
                embed.color = discord.Color.green()
            elif decision_option == 'denied':
                embed.color = discord.Color.red()
            else:
                embed.color = discord.Color.yellow()

            embed.add_field(name="Moderated Account", value=str(account), inline=False)
            embed.add_field(name="Platform", value=platform, inline=False)
            embed.add_field(name="Reason for Moderation", value=mod_reason, inline=False)
            embed.add_field(name="Information Provided to Staff", value=appeal_info, inline=False)

            if decision_time:
                embed.add_field(name="Decision", value=decision_option.upper(), inline=False)
                embed.add_field(name="Decision Time", value=f"<t:{int(decision_time)}:f>", inline=False)
                embed.add_field(name="Reason for Decision", value=decision_reason, inline=False)

            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            return await send_error(interaction, f"No such appeal under ID `{id}` was found! Please try again using a valid id.", True)