# =====================
# === main.py
# =====================
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from cogs.moeda import setup as economia_setup

# Carrega variáveis do .env (local). No Railway, variáveis já existem no ambiente.
load_dotenv()

TOKEN = os.getenv("TOKEN")
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", ".")
DATA_DIR = os.getenv("DATA_DIR", "data")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# Garante pasta "data"
os.makedirs(DATA_DIR, exist_ok=True)

COGS = [
    "cogs.xp",
    "cogs.tickets",
    "cogs.fun",
    "cogs.help_menu",
]

@bot.event
async def on_ready():
    print(f"Bot online como {bot.user} :3 (ID: {bot.user.id})")

    # Carregar cogs normais
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"Carregado: {cog}")
        except Exception as e:
            print(f"Falha ao carregar {cog}: {e}")

    # Carregar comandos da pasta economia (moeda)
    try:
        economia_setup(bot.tree)  # <-- AQUI ESTÁ CORRETO
        print("Comandos de economia carregados!")
    except Exception as e:
        print("Erro ao carregar comandos de economia:", e)

    # Sincronizar slash commands
    try:
        await bot.tree.sync()
        print("Slash commands sincronizados!")
    except Exception as e:
        print("Erro ao sincronizar slash commands:", e)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)


if __name__ == "__main__":
    bot.run(TOKEN)
