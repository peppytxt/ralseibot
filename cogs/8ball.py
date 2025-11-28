import discord
from discord import app_commands
from discord.ext import commands
import random


class ball8(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="8ball", description="Um oráculo")
    async def bola8(self, interaction: discord.Interaction, message: str):
        msg = ["Sim", "Não", "Talvez", "Provavelmente sim", "Provavelmente não", "Tente novamente...", "Quem sabe...", "Fake", "Verídico", "Sou inteligência artificial e não bola de cristal, bobão.", "Com certeza não", "Trouxa", "Não quero nem saber", "Não sei e nem quero saber", "Me dá robux que te conto", "Por você sim 👉👈😳", "fds", "Pelo meus cálculos sim", "Pelos meus cálculos não", "Preciso mesmo responder isso?", "Detergente", "Óbvio", "Nunca", "Jamais"]
        msgrandom = random.choice(msg)
        await interaction.response.send_message(f"{interaction.user}: {message}\n🎱 **{msgrandom}**")
        
async def setup(bot):
    await bot.add_cog(ball8(bot))