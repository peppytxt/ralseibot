import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from pymongo import MongoClient
from cogs.moeda import setup as economia_setup

load_dotenv()

TOKEN = os.getenv("TOKEN")
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", ".")
DATA_DIR = os.getenv("DATA_DIR", "data")
MONGO_URL = os.getenv("MONGO_URL")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# Criar pasta data
os.makedirs(DATA_DIR, exist_ok=True)

# ================================
#      MongoDB
# ================================
try:
    mongo_client = MongoClient(MONGO_URL)
    bot.db = mongo_client["ralsei_bot"]
    print("MongoDB conectado com sucesso!")
except Exception as e:
    print("Erro ao conectar no MongoDB:", e)
    bot.db = None

# ================================
#       📌 Lista de COGS
# ================================
COGS = [
    "cogs.xp",
    "cogs.profile",
    "cogs.8ball",
    "cogs.economy",
    "cogs.avatar",
    "cogs.tickets",
    "cogs.fun",
    "cogs.help_menu",
]

async def load_all_extensions():
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"Carregado: {cog}")
        except Exception as e:
            print(f"Falha ao carregar {cog}: {e}")

# ================================
#         EVENTOS
# ================================
@bot.event
async def on_ready():
    print(f"Bot online como {bot.user} :3 (ID: {bot.user.id})")

@bot.event
async def setup_hook():
    await load_all_extensions()

    # Carregar comandos da economia
    try:
        economia_setup(bot.tree)
    except Exception as e:
        print("Erro economia:", e)

    # Sincronizar slash commands
    try:
        await bot.tree.sync()
        print("Slash commands sincronizados!")
    except Exception as e:
        print("Erro ao sincronizar:", e)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if hasattr(ctx.cog, "on_command_error"):
        return
    print("Erro tratado (main)", error)


if __name__ == "__main__":
    bot.run(TOKEN)
