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
    def __init__(
        self,
        cog,
        interaction: discord.Interaction,
        page: int,
        page_size: int,
        build_func,
        get_rank_func
    ):
        super().__init__(timeout=60)

        self.cog = cog
        self.interaction = interaction
        self.page = page
        self.page_size = page_size
        self.build_func = build_func
        self.get_rank_func = get_rank_func
        self.author_id = interaction.user.id
        self.message = None


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
        
    @discord.ui.button(label="📍", style=discord.ButtonStyle.primary)
    async def my_position(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message(
                "❌ Apenas quem executou o comando pode usar.",
                ephemeral=True
            )

        rank = self.get_rank_func(interaction.user.id)

        if rank is None:
            return await interaction.response.send_message(
                "❌ Você não está no ranking.",
                ephemeral=True
            )

        self.page = (rank - 1) // self.page_size

        embed = await self.build_func(
            interaction,
            self.page,
            self.page_size
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.interaction.user.id:
            return await interaction.response.send_message(
                "❌ Apenas quem usou o comando pode interagir.",
                ephemeral=True
            )

        self.page += 1

        embed = await self.build_func(
            interaction,
            self.page,
            self.page_size
        )

        await interaction.response.edit_message(embed=embed, view=self)

        
        
    async def get_user_rank(self, user: discord.Member):
        # RANK GLOBAL
        if self.build_func == self.cog.build_rank_embed:
            data = self.cog.col.find_one({"_id": user.id})
            if not data:
                return None

            xp = data.get("xp_global", 0)
            return self.cog.col.count_documents(
                {"xp_global": {"$gt": xp}}
            ) + 1

        # RANK LOCAL
        if self.build_func == self.cog.build_local_rank_embed:
            guild_id = str(self.interaction.guild.id)

            data = self.cog.col.find_one({"_id": user.id})
            if not data:
                return None

            xp = data.get("xp_local", {}).get(guild_id, {}).get("xp", 0)

            return self.cog.col.count_documents({
                f"xp_local.{guild_id}.xp": {"$gt": xp}
            }) + 1
            
        # RANK COINS
        if self.build_func == self.cog.build_rankcoins_embed:
            data = self.cog.col.find_one({"_id": user.id})
            if not data:
                return None

            coins = data.get("coins", 0)
            return self.cog.col.count_documents(
                {"coins": {"$gt": coins}}
            ) + 1
        return None

class VoiceXP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_join_times = {}

    @property
    def col(self):
        return self.bot.get_cog("XP").col

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        print(
            f"[VOICE] {member} | "
            f"{before.channel} -> {after.channel} | "
            f"mute={after.self_mute} deaf={after.self_deaf}"
        )
        if member.bot:
            return

        user_id = member.id

        def is_counted(state):
            return not (state.self_mute or state.self_deaf or state.mute or state.deaf)

        if before.channel and not after.channel:
            join_time = self.voice_join_times.pop(user_id, None)
            if join_time and is_counted(before):
                elapsed = time.time() - join_time
                await self._process_voice_time(member, elapsed)

        elif before.channel and after.channel:
            join_time = self.voice_join_times.pop(user_id, None)
            if join_time and is_counted(before):
                elapsed = time.time() - join_time
                await self._process_voice_time(member, elapsed)

            if is_counted(after):
                self.voice_join_times[user_id] = time.time()

        elif not before.channel and after.channel:
            if is_counted(after):
                self.voice_join_times[user_id] = time.time()


    async def _process_voice_time(self, member, elapsed_seconds):
        earned_xp = int(elapsed_seconds / 60)
        if earned_xp <= 0:
            return

        self.col.update_one(
            {"_id": member.id},
            {"$inc": {"xp_voice": earned_xp}},
            upsert=True
        )

class XP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        MONGO_URL = os.getenv("MONGO_URL")
        if not MONGO_URL:
            raise ValueError("❌ ERRO: Variável de ambiente MONGO_URL não encontrada!")

        self.client = MongoClient(MONGO_URL)
        self.db = self.client["ralsei_bot"]
        self.col = self.db["users"]

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

        if "xp_global" not in user:
            user["xp_global"] = user.get("xp", 0)
            updated = True

        if "last_xp_global" not in user:
            user["last_xp_global"] = user.get("last_xp", 0)
            updated = True

        if "xp_local" not in user:
            user["xp_local"] = {}
            updated = True

        if updated:
            self.col.update_one(
                {"_id": user_id},
                {"$set": user}
            )

        xp_global = user["xp_global"]
        last_global = user["last_xp_global"]
        local_data = user["xp_local"]

        # ============================
        #   XP GLOBAL
        # ============================
        if now - last_global >= 10:
            gained = random.randint(5, 15)
            await self.add_xp(message.author, gained)

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

            local_data[guild_id] = local

            self.col.update_one(
                {"_id": user_id},
                {"$set": {"xp_local": local_data}}
            )

        await self.bot.process_commands(message)
        
    xp_group = app_commands.Group(
        name="xp",
        description="Comandos relacionados a XP"
    )

    # ------------------------------
    # /xp - mostra XP do usuário
    # ------------------------------
    @xp_group.command(name="view", description="Mostra seu XP global e do servidor")
    async def xp_info(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        guild_id = str(interaction.guild.id)

        data = self.col.find_one({"_id": user.id})

        if not data:
            return await interaction.response.send_message(
                f"{user.mention} ainda não possui XP registrado."
            )

        xp_global = data.get("xp_global", 0)
        rank_global = self.col.count_documents({"xp_global": {"$gt": xp_global}}) + 1

        local_data = data.get("xp_local", {})
        xp_local = local_data.get(guild_id, {}).get("xp", 0)

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
    # /xp voice
    # ------------------------------
    @xp_group.command(name="voice", description="Veja seu XP de voz")
    async def xp_voice(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None
    ):
        target = user or interaction.user
        data = self.col.find_one({"_id": target.id}) or {}
        xp_voice = data.get("xp_voice", 0)

        await interaction.response.send_message(
            f"🎧 **XP de Voz de {target.display_name}:** {xp_voice}",
            ephemeral=False
        )

    # ------------------------------
    # /rank global
    # ------------------------------

    @rank_group.command(
        name="global",
        description="Mostra o ranking de XP global."
    )
    @app_commands.describe(page="Página do ranking (ex: 1, 2, 3...)")
    async def rank_global(
        self,
        interaction: discord.Interaction,
        page: app_commands.Range[int, 1, 50] | None = None
    ):
        page_size = 10
        page_index = (page - 1) if page else 0

        embed = await self.build_rank_embed(
            interaction,
            page_index,
            page_size
        )

        view = RankView(
            cog=self,
            interaction=interaction,
            page=page_index,
            page_size=page_size,
            build_func=self.build_rank_embed,
            get_rank_func=self.get_xp_rank
        )


        await interaction.response.send_message(
            embed=embed,
            view=view
        )

        view.message = await interaction.original_response()

    # ------------------------------
    # /rank local 
    # ------------------------------
        
    @rank_group.command(
        name="local",
        description="Mostra o ranking de XP deste servidor."
    )
    @app_commands.describe(page="Página do ranking (padrão: 1)")
    async def rank_local(
        self,
        interaction: discord.Interaction,
        page: app_commands.Range[int, 1, 50] = 1
    ):
        await interaction.response.defer()

        page_size = 10
        page_index = page - 1

        embed = await self.build_local_rank_embed(
            interaction,
            page_index,
            page_size
        )

        if embed is None:
            return await interaction.followup.send(
                "❌ Não há usuários suficientes para essa página.",
                ephemeral=True
            )

        view = RankView(
            cog=self,
            interaction=interaction,
            page=page_index,
            page_size=page_size,
            build_func=self.build_local_rank_embed,
            get_rank_func=self.get_xp_rank
        )

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
            pass
        
        
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
    await bot.add_cog(VoiceXP(bot))
