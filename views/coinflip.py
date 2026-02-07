import discord
import random

MAX_DOUBLES = 5

BOT_ECONOMY_ID = 0

class CoinflipView(discord.ui.View):
    def __init__(self, cog, interaction, amount, side):
        super().__init__(timeout=30)
        self.cog = cog
        self.author_id = interaction.user.id
        self.amount = amount
        self.side = side
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
    
    def end_game(self, interaction, win_amount):
        self.cog.col.update_one(
            {"_id": self.author_id},
            {"$inc": {"coins": win_amount}}
        )
        self.stop()

    async def on_timeout(self):
        win_total = self.amount * 2
        self.cog.col.update_one({"_id": self.author_id},{"$inc": {"coins": win_total}})

        if self.message:
            try:
                embed = discord.Embed(
                    title="⏰ Tempo esgotado!",
                    description=(
                        f"Jogo encerrou por inatividade 😢\n\n"
                        f"Você coletou automaticamente **{win_total} ralcoins**!"
                    ),
                    color=discord.Color.orange()
                )
                await self.message.send_message(embed=embed, view=None)
            except Exception:
                pass

    @discord.ui.button(label="🔁 Dobrar", style=discord.ButtonStyle.success)
    async def double(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_pot = self.amount * 2

        bot_data = self.cog.col.find_one({"_id": BOT_ECONOMY_ID}) or {}
        if bot_data.get("coins", 0) < current_pot:
            return await interaction.response.send_message("🏦 O bot não tem saldo para bancar a próxima rodada.")

        result = random.choice(["cara", "coroa"])

        if result == self.side:
            self.amount *= 2
            self.rounds += 1

            embed = discord.Embed(
                title="🪙 Coinflip - Vitória!",
                description=(
                    f"💰 Valor atual: **{self.amount*2} ralcoins**\n"
                    f"🔥 Vitórias seguidas: **{self.rounds}**"
                ),
                color=discord.Color.green()
            )

            await interaction.response.send_message(embed=embed)

        else:
            print(self.amount)
            self.amount *= 4
            self.cog.col.update_one(
                {"_id": BOT_ECONOMY_ID},
                {"$inc": {"coins": self.amount}} 
            )

            self.cog.col.update_one(
                {"_id": self.author_id},
                {"$inc": {"coins": -self.amount}}
            )

            embed = discord.Embed(
                title="💥 Coinflip - Derrota!",
                description=f"Você perdeu **{self.amount} ralcoins** 😢",
                color=discord.Color.red()
            )

            await interaction.response.send_message(embed=embed)
            self.stop()


    @discord.ui.button(label="🛑 Parar", style=discord.ButtonStyle.danger)
    async def stop_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        win_total = self.amount * 2
        if interaction.user.id != self.author_id: 
            return await interaction.response.send_message("Não é seu jogo! Vaza daqui OwO", ephemeral=True)

        self.cog.col.update_one(
            {"_id": BOT_ECONOMY_ID},
            {"$inc": {"coins": -self.amount}}
        )

        print(f"{interaction.user} ganhou {self.amount} ralcoins no coinflip! ANTES DO USUÁRIO RECEBER")

        self.end_game(interaction, win_total)
        
        print(f"{interaction.user} ganhou {win_total} ralcoins no coinflip!")

        embed = discord.Embed(
            title="🏁 Aposta finalizada",
            description=f"Você sacou **{win_total} ralcoins** 💰",
            color=discord.Color.gold()
        )

        await interaction.response.send_message(embed=embed)
        self.stop()
