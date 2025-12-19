import discord
from discord.ext import commands
from discord import app_commands

class EconomyRank(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="rankcoins",
        description="Mostra o ranking dos 10 usuários mais ricos"
    )
    async def rankcoins(self, interaction: discord.Interaction):
        col = self.bot.get_cog("Economy").col

        # Busca top 10 por moedas
        top = col.find(
            {"coins": {"$exists": True}},
            {"_id": 1, "coins": 1}
        ).sort("coins", -1).limit(10)

        embed = discord.Embed(
            title="🏆 Ranking de Ralcoins",
            color=discord.Color.gold()
        )

        position = 1
        for user in top:
            member = interaction.guild.get_member(user["_id"])
            if not member:
                continue

            embed.add_field(
                name=f"{position}º • {member.name}",
                value=f"💰 {user['coins']} ralcoins",
                inline=False
            )
            position += 1

        if position == 1:
            embed.description = "Ninguém possui ralcoins ainda 😢"

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(EconomyRank(bot))
