import aiosqlite
import logging
import discord
import uuid

from datetime import datetime

log = logging.getLogger("twilightcogs.tickets_rewrite")

class TicketDB:
    def __init__(self, db_path):
        self.db_path = db_path / "database.db"

    async def initialize(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_history (
                    opener_id INTEGER PRIMARY KEY,
                    ticket_id TEXT,
                    channel_id TEXT,
                    ticket_type TEXT,
                    is_open BOOLEAN DEFAULT TRUE,
                    open_time REAL,
                    close_time REAL,
                    open_reason TEXT,
                    close_reason TEXT,
                    log_message_id INTEGER
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
                CREATE TABLE IF NOT EXISTS appeal_history (
                    appeal_user_id INTEGER PRIMARY KEY,
                    moderated_account_id INTEGER,
                    platform TEXT,
                    appeal_status TEXT DEFAULT 'PENDING',
                    appeal_info TEXT,
                    appeal_id TEXT,
                    appeal_time REAL,
                    decision_time REAL,
                    decision_staff_id INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_categories (
                    category_name TEXT PRIMARY KEY,
                    category_id INTEGER,
                    description TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    team_role_id INTEGER
                )
            """)
            await db.commit()

    async def create_ticket(self, interaction, ticket_id, channel_id, ticket_type, open_time, open_reason):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("INSERT INTO ticket_history (opener_id, ticket_id, channel_id, ticket_type, open_time, open_reason) VALUES (?, ?, ?, ?, ?, ?)", (interaction.user.id, ticket_id, channel_id, ticket_type, open_time, open_reason))
                await db.commit()

                log.info(f"Created a DB entry for {interaction.user} ({interaction.user.id}). Ticket ID is {ticket_id}")
            except Exception as e:
                log.error(f"Unable to create a DB entry for {interaction.user} ({interaction.user.id}): {e}")

    async def close_ticket(self, target_id: int, close_reason: str):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT ticket_id FROM ticket_history WHERE channel_id = ?, is_open = TRUE", (target_id))
                result = await cursor.fetchone()
                await cursor.close()

                close_time = int(datetime.now().timestamp())

                if result:
                    await db.execute("UPDATE ticket_history SET is_open = FALSE, close_time = ?, close_reason = ? WHERE channel_id = ?", (close_time, close_reason, target_id))
                    await db.commit()

                    log.info(f"Updated open status to closed for ticket {result}")
                    return True
                else:
                    log.error(f"Unable to find a ticket in the database for channel ID {target_id}")
                    return False
            except Exception as e:
                log.error(f"Encountered an error while trying to perform a DB query: {e}")

    async def existing_ticket_check(self, interaction, ticket_type):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT channel_id FROM ticket_history WHERE opener_id = ?, ticket_type = ?", (interaction.user.id, ticket_type))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    log.info(f"Existing ticket channel {result[0]} found for {interaction.user} ({interaction.user.id}) under {ticket_type} in DB")
                    return result[0]
                else:
                    return False
            except Exception as e:
                log.error(f"Encountered an error while checking for existing tickets in DB: {e}")
    
    async def create_appeal(self, interaction, moderated_account_id, platform, appeal_info):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                appeal_id = uuid.uuid4().hex[:8]
                appeal_time = int(datetime.now().timestamp())

                await db.execute("INSERT INTO appeal_history (appeal_user_id, moderated_account_id, platform, appeal_info, appeal_id, appeal_time) VALUES (?, ?, ?, ?, ?, ?)", (interaction.user.id, moderated_account_id, platform, appeal_info, appeal_id, appeal_time))
                await db.commit()

                log.info(f"Created DB entry for appeal {appeal_id} for {interaction.user} ({interaction.user.id})")
            except Exception as e:
                log.error(f"Unable to create DB entry for appeal {appeal_id} for {interaction.user} ({interaction.user.id}). Error: {e}")

    async def close_appeal(self, interaction, appeal_user_id):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT appeal_id FROM appeal_history WHERE appeal_status = 'PENDING', appeal_user_id = ?", (appeal_user_id))
                result = await cursor.fetchone()

                if result:
                    await db.execute("UPDATE appeal_history SET appeal_status = 'CLOSED', decision_staff_id = ? WHERE appeal_id = ?", (interaction.user.id, result[0]))
                    await db.commit()

                    log.info(f"Updated appeal status in DB for appeal {result[0]}")
                else:
                    log.error(f"No appeal DB entry was found for user id {appeal_user_id}.")
                
                await cursor.close()
            except Exception as e:
                log.error(f"Encountered an error for DB while closing appeal: {e}")

    async def existing_appeal_check(self, interaction):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT appeal_id FROM appeal_history WHERE appeal_user_id = ?, appeal_status = 'PENDING'", (interaction.user.id))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    log.info(f"Existing appeal {result[0]} found for {interaction.user} ({interaction.user.id}) in DB")
                    return result[0]
                else:
                    return None
                
            except Exception as e:
                log.error(f"Encountered an error while checking for existing tickets in DB: {e}")

    async def create_blacklist(self, interaction, target_user_id, reason):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("INSERT INTO blacklist (user_id, staff_member_id, reason) VALUES (?, ?, ?)", (target_user_id, interaction.user.id, reason))
                await db.commit()

                log.info(f"Created blacklist DB entry for user id {target_user_id}")
            except Exception as e:
                log.error(f"Encountered an error creating a blacklist DB entry: {e}")

    async def remove_blacklist(self, target_user_id):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT 1 FROM blacklist WHERE user_id = ?", (target_user_id))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    await db.execute("DELETE FROM blacklist WHERE user_id = ?", (target_user_id))
                    await db.commit()

                    log.info(f"Deleted blacklist DB entry for user id {target_user_id}")
                else:
                    log.info(f"No blacklist DB entry matching user id {target_user_id}. Aborting deletion")
            except Exception as e:
                log.error(f"Encountered an error while removing a blacklist DB entry: {e}")

    async def existing_blacklist_check(self, target_user_id) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT 1 FROM blacklist WHERE user_id = ?", (target_user_id))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    log.info(f"Existing blacklist for user id {result[0]} found in DB")
                    return True
                else:
                    return False
            except Exception as e:
                log.error(f"Encountered an error while checking for existing blacklists in DB: {e}")

    async def save_category(self, category_name, description, team_role_id):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("INSERT INTO ticket_categories (category_name, description, team_role_id)", (category_name, description, team_role_id))
                await db.commit()

                log.info(f"Successfully created DB entry for new ticket category {category_name}")
            except Exception as e:
                log.error(f"Was unable to create a DB entry for a new ticket category ({category_name}) due to: {e}")

    async def delete_category(self, category_name):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT 1 FROM ticket_categories WHERE category_name = ?", (category_name))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    await db.execute("DELETE FROM ticket_categories WHERE category_name = ?", (category_name))
                    await db.commit()

                    log.info(f"Successfully delete ticket category {category_name}")
                else:
                    log.info(f"No ticket category named '{category_name}' was found in the DB")
            except Exception as e:
                log.error(f"Encountered an error while trying to delete a ticket category: {e}")

    async def get_category(self, category_name):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT category_name FROM ticket_categories WHERE category_name = ?", (category_name))
                result = cursor.fetchone()

                if result:
                    return result[0]
                else:
                    log.info(f"No category name found for {category_name}")
                    return None

            except Exception as e:
                pass

    async def modify_category_status(self, category_name, status: bool):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT 1 FROM ticket_categories WHERE category_name = ?", (category_name))
                result = await cursor.fetchone()
                await cursor.close()

                if result:
                    await db.execute("UPDATE ticket_categories SET is_active = ? WHERE category_name = ?", (status, category_name))
                    await db.commit()

                    log.info(f"Successfully set category '{category_name}' status to '{status}'")
            except Exception as e:
                log.warning(f"Unable to update category status for {category_name} due to: {e}")

    async def return_category_count(self):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT COUNT(*) FROM ticket_categories")
                result = await cursor.fetchone()[0]
                await cursor.close()

                log.info(f"Returned category count: {result}")
                return int(result)
            except Exception as e:
                log.warning(f"Unable to return category count due to: {e}")

    async def fetch_categories(self):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("SELECT category_name, description, is_active FROM ticket_categories")
                results = await cursor.fetchall()
                await cursor.close()

                log.info(f"Fetched categories successfully.")
                return [
                    {
                        "name": result[0],
                        "description": result[1],
                        "status": result[2]
                    }
                    for result in results
                ]
            except Exception as e:
                log.warning(f"Unable to fetch categories due to: {e}")