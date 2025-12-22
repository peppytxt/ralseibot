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
    
    # ------------ REMOVER DEPOIS -------------------        
    def is_owner():
        async def predicate(interaction: discord.Interaction):
            return interaction.user.id == 274645285634834434
        return app_commands.check(predicate)

    @app_commands.command(name="perfil")
    @is_owner()  # REMOVER DEPOIS
    async def perfil(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user

        data = self.bot.get_cog("XP").col.find_one({"_id": member.id})
        if not data:
            return await interaction.response.send_message("Você ainda não possui XP registrado.")

        WIDTH = 931
        HEIGHT = 465
        
        # Fundo com imagem externa
        BASE = os.path.dirname(__file__)
        FONT_PATH = os.path.join(BASE, "fonts", "DejaVuSans.ttf")

        font_big = ImageFont.truetype(FONT_PATH, 32)
        font_small = ImageFont.truetype(FONT_PATH, 18)

        bg_path = os.path.join(BASE, "ProfileV1.png")

        background = Image.open(bg_path).convert("RGBA")
        background = background.resize((WIDTH, HEIGHT))

        img = background.copy()
        draw = ImageDraw.Draw(img)
        
        draw = ImageDraw.Draw(img)
        
        # --------------------- AVATAR ---------------------
        avatar = await self.fetch_avatar(member)
        avatar_size = 142
        avatar = avatar.resize((avatar_size, avatar_size))

        # Máscara circular
        mask = Image.new("L", (avatar_size, avatar_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)

        avatar_x = 45
        avatar_y = 161
        
        img.paste(avatar, (avatar_x, avatar_y), mask)

        # --------------------- NOME ---------------------
        name_x = avatar_x + 150
        name_y = avatar_y + 20

        draw.text((name_x, name_y), member.name, font=font_big, fill=(0, 0, 0))

        # --------------------- SOBRE MIM ---------------------

        about_x = 242
        about_y = 240      

        draw.text(
            (about_x + 25, about_y + 40),
            data.get("about", "Insira um SOBRE MIM :3"),
            font=font_small,
            fill=(0, 0, 0)
        )

        # --------------------- BARRA XP ---------------------
        bar_label_y = about_y + 120

        bar_x = 260
        bar_y = bar_label_y + 55
        bar_w = 400
        bar_h = 15

        radius = 12
        
        # fundo da barra
        draw.rounded_rectangle(
            (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h),
            radius=radius,
            fill=(255, 255, 255)
        )

        # progresso
        xp = data.get("xp_global", 0)
        level = xp // 1000
        xp_current = xp % 1000
        xp_next = 1000
        ratio = xp_current / xp_next

        progress_w = int(bar_w * ratio)

        draw.rounded_rectangle(
            (bar_x, bar_y, bar_x + progress_w, bar_y + bar_h),
            radius=radius,
            fill=(100, 230, 100)
        )

        # --------------------- TEXTO DO XP ---------------------
        xp_text = f"{xp_current}/{xp_next} • Nível {level}"

        text_x = bar_x + bar_w // 2
        text_y = bar_y + bar_h + 10

        bbox = draw.textbbox((0, 0), xp_text, font=font_small)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]

        # Centraliza
        draw.text((text_x - w // 2, text_y), xp_text, font=font_small, fill=(0, 0, 0))


        # --------------------- EXPORTAR ---------------------
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        await interaction.response.send_message(file=discord.File(buffer, "perfil.png"))


async def setup(bot):
    await bot.add_cog(Profile(bot))
