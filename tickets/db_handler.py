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
                    moderated_account_id TEXT, 
                    moderated_platform TEXT,
                    is_open BOOLEAN DEFAULT TRUE,
                    appeal_info TEXT,
                    appeal_time REAL,
                    decision_time REAL,
                    decision_reason TEXT,
                    decision_staff_id INTEGER,
                    log_message_id INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    discord_category_id INTEGER PRIMARY KEY,
                    category_name TEXT,
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
            await db.commit()

    async def create_ticket(self, unique_id: str, ticket_user_id: int, ticket_channel_id: int, category_type: str, ticket_title: str, ticket_description: str):
        open_time = int(datetime.now().timestamp())

        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("INSERT INTO ticket_history (unique_id, ticket_user, ticket_channel_id, category_type, open_time, ticket_title, ticket_description) VALUES (?, ?, ?, ?, ?, ?, ?)", (unique_id, ticket_user_id, ticket_channel_id, category_type, open_time, ticket_title, ticket_description))
                await db.commit()

                log.info(f"Created a {category_type} ticket for {ticket_user_id}: {ticket_title} - {ticket_description}")
            except Exception as e:
                log.error(f"Unable to create a {category_type} ticket for {ticket_user_id}: {e}")

    async def close_ticket(self, ticket_channel_id: int, closed_by: int, reason: str):
        close_time = int(datetime.now().timestamp())

        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT ticket_user FROM ticket_history WHERE ticket_channel_id = ? AND is_open = TRUE", (ticket_channel_id))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    try:
                        await db.execute("UPDATE ticket_history SET is_open = FALSE, close_time = ?, closed_by = ?, close_reason = ? WHERE ticket_channel_id = ?", (close_time, closed_by, reason, ticket_channel_id))
                        await db.commit()

                        log.info(f"{closed_by} successfully closed ticket {ticket_channel_id} for {reason}")
                        return result[0]
                    except Exception as e:
                        log.warning(f"Found ticket channel {ticket_channel_id} in DB but something happened: {e}")
                else:
                    log.error(f"Unable to find ticket channel {ticket_channel_id} in DB")
            except Exception as e:
                log.error(f"Unable to close ticket channel {ticket_channel_id} in DB: {e}")

    async def add_ticket_log(self, ticket_channel_id: int, log_message_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT * FROM ticket_history WHERE ticket_channel_id = ?", (ticket_channel_id))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    try:
                        await db.execute("UPDATE ticket_history SET log_message_id = ? WHERE ticket_channel_id = ?", (log_message_id, ticket_channel_id))
                        await db.commit()

                        log.info(f"Successfully DB entry for ticket channel {ticket_channel_id} and log message {log_message_id}")
                    except Exception as e:
                        log.warning(f"Found ticket channel {ticket_channel_id} in DB but something happened: {e}")
                else:
                    log.error(f"Unable to find ticket channel {ticket_channel_id} in DB")
            except Exception as e:
                log.error(f"Unable to update ticket channel {ticket_channel_id} with log message in DB: {e}")

    async def existing_check(self, type: str, target: int):
        async with aiosqlite.connect(self.db_path) as db:
            match type:
                case "appeal":
                    try:
                        cursor = await db.execute("SELECT unique_id FROM appeal_history WHERE is_open = TRUE, appealer_id = ?", (target))
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
                        cursor = await db.execute("SELECT ticket_channel_id FROM ticket_history WHERE is_open = TRUE, ticket_user = ?", (target))
                        result = await cursor.fetchone()

                        if result:
                            return result[0]
                        else:
                            return False
                    except Exception as e:
                        log.error(f"Exception occured when finding duplicates for tickets: {e}")
                case "category":
                    try:
                        cursor = await db.execute("SELECT category_name FROM categories WHERE discord_category_id = ?", (target))
                        result = await cursor.fetchone()

                        if result:
                            return result[0]
                        else:
                            return False
                    except Exception as e:
                        log.error(f"Exception occured when finding duplicates for categories: {e}")
                case _:
                    log.warning(f"Invalid option ({type} for duplicate check.)")

    async def create_appeal(self, unique_id: str, moderated_account: str, moderated_platform: str, appeal_user_id: int, appeal_info: str, log_message_id: int):
        appeal_time = int(datetime.now().timestamp())

        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("INSERT INTO appeal_history (unique_id, appealer_id, moderated_account, moderated_platform, appeal_time, appeal_info, log_message_id) VALUES (?, ?, ?, ?, ?, ?, ?)", (unique_id, appeal_user_id, moderated_account, moderated_platform, appeal_time, appeal_info, log_message_id))
                await db.commit()

                log.info(f"Created an appeal for {appeal_user_id} for platform {moderated_platform}: {appeal_info} (Account ID: {moderated_account})")
            except Exception as e:
                log.error(f"Unable to create an appeal for {appeal_user_id}: {e}")

    async def close_appeal(self, log_message_id: int, decision_user: int, reason: str):
        decision_time = int(datetime.now().timestamp())

        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT unique_id FROM appeal_history WHERE log_message_id = ? AND is_open = TRUE", (log_message_id))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    try:
                        await db.execute("UPDATE appeal_history SET is_open = FALSE, decision_time = ?, closed_by = ?, decision_reason = ? WHERE log_message_id = ?", (decision_time, decision_user.id, reason, log_message_id))
                        await db.commit()

                        log.info(f"{decision_user} successfully closed appeal {result[0]} for {reason}")
                        return result[0]
                    except Exception as e:
                        log.warning(f"Found appeal {result[0]} in DB but something happened: {e}")
                else:
                    log.error(f"Unable to find appeal {result[0]} in DB")
            except Exception as e:
                log.error(f"Unable to close appeal {result[0]} in DB: {e}")


    async def create_category(self, title: str, description: str, team: int | None, category: int):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("INSERT INTO categories (discord_category_id, category_name, description, responsible_team_role) VALUES (?, ?, ?, ?)", (category, title, description, team))
                await db.commit()

                log.info(f"Successfully created category {title} - {description}. Category ID: {category} - Team ID: {team}")
            except Exception as e:
                log.error(f"Unable to create category {title} due to: {e}")

    async def del_category(self, category: int):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT category_name FROM categories WHERE discord_category_id = ?", (category))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    await db.execute("DELETE FROM categories WHERE discord_category_id = ?", (category))
                    await db.commit()

                    log.info(f"Successfully deleted category {result[0]} ({category.id}) from DB")
                else:
                    log.warning(f"Couldn't find category {result[0]} ({category.id}) in DB")
            except Exception as e:
                log.error(f"Unable to delete {category.name} due to: {e}")

    async def fetch_category(self, category: int):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT category_name FROM categories WHERE discord_category_id = ?", (category.id))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    title = result[0]

                    return title
                else:
                    return None
            except Exception as e:
                log.error(f"Unable to fetch {category.name} due to: {e}")

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
                        "category_id": result[0],
                        "title": result[1],
                        "description": result[2],
                        "team_id": result[3]
                        } for result in results
                    ]
                else:
                    return None
            except Exception as e:
                log.error(f"Unable to list all categories: {e}")

    async def add_blacklist(self,):
        pass

    async def del_blacklist(self,):
        pass

    async def fetch_blacklist(self,):
        pass