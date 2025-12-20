import discord
from discord import app_commands
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Mostra todos os comandos disponíveis")
    async def help(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="🌟 Ralsei Bot — Central de Ajuda",
            description="Aqui estão todos os comandos disponíveis:",
            color=discord.Color.green()
        )

        embed.add_field(
            name="📈 XP & Progresso",
            value=(
                "`/xp` — Veja seu nível e experiência\n"
                "`/rank` — Ranking de XP"
            ),
            inline=False
        )

        embed.add_field(
            name="👤 Perfil",
            value=(
                "`/profile` — Veja seu perfil\n"
                "`/avatar` — Avatar de um usuário"
            ),
            inline=False
        )

        embed.add_field(
            name="💰 Economia",
            value=(
                "`/balance` — Veja seu saldo\n"
                "`/daily` — Recompensa diária\n"
                "`/rps` — Pedra Papel Tesoura com apostas"
            ),
            inline=False
        )

        embed.add_field(
            name="🎮 Diversão",
            value="`/8ball` — Pergunte à bola mágica",
            inline=False
        )

        embed.set_footer(
            text=f"Estou em {len(self.bot.guilds)} servidores 🌍"
        )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))
