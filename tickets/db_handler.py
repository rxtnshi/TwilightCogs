import aiosqlite
import logging
import discord
import uuid

from datetime import datetime

log = logging.getLogger("twilightcogs.ticketsv2")

class db:
    def __init__(self, db_path):
        self.db_path = db_path / "database.db"

    async def initialize(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_history (
                    unique_id TEXT PRIMARY KEY,
                    ticket_user INTEGER,
                    ticket_channel_id INTEGER,
                    category_type TEXT,
                    is_open BOOLEAN DEFAULT TRUE,
                    open_time REAL,
                    close_time REAL,
                    ticket_title TEXT,
                    ticket_description TEXT,
                    closed_by INTEGER,
                    close_reason TEXT,
                    log_message_id INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS appeal_history (
                    unique_id TEXT PRIMARY KEY,
                    appealer_id INTEGER,
                    moderated_account TEXT,
                    moderated_platform TEXT,
                    moderated_reason TEXT,
                    is_open BOOLEAN DEFAULT TRUE,
                    appeal_info TEXT,
                    appeal_time REAL,
                    decision_time REAL,
                    decision_option TEXT,
                    decision_reason TEXT,
                    decision_staff_id INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    category_name TEXT PRIMARY KEY,
                    discord_category_id INTEGER,
                    description TEXT,
                    responsible_team_role INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS blacklist (
                    user_id INTEGER PRIMARY KEY,
                    staff_member_id INTEGER,
                    reason TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS saved_views (
                    message_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    view_type TEXT,
                    appeal_id TEXT
                )
            """)
            await db.commit()

    async def create_ticket(self, unique_id: str, ticket_user_id: int, ticket_channel_id: int, category_type: str, ticket_title: str, ticket_description: str):
        open_time = int(datetime.now().timestamp())

        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("INSERT INTO ticket_history (unique_id, ticket_user, ticket_channel_id, category_type, open_time, ticket_title, ticket_description) VALUES (?, ?, ?, ?, ?, ?, ?)", (unique_id, ticket_user_id, ticket_channel_id, category_type, open_time, ticket_title, ticket_description,))
                await db.commit()

                log.info(f"Created a {category_type} ticket for {ticket_user_id}: {ticket_title} - {ticket_description}")
            except Exception as e:
                log.error(f"Unable to create a {category_type} ticket for {ticket_user_id}: {e}")

    async def close_ticket(self, ticket_channel_id: int, closed_by: int, reason: str, log_message_id: int):
        close_time = int(datetime.now().timestamp())

        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT ticket_user FROM ticket_history WHERE ticket_channel_id = ? AND is_open = TRUE", (ticket_channel_id,))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    try:
                        await db.execute("UPDATE ticket_history SET is_open = FALSE, close_time = ?, closed_by = ?, close_reason = ?, log_message_id = ? WHERE ticket_channel_id = ?", (close_time, closed_by, reason, log_message_id, ticket_channel_id,))
                        await db.commit()

                        log.info(f"{closed_by} successfully closed ticket {ticket_channel_id} for {reason}")
                        return result[0]
                    except Exception as e:
                        log.warning(f"Found ticket channel {ticket_channel_id} in DB but something happened: {e}")
                else:
                    log.error(f"Unable to find ticket channel {ticket_channel_id} in DB")
            except Exception as e:
                log.error(f"Unable to close ticket channel {ticket_channel_id} in DB: {e}")
    
    async def fetch_ticket(self, channel: int):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT unique_id, ticket_user, ticket_channel_id, category_type, is_open, open_time, close_time, ticket_title, ticket_description, closed_by, close_reason FROM ticket_history WHERE ticket_channel_id = ?", (channel,))
                results = await cursor.fetchone()
                await cursor.close()

                return {
                    "ticket_id": results[0],
                    "ticket_user": results[1],
                    "ticket_channel": results[2],
                    "category_type": results[3],
                    "is_open": results[4],
                    "open_time": results[5],
                    "close_time": results[6],
                    "title": results[7],
                    "description": results[8],
                    "closed_by": results[9],
                    "close_reason": results[10],
                }
            except Exception as e:
                log.error(f"Can't fetch ticket opener: {e}")

    async def fetch_ticket_history(self, user: int):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT unique_id, ticket_channel_id, log_message_id FROM ticket_history WHERE ticket_user = ?", (user,))
                results = await cursor.fetchall()

                if results:
                    return [
                        {
                            "ticket_id": result[0],
                            "ticket_channel": result[1],
                            "log_message_id": result[2]
                        } for result in results
                    ]
                
                return None
            except Exception as e:
                log.error(f"Exception occured when fetching ticket history for user {user}: {e}")

    async def existing_check(self, type: str, target: int):
        async with aiosqlite.connect(self.db_path) as db:
            match type:
                case "appeal":
                    try:
                        cursor = await db.execute("SELECT unique_id FROM appeal_history WHERE is_open = TRUE AND appealer_id = ?", (target,))
                        result = await cursor.fetchone()
                        await cursor.close()

                        if result:
                            return result[0]
                        else:
                            return False
                    except Exception as e:
                        log.error(f"Exception occured when finding duplicates for appeals: {e}")
                case "ticket":
                    try:
                        cursor = await db.execute("SELECT ticket_channel_id FROM ticket_history WHERE is_open = TRUE AND ticket_user = ?", (target,))
                        result = await cursor.fetchone()

                        if result:
                            return result[0]
                        else:
                            return False
                    except Exception as e:
                        log.error(f"Exception occured when finding duplicates for tickets: {e}")
                case "category":
                    try:
                        cursor = await db.execute("SELECT category_name FROM categories WHERE discord_category_id = ?", (target,))
                        result = await cursor.fetchone()

                        if result:
                            return result[0]
                        else:
                            return False
                    except Exception as e:
                        log.error(f"Exception occured when finding duplicates for categories: {e}")
                case _:
                    log.warning(f"Invalid option ({type} for duplicate check.)")

    async def create_appeal(self, unique_id: str, moderated_account: str, moderated_platform: str, moderated_reason: str, appeal_user_id: int, appeal_info: str, log_message_id: int):
        appeal_time = int(datetime.now().timestamp())

        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("INSERT INTO appeal_history (unique_id, appealer_id, moderated_account, moderated_platform, moderated_reason, appeal_time, appeal_info, log_message_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (unique_id, appeal_user_id, moderated_account, moderated_platform, moderated_reason, appeal_time, appeal_info, log_message_id,))
                await db.commit()

                log.info(f"Created an appeal for {appeal_user_id} for platform {moderated_platform}: {appeal_info} (Account ID: {moderated_account})")
            except Exception as e:
                log.error(f"Unable to create an appeal for {appeal_user_id}: {e}")
                raise Exception(f"Unable to create an appeal for {appeal_user_id}: {e}")

    async def close_appeal(self, log_message_id: int, decision_user: int, decision: str, reason: str):
        decision_time = int(datetime.now().timestamp())

        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT unique_id FROM appeal_history WHERE log_message_id = ? AND is_open = TRUE", (log_message_id,))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    try:
                        await db.execute("UPDATE appeal_history SET is_open = FALSE, decision_time = ?, decision_staff_id = ?, decision_reason = ?, decision_option = ? WHERE log_message_id = ?", (decision_time, decision_user, reason, decision, log_message_id,))
                        await db.commit()

                        log.info(f"{decision_user} successfully closed appeal {result[0]} for {reason}")
                        return result[0]
                    except Exception as e:
                        log.warning(f"Found appeal {result[0]} in DB but something happened: {e}")
                        raise Exception(f"Found appeal {result[0]} in DB but something happened: {e}")
                else:
                    log.error(f"Unable to find appeal {result[0]} in DB")
            except Exception as e:
                log.error(f"Unable to close appeal {result[0]} in DB: {e}")
                raise Exception(f"Unable to close appeal {result[0]} in DB: {e}")

    async def fetch_appeal(self, target: str):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT moderated_account, moderated_platform, moderated_reason, appeal_info, appeal_time, decision_time, decision_option, decision_reason, unique_id, appealer_id FROM appeal_history WHERE unique_id = ?", (target,))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    return {
                        "account": result[0],
                        "platform": result[1],
                        "reason": result[2],
                        "appeal_info": result[3],
                        "appeal_time": result[4],
                        "decision_time": result[5],
                        "decision_option": result[6],
                        "decision_reason": result[7],
                        "appeal_id": result[8],
                        "appealer_id": result[9]
                    }
                return None
            except Exception as e:
                log.error(f"Unable to fetch appeal {target}: {e}")

    async def create_category(self, title: str, description: str, team: int, category: int):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("INSERT INTO categories (discord_category_id, category_name, description, responsible_team_role) VALUES (?, ?, ?, ?)", (category, title, description, team,))
                await db.commit()

                log.info(f"Successfully created category {title} - {description}. Category ID: {category} - Team ID: {team}")
            except aiosqlite.IntegrityError:
                log.error(f"Unable to create category {title} due to it existing")
                raise aiosqlite.IntegrityError(f"Unable to create category {title} due to it existing already.")
            except Exception as e:
                log.error(f"Unable to create category {title} due to: {e}")
                raise Exception(f"Unable to create category {title} due to: `{e}`")

    async def del_category(self, category: int):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT category_name FROM categories WHERE discord_category_id = ?", (int(category),))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    await db.execute("DELETE FROM categories WHERE discord_category_id = ?", (category,))
                    await db.commit()

                log.info(f"Successfully deleted category {result[0]} ({category}) from DB")
                return result[0]
            except Exception as e:
                log.error(f"Unable to delete {category} due to: {e}")
                raise Exception(f"Unable to delete {category} due to: {e}")

    async def fetch_category(self, category: int):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT category_name FROM categories WHERE discord_category_id = ?", (category,))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    title = result[0]

                    return title
                else:
                    return None
            except Exception as e:
                log.error(f"Unable to fetch {category} due to: {e}")

    async def count_categories(self,):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT COUNT(*) FROM categories")
                result = await cursor.fetchone()
                await cursor.close()

                return result[0] if result[0] >= 1 else 0
            except Exception as e:
                log.error(f"Unable to fetch category count due to: {e}")

    async def list_categories(self):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT * FROM categories")
                results = await cursor.fetchall()
                await cursor.close()
                
                if results:
                    return [
                        {
                        "title": result[0],
                        "category_id": result[1],
                        "description": result[2],
                        "team_id": result[3]
                        } for result in results
                    ]
                else:
                    return None
            except Exception as e:
                log.error(f"Unable to list all categories: {e}")

    async def add_blacklist(self, target: int, staff_member: int, reason: str):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("INSERT INTO blacklist (user_id, staff_member_id, reason) VALUES (?, ?, ?)", (target, staff_member, reason,))
                await db.commit()
            except Exception as e:
                log.error(f"Unable to add user {target} to blacklist: {e}")

    async def del_blacklist(self, target: int):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT 1 FROM blacklist WHERE user_id = ?", (target,))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    await db.execute("DELETE FROM blacklist WHERE user_id = ?", (target,))
                    await db.commit()
            except Exception as e:
                log.error(f"Unable to remove user {target} from blacklist: {e}")

    async def fetch_blacklist(self, target: int):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT * FROM blacklist WHERE user_id = ?", (target,))
                results = await cursor.fetchone()
                await cursor.close()

                if results:
                    return {
                        "user_id": results[0],
                        "staff_member": results[1],
                        "reason": results[2]
                    }
                
                return None
            except Exception as e:
                log.error(f"Unable to fetch user {target} from blacklist: {e}")

    async def save_view(self, view_type: str, channel_id: int, message_id: int, appeal_id: str = None):
        async with aiosqlite.connect(self.db_path) as db:
            async def check_existing(channel_id):
                if view_type == "appeal-panel":
                    cursor = await db.execute("SELECT message_id FROM saved_views WHERE channel_id = ? AND appeal_id = ?", (channel_id, appeal_id,))
                else:
                    cursor = await db.execute("SELECT message_id FROM saved_views WHERE channel_id = ? AND view_type = ?", (channel_id, view_type,))
                result = await cursor.fetchone()

                if result:
                    await db.execute("DELETE FROM saved_views WHERE message_id = ?", (message_id,))
                    await db.commit()
                    log.info(f"Deleted {view_type} view with message id {message_id} since a duplicate entry was found.")
            
            try:
                match view_type:
                    case 'support-panel':
                        await check_existing(channel_id)    
                        await db.execute("INSERT INTO saved_views (view_type, message_id, channel_id) VALUES (?, ?, ?)", ('support-panel', message_id, channel_id,))
                        await db.commit()
                    case 'appeal-panel':
                        await check_existing(channel_id)
                        await db.execute("INSERT INTO saved_views (view_type, message_id, channel_id, appeal_id) VALUES (?, ?, ?, ?)", ('appeal-panel', message_id, channel_id, appeal_id))
                        await db.commit()
                    case 'ticket-view':
                        await check_existing(channel_id)
                        await db.execute("INSERT INTO saved_views (view_type, message_id, channel_id) VALUES (?, ?, ?)", ('ticket-view', message_id, channel_id,))
                        await db.commit()
                log.info(f"Saved view type {view_type} under channel {channel_id} with message id {message_id}")
            except Exception as e:
                log.error(f"Unable to save view to load on cog load: {e}")

    async def fetch_views(self):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT * FROM saved_views")
                results = await cursor.fetchall()
                await cursor.close()

                if results:
                    return [
                        {
                            "message_id": result[0],
                            "channel_id": result[1],
                            "view_type": result[2],
                            "appeal_id": result[3]
                        } for result in results
                    ]
                
                return False
            except Exception as e:
                log.error(f"Unable to fetch views: {e}")

    async def delete_view(self, message_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT 1 FROM saved_views WHERE message_id = ?", (message_id,))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    await db.execute("DELETE FROM saved_views WHERE message_id = ?", (message_id,))
                    await db.commit()
                    return True
                
                return False
            except Exception as e:
                log.error(f"Unable to delete view with message id {message_id}: {e}")