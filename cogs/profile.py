import discord
from discord import app_commands
from discord.ext import commands
import os
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

        data = self.bot.get_cog("XP").col.find_one({"_id": member.id})
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

        # ------------------------ AVATAR ------------------------
        avatar = await self.fetch_avatar(member)
        avatar_size = 170
        avatar = avatar.resize((avatar_size, avatar_size))

        # Máscara circular
        mask = Image.new("L", (avatar_size, avatar_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)

        # Borda
        border_size = avatar_size + 20
        border = Image.new("RGBA", (border_size, border_size), (255, 255, 255, 255))
        border_mask = Image.new("L", (border_size, border_size), 0)
        ImageDraw.Draw(border_mask).ellipse((0, 0, border_size, border_size), fill=255)

        avatar_x = 50
        avatar_y = 50

        img.paste(border, (avatar_x, avatar_y), border_mask)
        img.paste(avatar, (avatar_x + 10, avatar_y + 10), mask)

        # ------------------------ NOME ------------------------
        name_x = avatar_x + border_size + 30
        name_y = avatar_y + 60

        draw.text((name_x, name_y), member.name, font=font_big, fill=(0, 0, 0))

        # ------------------------ RALSEI ------------------------
        BASE = os.path.dirname(__file__)
        ralsei_path = os.path.join(BASE, "ralsei.png")

        ralsei = Image.open(ralsei_path).convert("RGBA")
        ralsei = ralsei.resize((250, 250))

        ralsei_x = 900 - 270  # alinhado à direita
        ralsei_y = 10         # alinhado ao topo do header

        img.paste(ralsei, (ralsei_x, ralsei_y), ralsei)

        # ------------------------ CAIXA SOBRE MIM ------------------------
        about_x = 60
        about_y = avatar_y + border_size + 30
        about_w = 780
        about_h = 140

        about_box = Image.new("RGBA", (about_w, about_h), (255, 255, 255, 255))
        img.paste(about_box, (about_x, about_y), about_box)

        draw.text(
            (about_x + 20, about_y + 40),
            data.get("about", "Insira um SOBRE MIM aqui :3"),
            font=font_small,
            fill=(0, 0, 0)
        )

        # ------------------------ BARRA DE XP ------------------------
        bar_label_x = 60
        bar_label_y = about_y + about_h + 20
        draw.text((bar_label_x, bar_label_y), "Progresso de XP", font=font_small, fill=(0, 0, 0))

        bar_x = 60
        bar_y = bar_label_y + 40
        bar_w = 780
        bar_h = 25

        # fundo da barra
        draw.rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), fill=(220, 220, 220))

        # progresso real
        xp = data.get("xp_global", 0)
        level = xp // 1000
        xp_next = (level + 1) * 1000
        ratio = xp / xp_next
        progress_w = int(bar_w * ratio)

        draw.rectangle((bar_x, bar_y, bar_x + progress_w, bar_y + bar_h), fill=(100, 230, 100))

        # ------------------------ EXPORTAR ------------------------
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        await interaction.response.send_message(file=discord.File(buffer, "perfil.png"))


async def setup(bot):
    await bot.add_cog(Profile(bot))
