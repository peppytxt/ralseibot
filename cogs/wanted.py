import discord
from discord import app_commands
from discord.ext import commands
import io
from PIL import Image

class WantedCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="wanted", description="Procurado!")
    @app_commands.describe(usuario="O usuário que vai virar procurado (padrão: você)")
    async def wanted(self, interaction: discord.Interaction, usuario: discord.Member = None):
        alvo = usuario or interaction.user
        
        await interaction.response.defer()

        try:
            imagem_fundo = Image.open("../images/wanted.jpg").convert("RGBA")

            avatar_bytes = await alvo.display_avatar.read()

            imagem_avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")

            tamanho_avatar = (400, 400)
            imagem_avatar = imagem_avatar.resize(tamanho_avatar, Image.Resampling.LANCZOS)

            posicao_x = 250
            posicao_y = 180
            
            imagem_fundo.paste(imagem_avatar, (posicao_x, posicao_y), imagem_avatar)

            buffer = io.BytesIO()
            imagem_fundo.save(buffer, format="PNG")
            buffer.seek(0)

            arquivo_discord = discord.File(fp=buffer, filename="wanted.png")
            
            await interaction.followup.send(
                file=arquivo_discord
            )

        except Exception as e:
            print(f"Erro ao gerar comando de imagem: {e}")
            await interaction.followup.send("Ocorreu um erro ao processar a imagem do Wanted.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(WantedCog(bot))