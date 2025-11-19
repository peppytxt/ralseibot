import discord
from discord.ext import commands
from discord import app_commands
import time
import random
from utils.database import users

class XPSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        user_id = message.author.id
        now = time.time()

        user = users.find_one({"_id": user_id})

        if not user:
            users.insert_one({
                "_id": user_id,
                "xp": 0,
                "last_xp": 0
            })
            user = {"xp": 0, "last_xp": 0}

        # cooldown
        if now - user["last_xp"] >= 10:
            gained = random.randint(5, 15)

            users.update_one(
                {"_id": user_id},
                {"$set": {"xp": user["xp"] + gained, "last_xp": now}}
            )

    @app_commands.command(name="xp", description="Mostra seu XP e ranking.")
    async def xp(self, interaction: discord.Interaction, user: discord.Member = None):

        user = user or interaction.user
        data = users.find_one({"_id": user.id})

        if not data:
            return await interaction.response.send_message("Nenhum XP registrado.")

        xp_value = data["xp"]

        # ranking
        rank = users.count_documents({"xp": {"$gt": xp_value}}) + 1

        await interaction.response.send_message(
            f"🏅 **{user.display_name}**\n"
            f"XP: **{xp_value}**\n"
            f"Rank: **#{rank}**"
        )

async def setup(bot):
    await bot.add_cog(XPSystem(bot))
