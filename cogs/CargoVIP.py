import discord
from discord import app_commands, ui
from discord.ext import commands

class CreateRoleModal(ui.Modal, title="Criar Cargo VIP Personalizado"):
    nome = ui.TextInput(
        label="Nome do Cargo",
        placeholder="Ex: Supremos do Ralsei",
        min_length=1,
        max_length=32
    )
    cor = ui.TextInput(
        label="Cor Principal (Hex)",
        placeholder="Ex: #00FFCC",
        min_length=4,
        max_length=7
    )
    segunda_cor = ui.TextInput(
        label="Segunda Cor p/ Gradiente (Opcional)",
        placeholder="Ex: #FF5733 (Deixe vazio para cor sólida)",
        min_length=0,
        max_length=7,
        required=False
    )

    def __init__(self, cog, prompt_interaction=None):
        super().__init__()
        self.cog = cog
        self.prompt_interaction = prompt_interaction 

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        registro_existente = await self.cog.col_vips.find_one({"_id": interaction.user.id, "guild_id": interaction.guild.id})
        if registro_existente:
            cargo_atual = interaction.guild.get_role(registro_existente["role_id"])
            if cargo_atual:
                painel_existente = VipRolePanel(self.cog, interaction.user, cargo_atual)
                painel_existente.build_interface()
                
                container_aviso = ui.Container(accent_color=discord.Color.orange())
                container_aviso.add_item(ui.TextDisplay(
                    "**Atenção:** Você já possui um cargo personalizado criado >:3\n"
                    "Gerencie o seu atual abaixo:"
                ))
                
                view_aviso = ui.LayoutView()
                view_aviso.add_item(container_aviso)
                for item in painel_existente.children:
                    view_aviso.add_item(item)

                return await interaction.followup.send(view=view_aviso, ephemeral=True)

        ID_CARGO_ANCORA = 1410303016980054087

        try:
            color_obj = discord.Color.from_str(self.cor.value)
            
            kwargs = {
                "name": self.nome.value,
                "color": color_obj,
                "reason": f"Cargo personalizado criado por {interaction.user}"
            }

            if self.segunda_cor.value and self.segunda_cor.value.strip():
                sec_color_obj = discord.Color.from_str(self.segunda_cor.value.strip())
                kwargs["secondary_color"] = sec_color_obj

        except ValueError:
            return await interaction.followup.send(
                "Formato de cor inválido! Use o padrão hexadecimal ex: `#FF5733` owo",
                ephemeral=True
            )

        try:
            novo_cargo = await interaction.guild.create_role(**kwargs)

            cargo_ancora = interaction.guild.get_role(ID_CARGO_ANCORA)
            if cargo_ancora:
                posicao_desejada = max(1, cargo_ancora.position - 1)
                try:
                    await novo_cargo.edit(position=posicao_desejada)
                except discord.HTTPException:
                    pass

            await interaction.user.add_roles(novo_cargo, reason="Cargo VIP criado pelo próprio usuário.")

            await self.cog.col_vips.update_one(
                {"_id": interaction.user.id, "guild_id": interaction.guild.id},
                {"$set": {"role_id": novo_cargo.id}},
                upsert=True
            )

            novo_painel = VipRolePanel(self.cog, interaction.user, novo_cargo)
            novo_painel.build_interface()

            container_sucesso = ui.Container(accent_color=color_obj)
            container_sucesso.add_item(ui.TextDisplay(
                f"✨ **Criado com Sucesso!**\n"
                f"Seu cargo {novo_cargo.mention} foi criado ^w^\n\n"
                f"-# Gerencie-o através do painel abaixo:"
            ))
            
            view_final = ui.LayoutView()
            view_final.add_item(container_sucesso)
            
            for item in novo_painel.children:
                view_final.add_item(item)

            await interaction.followup.send(view=view_final)

            if self.prompt_interaction:
                try:
                    await self.prompt_interaction.delete_original_response()
                except Exception:
                    pass

        except discord.Forbidden:
            await interaction.followup.send(
                "Não tenho permissão para criar/gerenciar cargos ou o servidor não atinge os requisitos de Boost para gradientes :(",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"Ocorreu um erro ao criar o cargo: `{e}`",
                ephemeral=True
            )

