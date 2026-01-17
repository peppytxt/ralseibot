import discord
from discord import ui, app_commands
from discord.ext import commands

class AchievementsV2(ui.LayoutView):
    def __init__(self, user, user_data):
        super().__init__(timeout=120)
        self.user = user
        self.user_data = user_data

        # Criando o container (Layout V2)
        container = ui.Container(
            title=f"🏆 Conquistas de {user.display_name}",
            accent_color=discord.Color.gold()
        )
        
        # Exemplo de conteúdo do container
        container.add_item(ui.TextDisplay("Aqui estão suas medalhas e marcos no servidor!"))
        self.add_item(container)

class Achievements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="conquistas", description="Veja suas conquistas!")
    async def conquistas(self, interaction: discord.Interaction):

        user_data = {"achievements": ["first_message"]} 
        
        view = AchievementsV2(interaction.user, user_data)

        await interaction.response.send_message(
            view=view, 
            flags=discord.MessageFlags.is_components_v2()
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Achievements(bot))