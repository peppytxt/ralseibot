import discord
from discord import app_commands, ui
from discord.ext import commands
from datetime import datetime, timedelta, timezone
import random
from cogs.xp import RankView
from views.coinflip import CoinflipView
from views.pay_confirm import PayConfirmView

BR_TZ = timezone(timedelta(hours=-3))

BOT_ECONOMY_ID = 0

class FishingLayout(ui.LayoutView):
    def __init__(self, user, fish_data, cog):
        super().__init__()
        self.user = user
        self.fish = fish_data
        self.cog = cog 

        container = ui.Container(accent_color=discord.Color.blue())
        container.add_item(ui.TextDisplay(f"### 🎣 Pescaria de {self.user.display_name}"))
        container.add_item(ui.Separator())

        rarity_colors = {"Lixo": "⚪", "Comum": "🟢", "Raro": "🔵", "Lendário": "🟡"}
        emoji = rarity_colors.get(self.fish['rarity'], "🐟")
        
        res_text = (
            f"Você jogou a linha e... **{self.fish['name']}**!\n"
            f"{emoji} **Raridade:** {self.fish['rarity']}\n"
            f"💰 **Valor de Venda:** {self.fish['price']} ralcoins"
        )
        container.add_item(ui.TextDisplay(res_text))
        
        row = ui.ActionRow()
        btn_sell = ui.Button(label="Vender agora", style=discord.ButtonStyle.success, emoji="💰")
        btn_keep = ui.Button(label="Guardar no Balde", style=discord.ButtonStyle.secondary, emoji="🪣")
        
        btn_sell.callback = self.sell_callback
        btn_keep.callback = self.keep_callback
        row.add_item(btn_sell)
        row.add_item(btn_keep)
        container.add_item(row)
        self.add_item(container)

    async def sell_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Essa vara não é sua!", ephemeral=True)
        
        self.cog.col.update_one(
            {"_id": interaction.user.id},
            {"$inc": {"coins": self.fish['price']}},
            upsert=True
        )
        
        await interaction.response.send_message(content=f"✅ Você vendeu {self.fish['name']} por **{self.fish['price']}! ralcoins**")
        self.stop()

    async def keep_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Essa vara não é sua!", ephemeral=True)

        self.cog.col.update_one(
            {"_id": interaction.user.id},
            {"$push": {"inventory": self.fish['name']}},
            upsert=True
        )
        
        await interaction.response.send_message(
            content=f"🪣 Você guardou **{self.fish['name']}** no seu balde!", 
            view=None
        )
        self.stop()

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.col = bot.get_cog("XP").col
        
        self.col.update_one(
            {"_id": BOT_ECONOMY_ID},
            {"$setOnInsert": {"coins": 0}},
            upsert=True
        )
        
    async def check_economy_achievements(self, user_id: int):
        user_data = self.col.find_one({"_id": user_id}) or {}
        coins = user_data.get("coins", 0)

        ach_cog = self.bot.get_cog("AchievementsCog")
        if ach_cog:
            if coins >= 100000:
                await ach_cog.give_achievement(user_id, "coins_100000")

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
                await self.check_economy_achievements(user_id)
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
        
        await self.check_economy_achievements(user_id)

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
            "coins": {"$gt": coins},
            "_id": {"$ne": BOT_ECONOMY_ID}
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
                {
                    "coins": {"$exists": True},
                    "_id": {"$ne": BOT_ECONOMY_ID}
                },
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
            {
                "coins": {"$exists": True},
                "_id": {"$ne": BOT_ECONOMY_ID}
            },
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
    
    # ------------------ PAY ------------------
    
    @app_commands.command(
        name="pay",
        description="Pague ralcoins para outro usuário"
    )
    @app_commands.describe(
        user="Usuário que receberá as ralcoins",
        quantidade="Quantidade de ralcoins",
        tempo="Tempo limite para confirmação (em minutos, padrão 15)"
    )
    async def pay(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        quantidade: app_commands.Range[int, 1, 1_000_000],
        tempo: app_commands.Range[int, 1, 60] | None = None
    ):


        timeout_minutes = tempo if tempo is not None else 15
        timeout_seconds = timeout_minutes * 60

        sender = interaction.user
        receiver = user

        if sender.id == receiver.id:
            return await interaction.response.send_message(
                "❌ Você não pode pagar a si mesmo.",
                ephemeral=True
            )

        if receiver.bot:
            return await interaction.response.send_message(
                "❌ Você não pode pagar bots.",
                ephemeral=True
            )

        sender_data = self.col.find_one({"_id": sender.id}) or {}
        sender_coins = sender_data.get("coins", 0)

        if sender_coins < quantidade:
            return await interaction.response.send_message(
                "❌ Você não tem ralcoins suficientes.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="⚠️ Confirmação de pagamento",
            description=(
                f"**{sender.display_name}**, você deseja pagar:\n\n"
                f"💰 **{quantidade} ralcoins**\n"
                f"👤 Para: **{receiver.display_name}**\n\n"
                "⚠️ **Ambos precisam confirmar para concluir**"
            ),
            color=discord.Color.orange()
        )

        view = PayConfirmView(
            cog=self,
            sender=sender,
            receiver=receiver,
            amount=quantidade,
            timeout_seconds=timeout_seconds
        )


        await interaction.response.send_message(
            content=f"{user.mention}, você recebeu uma solicitação de pagamento 💸",
            embed=embed,
            view=view
        )
        view.message = await interaction.original_response()

    
    @bet.command(name="coinflip", description="Aposte no cara ou coroa")
    @app_commands.describe(
        side="Escolha cara ou coroa",
        quantidade="Valor da aposta"
    )
    @app_commands.choices(
        side=[
            app_commands.Choice(name="Cara", value="cara"),
            app_commands.Choice(name="Coroa", value="coroa")
        ]
    )
    async def bet_coinflip(
        self,
        interaction: discord.Interaction,
        side: app_commands.Choice[str],
        quantidade: app_commands.Range[int, 100, 100_000]
    ):
        if quantidade < 100:
            return await interaction.response.send_message(
                "❌ A aposta mínima é de **100 ralcoins**.",
                ephemeral=True
            )

        bot_data = self.col.find_one({"_id": BOT_ECONOMY_ID}) or {}
        bot_coins = bot_data.get("coins", 0)

        if bot_coins < quantidade:
            return await interaction.response.send_message(
                "🏦 O bot não tem saldo suficiente para bancar essa aposta.",
                ephemeral=True
            )

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
            {"$inc": {"coins": -quantidade}}
        )

        result = random.choice(["cara", "coroa"])

        if result != side.value:
            self.col.update_one(
                {"_id": BOT_ECONOMY_ID},
                {"$inc": {"coins": quantidade}}
            )

            embed = discord.Embed(
                title="💥 Coinflip - Derrota!",
                description=(
                    f"🪙 Caiu **{result}**\n"
                    f"Você perdeu **{quantidade} ralcoins** 😢"
                ),
                color=discord.Color.red()
            )

            return await interaction.response.send_message(embed=embed)

        embed = discord.Embed(
            title="🪙 Coinflip - Vitória!",
            description=(
                f"🪙 Caiu **{result}**\n\n"
                f"💰 Você ganhou **{quantidade*2} ralcoins**!\n"
                f"Quer dobrar ou parar?"
            ),
            color=discord.Color.green()
        )

        view = CoinflipView(
            self,
            interaction,
            amount=quantidade
        )

        await interaction.response.send_message(
            embed=embed,
            view=view
        )

        view.message = await interaction.original_response()

    @commands.is_owner()
    @app_commands.command(
        name="bank_add",
        description="Adicionar ralcoins ao banco do bot"
    )
    @app_commands.describe(quantidade="Quantidade de ralcoins")
    async def bank_add(
        self,
        interaction: discord.Interaction,
        quantidade: app_commands.Range[int, 1, 10_000_000]
    ):
        self.col.update_one(
            {"_id": BOT_ECONOMY_ID},
            {"$inc": {"coins": quantidade}},
            upsert=True
        )

        await interaction.response.send_message(
            f"🏦 Banco do bot recebeu **{quantidade} ralcoins**.",
            ephemeral=True
        )

    @commands.is_owner()
    @commands.hybrid_command(name="pescar", description="Tente a sorte no lago!")
    async def pescar(self, ctx: commands.Context):
        choices = [
            {"name": "Bota Velha", "rarity": "Lixo", "price": 10, "weight": 60},
            {"name": "Sardinha", "rarity": "Comum", "price": 150, "weight": 30},
            {"name": "Atum Real", "rarity": "Raro", "price": 800, "weight": 8},
            {"name": "Tubarão Branco", "rarity": "Lendário", "price": 5000, "weight": 2}
        ]
        
        fish = random.choices(choices, weights=[f['weight'] for f in choices], k=1)[0]

        view = FishingLayout(ctx.author, fish, self)
        await ctx.send(view=view)


async def setup(bot):
    await bot.add_cog(Economy(bot))
