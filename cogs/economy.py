import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone
import random
from cogs.xp import RankView
from views.coinflip import CoinflipView

BR_TZ = timezone(timedelta(hours=-3))

BOT_ECONOMY_ID = 0

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.col = bot.get_cog("XP").col
        self.bot.tree.add_command(self.bet)
        
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

               
    async def build_rankcoins_embed(self, interaction, page: int, page_size: int):
        if page < 0:
            page = 0

        skip = page * page_size

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
        start_pos = skip + 1

        for i, u in enumerate(users):
            pos = start_pos + i
            uid = u["_id"]
            coins = u.get("coins", 0)

            user = interaction.client.get_user(uid)
            name = user.display_name if user else f"Usuário {uid}"

            if uid == interaction.user.id:
                desc += f"## ⭐ **#{pos} - {name.upper()}** • {coins} ralcoins\n"
            else:
                desc += f"**#{pos} - {name}** • {coins} ralcoins\n"


        embed = discord.Embed(
            title="🏦 Rank Global de Ralcoins",
            description=desc,
            color=discord.Color.gold()
        )

        embed.set_footer(text=f"Página {page + 1}")
        return embed
    
    
    def get_coin_rank(self, user_id: int) -> int | None:
        cursor = self.col.find(
            {"coins": {"$exists": True}},
            {"_id": 1}
        ).sort("coins", -1)

        for index, user in enumerate(cursor, start=1):
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
            page_index,
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
            get_rank_func=self.get_coin_rank
        )

        await interaction.response.send_message(
            embed=embed,
            view=view
        )

        view.message = await interaction.original_response()
        
    bet = app_commands.Group(
        name="bet",
        description="Sistema de apostas"
    )
    
    @bet.command(name="coinflip", description="Aposte no cara ou coroa")
    @app_commands.describe(
        side="Escolha cara ou coroa",
        quantidade="Valor da aposta"
    )
    async def bet_coinflip(
        self,
        interaction: discord.Interaction,
        side: app_commands.Choice[str],
        quantidade: app_commands.Range[int, 100, 100_000]
    ):
        user_id = interaction.user.id

        data = self.col.find_one({"_id": user_id}) or {}
        coins = data.get("coins", 0)

        if coins < quantidade:
            return await interaction.response.send_message(
                "❌ Você não tem ralcoins suficientes.",
                ephemeral=True
            )

        # Debita aposta inicial
        self.col.update_one(
            {"_id": user_id},
            {"$inc": {"coins": -quantidade}},
            upsert=True
        )

        result = random.choice(["cara", "coroa"])

        if result != side.value:
            embed = discord.Embed(
                title="💥 Coinflip — Derrota!",
                description=(
                    f"🪙 Caiu **{result}**\n"
                    f"Você perdeu **{quantidade} ralcoins** 😢"
                ),
                color=discord.Color.red()
            )

            return await interaction.response.send_message(embed=embed)

        # Vitória inicial
        embed = discord.Embed(
            title="🪙 Coinflip — Vitória!",
            description=(
                f"🪙 Caiu **{result}**\n\n"
                f"💰 Você ganhou **{quantidade} ralcoins**!\n"
                f"Quer dobrar ou parar?"
            ),
            color=discord.Color.green()
        )

        view = CoinflipView(
            cog=self,
            interaction=interaction,
            quantidade = quantidade * 2
        )

        await interaction.response.send_message(
            embed=embed,
            view=view
        )

        view.message = await interaction.original_response()



async def setup(bot):
    await bot.add_cog(Economy(bot))
