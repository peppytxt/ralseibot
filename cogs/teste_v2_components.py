import discord
from discord import ui

class RankV2(ui.LayoutView):
    def __init__(self):
        super().__init__()
        
        container = ui.Container(ui.TextDisplay("Isso aqui funciona?"))
        self.add_item(container)
        
@bot.tree.command(name="teste", description="testeeeeeeeeeeeee :3")
async def testerankv2(interaction: discord.Interaction):
    view = RankV2()
    await interaction.response.send_message(view=view, flags=discord.MessageFlags.IS_COMPONENTS_V2)