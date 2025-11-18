import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import random
import time
import os

class XPSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Criar pasta data se não existir
        if not os.path.exists("data"):
            os.makedirs("data")

        # Conectar ao SQLite
        base_path = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_path, "../data/xp.db")

        self.con = sqlite3.connect(db_path)

        self.cur = self.con.cursor()

        # Criar tabela de XP
        self.cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            xp INTEGER,
            last_xp REAL
        )
        """)
        self.con.commit()
        
        print("Banco de dados aberto em:", os.path.abspath("data/xp.db"))

    # ------------------------------
    # EVENTO: ganhar XP ao mandar mensagem
    # ------------------------------
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        user_id = message.author.id
        now = time.time()

        # Verificar se já existe no DB
        self.cur.execute("SELECT xp, last_xp FROM users WHERE user_id=?", (user_id,))
        data = self.cur.fetchone()

        if data is None:
            self.cur.execute("INSERT INTO users (user_id, xp, last_xp) VALUES (?, ?, ?)",
                             (user_id, 0, 0))
            self.con.commit()
            data = (0, 0)

        xp, last_xp = data

        # Cooldown de 10 segundos por XP
        if now - last_xp >= 10:
            gained = random.randint(5, 15)
            xp += gained

            self.cur.execute("UPDATE users SET xp=?, last_xp=? WHERE user_id=?",
                             (xp, now, user_id))
            self.con.commit()
            
            
        await self.bot.process_commands(message)
    # ------------------------------
    # COMANDO /xp — mostra XP e ranking
    # ------------------------------
    @app_commands.command(name="xp", description="Mostra seu XP atual e seu rank.")
    async def xp_command(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user

        self.cur.execute("SELECT xp FROM users WHERE user_id=?", (user.id,))
        row = self.cur.fetchone()

        if row is None:
            return await interaction.response.send_message(
                f"{user.mention} ainda não possui XP registrado."
            )

        xp_value = row[0]

        # Calcular ranking
        self.cur.execute("SELECT COUNT(*) FROM users WHERE xp > ?", (xp_value,))
        rank = self.cur.fetchone()[0] + 1

        await interaction.response.send_message(
            f"🏅 **{user.display_name}**\n"
            f"🔸 XP: **{xp_value}**\n"
            f"🔸 Rank: **#{rank}**"
        )
        
    # ------------------------------
    # COMANDO /rank — mostra o top 10 usuários do servidor
    # ------------------------------
    @app_commands.command(name="rank", description="Mostra o ranking dos usuários com mais XP.")
    async def rank_command(self, interaction: discord.Interaction):
        # Buscar top 10 no banco
        self.cur.execute("SELECT user_id, xp FROM users ORDER BY xp DESC LIMIT 10")
        rows = self.cur.fetchall()

        if not rows:
            return await interaction.response.send_message("Ainda não há usuários com XP registrado.")

        description = ""

        # Montar ranking
        for pos, (user_id, xp) in enumerate(rows, start=1):
            user = interaction.guild.get_member(user_id)
            if user is None:
                name = f"Usuário desconhecido ({user_id})"
            else:
                name = user.display_name

            description += f"**#{pos}** — {name} — **{xp} XP**\n"

        embed = discord.Embed(
            title="🏆 Ranking de XP — Top 10",
            description=description,
            color=discord.Color.gold()
        )

        await interaction.response.send_message(embed=embed)


# NECESSÁRIO PARA COG FUNCIONAR
async def setup(bot):
    await bot.add_cog(XPSystem(bot))
    
    