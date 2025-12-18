import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone
import random


BR_TZ = timezone(timedelta(hours=-3))


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.col = bot.get_cog("XP").col


    # ------------------ DAILY ------------------
    @app_commands.command(name="daily", description="Colete suas moedas diárias")
    async def daily(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        now = datetime.now(BR_TZ)
        today = now.date()

        user = self.col.find_one({"_id": user_id})

        if user and "last_daily" in user:
            last_daily = user["last_daily"].astimezone(BR_TZ).date()
            if last_daily == today:
                return await interaction.response.send_message(
                    "❌ Você já coletou seu daily hoje!", ephemeral=True
                )

        coins = random.randint(1000, 3000)

        self.col.update_one(
            {"_id": user_id},
            {
                "$inc": {"coins": coins},
                "$set": {"last_daily": now}
            },
            upsert=True
        )

        await interaction.response.send_message(
            f"<:ralsei_love:1410029625358417952> Você coletou **{coins} ralcoins!** hoje!"
        )


    # ------------------ BALANCE ------------------
    @app_commands.command(name="balance", description="Veja seu saldo")
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user

        data = self.col.find_one({"_id": user.id})
        coins = data.get("coins", 0) if data else 0

        await interaction.response.send_message(
            f"💳 **Saldo de {user.display_name}:** {coins} ralcoins!"
        )

async def setup(bot):
    await bot.add_cog(Economy(bot))
