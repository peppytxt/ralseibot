# =====================
# === File: main.py
# =====================
import os
import discord
from discord.ext import commands
from config import TOKEN, COMMAND_PREFIX, DATA_DIR

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# garante pasta data
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

    # carregar cogs
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"Carregado: {cog}")
        except Exception as e:
            print(f"Falha ao carregar {cog}: {e}")

    # sincroniza os slash commands (global); para guild-only, passe guilds=[discord.Object(id=GUILD_ID)]
    try:
        await bot.tree.sync()
        print("Slash commands sincronizados!")
    except Exception as e:
        print("Erro ao sincronizar slash commands:", e)

    # registra views persistentes se algum cog adicionar (opcional)

@bot.event
async def on_message(message):
    # exemplo simples: não processa mensagens de bots
    if message.author.bot:
        return

    # permite que comandos de prefix funcionem junto com on_message
    await bot.process_commands(message)


if __name__ == "__main__":
    bot.run(TOKEN)


# =====================
# === File: cogs/tickets.py
# =====================
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, SelectOption, Button

class TicketDropdown(Select):
    def __init__(self):
        options = [
            SelectOption(label="Suporte", value="support", emoji="🛠️"),
            SelectOption(label="Denúncia", value="report", emoji="⚠️"),
        ]
        super().__init__(placeholder="Escolha o tipo de ticket...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        if value == "support":
            await interaction.response.send_message("Você abriu um ticket de suporte (exemplo).", ephemeral=True)
        elif value == "report":
            await interaction.response.send_message("Você abriu um ticket de denúncia (exemplo).", ephemeral=True)

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())
        self.add_item(Button(label="Abrir Ticket", style=discord.ButtonStyle.primary, custom_id="open_ticket_btn"))

    @discord.ui.button(label="Abrir Ticket", style=discord.ButtonStyle.primary, custom_id="open_ticket_btn2")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Exemplo simples: cria um thread ou canal
        channel = interaction.channel
        thread = await channel.create_thread(name=f"ticket-{interaction.user.id}", auto_archive_duration=1440)
        await interaction.response.send_message(f"Ticket criado: {thread.mention}", ephemeral=True)
        await thread.send(f"{interaction.user.mention} descreva seu problema aqui.")

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup_ticket", description="Cria um painel de ticket (apenas administradores)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_ticket(self, interaction: discord.Interaction):
        view = TicketView()
        embed = discord.Embed(title="Painel de Tickets", description="Clique no botão para abrir um ticket.")
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))

# =====================
# === File: cogs/fun.py
# =====================
import discord
from discord.ext import commands
from discord import app_commands
import random

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="dado", description="Rola um dado de 1 a 6")
    async def dado(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🎲 Número: {random.randint(1,6)}")

    @app_commands.command(name="say", description="Repete a mensagem")
    @app_commands.describe(mensagem="Mensagem a repetir")
    async def say(self, interaction: discord.Interaction, mensagem: str):
        await interaction.response.send_message(mensagem)

    @app_commands.command(name="8ball", description="Oráculo")
    async def _8ball(self, interaction: discord.Interaction, Pergunta: str):
        respostas = ["Sim", "Não", "Talvez", "Pergunte novamente"]
        await interaction.response.send_message(f"🎱 {random.choice(respostas)}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))

# =====================
# === File: cogs/help_menu.py
# =====================
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, SelectOption

class HelpSelect(Select):
    def __init__(self):
        options = [
            SelectOption(label="Diversão", value="fun", emoji="🎯"),
            SelectOption(label="Utilidade", value="util", emoji="⚙️"),
            SelectOption(label="Imagem", value="img", emoji="🖼️"),
        ]
        super().__init__(placeholder="Escolha uma categoria...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        v = self.values[0]
        if v == "fun":
            embed = discord.Embed(title="Comandos - Diversão", description="/dado, /say, /8ball", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        elif v == "util":
            embed = discord.Embed(title="Comandos - Utilidade", description="/ping, /userinfo, /avatar", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("Em breve...", ephemeral=True)

class HelpView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(HelpSelect())

class HelpMenu(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Abre o painel de ajuda")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Central de Ajuda", description="Escolha uma opção abaixo")
        await interaction.response.send_message(embed=embed, view=HelpView())

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpMenu(bot))
