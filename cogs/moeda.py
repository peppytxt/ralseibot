import discord
import requests
from discord import app_commands


def setup(tree):
    @tree.command(name="cotacao", description="Verifica a cotação de moedas.")
    @app_commands.describe(moeda="Escolha a moeda para consultar")
    @app_commands.choices(
        moeda=[
            discord.app_commands.Choice(name="Dólar (USD)", value="USD-BRL"),
            discord.app_commands.Choice(name="Euro (EUR)", value="EUR-BRL"),
            discord.app_commands.Choice(name="Bitcoin (BTC)", value="BTC-BRL")
        ]
    )
    async def cotacao(interaction: discord.Interaction, moeda: discord.app_commands.Choice[str]):

        url = f"https://economia.awesomeapi.com.br/last/{moeda.value}"

        try:
            req = requests.get(url, timeout=4)
            req.raise_for_status()
            key = moeda.value.replace("-", "")
            data = req.json()[key]
        except Exception:
            return await interaction.response.send_message(
                "❌ Não consegui buscar a cotação no momento."
            )

        valor = float(data["bid"])
        variacao = float(data["pctChange"])

        embed = discord.Embed(
            title=f"💱 Cotação — {moeda.name}",
            description=f"Valor atual: **R${valor:.2f}**",
            color=discord.Color.red() if variacao >= 0 else discord.Color.green()
        )

        embed.add_field(name="🌡️ Variação (%)", value=f"{variacao:.2f}%")

        await interaction.response.send_message(embed=embed)
