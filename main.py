import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from cogs.moeda import setup as economia_setup

load_dotenv()

TOKEN = os.getenv("TOKEN")
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", ".")
DATA_DIR = os.getenv("DATA_DIR", "data")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=None, intents=intents)

# Criar pasta data
os.makedirs(DATA_DIR, exist_ok=True)

COGS = [
    "cogs.xp",
    "cogs.profile",
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
        return  # evita duplicar

    print("Erro tratado (main)")

if __name__ == "__main__":
    bot.run(TOKEN)
