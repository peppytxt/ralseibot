import os
import discord
import random
import asyncio
from discord.ext import commands, tasks
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from cogs.challenges import AnagramStaffDecisionView, PhraseStaffDecisionView, StaffDecisionView, SuggestAnagramStarterLayout, SuggestPhraseModal, SuggestPhraseStarterLayout, SuggestStarterLayout
from cogs.confessions import ConfessionLayout, ConfessionStarterLayout
from cogs.moeda import setup as economia_setup

load_dotenv()

TOKEN = os.getenv("TOKEN")
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "[]")
DATA_DIR = os.getenv("DATA_DIR", "data")
MONGO_URL = os.getenv("MONGO_URL")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)
bot.remove_command('help')

os.makedirs(DATA_DIR, exist_ok=True)

# ================================
#      MongoDB
# ================================
try:
    mongo_client = AsyncIOMotorClient(MONGO_URL) 
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
    "cogs.economy_rps",
    "cogs.avatar",
    "cogs.challenges",
    "cogs.birthday",
    "cogs.tickets",
    "cogs.fun",
    "cogs.achievements",
    "cogs.welcome",
    "cogs.help",
    "cogs.ship",
    "cogs.admin",
    "cogs.confessions",
    "cogs.wanted"
]

async def load_all_extensions():
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"Carregado: {cog}")
        except Exception as e:
            print(f"Falha ao carregar {cog}: {e}")

# ================================
#         HOOK DE SETUP (UNIFICADO)
# ================================
@bot.event
async def setup_hook():
    # 1. Carrega todas as extensões primeiro
    await load_all_extensions()
    
    # 2. Registra TODAS as Views persistentes do bot para não morrerem no restart
    bot.add_view(SuggestStarterLayout())
    bot.add_view(StaffDecisionView())
    bot.add_view(SuggestPhraseStarterLayout())
    bot.add_view(PhraseStaffDecisionView())
    bot.add_view(SuggestAnagramStarterLayout())
    bot.add_view(AnagramStaffDecisionView())
    bot.add_view(ConfessionStarterLayout())
    bot.add_view(ConfessionLayout(text="", num=0))
    print("🔄 Views persistentes (Quiz e Confissões) carregadas com sucesso!")

    ID_SERVIDOR = 1410006076400599235  
    guild_objeto = discord.Object(id=ID_SERVIDOR)

    bot.tree.copy_global_to(guild=guild_objeto)

    await bot.tree.sync(guild=guild_objeto)
    print(f"✅ Comandos locais sincronizados para o servidor: {ID_SERVIDOR}")

    # 3. Carregar comandos externos da economia
    try:
        economia_setup(bot.tree)
    except Exception as e:
        print("Erro economia:", e)

    # 4. Sincronizar slash commands com o Discord
    try:
        await bot.tree.sync()
        print("Slash commands sincronizados!")
    except Exception as e:
        print("Erro ao sincronizar:", e)

# ================================
#         EVENTOS
# ================================
@bot.event
async def on_ready():
    if not status_task.is_running():
        status_task.start()
    print(f"Bot online como {bot.user} :3 (ID: {bot.user.id})")

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

# ================================
#         TASKS
# ================================
@tasks.loop(seconds=30)
async def status_task():
    guilds = len(bot.guilds)
    users = len(set(bot.get_all_members()))

    statuses = [
        discord.Game(name="DELTARUNE"),
        discord.Game(name=f"Atualmente em {guilds} servidores"),
        discord.Activity(
            type=discord.ActivityType.watching,
            name=f"Interagindo com {users} pessoas"
        )
    ]

    await bot.change_presence(
        status=discord.Status.online,
        activity=random.choice(statuses)
    )

if __name__ == "__main__":
    bot.run(TOKEN)