class VipCreatePromptView(ui.LayoutView):
    def __init__(self, cog):
        super().__init__(timeout=180)
        self.cog = cog

        container = ui.Container(accent_color=discord.Color.gold())
        container.add_item(ui.TextDisplay(
            "## 👑 Criador de Cargo VIP\n"
            "Você ainda não possui um cargo personalizado no servidor!\n\n"
            "Clique no botão abaixo para escolher o **nome** e a **cor** do seu cargo personalizado."
        ))

        row = ui.ActionRow()
        btn_criar = ui.Button(label="Criar Meu Cargo VIP", style=discord.ButtonStyle.success, emoji="✨")
        btn_criar.callback = self.press_criar
        row.add_item(btn_criar)

        container.add_item(row)
        self.add_item(container)

    async def press_criar(self, interaction: discord.Interaction):
        user_roles = [role.id for role in interaction.user.roles]
        tem_cargo_vip = any(role_id in self.cog.VIP_ROLE_IDS for role_id in user_roles)
        eh_booster = interaction.user.premium_since is not None

        if not tem_cargo_vip and not eh_booster:
            return await interaction.response.send_message(
                "Apenas membros com **cargos VIP autorizados** ou **Boosters** podem criar um cargo personalizado rsrs",
                ephemeral=True
            )

        await interaction.response.send_modal(CreateRoleModal(self.cog, interaction))

