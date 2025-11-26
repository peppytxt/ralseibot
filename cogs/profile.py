import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import aiohttp
from io import BytesIO

class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.col = bot.get_cog("XP").col
        
    async def fetch_avatar(self, user):
        url = user.avatar.url if user.avatar else user.default_avatar.url
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                return Image.open(BytesIO(await resp.read())).convert("RGBA")

    @app_commands.command(name="perfil", description="Mostra o perfil de um usuário.")
    async def perfil(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user

        data = self.col.find_one({"_id": interaction.user.id})
        if not data:
            return await interaction.response.send_message("Você ainda não possui XP registrado.")

        avatar = await self.fetch_avatar(interaction.user)
        avatar = avatar.resize((220, 220))

        img = Image.new("RGBA", (600, 300), (45, 45, 45, 255))
        draw = ImageDraw.Draw(img)
        
        draw.rectangle([(0, 280), (900, 400)], fill=(44, 44, 44))
        
        mask = Image.new("L", (220, 220), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, 220, 220), fill=255)
        img.paste(avatar, (40, 90), mask)

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        await interaction.response.send_message(
            file=discord.File(buffer, filename="perfil.png")
        )


async def setup(bot):
    await bot.add_cog(Profile(bot))
