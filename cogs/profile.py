import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import aiohttp
from io import BytesIO

class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_avatar(self, user):
        url = user.avatar.url if user.avatar else user.default_avatar.url
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                return Image.open(BytesIO(await r.read())).convert("RGBA")

    @app_commands.command(name="perfil")
    async def perfil(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user

        data = self.bot.db.xp.find_one({"_id": member.id})
        if not data:
            return await interaction.response.send_message("Você ainda não possui XP registrado.")

        # Base do card
        img = Image.new("RGBA", (900, 550), (240, 240, 240, 255))
        draw = ImageDraw.Draw(img)

        # Fonte
        font_big = ImageFont.truetype("arial.ttf", 32)
        font_small = ImageFont.truetype("arial.ttf", 26)

        # Fundo roxo
        header = Image.new("RGBA", (900, 250), (170, 110, 255, 255))
        img.paste(header, (0, 0))

        # Avatar
        avatar = await self.fetch_avatar(member)
        avatar = avatar.resize((180, 180))

        mask = Image.new("L", (180, 180), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, 180, 180), fill=255)

        border = Image.new("RGBA", (200, 200), (255, 255, 255, 255))
        border_mask = Image.new("L", (200, 200), 0)
        draw_bmask = ImageDraw.Draw(border_mask)
        draw_bmask.ellipse((0, 0, 200, 200), fill=255)

        img.paste(border, (40, 70), border_mask)
        img.paste(avatar, (50, 80), mask)

        # Nome
        draw.text((260, 140), member.name, font=font_big, fill=(0, 0, 0))

        # Ralsei
        ralsei = Image.open("ralsei.png").convert("RGBA")
        ralsei = ralsei.resize((300, 300))
        img.paste(ralsei, (560, 0), ralsei)

        # Caixa de sobre mim
        about_box = Image.new("RGBA", (700, 130), (255, 255, 255, 255))
        img.paste(about_box, (100, 260), about_box)

        draw.text((120, 300), data.get("about", "Insira um SOBRE MIM aqui :3"), font=font_small, fill=(0, 0, 0))

        # Barra XP
        draw.text((100, 410), "Progresso de XP", font=font_small, fill=(0, 0, 0))

        draw.rectangle((100, 450, 800, 470), fill=(230, 230, 230))
        
        ratio = data["xp"] / data["xp_next"]
        bar_width = int(700 * ratio)

        draw.rectangle((100, 450, 100 + bar_width, 470), fill=(100, 230, 100))

        draw.text((100, 480), f"{data['xp']}/{data['xp_next']}", font=font_small, fill=(0, 0, 0))
        draw.text((650, 480), f"Nível {data['level']}", font=font_small, fill=(0, 0, 0))

        # Exportar
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        await interaction.response.send_message(file=discord.File(buffer, "perfil.png"))


async def setup(bot):
    await bot.add_cog(Profile(bot))