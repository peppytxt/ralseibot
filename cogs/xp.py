import discord
from discord.ext import commands
from discord import ui
from discord import app_commands
from pymongo import MongoClient
import random
import time
from config import MONGO_URL  # ← Certifique-se que esse valor está no config.py

class XP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Conexão com MongoDB
        self.client = MongoClient(MONGO_URL)
        self.db = self.client["ralsei_bot"]
        self.col = self.db["users"]

        # Criar índice para melhorar o ranking (opcional, mas recomendado)
        self.col.create_index("users")

        print("Conectado ao MongoDB com sucesso!")

    # ------------------------------
    # EVENTO: ganhar XP ao mandar mensagem
    # ------------------------------
    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        user_id = message.author.id
        now = time.time()

        user = self.col.find_one({"_id": user_id})

        # Se não existe no banco, cria
        if user is None:
            self.col.insert_one({
                "_id": user_id,
                "xp": 0,
                "last_xp": 0
            })
            user = {"xp": 0, "last_xp": 0}

        # Cooldown de 10 segundos
        if now - user["last_xp"] >= 10:
            gained = random.randint(5, 15)

            self.col.update_one(
                {"_id": user_id},
                {"$set": {
                    "xp": user["xp"] + gained,
                    "last_xp": now
                }}
            )

        # Permitir comandos funcionarem
        await self.bot.process_commands(message)

    # ------------------------------
    # COMANDO /xp
    # ------------------------------
    @app_commands.command(name="xp", description="Mostra seu XP atual e seu rank.")
    async def xp_command(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user

        data = self.col.find_one({"_id": user.id})

        if not data:
            return await interaction.response.send_message(
                f"{user.mention} ainda não possui XP registrado no meu Banco de Dados."
            )

        xp_value = data["xp"]

        # Calcula rank contando quem tem mais XP
        rank = self.col.count_documents({"xp": {"$gt": xp_value}}) + 1

        await interaction.response.send_message(
            f"🏅 **{user.display_name}**\n"
            f"🔸 XP: **{xp_value}**\n"
            f"🔸 Rank: **#{rank}**"
        )

    # ------------------------------
    # COMANDO /rank — top 10
    # ------------------------------
    @app_commands.command(name="rank", description="Mostra o ranking dos usuários com mais XP.")
    async def rank_command(self, interaction: discord.Interaction):
        top = self.col.find().sort("xp", -1).limit(10)
        top = list(top)

        if not top:
            return await interaction.response.send_message("Ainda não há usuários com XP registrado.")

        description = ""

        for pos, user in enumerate(top, start=1):
            user_id = user["_id"]

            # Primeiro tenta pegar pelo servidor
            member = interaction.guild.get_member(user_id)

            if member:
                name = member.display_name
            else:
                try:
                    # Busca o usuário via API mesmo fora do servidor
                    fetched_user = await interaction.client.fetch_user(user_id)
                    name = fetched_user.name
                except:
                    name = f"Usuário desconhecido ({user_id})"

            description += f"**#{pos}** — {name} — **{user['xp']} XP**\n"

        embed = discord.Embed(
            title="🏆 Ranking de XP — Top 10",
            description=description,
            color=discord.Color.gold()
        )
        
        await interaction.response.send_message(embed=embed)
        
# -------------------------------------


async def setup(bot):
    await bot.add_cog(XP(bot))
