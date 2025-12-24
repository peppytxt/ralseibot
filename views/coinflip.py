import discord
import random

WIN_CHANCE = 0.48
MAX_DOUBLES = 5

BOT_ECONOMY_ID = 0

class CoinflipView(discord.ui.View):
    def __init__(self, cog, interaction, amount):
        super().__init__(timeout=30)
        self.cog = cog
        self.author_id = interaction.user.id
        self.amount = amount
        self.rounds = 0
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Apenas quem apostou pode usar.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="🔁 Dobrar", style=discord.ButtonStyle.success)
    async def double(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        bot_data = self.cog.col.find_one({"_id": BOT_ECONOMY_ID}) or {}
        if bot_data.get("coins", 0) < self.amount:
            return await interaction.response.send_message(
                "🏦 O bot não tem saldo para bancar a próxima rodada.",
                ephemeral=True
            )

        self.rounds += 1

        if random.random() < WIN_CHANCE:
            self.amount *= 2

            if self.rounds >= MAX_DOUBLES:
                button.disabled = True

            embed = discord.Embed(
                title="🪙 Coinflip - Vitória!",
                description=(
                    f"Você ganhou!\n\n"
                    f"💰 Valor atual: **{self.amount} ralcoins**\n"
                    f"🔥 Vitórias seguidas: **{self.rounds}**"
                ),
                color=discord.Color.green()
            )

            await interaction.response.send_message(embed=embed)

        else:
            embed = discord.Embed(
                title="💥 Coinflip - Derrota!",
                description="Você perdeu **tudo** 😢",
                color=discord.Color.red()
            )

            await interaction.response.edit_message(embed=embed, view=None)
            self.stop()

    @discord.ui.button(label="🛑 Parar", style=discord.ButtonStyle.danger)
    async def stop_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Usuário recebe
        self.cog.col.update_one(
            {"_id": self.author_id},
            {"$inc": {"coins": self.amount}}
        )

        # Bot paga
        self.cog.col.update_one(
            {"_id": BOT_ECONOMY_ID},
            {"$inc": {"coins": -self.amount}}
        )


        embed = discord.Embed(
            title="🏁 Aposta finalizada",
            description=f"Você sacou **{self.amount} ralcoins** 💰",
            color=discord.Color.gold()
        )

        await interaction.response.send_message(embed=embed)
        self.stop()

    async def on_timeout(self):
        if self.message:
            await self.message.edit(view=None)
