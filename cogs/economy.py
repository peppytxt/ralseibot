import discord
from discord import app_commands, ui
from discord.ext import commands
from datetime import datetime, timedelta, timezone
import os
import random
import time
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
        
        await interaction.response.send_message(content=f"✅ Você vendeu {self.fish['name']} por **{self.fish['price']} ralcoins**")
        self.stop()

    async def keep_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Essa vara não é sua!", ephemeral=True)

        self.cog.col.update_one(
            {"_id": interaction.user.id},
            {"$push": {"inventory": self.fish['name']}},
            upsert=True
        )
        
        await interaction.response.send_message(content=f"🪣 Você guardou **{self.fish['name']}** no seu balde!")
        self.stop()

class BaldeView(ui.View):
    def __init__(self, cog, user, inventory):
        super().__init__(timeout=60)
        self.cog = cog
        self.user = user
        self.inventory = inventory

    @ui.button(label="Vender Tudo", style=discord.ButtonStyle.success, emoji="💰")
    async def vender_tudo(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Este balde não é seu!", ephemeral=True)

        precos = {
            "Bota Velha": 10,
            "Sardinha": 150,
            "Atum Real": 800,
            "Tubarão Branco": 5000
        }

        total_ganho = 0
        for item in self.inventory:
            total_ganho += precos.get(item, 0)

        self.cog.col.update_one(
            {"_id": self.user.id},
            {
                "$set": {"inventory": []},
                "$inc": {"coins": total_ganho}
            }
        )

        await interaction.response.send_message(
            content=f"✅ Você vendeu todo o conteúdo do balde por **{total_ganho} ralcoins**!",
            embed=None,
        )

    @ui.button(label="Vender Tudo (Exceto Lendários)", style=discord.ButtonStyle.secondary, emoji="💰")
    async def vender_quase_tudo(self, interaction: discord.Interaction, button: ui.Button):
        user_data = self.cog.col.find_one({"_id": interaction.user.id}) or {}
        inventory = user_data.get("inventory", [])

        if not inventory:
            return await interaction.response.send_message("📭 Seu inventário está vazio!", ephemeral=True)

        fish_data = {
            "Bota Velha": {"rarity": "Lixo", "price": 10},
            "Sardinha": {"rarity": "Comum", "price": 150},
            "Atum Real": {"rarity": "Raro", "price": 800},
            "Tubarão Branco": {"rarity": "Lendário", "price": 5000}
        }

        a_vender_nomes = []
        a_manter_nomes = []
        lucro_total = 0

        for fish_name in inventory:
            data = fish_data.get(fish_name)
            
            if data and data["rarity"] == "Lendário":
                a_manter_nomes.append(fish_name)
            else:
                a_vender_nomes.append(fish_name)
                lucro_total += data["price"] if data else 0

        if not a_vender_nomes:
            return await interaction.response.send_message("💎 Você só tem itens Lendários! Esses eu não vendo.", ephemeral=True)

        self.cog.col.update_one(
            {"_id": interaction.user.id},
            {
                "$inc": {"coins": lucro_total},
                "$set": {"inventory": a_manter_nomes}
            }
        )

        success_view = ui.LayoutView()
        container = ui.Container(accent_color=discord.Color.gold())
        container.add_item(ui.TextDisplay(f"## 💰 Venda Coletiva"))
        container.add_item(ui.TextDisplay(
            f"Você vendeu **{len(a_vender_nomes)}** itens por **{lucro_total} ralcoins**.\n"
            f"📦 **Lendários Preservados:** {len(a_manter_nomes)}"
        ))
        success_view.add_item(container)

        await interaction.response.send_message(view=success_view, embeds=[])

class LojaView(ui.LayoutView):
    def __init__(self, cog):
        super().__init__(timeout=60)
        self.cog = cog

        container = ui.Container(accent_color=discord.Color.gold())

        container.add_item(ui.TextDisplay("## 🛒 Loja do Ralsei"))
        container.add_item(ui.Separator())

        item_vara = (
            "### Vara de Bambu 🎣\n"
            "Uma vara simples, mas confiável.\n\n"
            "💰 **Preço:** `1000 ralcoins`\n"
            "🛠️ **Durabilidade:** `100` (10 usos)"
        )
        container.add_item(ui.TextDisplay(item_vara))

        item_cafe = (
            "### Café Expresso ☕\n"
            "Reduz o cooldown da pesca para **30 segundos**.\n"
            "⏱️ **Duração:** `30 minutos` | 💰 **Preço:** `5000 ralcoins`"
        )
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay(item_cafe))

        row = ui.ActionRow()
        btn_comprar = ui.Button(
            label="Comprar Vara", 
            style=discord.ButtonStyle.success, 
            emoji="🎣"
        )
        btn_comprar.callback = self.comprar_vara
        row.add_item(btn_comprar)

        btn_cafe = ui.Button(label="Comprar Café", style=discord.ButtonStyle.success, emoji="☕")
        btn_cafe.callback = self.comprar_cafe
        
        row.add_item(btn_cafe)

        
        container.add_item(ui.Separator())
        container.add_item(row)
        self.add_item(container)

    async def comprar_vara(self, interaction: discord.Interaction):
        preco = 1000
        user_data = self.cog.col.find_one({"_id": interaction.user.id}) or {"coins": 0}

        current_rod = user_data.get("fishing_rod", {})
        if current_rod.get("durability", 0) > 20:
            return await interaction.response.send_message("⚠️ Sua vara atual ainda está boa! Use-a até ficar com menos de 20 de durabilidade para comprar uma nova.", ephemeral=True)
        
        if user_data.get("coins", 0) < preco:
            return await interaction.response.send_message("❌ Saldo insuficiente!", ephemeral=True)

        self.cog.col.update_one(
            {"_id": interaction.user.id},
            {
                "$inc": {"coins": -preco},
                "$set": {
                    "fishing_rod": {
                        "name": "Vara de Bambu",
                        "durability": 100
                    }
                }
            },
            upsert=True
        )

        await interaction.response.send_message("✅ Compra realizada com sucesso!", ephemeral=True)

    
    async def comprar_cafe(self, interaction: discord.Interaction):
        preco = 5000
        user_data = self.cog.col.find_one({"_id": interaction.user.id}) or {"coins": 0}

        if user_data.get("coins", 0) < preco:
            return await interaction.response.send_message("❌ Saldo insuficiente para o café!", ephemeral=True)

        expires_at = int(time.time() + (30 * 60))

        self.cog.col.update_one(
            {"_id": interaction.user.id},
            {
                "$inc": {"coins": -preco},
                "$set": {"fishing_buff_until": expires_at}
            },
            upsert=True
        )

        await interaction.response.send_message(f"☕ **Gole!** Você está energizado! Seu cooldown agora é de 30s até <t:{expires_at}:t>!", ephemeral=True)