class ConfirmDeleteView(ui.LayoutView):
    def __init__(self, cog, user, role, panel_view):
        super().__init__(timeout=60)
        self.cog = cog
        self.user = user
        self.role = role
        self.panel_view = panel_view

        container = ui.Container(accent_color=discord.Color.red())
        container.add_item(ui.TextDisplay(
            "⚠️ **Tem certeza que deseja deletar seu cargo personalizado?**\n\n"
            "Esta ação é **irreversível** e todos os membros perderão o cargo imediatamente!"
        ))

        row = ui.ActionRow()
        btn_sim = ui.Button(label="Sim, Deletar", style=discord.ButtonStyle.danger, emoji="🗑️")
        btn_sim.callback = self.press_yes

        btn_nao = ui.Button(label="Cancelar", style=discord.ButtonStyle.secondary, emoji="❌")
        btn_nao.callback = self.press_no

        row.add_item(btn_sim)
        row.add_item(btn_nao)
        container.add_item(row)
        self.add_item(container)

    async def press_yes(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Apenas o dono pode fazer isso!", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        if self.role:
            try:
                await self.role.delete(reason=f"Deletado pelo dono ({interaction.user})")
            except discord.Forbidden:
                pass

        await self.cog.col_vips.delete_one({"_id": self.user.id, "guild_id": interaction.guild.id})
        
        container_ok = ui.Container(accent_color=discord.Color.green())
        container_ok.add_item(ui.TextDisplay("🗑️ **Cargo Deletado com Sucesso!** Use `/cargo painel` se quiser criar um novo owo"))
        
        view_ok = ui.LayoutView()
        view_ok.add_item(container_ok)

        await interaction.edit_original_response(view=view_ok)

    async def press_no(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Apenas o dono pode fazer isso!", ephemeral=True)

        await interaction.response.edit_message(view=self.panel_view)

# ==========================================
# MODAIS DE EDIÇÃO (NOME E COR)
# ==========================================
class EditRoleNameModal(ui.Modal, title="Altere Nome do Cargo"):
    novo_nome = ui.TextInput(
        label="Novo Nome do Cargo",
        placeholder="Ex: Supremos do Ralsei",
        min_length=1,
        max_length=32
    )

    def __init__(self, role, view):
        super().__init__()
        self.role = role
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.role.edit(name=self.novo_nome.value, reason=f"Nome alterado por {interaction.user}")
            
            await self.view.refresh_panel(interaction)
            await interaction.followup.send(
                embed=discord.Embed(title="✏️ Nome Atualizado", description=f"O nome do cargo foi alterado para **{self.novo_nome.value}** ^w^", color=self.role.color)
            )
        except discord.Forbidden:
            await interaction.response.send_message("Não tenho permissão para editar o nome deste cargo :( consulte um administrador", ephemeral=True)


class EditRoleColorModal(ui.Modal, title="Altere a Cor do Cargo"):
    nova_cor = ui.TextInput(
        label="Cor Principal (Hex)",
        placeholder="Ex: #FF5733",
        min_length=4,
        max_length=7
    )
    segunda_cor = ui.TextInput(
        label="Segunda Cor p/ Gradiente (Opcional)",
        placeholder="Ex: #00FFCC (Deixe vazio)",
        min_length=0,
        max_length=7,
        required=False
    )

    def __init__(self, role, view):
        super().__init__()
        self.role = role
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            color_obj = discord.Color.from_str(self.nova_cor.value)
            kwargs = {"color": color_obj, "reason": f"Cor alterada por {interaction.user}"}
            
            if self.segunda_cor.value and self.segunda_cor.value.strip():
                sec_color_obj = discord.Color.from_str(self.segunda_cor.value.strip())
                kwargs["secondary_color"] = sec_color_obj
            else:
                kwargs["secondary_color"] = None

            await self.role.edit(**kwargs)
            
            await self.view.refresh_panel(interaction)
            
            container_cor = ui.Container(accent_color=color_obj)
            container_cor.add_item(ui.TextDisplay(f"🎨 **Cor Atualizada!**\nA cor do cargo foi alterada com sucesso uwu"))
            view_cor = ui.LayoutView()
            view_cor.add_item(container_cor)
            
            await interaction.followup.send(view=view_cor, ephemeral=True)

        except ValueError:
            await interaction.followup.send("Formato de cor inválido! Use o padrão hexadecimal ex: `#FF5733` ksks", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("Não tenho permissão para alterar a cor ou o servidor não tem Boost suficiente para gradientes :( consulte um administrador", ephemeral=True)

class EditRoleIconModal(ui.Modal, title="Alterar Ícone do Cargo"):
    url_icone = ui.TextInput(
        label="Link Direto da Imagem (URL)",
        placeholder="https://exemplo.com/icone.png (Deixe vazio para remover)",
        min_length=0,
        max_length=500,
        required=False
    )

    def __init__(self, role, view):
        super().__init__()
        self.role = role
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        url = self.url_icone.value.strip()
        icon_bytes = None

        if url:
            import aiohttp
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            icon_bytes = await resp.read()
                        else:
                            return await interaction.followup.send("Não foi possível baixar a imagem do link fornecido. Verifique se a URL é válida.", ephemeral=True)
            except Exception:
                return await interaction.followup.send("Erro ao processar o link da imagem. Certifique-se de que é um link direto de imagem owo", ephemeral=True)

        try:
            await self.role.edit(display_icon=icon_bytes, reason=f"Ícone alterado por {interaction.user}")
            
            await self.view.refresh_panel(interaction)
            
            container_icon = ui.Container(accent_color=self.role.color)
            container_icon.add_item(ui.TextDisplay("✨ **Ícone Atualizado com Sucesso!** O ícone do seu cargo foi modificaduwu"))
            view_icon = ui.LayoutView()
            view_icon.add_item(container_icon)
            
            await interaction.followup.send(view=view_icon, ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("Não tenho permissão para alterar o ícone ou o servidor não atinge o nível de Boost necessário para ícones de cargo :(", ephemeral=True)

class VipInviteView(ui.LayoutView):
    def __init__(self, role, dono, amigo, panel_view):
        super().__init__(timeout=180)
        self.role = role
        self.dono = dono
        self.amigo = amigo
        self.panel_view = panel_view
        self.is_accepted = False
        self.message = None

        container = ui.Container(accent_color=role.color if role.color.value != 0 else discord.Color.blue())
        container.add_item(ui.TextDisplay(
            f"## 📜 Convite de Cargo VIP!\n"
            f"{self.amigo.mention}, você recebeu um convite de {self.dono.mention} "
            f"para receber o cargo personalizado {self.role.mention}!\n\n"
            f"⏰ **Você tem 3 minutos para aceitar este convite ^w^**"
        ))

        row = ui.ActionRow()
        btn_accept = ui.Button(label="Aceitar Convite", style=discord.ButtonStyle.success, emoji="✅")
        btn_accept.callback = self.press_accept
        row.add_item(btn_accept)

        container.add_item(row)
        self.add_item(container)

    async def press_accept(self, interaction: discord.Interaction):
        if interaction.user.id != self.amigo.id:
            return await interaction.response.send_message("Este convite não é para você, bobinho >:3", ephemeral=True)

        self.is_accepted = True

        cargo_atualizado = interaction.guild.get_role(self.role.id)
        if not cargo_atualizado:
            return await interaction.response.send_message("Este cargo não existe mais.", ephemeral=True)

        membros_atuais = [m for m in cargo_atualizado.members if m.id != self.dono.id]
        
        if len(membros_atuais) >= 5:
            container_erro = ui.Container(accent_color=discord.Color.red())
            container_erro.add_item(ui.TextDisplay("O limite máximo de **5 membros** compartilhando este cargo já foi atingido!"))
            layout = ui.LayoutView()
            layout.add_item(container_erro)
            return await interaction.response.edit_message(view=layout)

        try:
            await self.amigo.add_roles(cargo_atualizado, reason=f"Convite VIP aceito (enviado por {self.dono})")
            
            container_sucesso = ui.Container(accent_color=discord.Color.green())
            container_sucesso.add_item(ui.TextDisplay(
                f"🎉 **Convite Aceito!**\n"
                f"{self.amigo.mention} agora possui o cargo {cargo_atualizado.mention}!"
            ))
            
            layout = ui.LayoutView()
            layout.add_item(container_sucesso)
            await interaction.response.send_message(view=layout)

            if self.panel_view:
                await self.panel_view.refresh_panel(interaction)

        except discord.Forbidden:
            await interaction.response.send_message("Não tenho permissão para atribuir este cargo :( consulte um administrador", ephemeral=True)

    async def on_timeout(self):
        if self.is_accepted:
            return

        container_expired = ui.Container(accent_color=discord.Color.dark_gray())
        container_expired.add_item(ui.TextDisplay(f"⏰ **Convite Expirado**\nO tempo para aceitar o cargo {self.role.name} esgotou."))
        layout = ui.LayoutView()
        layout.add_item(container_expired)
        try:
            if self.message:
                await self.message.edit(view=layout)
        except Exception:
            pass

# ==========================================
# PAINEL PRINCIPAL (LAYOUT V2)
# ==========================================
class VipRolePanel(ui.LayoutView):
    def __init__(self, cog, user, role):
        super().__init__(timeout=180)
        self.cog = cog
        self.user = user
        self.role = role

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "Ei! Este painel de cargo VIP pertence a outra pessoa. Você não pode mexer nele >:c",
                ephemeral=True
            )
            return False
        return True

    def build_interface(self):
        self.clear_items()

        if not self.role:
            container = ui.Container(accent_color=discord.Color.red())
            container.add_item(ui.TextDisplay("Sryy, mas **o seu cargo VIP não existe mais no servidor.**\nUse `/cargo criar` para gerar um novo."))
            self.add_item(container)
            return

        container = ui.Container(accent_color=self.role.color if self.role.color.value != 0 else discord.Color.blurple())

        membros_com_cargo = [m.mention for m in self.role.members if m.id != self.user.id]
        membros_str = ", ".join(membros_com_cargo) if membros_com_cargo else "_Nenhum amigo adicionado no momento_"

        texto = (
            f"## 👑 Painel do seu Cargo VIP\n"
            f"**Cargo:** {self.role.mention}\n"
            f"**Cor Hex:** `{str(self.role.color)}`\n\n"
            f"👥 **Amigos com acesso ({len(membros_com_cargo)}/5):**\n"
            f"{membros_str}\n\n"
            f"-# Utilize os botões abaixo para gerenciar seu cargo personalizado."
        )

        container.add_item(ui.TextDisplay(texto))

        # --- BOTÕES DE AÇÃO ---
        row1 = ui.ActionRow()
        
        btn_nome = ui.Button(label="Editar Nome", style=discord.ButtonStyle.primary, emoji="✏️")
        btn_nome.callback = self.callback_editar_nome

        btn_cor = ui.Button(label="Mudar Cor", style=discord.ButtonStyle.secondary, emoji="🎨")
        btn_cor.callback = self.callback_editar_cor

        btn_icone = ui.Button(label="Mudar Ícone", style=discord.ButtonStyle.secondary, emoji="🖼️")
        btn_icone.callback = self.callback_editar_icone

        btn_deletar = ui.Button(label="Deletar Cargo", style=discord.ButtonStyle.danger, emoji="🗑️")
        btn_deletar.callback = self.callback_deletar

        row1.add_item(btn_nome)
        row1.add_item(btn_cor)
        row1.add_item(btn_icone)
        row1.add_item(btn_deletar)
        container.add_item(row1)

        # --- SELETOR PARA ADICIONAR / REMOVER AMIGOS (Até 5) ---
        row2 = ui.ActionRow()
        select_membro = ui.UserSelect(
            placeholder="Selecione um membro para dar/remover o cargo...",
            min_values=1,
            max_values=1
        )
        select_membro.callback = self.callback_gerenciar_membro
        row2.add_item(select_membro)
        container.add_item(row2)

        self.add_item(container)

    async def refresh_panel(self, interaction: discord.Interaction):
        self.role = interaction.guild.get_role(self.role.id)
        self.build_interface()
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.edit_message(view=self)

    async def callback_editar_nome(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EditRoleNameModal(self.role, self))

    async def callback_editar_icone(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EditRoleIconModal(self.role, self))

    async def callback_editar_cor(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EditRoleColorModal(self.role, self))

    async def callback_gerenciar_membro(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Você não pode gerenciar os amigos de um cargo que não é seu uwu", ephemeral=True)
        
        await interaction.response.defer(ephemeral=False)

        membro_alvo = interaction.data['values'][0]
        membro = interaction.guild.get_member(int(membro_alvo))

        if not membro:
            return await interaction.followup.send("Membro não encontrado :(")

        if membro.bot:
            return await interaction.followup.send("Você não pode atribuir seu cargo a bots, bobinho TwT")

        if membro == interaction.user:
            return await interaction.followup.send("Você já é o dono do cargo principal ksks")

        if membro in self.role.members:
            await membro.remove_roles(self.role, reason=f"Removido pelo dono do VIP ({interaction.user})")
            await self.refresh_panel(interaction)
            return await interaction.followup.send(
                f"🗑️ O cargo foi removido de {membro.mention}.", 
                ephemeral=True
            )

        membros_com_cargo = [m for m in self.role.members if m.id != self.user.id]
        if len(membros_com_cargo) >= 5:
            return await interaction.followup.send(
                "⚠️ Você atingiu o limite máximo de **5 pessoas** compartilhando seu cargo TwT", 
                ephemeral=True
            )
        
        invite_view = VipInviteView(self.role, self.user, membro, self)
        msg_convite = await interaction.channel.send(view=invite_view)
        invite_view.message = msg_convite

        await interaction.followup.send(
            embed=discord.Embed(
                title="📩 Convite Enviado!", 
                description=f"Um convite foi enviado para {membro.mention} no chat. Tem **3 minutos** para aceitar!", 
                color=discord.Color.blue()
            )
        )

    async def callback_deletar(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Ei! Esse painel não é seu >:c", ephemeral=True)

        confirm_view = ConfirmDeleteView(self.cog, self.user, self.role, self)
        await interaction.response.edit_message(view=confirm_view)

        await interaction.response.defer(ephemeral=False)
        if self.role:
            try:
                await self.role.delete(reason=f"Deletado pelo dono ({interaction.user})")
            except discord.Forbidden:
                pass

        await self.cog.col_vips.delete_one({"_id": self.user.id, "guild_id": interaction.guild.id})
        
        embed = discord.Embed(title="🗑️ Cargo Deletado", description="Seu cargo VIP personalizado foi excluído com sucesso. Use `/cargo criar` se quiser gerar outro UwU", color=discord.Color.green())
        await interaction.followup.send(embed=embed)
        await interaction.delete_original_response()


# ==========================================
# COG PRINCIPAL DE CARGOS VIP
# ==========================================
class VipRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    SERVER_ID = 1410006076400599235  

    VIP_ROLE_IDS = [
        1411874300952318126, # Espresso Premium
        1415850384722886818 # Booster
    ]

    @property
    def col_vips(self):
        database = getattr(self.bot, "db", None)
        return database.vip_roles if database is not None else None

    cargo_group = app_commands.Group(
        name="cargo", 
        description="Gerencie seu cargo VIP personalizado",
        guild_ids=[1410006076400599235]
    )

    @cargo_group.command(name="painel", description="Abre o painel interativo de gerenciamento do seu cargo VIP.")
    async def cargo_painel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        # Checagem de VIP/Booster
        user_roles = [role.id for role in interaction.user.roles]
        tem_cargo_vip = any(role_id in self.VIP_ROLE_IDS for role_id in user_roles)
        eh_booster = interaction.user.premium_since is not None

        if not tem_cargo_vip and not eh_booster:
            return await interaction.followup.send(
                embed=discord.Embed(
                    title="Sinto muito :(", 
                    description="Apenas membros com **cargos VIP** ou **Server Boosters** podem criar e gerenciar cargos personalizados!", 
                    color=discord.Color.red()
                ),
            )

        if self.col_vips is None:
            return await interaction.followup.send("Banco de dados offline, consulte um administrador owo", ephemeral=True)

        registro = await self.col_vips.find_one({"_id": interaction.user.id, "guild_id": interaction.guild.id})
        
        if not registro:
            prompt_view = VipCreatePromptView(self)
            return await interaction.followup.send(view=prompt_view)

        role = interaction.guild.get_role(registro["role_id"])

        if not role:
            await self.col_vips.delete_one({"_id": interaction.user.id, "guild_id": interaction.guild.id})
            prompt_view = VipCreatePromptView(self)
            return await interaction.followup.send(
                embed=discord.Embed(title="Cargo Não Encontrado :(", description="Seu cargo personalizado antigo foi removido do servidor. Você pode criar um novo abaixo!", color=discord.Color.orange()),
                view=prompt_view
            )

        view = VipRolePanel(self, interaction.user, role)
        view.build_interface()

        await interaction.followup.send(view=view)

async def setup(bot):
    await bot.add_cog(VipRoles(bot))