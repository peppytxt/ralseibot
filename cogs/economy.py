import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone
import random
from cogs.xp import RankView

BR_TZ = timezone(timedelta(hours=-3))

BOT_ECONOMY_ID = 0

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.col = bot.get_cog("XP").col
        
        self.col.update_one(
            {"_id": BOT_ECONOMY_ID},
            {"$setOnInsert": {"coins": 0}},
            upsert=True
        )

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
            f"<:ralsei_love:1410029625358417952> Você coletou **{coins} ralcoins** no daily!"
        )


    # ------------------ BALANCE ------------------
    @app_commands.command(name="balance", description="Veja seu saldo")
    async def balance(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None
    ):
        if user is None:
            user = interaction.user
            user_id = user.id
            name = user.display_name
        elif user.bot:
            user_id = BOT_ECONOMY_ID
            name = "Ralsei"
        else:
            user_id = user.id
            name = user.display_name

        data = self.col.find_one({"_id": user_id}) or {}
        coins = data.get("coins", 0)

        rank = self.col.count_documents({
            "coins": {"$gt": coins}
        }) + 1

        await interaction.response.send_message(
            f"💳 **Saldo de {name}:** {coins} ralcoins\n"
            f"🏆 **Rank global:** #{rank}"
        )

               
    async def build_rankcoins_embed(
        self,
        interaction: discord.Interaction,
        page: int,
        page_size: int
    ):
        skip = (page - 1) * page_size

        users = list(
            self.col.find(
                {"coins": {"$exists": True}},
                {"coins": 1}
            )
            .sort("coins", -1)
            .skip(skip)
            .limit(page_size)
        )

        if not users:
            return None

        desc = ""

        for i, u in enumerate(users, start=skip + 1):
            user = interaction.client.get_user(u["_id"])
            name = user.display_name if user else f"Usuário {u['_id']}"
            coins = u.get("coins", 0)

            if u["_id"] == interaction.user.id:
                desc += f"## ⭐ **#{i} - {name.upper()}** • {coins} ralcoins\n"
            else:
                desc += f"**#{i} - {name}** • {coins} ralcoins\n"

        embed = discord.Embed(
            title="🏦 Ranking Global de Ralcoins",
            description=desc,
            color=discord.Color.gold()
        )

        embed.set_footer(text=f"Página {page}")
        return embed

    
    def get_coin_position(self, user_id: int) -> int | None:
        users = list(
            self.col.find(
                {"coins": {"$exists": True}}
            ).sort("coins", -1)
        )

        for index, user in enumerate(users, start=1):
            if user["_id"] == user_id:
                return index

        return None


      # ------------------ RANK GLOBAL ------------------
    @app_commands.command(name="rankcoins", description="Ranking global de ralcoins")
    @app_commands.describe(page="Página do ranking (1–50)")
    async def rankcoins(
        self,
        interaction: discord.Interaction,
        page: app_commands.Range[int, 1, 50] | None = None
    ):
        page_size = 5
        page_index = (page - 1) if page else 0

        embed = await self.build_rankcoins_embed(
            interaction,
            page_index + 1,
            page_size
        )

        if embed is None:
            return await interaction.response.send_message(
                "❌ Não há dados para essa página.",
                ephemeral=True
            )

        view = RankView(
            cog=self,
            interaction=interaction,
            page=page_index,
            page_size=page_size,
            build_func=self.build_rankcoins_embed,
            get_rank_func=self.get_coin_position
        )


        await interaction.response.send_message(
            embed=embed,
            view=view
        )

        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Economy(bot))