class RankCoinsView(ui.LayoutView):
    def __init__(self, cog, interaction, is_local):
        super().__init__(timeout=120)
        self.cog = cog
        self.interaction = interaction
        self.is_local = is_local
        self.page = 0
        self.page_size = 5

    def build_interface(self, title, description):
        self.clear_items()

        # Define a cor baseada no modo (Ouro para Global, Verde para Local)
        color = discord.Color.gold() if not self.is_local else discord.Color.green()
        container = ui.Container(accent_color=color)
        
        # Adiciona o Embed dentro do Container
        container.add_item(ui.TextDisplay(f"## {title}"))
        container.add_item(ui.TextDisplay(description))
        
        # Linha de comandos (ActionRow)
        row = ui.ActionRow()
        
        btn_prev = ui.Button(emoji="⬅️", style=discord.ButtonStyle.gray, disabled=self.page == 0)
        btn_prev.callback = self.prev_page
        btn_current = ui.Button(label=f"Pág {self.page + 1}", style=discord.ButtonStyle.gray, disabled=True)
        btn_next = ui.Button(emoji="➡️", style=discord.ButtonStyle.gray)
        btn_next.callback = self.next_page
        
        row.add_item(btn_prev)
        row.add_item(btn_current)
        row.add_item(btn_next)
        
        container.add_item(row)
        self.add_item(container)

    async def update_display(self, interaction: discord.Interaction):
        result = await self.cog.build_rankcoins_embed(interaction, self.page, self.page_size, self.is_local)
        
        if not result:
            if self.page > 0:
                self.page -= 1
            return await interaction.response.send_message("❌ Não há mais páginas!", ephemeral=True)

        titulo, descricao = result 

        self.build_interface(titulo, descricao)
        await interaction.response.edit_message(view=self)

    async def next_page(self, interaction: discord.Interaction):
        self.page += 1
        await self.update_display(interaction)

    async def prev_page(self, interaction: discord.Interaction):
        self.page = max(0, self.page - 1)
        await self.update_display(interaction)

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

               
    async def build_rankcoins_embed(self, interaction, page: int, page_size: int, is_local: bool = False):
        if page < 0:
            page = 0

        skip = page * page_size
        
        # Filtro base: usamos BOT_ECONOMY_ID
        query = {
            "coins": {"$exists": True},
            "_id": {"$ne": BOT_ECONOMY_ID} 
        }

        if is_local:
            member_ids = [m.id for m in interaction.guild.members]
            query["_id"] = {"$in": member_ids, "$ne": BOT_ECONOMY_ID}

        cursor = self.col.find(query, {"coins": 1}).sort("coins", -1).skip(skip).limit(page_size)
        users = list(cursor)

        if not users:
            return None

        desc = ""
        start_pos = skip + 1

        for i, u in enumerate(users):
            pos = start_pos + i
            uid = u["_id"]
            coins = u.get("coins", 0)

            user = interaction.client.get_user(uid)
            if not user:
                try:
                    user = await interaction.client.fetch_user(uid)
                except:
                    user = None
            
            name = user.display_name if user else f"Usuário {uid}"

            if uid == interaction.user.id:
                desc += f"## ⭐ **#{pos} - {name.upper()}** • {coins} ralcoins\n"
            else:
                desc += f"**#{pos} - {name}** • {coins} ralcoins\n"

        titulo = "🏦 Rank Local de Ralcoins" if is_local else "🏦 Rank Global de Ralcoins"
        cor = discord.Color.green() if is_local else discord.Color.gold()

        return titulo, desc
        
    
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


    # Grupo principal /rankcoins
    rankcoins_group = app_commands.Group(name="rankcoins", description="Visualizar o ranking de Ralcoins")

    @rankcoins_group.command(name="global", description="Ranking global de Ralcoins")
    @app_commands.describe(page="Página do ranking")
    async def rank_global(self, interaction: discord.Interaction, page: app_commands.Range[int, 1, 50] = 1):
        await self._send_rank(interaction, page, is_local=False)

    @rankcoins_group.command(name="local", description="Ranking de Ralcoins neste servidor")
    @app_commands.describe(page="Página do ranking")
    async def rank_local(self, interaction: discord.Interaction, page: app_commands.Range[int, 1, 50] = 1):
        await self._send_rank(interaction, page, is_local=True)

    # Função auxiliar para evitar repetição de código
    async def _send_rank(self, interaction: discord.Interaction, page: int, is_local: bool):
        page_index = page - 1
        page_size = 10

        # Título e descrição
        result = await self.build_rankcoins_embed(interaction, page_index, page_size, is_local)
        
        if not result:
            return await interaction.response.send_message("❌ Sem dados.", ephemeral=True)

        titulo, descricao = result
        view = RankCoinsView(self, interaction, is_local)
        view.page = page_index
        view.build_interface(titulo, descricao) 

        await interaction.response.send_message(view=view)
        
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
                "❌ Você não tem ralcoins suficientes para essa transação.")

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
    @app_commands.describe(side="Escolha cara ou coroa", quantidade="Valor da aposta")
    @app_commands.choices(side=[app_commands.Choice(name="Cara", value="cara"), app_commands.Choice(name="Coroa", value="coroa")])
    async def bet_coinflip(self, interaction: discord.Interaction, side: app_commands.Choice[str], quantidade: app_commands.Range[int, 100, 100_000]):
        user_id = interaction.user.id
        valor_inicial = quantidade
        data = self.col.find_one({"_id": user_id}) or {}

        if quantidade < 100:
            return await interaction.response.send_message(
                "❌ A aposta mínima é de **100 ralcoins** :3.",
                ephemeral=True
            )

        bot_data = self.col.find_one({"_id": BOT_ECONOMY_ID}) or {}
        bot_coins = bot_data.get("coins", 0)

        if bot_coins < quantidade:
            return await interaction.response.send_message(
                "🏦 O bot não tem saldo suficiente para bancar essa aposta.", ephemeral=True)

        if data.get("coins", 0) < quantidade:
            return await interaction.response.send_message("❌ Você não tem ralcoins suficientes.")

        self.col.update_one({"_id": user_id}, {"$inc": {"coins": -quantidade}})

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

        view = CoinflipView(self, interaction, amount=quantidade, side=side.value, valor_inicial=valor_inicial)

        embed = discord.Embed(
            title="🪙 Coinflip - Vitória!",
            description=(
                f"🪙 Caiu **{result}**\n\n"
                f"💰 Você ganhou **+{quantidade*2} ralcoins**!\n"
                f"Quer dobrar ou parar?"
            ),
            color=discord.Color.green()
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

    @commands.hybrid_command(name="pescar", description="Tente a sorte no lago!")
    async def pescar(self, ctx: commands.Context):
        user_data = self.col.find_one({"_id": ctx.author.id}) or {}
        
        now = time.time()
        buff_until = user_data.get("fishing_buff_until", 0)

        is_buffed = now < buff_until
        cooldown_seconds = 30 if is_buffed else 600
        
        last_fish = user_data.get("last_fish", 0)
        tempo_passado = now - last_fish

        if tempo_passado < cooldown_seconds:
            restante = int(cooldown_seconds - tempo_passado)
            
            if restante > 60:
                msg = f"⏳ Seus braços estão cansados! Espere mais **{restante // 60} minutos**."
            else:
                msg = f"⚡ O café ainda faz efeito! Espere mais **{restante} segundos**."
            
            return await ctx.send(msg, ephemeral=True)

        vara = user_data.get("fishing_rod")
        if not vara or vara.get("durability", 0) <= 0:
            return await ctx.send("❌ Sua vara de pesca quebrou ou você não tem uma! Compre uma nova na `/loja`.", ephemeral=True)

        choices = [
            {"name": "Bota Velha", "rarity": "Lixo", "price": 10, "weight": 60},
            {"name": "Sardinha", "rarity": "Comum", "price": 150, "weight": 30},
            {"name": "Atum Real", "rarity": "Raro", "price": 800, "weight": 8},
            {"name": "Tubarão Branco", "rarity": "Lendário", "price": 5000, "weight": 2}
        ]
        fish = random.choices(choices, weights=[f['weight'] for f in choices], k=1)[0]

        self.col.update_one(
            {"_id": ctx.author.id},
            {
                "$set": {"last_fish": now},
                "$inc": {"fishing_rod.durability": -10}
            }
        )
        view = FishingLayout(ctx.author, fish, self)
        await ctx.send(view=view)

    @app_commands.command(name="balde", description="Veja os peixes que você guardou")
    async def balde(self, interaction: discord.Interaction):
        user_data = self.col.find_one({"_id": interaction.user.id})
        
        inventory = user_data.get("inventory", []) if user_data else []
        
        if not inventory:
            return await interaction.response.send_message(
                "🪣 Seu balde está vazio! Vá pescar algo primeiro.", 
                ephemeral=True
            )

        counts = {}
        for item in inventory:
            counts[item] = counts.get(item, 0) + 1

        lista_texto = ""
        for peixe, qtd in counts.items():
            lista_texto += f"• **{peixe}** x{qtd}\n"

        embed = discord.Embed(
            title=f"🪣 Balde de {interaction.user.display_name}",
            description=lista_texto,
            color=discord.Color.blue()
        )

        view = BaldeView(self, interaction.user, inventory)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="loja", description="Abre a loja de equipamentos")
    async def loja(self, interaction: discord.Interaction):
        view = LojaView(self)
        await interaction.response.send_message(view=view)


async def setup(bot):
    await bot.add_cog(Economy(bot))
