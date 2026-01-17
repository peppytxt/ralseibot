import discord
from discord import ui, app_commands
from discord.ext import commands

class AchievementsV2(ui.LayoutView):
    def __init__(self, user):
        super().__init__(timeout=120)
        
        # Como o ContainerConfig deu erro de atributo, 
        # vamos usar o Container seco primeiro para testar a comunicação.
        container = ui.Container()
        container.add_item(ui.TextDisplay(f"🏆 **Conquistas de {user.display_name}**"))
        container.add_item(ui.TextDisplay("Seu progresso atualizado no sistema V2."))
        
        self.add_item(container)

class Achievements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="conquistas", description="Teste de Components V2")
    async def conquistas(self, interaction: discord.Interaction):
        view = AchievementsV2(interaction.user)
        
        # AJUSTE DA FLAG: 
        # O erro sugeriu 'components_v2'. No discord.py, criamos o objeto MessageFlags
        # e definimos a flag como True.
        flags = discord.MessageFlags()
        flags.components_v2 = True 
        
        await interaction.response.send_message(
            view=view, 
            flags=flags
        )

async def setup(bot):
    await bot.add_cog(Achievements(bot))