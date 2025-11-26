import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        
    @commands.command(name="perfil")
    async def profile(self, ctx, member:discord.Member = None):
        member = member or ctx.author
        
        img = Image.new("RGB", (600, 300), (45, 45, 45))
        draw = ImageDraw.Draw(img)
        
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        
        await ctx.send(file=discord.File(buffer, filename="perfil.png"))
        
async def setup(bot):
    print("CARREGANDO PROFILE.PY!")
    await bot.add_cog(Profile(bot))