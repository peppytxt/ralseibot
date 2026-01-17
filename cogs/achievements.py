import discord
from discord import ui, app_commands
from discord.ext import commands

class AchievementsV2(ui.LayoutView):
    def __init__(self, user):
        super().__init__(timeout=120)
        
        container = ui.Container()
        container.add_item(ui.TextDisplay(f"🏆 **Conquistas de {user.display_name}**"))
        container.add_item(ui.TextDisplay("Seu progresso de conquistas"))
        
        self.add_item(container)

class Achievements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="conquistas", description="Conquistas atingidas pelo usuário")
    async def conquistas(self, interaction: discord.Interaction):
        view = AchievementsV2(interaction.user)

        flags = discord.MessageFlags()
        flags.components_v2 = True
        
        
        try:
            await interaction.response.send_message(view=view)
        except Exception:
            await interaction.response.send_message(
                "Erro",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Achievements(bot))