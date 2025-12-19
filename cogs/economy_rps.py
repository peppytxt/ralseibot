import discord
from discord import app_commands
from discord.ext import commands
import random

class RockPaperScissors(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}  # guarda jogos em andamento

    def get_winner(self, a, b):
        if a == b:
            return None
        rules = {
            "🪨": "✂",  # Rock vence Tesoura
            "✂": "📄",  # Tesoura vence Papel
            "📄": "🪨",  # Papel vence Pedra
        }
        return "A" if rules[a] == b else "B"

    @app_commands.command(name="rps", description="Desafiar alguém para Pedra Papel Tesoura e apostar moedas!")
    async def rps(self, interaction: discord.Interaction, opponent: discord.Member, amount: int):
        if opponent.id == interaction.user.id:
            return await interaction.response.send_message("Você não pode desafiar você mesmo!", ephemeral=True)

        # Verifica saldo
        db = self.bot.get_cog("XP").col
        user_data = db.find_one({"_id": interaction.user.id}) or {}
        opp_data = db.find_one({"_id": opponent.id}) or {}

        if user_data.get("coins", 0) < amount:
            return await interaction.response.send_message("Você não tem moedas suficientes!", ephemeral=True)
        if opp_data.get("coins", 0) < amount:
            return await interaction.response.send_message(f"{opponent.display_name} não tem moedas suficientes!", ephemeral=True)

        game_id = f"{interaction.user.id}-{opponent.id}"
        if game_id in self.ongoing_games:
            return await interaction.response.send_message("Já existe uma partida entre vocês!", ephemeral=True)

        self.ongoing_games[game_id] = {
            "A": None, "B": None,
            "userA": interaction.user,
            "userB": opponent,
            "amount": amount
        }

        view = discord.ui.View(timeout=60)
        for emoji in ["🪨","📄","✂"]:
            view.add_item(discord.ui.Button(label=emoji, style=discord.ButtonStyle.secondary, custom_id=f"A-{emoji}-{game_id}"))

        await interaction.response.send_message(
            f"{interaction.user.mention} desafiou {opponent.mention} para uma aposta de **{amount} moedas**!\n"
            "🪨 🧾 ✂ Escolha sua jogada!",
            view=view
        )

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        # Checar se é um botão custom de RPS
        cid = interaction.data.get("custom_id")
        if not cid:
            return

        parts = cid.split("-")
        if len(parts) != 3:
            return

        pos, choice, game_id = parts
        if game_id not in self.ongoing_games:
            return await interaction.response.send_message("Partida expirada ou inválida!", ephemeral=True)

        game = self.ongoing_games[game_id]

        # Autorização
        if interaction.user.id not in (game["userA"].id, game["userB"].id):
            return await interaction.response.send_message("❌ Você não faz parte dessa partida!", ephemeral=True)

        # Escolha do jogador
        side = "A" if interaction.user.id == game["userA"].id else "B"
        if game[side] is not None:
            return await interaction.response.send_message("Você já escolheu!", ephemeral=True)

        game[side] = choice

        await interaction.response.send_message(f"✅ {interaction.user.display_name} escolheu!", ephemeral=True)

        # Se ambos já escolheram, calcula
        if game["A"] and game["B"]:
            winner = self.get_winner(game["A"], game["B"])
            db = self.bot.get_cog("XP").col

            amount = game["amount"]
            userA = game["userA"]
            userB = game["userB"]

            text = (
                f"🪨📄✂ Resultado!\n"
                f"{userA.mention} jogou **{game['A']}**\n"
                f"{userB.mention} jogou **{game['B']}**\n"
            )

            if winner is None:
                text += "➡️ Empate! Ninguém perde moedas!"
            elif winner == "A":
                text += f"🎉 {userA.mention} venceu e ganhou **{amount} moedas**!"
                db.update_one({"_id": userA.id}, {"$inc": {"coins": amount}})
                db.update_one({"_id": userB.id}, {"$inc": {"coins": -amount}})
            else:
                text += f"🎉 {userB.mention} venceu e ganhou **{amount} moedas**!"
                db.update_one({"_id": userB.id}, {"$inc": {"coins": amount}})
                db.update_one({"_id": userA.id}, {"$inc": {"coins": -amount})

            del self.ongoing_games[game_id]
            await interaction.followup.send(text)
