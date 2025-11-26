import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw
from io import BytesIO

class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="perfil", description="Mostra o perfil de um usuário.")
    async def perfil(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user

        # Criar imagem simples
        img = Image.new("RGB", (600, 300), (45, 45, 45))
        draw = ImageDraw.Draw(img)

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        await interaction.response.send_message(
            file=discord.File(buffer, filename="perfil.png")
        )


async def setup(bot):
    await bot.add_cog(Profile(bot))
