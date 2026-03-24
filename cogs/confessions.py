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
        row = ui.ActionRow()
        btn_start = ui.Button(label="Enviar Desabafo", custom_id="btn_confess", style=discord.ButtonStyle.primary, emoji="📝")
        
        btn_start.callback = self.start_confess
        
        row.add_item(btn_start)
        container.add_item(row)
        self.add_item(container)

    async def start_confess(self, interaction: discord.Interaction):
        print("o botão foi apertado?")
        await interaction.response.send_modal(ConfessionModal(title="Nova Confissão"))

class ConfessionLayout(ui.LayoutView):
    def __init__(self, text, num, img_url=None):
        super().__init__(timeout=None) 
        container = ui.Container(accent_color=discord.Color.random())
        container.add_item(ui.TextDisplay(f"## 👤 Confissão Anônima (#{num:03d})\n\n{text}"))
        
        if img_url and img_url.startswith(("http", "https")):
            img_embed = discord.Embed()
            img_embed.set_image(url=img_url)
            
            container.add_item(ui.EmbedDisplay(img_embed))
            
        row = ui.ActionRow()
        
        container.add_item(ui.Separator())
        
        btn_new = ui.Button(
            label="Desabafar", 
            style=discord.ButtonStyle.success, 
            emoji="🔒", 
            custom_id="btn_confess"
        )
        btn_new.callback = self.start_confess_new

        btn_reply = ui.Button(
            label="Responder", 
            style=discord.ButtonStyle.secondary, 
            emoji="💬", 
            custom_id="btn_reply"
        )
        btn_reply.callback = self.reply_callback
        
        row.add_item(btn_new)
        row.add_item(btn_reply)
        container.add_item(row)
        self.add_item(container)

    async def start_confess_new(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ConfessionModal(title="Nova Confissão"))

    async def reply_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            ConfessionModal(title="Responder Confissão", is_reply=True, message_id=interaction.message.id)
        )
        
class ConfessionModal(ui.Modal):
    def __init__(self, title, is_reply=False, message_id=None):
        super().__init__(title=title)
        self.is_reply = is_reply
        self.message_id = message_id

        self.content = ui.TextInput(label="Sua Confissão", style=discord.TextStyle.paragraph, required=True)
        self.image_url = ui.TextInput(label="URL da Imagem (NÃO FUNCIONA!!!)", required=False)
        self.add_item(self.content)
        self.add_item(self.image_url)

    async def on_submit(self, interaction: discord.Interaction):
        await handle_confession_submission(interaction, self.content.value, self.image_url.value, self.is_reply, self.message_id)

class ConfessionsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup_confissoes", description="Envia o painel inicial de confissões anônimas")
    @app_commands.guilds(discord.Object(id=1410006076400599235))
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_confissoes(self, interaction: discord.Interaction):
        view = ConfessionStarterLayout()
        await interaction.channel.send(view=view)
        await interaction.response.send_message("✅ Painel configurado!", ephemeral=True)

async def handle_confession_submission(interaction: discord.Interaction, text, img_url, is_reply, message_id):
    db = interaction.client.db 
    LOG_CHANNEL_ID = 1442962186120069234
    log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)

    author = interaction.user
    
    if not is_reply:
        num = await get_next_confession_number(db, interaction.guild.id)
        
        embed = None
        if img_url and img_url.startswith(("http", "https")):
            embed = discord.Embed()
            embed.set_image(url=img_url)

        layout = ConfessionLayout(text, num) 
        
        confession_msg = await interaction.channel.send(embed=embed, view=layout)
        await interaction.response.send_message(f"Sua confissão **#{num:03d}** foi enviada!", ephemeral=True)

        if log_channel:
            log_embed = discord.Embed(
                title=f"📝 Log de Confissão #{num:03d}",
                description=f"**Conteúdo:**\n{text}",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            log_embed.add_field(name="👤 Autor", value=f"{author.mention} ({author.name})", inline=True)
            log_embed.add_field(name="🆔 ID do Autor", value=f"`{author.id}`", inline=True)
            log_embed.add_field(name="🔗 Link", value=f"[Ir para confissão]({confession_msg.jump_url})", inline=False)
            
            if img_url:
                log_embed.add_field(name="🖼️ URL da Imagem", value=img_url, inline=False)
            
            await log_channel.send(embed=log_embed)

    else:
        target_msg = await interaction.channel.fetch_message(message_id)
        if target_msg.thread is None:
            thread = await target_msg.create_thread(name=f"Respostas #{target_msg.id % 1000}")
        else:
            thread = target_msg.thread
            
        reply_layout = ui.LayoutView()
        cont = ui.Container(accent_color=discord.Color.blue())
        cont.add_item(ui.TextDisplay(f"**Resposta Anônima:**\n{text}"))
        reply_layout.add_item(cont)
        
        await thread.send(view=reply_layout)
        await interaction.response.send_message("Resposta enviada!", ephemeral=True)

        if log_channel:
            log_reply = discord.Embed(
                title="💬 Log de Resposta Anônima",
                description=f"**Resposta:**\n{text}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            log_reply.add_field(name="👤 Autor", value=f"{author.mention}", inline=True)
            log_reply.add_field(name="📌 Na Confissão", value=f"[Ir para mensagem]({target_msg.jump_url})", inline=True)
            
            await log_channel.send(embed=log_reply)

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