import discord
from discord import app_commands
from discord.ext import commands
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
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

        WIDTH = 900
        HEIGHT = 500
        img = Image.new("RGBA", (WIDTH, HEIGHT), (200, 200, 240, 255))

        # Fonte
        font_big = ImageFont.truetype("arial.ttf", 32)
        font_small = ImageFont.truetype("arial.ttf", 26)
        
        draw = ImageDraw.Draw(img)

        # Fundo roxo
        header_h = 230
        header = Image.new("RGBA", (WIDTH, header_h), (170, 110, 255, 255))
        img.paste(header, (0, 0))
        
        # --------------------- RALSEI ---------------------
        """
        BASE = os.path.dirname(__file__)
        ralsei_path = os.path.join(BASE, "ralsei.png")

        ralsei = Image.open(ralsei_path).convert("RGBA")
        ralsei = ralsei.resize((260, 260))

        ralsei_x = WIDTH - 270
        ralsei_y = -5

        img.paste(ralsei, (ralsei_x, ralsei_y), ralsei)
        """

        # --------------------- AVATAR ---------------------
        avatar = await self.fetch_avatar(member)
        avatar_size = 150
        avatar = avatar.resize((avatar_size, avatar_size))

        # Máscara circular
        mask = Image.new("L", (avatar_size, avatar_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)

        # Borda circular
        border_size = avatar_size + 20
        border = Image.new("RGBA", (border_size, border_size), (255, 255, 255, 255))
        bmask = Image.new("L", (border_size, border_size), 0)
        ImageDraw.Draw(bmask).ellipse((0, 0, border_size, border_size), fill=255)

        avatar_x = 50
        avatar_y = 135
        
        shadow_w = border_size
        shadow_h = int(border_size * 0.45)  # deixa só na parte de baixo

        shadow = Image.new("RGBA", (shadow_w, shadow_h), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)

        # Sombra elíptica preta com leve transparência
        shadow_draw.ellipse(
            (0, 0, shadow_w, shadow_h),
            fill=(0, 0, 0, 120)  # Ajuste o 120 para mais/menos opacidade
        )

        # Aplicar blur suave
        shadow = shadow.filter(ImageFilter.GaussianBlur(18))

        # Posição da sombra (um pouco abaixo do avatar)
        shadow_x = avatar_x
        shadow_y = avatar_y + border_size - int(shadow_h / 2)

        # Colar sombra na imagem
        img.paste(shadow, (shadow_x, shadow_y), shadow)

        img.paste(border, (avatar_x, avatar_y), bmask)
        img.paste(avatar, (avatar_x + 10, avatar_y + 10), mask)

        # --------------------- NOME ---------------------
        name_x = avatar_x + border_size + 30
        name_y = avatar_y + 40

        draw.text((name_x, name_y), member.name, font=font_big, fill=(0, 0, 0))

        # --------------------- LINHA ---------------------
        line_y = avatar_y + 90
        line_h = 5
        line_color = (255, 255, 255)

        avatar_right = avatar_x + border_size

        # Esquerda
        draw.rectangle((0, line_y, avatar_x, line_y + line_h), fill=line_color)

        # Direita
        draw.rectangle((avatar_right, line_y, WIDTH, line_y + line_h), fill=line_color)

        # --------------------- CAIXA SOBRE MIM ---------------------
        about_w = 520
        about_h = 130

        about_x = 230
        about_y = header_h + 30

        radius = 30

        about_box = Image.new("RGBA", (about_w, about_h), (0, 0, 0, 0))
        box_draw = ImageDraw.Draw(about_box)

        box_draw.rounded_rectangle(
            (0, 0, about_w, about_h),
            radius=radius,
            fill=(255, 255, 255, 255)
        )

        img.paste(about_box, (about_x, about_y), about_box)

        draw.text(
            (about_x + 25, about_y + 40),
            data.get("about", "Insira um SOBRE MIM aqui :3"),
            font=font_small,
            fill=(0, 0, 0)
        )

        # --------------------- BARRA XP ---------------------
        bar_label_x = 60
        bar_label_y = about_y + about_h + 20
        draw.text((bar_label_x, bar_label_y), "Progresso de XP", font=font_small, fill=(0, 0, 0))

        bar_x = 60
        bar_y = bar_label_y + 35
        bar_w = 700
        bar_h = 22

        # fundo da barra
        draw.rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), fill=(220, 220, 220))

        # progresso
        xp = data.get("xp_global", 0)
        level = xp // 100
        xp_next = (level + 1) * 1000
        ratio = xp / xp_next
        progress_w = int(bar_w * ratio)

        draw.rectangle((bar_x, bar_y, bar_x + progress_w, bar_y + bar_h), fill=(100, 230, 100))

        # --------------------- EXPORTAR ---------------------
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        await interaction.response.send_message(file=discord.File(buffer, "perfil.png"))


async def setup(bot):
    await bot.add_cog(Profile(bot))
