import discord
from discord import app_commands
from discord.ext import commands
import os
import time
from PIL import Image, ImageDraw, ImageFont, ImageEmoji
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

    @app_commands.command(name="perfil", description="Mostra o perfil de um usuário")
    async def perfil(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        
        data = self.bot.get_cog("XP").col.find_one({"_id": member.id})
        if not data:
            return await interaction.response.send_message("Usuário sem dados registrados.")

        WIDTH = 931
        HEIGHT = 465
        BASE = os.path.dirname(__file__)
        FONT_PATH = os.path.join(BASE, "fonts", "DejaVuSans.ttf")

        font_big = ImageFont.truetype(FONT_PATH, 30)
        font_mid = ImageFont.truetype(FONT_PATH, 18)
        font_small = ImageFont.truetype(FONT_PATH, 14)

        FONT_EMOJI_PATH = os.path.join(BASE, "fonts", "Symbola.ttf") # Uma fonte comum para símbolos

        try:
            font_emoji = ImageFont.truetype(FONT_EMOJI_PATH, 14)
        except:
            font_emoji = font_small

        background = Image.open(os.path.join(BASE, "ProfileV1.png")).convert("RGBA")
        img = background.resize((WIDTH, HEIGHT))
        draw = ImageDraw.Draw(img)

        # --------------------- AVATAR ---------------------
        avatar = await self.fetch_avatar(member)
        avatar = avatar.resize((142, 142))
        mask = Image.new("L", (142, 142), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 142, 142), fill=255)
        img.paste(avatar, (46, 161), mask)

        # --------------------- NOME ---------------------
        draw.text((195, 185), member.display_name, font=font_big, fill=(0, 0, 0))

        # --------------------- SOBRE MIM ---------------------
        draw.text((275, 278), data.get("about", "Insira um SOBRE MIM :3")[:100], font=font_small, fill=(50, 50, 50))

        # --------------------- STATUS DE CASAMENTO (Campo abaixo do Nome) ---------------------
        partner_id = data.get("marry_id")
        if partner_id:
            try:
                partner = self.bot.get_user(partner_id) or await self.bot.fetch_user(partner_id)
                marry_text = f"❤️ Casado com: {partner.name}"
            except:
                marry_text = "❤️ Casado(a)"
        else:
            marry_text = "💔 Solteiro(a)"
        draw.text((285, 345), marry_text, font=font_small, fill=(200, 0, 0))

        # --------------------- BUFF DE CAFÉ (Campo ao lado do Casamento) ---------------------
        buff_until = data.get("fishing_buff_until", 0)
        now = time.time()
        if now < buff_until:
            rem = int((buff_until - now) / 60)
            buff_text = f"☕ Café: {rem}m restando"
        else:
            buff_text = "☕ Sem Buff ativo"
        draw.text((515, 345), buff_text, font=font_small, fill=(100, 70, 0))

        # --------------------- COLUNA XP ---------------------
        xp = data.get("xp_global", 0)
        xp_global_rank = self.bot.get_cog("XP").col.count_documents({"xp_global": {"$gt": xp}}) + 1
        level = xp // 1000
        xp_curr = xp % 1000
        ratio = xp_curr / 1000
        
        draw.rounded_rectangle((185, 400, 195 + 180, 412), radius=6, fill=(230, 230, 230))
        draw.rounded_rectangle((185, 400, 195 + (180 * ratio), 412), radius=6, fill=(100, 230, 100))
        draw.text((185, 415), f"Level {level} ({xp_curr}/1000) #{xp_global_rank}", font=font_small, fill=(0, 0, 0))

        # --------------------- COLUNA ECONOMIA (Vara) ---------------------
        rod = data.get("fishing_rod", {})
        ralcoins = data.get("coins", 0) 

        rank_global_ralcoins = self.bot.get_cog("XP").col.count_documents({"coins": {"$gt": ralcoins}}) + 1

        rod_name = rod.get("name", "Nenhuma")
        rod_dur = rod.get("durability", 0)
        
        draw.text((395, 430), f"💰 Ralcoins: {ralcoins} #{rank_global_ralcoins}", font=font_small, fill=(0, 0, 0))
        draw.text((395, 400), f"🎣 {rod_name}: {rod_dur}/100", font=font_small, fill=(0, 0, 0))

        # --------------------- COLUNA INVENTÁRIO (Balde) ---------------------
        inventory = data.get("inventory", [])
        inv_counts = {}
        for item in inventory:
            inv_counts[item] = inv_counts.get(item, 0) + 1
        
        inv_text = "\n".join([f"{qty}x {name}" for name, qty in list(inv_counts.items())[:3]])
        if not inv_text: inv_text = "Vazio..."
        draw.text((620, 400), inv_text, font=font_small, fill=(0, 0, 0))

        # --------------------- EXPORTAR ---------------------
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        await interaction.response.send_message(file=discord.File(buffer, "perfil.png"))

async def setup(bot):
    await bot.add_cog(Profile(bot))
