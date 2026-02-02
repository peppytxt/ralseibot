import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
import random
import time
import hashlib

class MarriageProposalView(ui.LayoutView):
    def __init__(self, cog, requester, target):
        super().__init__(timeout=60)
        self.cog = cog
        self.requester = requester
        self.target = target
        self.custo = 10000

        container = ui.Container(accent_color=discord.Color.red())
        container.add_item(ui.TextDisplay(f"## 💍 Pedido de Casamento"))
        container.add_item(ui.TextDisplay(f"{self.target.mention}, você aceita se casar com {self.requester.mention}?"))
        
        row = ui.ActionRow()
        btn_accept = ui.Button(label="Aceito!", style=discord.ButtonStyle.success, emoji="👰")
        btn_decline = ui.Button(label="Recusar", style=discord.ButtonStyle.danger)
        
        btn_accept.callback = self.accept_callback
        btn_decline.callback = self.decline_callback
        
        row.add_item(btn_accept)
        row.add_item(btn_decline)
        container.add_item(row)
        self.add_item(container)

    async def accept_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("❌ Não és o alvo!", ephemeral=True)

        requester_data = self.cog.col.find_one({"_id": self.requester.id}) or {"coins": 0}
        if requester_data.get("coins", 0) < 10000:
            return await interaction.response.send_message("❌ O proponente não tem mais o dinheiro!", ephemeral=True)

        ts = int(time.time())

        self.cog.col.update_one(
            {"_id": self.requester.id}, 
            {"$inc": {"coins": -10000}, "$set": {"marry_id": self.target.id, "marry_date": ts}}
        )

        self.cog.col.update_one(
            {"_id": self.target.id}, 
            {"$set": {"marry_id": self.requester.id, "marry_date": ts}}
        )

        await interaction.response.edit_message(content=f"🎉 **{self.target.display_name}** aceitou! Estão oficialmente casados!", view=None)

    async def decline_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("❌", ephemeral=True)
        await interaction.response.edit_message(content="💔 O pedido foi recusado...", view=None)

class ShipCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def col(self):
        return self.bot.get_cog("XP").col

    @app_commands.command(name="ship", description="Veja a afinidade entre dois usuários")
    @app_commands.describe(user1="Primeiro usuário", user2="Segundo usuário")
    async def ship(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member = None):
        user2 = user2 or interaction.user
        
        combined_id = "".join(sorted([str(user1.id), str(user2.id)]))
        percentage = int(hashlib.md5(combined_id.encode()).hexdigest(), 16) % 101

        if percentage < 20: status = "💔 | Clima pesado..."
        elif percentage < 50: status = "⚖️ | Amizade (talvez?)"
        elif percentage < 80: status = "💖 | Há algo no ar!"
        else: status = "🔥 | Almas Gêmeas!"

        container = ui.Container(accent_color=discord.Color.from_rgb(255, 105, 180))
        container.add_item(ui.TextDisplay(f"## ❤️ Teste de Afinidade"))
        container.add_item(ui.TextDisplay(f"**{user1.display_name}** + **{user2.display_name}**"))
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay(f"### Resultado: {percentage}%"))
        container.add_item(ui.TextDisplay(f"> {status}"))
        
        view = ui.LayoutView()
        view.add_item(container)
        await interaction.response.send_message(view=view)

    @app_commands.command(name="casar", description="Peça alguém em casamento :3")
    async def casar(self, interaction: discord.Interaction, user: discord.Member):
        custo = 10000
        
        if user.bot or user.id == interaction.user.id:
            return await interaction.response.send_message("❌ Alvo inválido.", ephemeral=True)

        u1_data = self.col.find_one({"_id": interaction.user.id}) or {"coins": 0}
        u2_data = self.col.find_one({"_id": user.id}) or {}

        if u1_data.get("coins", 0) < custo:
            return await interaction.response.send_message(f"❌ Precisa de **{custo} ralcoins** para casar!", ephemeral=True)

        if u1_data.get("marry_id") or u2_data.get("marry_id"):
            return await interaction.response.send_message("❌ Um de vocês já está casado!", ephemeral=True)

        view = MarriageProposalView(self, interaction.user, user, custo)
        await interaction.response.send_message(content=user.mention, view=view)


    casamento = app_commands.Group(name="casamento",description="Comandos relacionados a casamento")
    @casamento.command(name="info", description="Mostra detalhes do teu casamento ou de alguém")
    async def marry_info(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = self.col.find_one({"_id": target.id}) or {}
        
        partner_id = data.get("marry_id")
        if not partner_id:
            msg = "Esta pessoa está solteira." if user else "Não está casado(a) ainda."
            return await interaction.response.send_message(msg, ephemeral=True)
            
        partner = self.bot.get_user(partner_id) or await self.bot.fetch_user(partner_id)
        marry_date = data.get("marry_date")

        container = ui.Container(accent_color=discord.Color.from_rgb(255, 105, 180))
        container.add_item(ui.TextDisplay(f"## 💍 Certidão de Casamento"))
        
        info_text = (
            f"❤️ **Cônjuge:** {partner.mention}\n"
            f"📅 **Casados desde:** <t:{marry_date}:D> (<t:{marry_date}:R>)\n\n"
            f"*Que a união dure enquanto houver ralcoins!*"
        )
        container.add_item(ui.TextDisplay(info_text))
        
        view = ui.LayoutView()
        view.add_item(container)
        await interaction.response.send_message(view=view)

    @casamento.command(name="divorciar", description="Terminar o casamento atual")
    async def divorcio(self, interaction: discord.Interaction):
        user_data = self.col.find_one({"_id": interaction.user.id}) or {}
        partner_id = user_data.get("marry_id")

        if not partner_id:
            return await interaction.response.send_message("Tu nem sequer está casado! >:3", ephemeral=True)

        self.col.update_one({"_id": partner_id}, {"$unset": {"marry_id": "", "marry_date": ""}})

        await interaction.response.send_message("💔 O casamento acabou. Espero que seja mais feliz enquanto solteiro.")

async def setup(bot):
    await bot.add_cog(ShipCog(bot))