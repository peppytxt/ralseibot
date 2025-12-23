import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
import random
import time
import os

XP_PER_LEVEL = 1000
LEVEL_REWARD = 5000

RANK_PAGE_SIZE = 10
MAX_RANK_PAGE = 50

class RankView(discord.ui.View):
    def __init__(self, cog, interaction, page, page_size=10, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.author_id = interaction.user.id
        self.page = page
        self.page_size = page_size
        self.message = None
        self.build_func = cog.build_rank_embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Apenas quem executou o comando pode usar esses botões.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        if self.message:
            await self.message.edit(view=self)

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page <= 0:
            await interaction.response.defer()
            return

        self.page -= 1
        embed = await self.build_func(interaction, self.page, self.page_size)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        embed = await self.build_func(interaction, self.page, self.page_size)

        if embed is None:
            self.page -= 1
            await interaction.response.defer()
            return

        await interaction.response.edit_message(embed=embed, view=self)

class XP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        MONGO_URL = os.getenv("MONGO_URL")
        if not MONGO_URL:
            raise ValueError("❌ ERRO: Variável de ambiente MONGO_URL não encontrada!")

        # Conexão com MongoDB
        self.client = MongoClient(MONGO_URL)
        self.db = self.client["ralsei_bot"]
        self.col = self.db["users"]

        # Index para ranking (sem erro)
        self.col.create_index("xp_global")

        print("Conectado ao MongoDB com sucesso!")
        
    rank_group = app_commands.Group(name="rank", description="Comandos de ranking de XP.")
    # ------------------------------
    # Ganha XP ao mandar mensagem
    # ------------------------------
    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        guild_id = str(message.guild.id)  
        user_id = message.author.id
        now = time.time()

        user = self.col.find_one({"_id": user_id})

        # ----------------------------
        # CRIA NOVO USUÁRIO DO ZERO
        # ----------------------------
        if user is None:
            user = {
                "_id": user_id,
                "xp_global": 0,
                "last_xp_global": 0,
                "xp_local": {}
            }
            self.col.insert_one(user)
        updated = False

        # Caso era o formato antigo: "xp"
        if "xp_global" not in user:
            user["xp_global"] = user.get("xp", 0)
            updated = True

        if "last_xp_global" not in user:
            user["last_xp_global"] = user.get("last_xp", 0)
            updated = True

        if "xp_local" not in user:
            user["xp_local"] = {}
            updated = True

        # Se algo foi alterado, salva no banco
        if updated:
            self.col.update_one(
                {"_id": user_id},
                {"$set": user}
            )

        # Atualiza variáveis após migração
        xp_global = user["xp_global"]
        last_global = user["last_xp_global"]
        local_data = user["xp_local"]

        # ============================
        #   XP GLOBAL
        # ============================
        if now - last_global >= 10:
            gained = random.randint(5, 15)
            await self.add_xp(message.author, gained)

            # atualiza apenas o cooldown
            self.col.update_one(
                {"_id": user_id},
                {"$set": {"last_xp_global": now}}
            )

        # ============================
        #   XP LOCAL POR SERVIDOR
        # ============================
        local = local_data.get(guild_id, {"xp": 0, "last_xp": 0})

        if now - local["last_xp"] >= 10:
            gained = random.randint(5, 15)
            local["xp"] += gained
            local["last_xp"] = now

            # salva no dict e depois no Mongo
            local_data[guild_id] = local

            self.col.update_one(
                {"_id": user_id},
                {"$set": {"xp_local": local_data}}
            )

        await self.bot.process_commands(message)

    # ------------------------------
    # /xp — mostra XP do usuário
    # ------------------------------
    @app_commands.command(name="xp", description="Mostra seu XP global e do servidor.")
    async def xp_command(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        guild_id = str(interaction.guild.id)

        data = self.col.find_one({"_id": user.id})

        if not data:
            return await interaction.response.send_message(
                f"{user.mention} ainda não possui XP registrado."
            )

        ### ===== GLOBAL =====
        xp_global = data.get("xp_global", 0)
        rank_global = self.col.count_documents({"xp_global": {"$gt": xp_global}}) + 1

        ### ===== LOCAL =====
        local_data = data.get("xp_local", {})
        xp_local = local_data.get(guild_id, {}).get("xp", 0)

        # rank local (puxar apenas desse servidor!)
        rank_local = self.col.count_documents({
            f"xp_local.{guild_id}.xp": {"$gt": xp_local}
        }) + 1

        embed = discord.Embed(
            title=f"XP - {user.display_name}",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="🌍 XP Global",
            value=f"XP: **{xp_global}**\nRank global: **#{rank_global}**",
            inline=False
        )

        embed.add_field(
            name=f"🏠 XP Local - {interaction.guild.name}",
            value=f"XP: **{xp_local}**\nRank local: **#{rank_local}**",
            inline=False
        )

        await interaction.response.send_message(embed=embed)


    # ------------------------------
    # /rank global
    # ------------------------------


    @rank_group.command(
        name="global",
        description="Mostra o ranking global de XP."
    )
    async def rank_global(
        self,
        interaction: discord.Interaction
    ):
        await interaction.response.defer()

        page_size = 10
        page = 0

        embed = await self.build_rank_embed(
            interaction,
            page,
            page_size
        )

        if embed is None:
            return await interaction.followup.send(
                "❌ Não há usuários no ranking.",
                ephemeral=True
            )

        view = RankView(
            cog=self,
            interaction=interaction,
            page=page,
            page_size=page_size,
            timeout=60
        )

        message = await interaction.followup.send(
            embed=embed,
            view=view
        )

        view.message = message

    # ------------------------------
    # /rank local 
    # ------------------------------
        
    @rank_group.command(name="local", description="Mostra o ranking de XP deste servidor.")
    async def rank_local(self, interaction: discord.Interaction):
        await interaction.response.defer()

        page = 0
        page_size = 10

        embed = await self.build_local_rank_embed(
            interaction,
            page,
            page_size
        )

        if embed is None:
            return await interaction.followup.send(
                "❌ Não há XP registrado neste servidor.",
                ephemeral=True
            )

        view = RankView(
            cog=self,
            interaction=interaction,
            page=page,
            page_size=page_size,
            timeout=60
        )

        view.build_func = self.build_local_rank_embed

        message = await interaction.followup.send(
            embed=embed,
            view=view
        )

        view.message = message



    async def add_xp(self, user: discord.Member, amount: int):
        col = self.col

        data = col.find_one({"_id": user.id}) or {
            "xp_global": 0,
            "coins": 0,
            "dm_level": True
        }

        old_xp = data.get("xp_global", 0)
        old_level = old_xp // XP_PER_LEVEL

        new_xp = old_xp + amount
        new_level = new_xp // XP_PER_LEVEL

        col.update_one(
            {"_id": user.id},
            {"$set": {"xp_global": new_xp}},
            upsert=True
        )

        if new_level > old_level:
            levels_gained = new_level - old_level
            reward = LEVEL_REWARD * levels_gained

            col.update_one(
                {"_id": user.id},
                {"$inc": {"coins": reward}}
            )

            if data.get("dm_level", True):
                await self.send_level_up_dm(user, new_level, reward)



    def get_xp_rank(self, user_id: int):
        users = list(
            self.col.find().sort("xp_global", -1)
        )

        for i, u in enumerate(users, start=1):
            if u["_id"] == user_id:
                return i

        return None


    def get_coin_rank(self, user_id: int):
        users = list(
            self.col.find().sort("coins", -1)
        )

        for i, u in enumerate(users, start=1):
            if u["_id"] == user_id:
                return i

        return None

    async def send_level_up_dm(self, user: discord.Member, level: int, reward: int):
        xp_rank = self.get_xp_rank(user.id)
        coin_rank = self.get_coin_rank(user.id)

        embed = discord.Embed(
            title="🎉 Você subiu de nível!",
            description=(
                f"✨ **Novo nível:** {level}\n"
                f"💰 **Recompensa:** {reward} ralcoins\n\n"
                f"🏆 **Rank de XP:** #{xp_rank}\n"
                f"🏦 **Rank de Saldo:** #{coin_rank}\n\n"
                "🔕 Não quer receber essa DM?\n"
                "Use `/leveldm off`"
            ),
            color=discord.Color.gold()
        )

        embed.set_footer(text="Continue interagindo para ganhar mais recompensas!")

        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            pass  # usuário com DM fechada
        
        
    @app_commands.command(name="leveldm", description="Ativar ou desativar DM ao subir de nível")
    @app_commands.choices(
        estado=[
            app_commands.Choice(name="Ativado", value=1),
            app_commands.Choice(name="Desativado", value=0)
        ]
    )
    async def leveldm(
        self,
        interaction: discord.Interaction,
        estado: app_commands.Choice[int]
    ):
        enabled = bool(estado.value)

        self.col.update_one(
            {"_id": interaction.user.id},
            {"$set": {"dm_level": enabled}},
            upsert=True
        )

        await interaction.response.send_message(
            f"🔔 DM de level **{'ativada' if enabled else 'desativada'}**!",
            ephemeral=True
        )
        
    # ------------------ APAGAR DEPOIS ------------------ #
    @app_commands.command(name="addxp", description="(DEV) Adiciona XP para testes")
    async def addxp(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: int
    ):
        # Permissão
        if interaction.user.id != 274645285634834434:
            return await interaction.response.send_message(
                "❌ Você não tem permissão para usar este comando.",
                ephemeral=True
            )

        self.col.update_one(
            {"_id": user.id},
            {"$inc": {"xp_global": amount}},
            upsert=True
        )

        await interaction.response.send_message(
            f"🧪 XP de **{user.display_name}** aumentado em **{amount}**."
    )
    # -----------------------------------------------------
    
    async def build_rank_embed(self, interaction, page, page_size):
        skip = page * page_size

        cursor = (
            self.col.find()
            .sort("xp_global", -1)
            .skip(skip)
            .limit(page_size)
        )

        users = list(cursor)
        if not users:
            return None

        desc = ""
        start_pos = skip + 1

        for i, user in enumerate(users):
            pos = start_pos + i
            uid = user["_id"]
            xp = user.get("xp_global", 0)

            try:
                discord_user = interaction.client.get_user(uid) or await interaction.client.fetch_user(uid)
                name = discord_user.display_name
            except:
                name = f"Usuário ({uid})"

            if uid == interaction.user.id:
                desc += f"## ⭐ **#{pos} - {name.upper()}** • {xp} XP\n"
            else:
                desc += f"**#{pos} - {name}** • {xp} XP\n"

        embed = discord.Embed(
            title="🌍 Ranking Global de XP",
            description=desc,
            color=discord.Color.gold()
        )

        embed.set_footer(text=f"Página {page + 1}")
        return embed


    async def build_local_rank_embed(self, interaction, page, page_size):
        guild_id = str(interaction.guild.id)
        skip = page * page_size

        cursor = (
            self.col.find({f"xp_local.{guild_id}.xp": {"$exists": True}})
            .sort([(f"xp_local.{guild_id}.xp", -1)])
            .skip(skip)
            .limit(page_size)
        )

        users = list(cursor)
        if not users:
            return None

        desc = ""
        start_pos = skip + 1

        for i, user in enumerate(users):
            pos = start_pos + i
            uid = user["_id"]
            xp = user["xp_local"][guild_id]["xp"]

            member = interaction.guild.get_member(uid)
            name = member.display_name if member else f"Usuário ({uid})"

            if uid == interaction.user.id:
                desc += f"## ⭐ **#{pos} - {name.upper()}** • {xp} XP\n"
            else:
                desc += f"**#{pos} - {name}** • {xp} XP\n"

        embed = discord.Embed(
            title=f"🏠 Ranking Local - {interaction.guild.name}",
            description=desc,
            color=discord.Color.green()
        )

        embed.set_footer(text=f"Página {page + 1}")
        return embed


async def setup(bot):
    await bot.add_cog(XP(bot))
