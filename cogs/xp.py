import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
import random
import time
import os


class XP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # --- Pega a URL do Mongo do ambiente (Railway ou .env) ---
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
            xp_global += gained

            self.col.update_one(
                {"_id": user_id},
                {"$set": {
                    "xp_global": xp_global,
                    "last_xp_global": now
                }}
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
    # /rank global — top 10
    # ------------------------------
    @rank_group.command(
    name="global",
    description="Mostra o ranking de XP global."
    )
    async def rank_global(self, interaction: discord.Interaction):
        top = list(self.col.find().sort("xp_global", -1).limit(10))

        if not top:
            return await interaction.response.send_message(
                "Ainda não há usuários com XP registrado."
            )

        desc = ""

        for pos, user in enumerate(top, start=1):
            uid = user["_id"]
            xp = user.get("xp_global", 0)

            # nome
            try:
                discord_user = interaction.client.get_user(uid) or await interaction.client.fetch_user(uid)
                name = discord_user.name
            except:
                name = f"Usuário desconhecido ({uid})"

            desc += f"**#{pos} - {name}** - {xp} XP\n"

        embed = discord.Embed(
            title="🌍 Ranking Global - Top 10",
            description=desc,
            color=discord.Color.gold()
        )

        await interaction.response.send_message(embed=embed)
        
        
    # ------------------------------
    # /rank local — top 10
    # ------------------------------
        
    @rank_group.command(
        name="local",
        description="Mostra o ranking de XP apenas deste servidor."
    )
    async def rank_local(self, interaction: discord.Interaction):

        guild_id = str(interaction.guild.id)

        cursor = self.col.find(
            {f"xp_local.{guild_id}.xp": {"$exists": True}}
        ).sort(
            [(f"xp_local.{guild_id}.xp", -1)]
        ).limit(10)

        top = list(cursor)

        if not top:
            return await interaction.response.send_message(
                "Ainda não há usuários com XP local neste servidor."
            )

        desc = ""

        for pos, user in enumerate(top, start=1):
            uid = user["_id"]

            xp = user.get("xp_local", {}).get(guild_id, {}).get("xp", 0)

            member = interaction.guild.get_member(uid)

            if member:
                name = member.display_name
            else:
                try:
                    fetched = await interaction.client.fetch_user(uid)
                    name = fetched.name
                except:
                    name = f"Usuário desconhecido ({uid})"

            desc += f"**#{pos} - {name}** - {xp} XP\n"

        embed = discord.Embed(
            title=f"🏠 Ranking Local - {interaction.guild.name}",
            description=desc,
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(XP(bot))
