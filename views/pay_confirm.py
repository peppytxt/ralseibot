import discord

class PayConfirmView(discord.ui.View):
    def __init__(self, cog, sender, receiver, amount, timeout_seconds: int = 900):
        super().__init__(timeout=timeout_seconds)

        self.cog = cog
        self.sender = sender
        self.receiver = receiver
        self.amount = amount

        self.sender_confirmed = False
        self.receiver_confirmed = False
        self.message = None

    def both_confirmed(self):
        return self.sender_confirmed and self.receiver_confirmed

    async def finalize(self, interaction: discord.Interaction):
        # 💸 Debita pagador
        self.cog.col.update_one(
            {"_id": self.sender.id},
            {"$inc": {"coins": -self.amount}}
        )

        # 💰 Credita receptor
        self.cog.col.update_one(
            {"_id": self.receiver.id},
            {"$inc": {"coins": self.amount}},
            upsert=True
        )

        embed = discord.Embed(
            title="💸 Transferência concluída!",
            description=(
                f"**{self.sender.display_name}** transferiu "
                f"**{self.amount} ralcoins** para "
                f"**{self.receiver.display_name}** 💰"
            ),
            color=discord.Color.green()
        )

        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id == self.sender.id:
            self.sender_confirmed = True
        elif interaction.user.id == self.receiver.id:
            self.receiver_confirmed = True
        else:
            return await interaction.response.send_message(
                "❌ Você não faz parte desta transação.",
                ephemeral=True
            )

        if self.both_confirmed():
            return await self.finalize(interaction)

        await interaction.response.send_message(
            "✅ Confirmação registrada. Aguardando a outra parte.",
            ephemeral=True
        )

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id not in (self.sender.id, self.receiver.id):
            return await interaction.response.send_message(
                "❌ Você não pode cancelar esta transação.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="❌ Transferência cancelada",
            description="A transação foi cancelada.",
            color=discord.Color.red()
        )

        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    async def on_timeout(self):
        if self.message:
            embed = discord.Embed(
                title="⏰ Transferência expirada",
                description="O tempo para confirmação acabou. Nenhuma ralcoin foi transferida.",
                color=discord.Color.red()
            )
            await self.message.send(embed=embed, view=None)
