import discord
from discord import ui, app_commands
from discord.ext import commands
from datetime import datetime

class ConfessionStarterLayout(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        container = ui.Container(accent_color=discord.Color.blurple())
        container.add_item(ui.TextDisplay(
            "## 🤫 Mural de Confissões Anônimas\n"
            "Clique abaixo para enviar sua confissão.\n\n"
        ))
        
        self.add_item(container)

    @ui.button(label="Enviar Desabafo", custom_id="btn_confess", style=discord.ButtonStyle.primary, emoji="📝")
    async def start_confess(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ConfessionModal(title="Nova Confissão"))

class ConfessionLayout(ui.LayoutView):
    def __init__(self, text, num, img_url=None):
        super().__init__(timeout=None) 
        container = ui.Container(accent_color=discord.Color.random())
        container.add_item(ui.TextDisplay(f"## 👤 Confissão Anônima (#{num:03d})\n\n{text}"))
        
        if img_url and img_url.startswith(("http", "https")):
            gallery = ui.MediaGallery()
            gallery.add_item(ui.Media(img_url))
            container.add_item(gallery)
            
        row = ui.ActionRow()
        btn_new = ui.Button(label="Desabafar", style=discord.ButtonStyle.success, emoji="🔒", custom_id="btn_confess")
        btn_reply = ui.Button(label="Responder", style=discord.ButtonStyle.secondary, emoji="💬", custom_id="btn_reply")
        
        row.add_item(btn_new)
        row.add_item(btn_reply)
        container.add_item(row)
        self.add_item(container)

    @ui.button(custom_id="btn_reply", style=discord.ButtonStyle.secondary, label="Responder")
    async def reply_callback(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ConfessionModal(title="Responder Confissão", is_reply=True, message_id=interaction.message.id))

class ConfessionModal(ui.Modal):
    def __init__(self, title, is_reply=False, message_id=None):
        super().__init__(title=title)
        self.is_reply = is_reply
        self.message_id = message_id

        self.content = ui.TextInput(label="Sua Confissão", style=discord.TextStyle.paragraph, required=True)
        self.image_url = ui.TextInput(label="URL da Imagem (Opcional)", required=False)
        self.add_item(self.content)
        self.add_item(self.image_url)

    async def on_submit(self, interaction: discord.Interaction):
        await handle_confession_submission(interaction, self.content.value, self.image_url.value, self.is_reply, self.message_id)

class ConfessionsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup_confissoes", description="Envia o painel inicial de confissões anônimas")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_confissoes(self, interaction: discord.Interaction):
        view = ConfessionStarterLayout()
        await interaction.channel.send(view=view)
        await interaction.response.send_message("✅ Painel configurado!", ephemeral=True)


async def handle_confession_submission(interaction: discord.Interaction, text, img_url, is_reply, message_id):
    db = interaction.client.db 
    
    if not is_reply:
        num = await get_next_confession_number(db, interaction.guild.id)
        layout = ConfessionLayout(text, num, img_url)
        await interaction.channel.send(view=layout)
        await interaction.response.send_message(f"Sua confissão **#{num:03d}** foi enviada!", ephemeral=True)
    else:
        target_msg = await interaction.channel.fetch_message(message_id)
        if target_msg.thread is None:
            thread = await target_msg.create_thread(name=f"Respostas #{target_msg.id % 1000}")
        else:
            thread = target_msg.thread
            
        reply_layout = ui.LayoutView()
        cont = ui.Container(accent_color=discord.Color.blue())
        cont.add_item(ui.TextDisplay(f"**Resposta Anônima:**\n{text}"))
        if img_url:
            gal = ui.MediaGallery()
            gal.add_item(ui.Media(img_url))
            cont.add_item(gal)
        
        reply_layout.add_item(cont)
        await thread.send(view=reply_layout)
        await interaction.response.send_message("Resposta enviada!", ephemeral=True)

async def get_next_confession_number(db, guild_id):
    result = await db.col_counters.find_one_and_update(
        {"_id": guild_id, "type": "confession"},
        {"$inc": {"count": 1}},
        upsert=True,
        return_document=True
    )
    return result.get("count", 1)


async def setup(bot):
    await bot.add_cog(ConfessionsCog(bot))