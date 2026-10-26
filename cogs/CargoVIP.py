import discord
from discord import app_commands
from discord.ext import commands

class VipRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    SERVER_ID = 1410006076400599235 
    
    VIP_ROLE_IDS = [
        1411874300952318126, # Espersso Premium
        1415850384722886818  # Booster
    ]

    @property
    def col_vips(self):
        database = getattr(self.bot, "db", None)
        return database.vip_roles if database is not None else None

    cargo_group = app_commands.Group(
        name="cargo", 
        description="Gerencie seu cargo VIP personalizado",
        guilds=[discord.Object(id=1410006076400599235)]
    )

    # ==========================================
    # 1. /cargo criar
    # ==========================================
    @cargo_group.command(name="criar", description="Cria o seu cargo VIP personalizado.")
    @app_commands.describe(
        nome="Nome do cargo",
        cor="Cor em Hexadecimal (ex: #FF5733)",
        cor2="Segunda cor para gradiente (Opcional)",
        icone="Imagem opcional para ser o ícone do cargo"
    )
    async def cargo_criar(
        self, 
        interaction: discord.Interaction, 
        nome: str, 
        cor: str, 
        cor2: str = None, 
        icone: discord.Attachment = None
    ):
        await interaction.response.defer(ephemeral=True)

        user_roles = [role.id for role in interaction.user.roles]
        tem_cargo_vip = any(role_id in self.VIP_ROLE_IDS for role_id in user_roles)
        eh_booster = interaction.user.premium_since is not None

        if not tem_cargo_vip and not eh_booster:
            embed = discord.Embed(
                title="Sinto Muito :(",
                description="Massss apenas membros com **cargos VIP** ou **Server Boosters** podem criar um cargo personalizado!",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        if self.col_vips is None:
            embed = discord.Embed(
                title="Erro no Banco",
                description="O banco de dados está temporariamente offline :( consulte um administrador.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        registro = await self.col_vips.find_one({"_id": interaction.user.id, "guild_id": interaction.guild.id})
        if registro:
            embed = discord.Embed(
                title="Cargo já existe >:3",
                description="Você já possui um cargo VIP criado! Use `/cargo deletar` se quiser remover o atual antes de criar outro.",
                color=discord.Color.orange()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        try:
            color_obj = discord.Color.from_str(cor)
        except ValueError:
            embed = discord.Embed(
                title="Cor Inválida",
                description="Use o formato hexadecimal correto, por exemplo: `#FF5733` :3",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        icon_bytes = None
        if icone:
            if not icone.content_type or not icone.content_type.startswith("image/"):
                embed = discord.Embed(
                    title="Arquivo Inválido :(",
                    description="O anexo precisa ser uma imagem válida!",
                    color=discord.Color.red()
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            icon_bytes = await icone.read()

        try:
            novo_cargo = await interaction.guild.create_role(
                name=nome,
                color=color_obj,
                icon=icon_bytes,
                reason=f"Cargo VIP criado por {interaction.user} ({interaction.user.id}) ^w^"
            )

            await interaction.user.add_roles(novo_cargo, reason="Cargo VIP criado pelo próprio usuário :3")

            await self.col_vips.update_one(
                {"_id": interaction.user.id, "guild_id": interaction.guild.id},
                {"$set": {"role_id": novo_cargo.id}},
                upsert=True
            )

            embed = discord.Embed(
                title="Cargo VIP Criado!",
                description=f"Seu cargo VIP {novo_cargo.mention} foi criado e atribuído a você com sucesso UwU",
                color=color_obj
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except discord.Forbidden:
            embed = discord.Embed(
                title="Sem Permissão",
                description="Eu não tenho permissão para gerenciar cargos neste servidor. Consulte um administador.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="Erro Inesperado",
                description=f"Ocorreu um erro 'diferenciado' ao criar o cargo: `{e}`",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    # ==========================================
    # 2. /cargo atribuir (Até 5 pessoas)
    # ==========================================
    @cargo_group.command(name="atribuir", description="Atribui ou remove seu cargo VIP de um membro (máximo de 5 pessoas).")
    @app_commands.describe(membro="Membro que receberá ou perderá o cargo")
    async def cargo_atribuir(self, interaction: discord.Interaction, membro: discord.Member):
        await interaction.response.defer(ephemeral=True)

        if self.col_vips is None:
            embed = discord.Embed(
                title="Erro no Banco",
                description="O banco de dados está temporariamente offline :( consulte um administrador",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        registro = await self.col_vips.find_one({"_id": interaction.user.id, "guild_id": interaction.guild.id})
        if not registro:
            embed = discord.Embed(
                title="Nenhum Cargo Encontrado",
                description="Você ainda não criou nenhum cargo VIP! Use `/cargo criar` antes de tuduwu",
                color=discord.Color.orange()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        role = interaction.guild.get_role(registro["role_id"])
        if not role:
            embed = discord.Embed(
                title="Cargo Excluído",
                description="O seu cargo VIP foi deletado do servidor. Crie um novo com `/cargo criar` :3",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        if membro.bot:
            embed = discord.Embed(
                title="Ação Inválida",
                description="Você não pode atribuir seu cargo a bots, bobinho TwT",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        if membro == interaction.user:
            embed = discord.Embed(
                title="Ação Inválida",
                description="Você já possui o cargo principal ksks",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        membros_com_cargo = [m for m in role.members if m.id != interaction.user.id]

        if membro in role.members:
            await membro.remove_roles(role, reason=f"Removido pelo dono do VIP ({interaction.user})")
            embed = discord.Embed(
                title="Cargo Removido!",
                description=f"O cargo {role.mention} foi **removido** de {membro.mention}.",
                color=discord.Color.orange()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            if len(membros_com_cargo) >= 5:
                embed = discord.Embed(
                    title="Limite Atingido",
                    description="Você atingiu o limite máximo de **5 pessoas** compartilhando o seu cargo VIP.",
                    color=discord.Color.orange()
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            await membro.add_roles(role, reason=f"Atribuído pelo dono do VIP ({interaction.user})")
            embed = discord.Embed(
                title="Cargo Atribuído",
                description=f"O cargo {role.mention} foi **atribuído** para {membro.mention} com sucesso!",
                color=discord.Color.green()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

    # ==========================================
    # 3. /cargo cor (Editar cor)
    # ==========================================
    @cargo_group.command(name="cor", description="Altera a cor do seu cargo VIP.")
    @app_commands.describe(cor="Nova cor em formato Hexadecimal (ex: #00FFCC)")
    async def cargo_cor(self, interaction: discord.Interaction, cor: str):
        await interaction.response.defer(ephemeral=True)

        registro = await self.col_vips.find_one({"_id": interaction.user.id, "guild_id": interaction.guild.id})
        if not registro:
            embed = discord.Embed(
                title="Nenhum Cargo Encontrado",
                description="Você não tem um cargo VIP criado, sry",
                color=discord.Color.orange()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        role = interaction.guild.get_role(registro["role_id"])
        if not role:
            embed = discord.Embed(
                title="Cargo Excluído",
                description="Seu cargo VIP não existe mais no servidor, sryy",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        try:
            color_obj = discord.Color.from_str(cor)
        except ValueError:
            embed = discord.Embed(
                title="Cor Inválida",
                description="Código de cor inválido. Use o formato Hex ex: `#FF0000` >:3",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        try:
            await role.edit(color=color_obj, reason=f"Cor alterada por {interaction.user}")
            embed = discord.Embed(
                title="Cor Atualizada",
                description=f"A cor do seu cargo {role.mention} foi atualizada com sucesso uwu",
                color=color_obj
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except discord.Forbidden:
            embed = discord.Embed(
                title="Sem Permissão",
                description="Não tenho permissão para editar este cargo :( consulte um administrador.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    # ==========================================
    # 4. /cargo deletar
    # ==========================================
    @cargo_group.command(name="deletar", description="Exclui permanentemente o seu cargo VIP atual.")
    async def cargo_deletar(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        registro = await self.col_vips.find_one({"_id": interaction.user.id, "guild_id": interaction.guild.id})
        if not registro:
            embed = discord.Embed(
                title="Nenhum Cargo Encontrado",
                description="Você não possui nenhum cargo VIP registrado, sinto muito :(",
                color=discord.Color.orange()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        role = interaction.guild.get_role(registro["role_id"])
        if role:
            try:
                await role.delete(reason=f"Deletado pelo dono do VIP ({interaction.user})")
            except discord.Forbidden:
                pass

        await self.col_vips.delete_one({"_id": interaction.user.id, "guild_id": interaction.guild.id})
        
        embed = discord.Embed(
            title="Cargo Deletado",
            description="Seu cargo VIP foi deletado com sucesso. Agora você pode criar um novo se desejar ^w^",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ==========================================
    # 5. /cargo nome (Editar nome do cargo)
    # ==========================================
    @cargo_group.command(name="nome", description="Altera o nome do seu cargo VIP.")
    @app_commands.describe(nome="Novo nome para o seu cargo")
    async def cargo_nome(self, interaction: discord.Interaction, nome: str):
        await interaction.response.defer(ephemeral=True)

        registro = await self.col_vips.find_one({"_id": interaction.user.id, "guild_id": interaction.guild.id})
        if not registro:
            embed = discord.Embed(
                title="Nenhum Cargo Encontrado",
                description="Você não tem um cargo VIP criado, sorryyyyy :(",
                color=discord.Color.orange()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        role = interaction.guild.get_role(registro["role_id"])
        if not role:
            embed = discord.Embed(
                title="Cargo Excluído",
                description="Seu cargo VIP não existe mais no servidor rsrs",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        try:
            await role.edit(name=nome, reason=f"Nome alterado por {interaction.user}")
            embed = discord.Embed(
                title="Nome Atualizado",
                description=f"O nome do seu cargo {role.mention} foi alterado para **{nome}** com sucesso owo",
                color=role.color
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except discord.Forbidden:
            embed = discord.Embed(
                title="Sem Permissão",
                description="Não tenho permissão para editar o nome deste cargo :( consulte um administrador",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    # ==========================================
    # 6. /cargo icone (Editar ícone do cargo)
    # ==========================================
    @cargo_group.command(name="icone", description="Altera a imagem/ícone do seu cargo VIP.")
    @app_commands.describe(icone="Nova imagem para o ícone do cargo")
    async def cargo_icone(self, interaction: discord.Interaction, icone: discord.Attachment):
        await interaction.response.defer(ephemeral=True)

        registro = await self.col_vips.find_one({"_id": interaction.user.id, "guild_id": interaction.guild.id})
        if not registro:
            embed = discord.Embed(
                title="Nenhum Cargo Encontrado",
                description="Você não tem um cargo VIP criado, sorryy",
                color=discord.Color.orange()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        role = interaction.guild.get_role(registro["role_id"])
        if not role:
            embed = discord.Embed(
                title="Cargo Excluído",
                description="Seu cargo VIP não existe mais no servidor owo",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        if not icone.content_type or not icone.content_type.startswith("image/"):
            embed = discord.Embed(
                title="Arquivo Inválido",
                description="O anexo precisa ser uma imagem válida!",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        try:
            icon_bytes = await icone.read()
            await role.edit(icon=icon_bytes, reason=f"Ícone alterado por {interaction.user}")
            
            embed = discord.Embed(
                title="Ícone Atualizado",
                description=f"O ícone do seu cargo {role.mention} foi atualizado com sucesso ^w^",
                color=role.color
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except discord.Forbidden:
            embed = discord.Embed(
                title="Sem Permissão",
                description="Não tenho permissão para alterar o ícone (servidor não tem level 2).",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(VipRoles(bot))