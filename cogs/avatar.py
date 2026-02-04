import discord
from discord import app_commands
from discord.ext import commands


class Avatar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="avatar", description="Veja o avatar de algum usuário")
    async def avatar(self, interaction: discord.Interaction, membro: discord.Member = None):
        
        membro = membro or interaction.user

        embed = (
            discord.Embed(
                description=f"{membro.mention} que bela pfp você tem!",
                colour=discord.Color.blurple()
            )
            .set_image(url=membro.avatar.url if membro.avatar else membro.default_avatar.url)
        )

        await interaction.response.send_message(embed=embed)
            
            
async def setup(bot):
    await bot.add_cog(Avatar(bot))
