import discord
from discord.ext import commands
from discord import app_commands

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.col = bot.get_cog("XP").col

    @app_commands.command(
        name="rankcoins",
        description="Mostra o ranking global de moedas"
    )
    async def rankcoins(self, interaction: discord.Interaction):

        # busca top 10 mais ricos
        top = list(
            self.col.find({"coins": {"$gt": 0}})
            .sort("coins", -1)
            .limit(10)
        )

        if not top:
            return await interaction.response.send_message(
                "Ainda não há dados de economia.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="🏆 Ranking Global de Moedas",
            color=discord.Color.gold()
        )

        medals = ["🥇", "🥈", "🥉"]

        for i, user in enumerate(top):
            member = interaction.guild.get_member(user["_id"])

            name = member.name if member else f"Usuário {user['_id']}"
            coins = user.get("coins", 0)

            emoji = medals[i] if i < 3 else f"#{i+1}"

            embed.add_field(
                name=f"{emoji} {name}",
                value=f"💰 **{coins:,} moedas**",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))
