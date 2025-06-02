# scrim_system.py

import discord
from discord import app_commands, Interaction
from discord.ext import commands
from discord.ui import View, Button
from typing import Dict

scrim_requests: Dict[int, Dict] = {}  # {target_guild_id: {from_guild_id, info}}

class ScrimRequestView(View):
    def __init__(self, from_guild_name: str, from_guild_id: int):
        super().__init__(timeout=600)
        self.from_guild_name = from_guild_name
        self.from_guild_id = from_guild_id

        accept_btn = Button(label="수락", style=discord.ButtonStyle.green)
        decline_btn = Button(label="거절", style=discord.ButtonStyle.danger)

        accept_btn.callback = self.accept
        decline_btn.callback = self.decline

        self.add_item(accept_btn)
        self.add_item(decline_btn)

    async def accept(self, interaction: Interaction):
        await interaction.response.send_message(f"✅ {self.from_guild_name}의 스크림 요청을 수락했습니다.")
        # 양쪽에 확정 메시지
        from_guild = self.from_guild_id
        target_guild = interaction.guild.id
        scrim_requests.pop(target_guild, None)

    async def decline(self, interaction: Interaction):
        await interaction.response.send_message("❌ 스크림 요청을 거절했습니다.", ephemeral=True)
        scrim_requests.pop(interaction.guild.id, None)

def add_scrim_commands(bot: commands.Bot):

    @bot.tree.command(name="스크림요청", description="다른 서버에 스크림을 요청합니다.")
    @app_commands.describe(target_guild_id="상대 서버의 ID")
    async def 스크림요청(interaction: Interaction, target_guild_id: str):
        try:
            guild_id = int(target_guild_id)
            target_guild = bot.get_guild(guild_id)
            if not target_guild:
                await interaction.response.send_message("❌ 봇이 해당 서버에 없습니다.", ephemeral=True)
                return

            scrim_requests[guild_id] = {
                "from": interaction.guild.id,
                "info": f"{interaction.guild.name} 서버에서 스크림을 요청했습니다."
            }

            for channel in target_guild.text_channels:
                if channel.permissions_for(target_guild.me).send_messages:
                    view = ScrimRequestView(interaction.guild.name, interaction.guild.id)
                    await channel.send(f"📨 {interaction.guild.name}에서 스크림 요청이 왔습니다!", view=view)
                    break
            await interaction.response.send_message("✅ 요청이 전송되었습니다.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 오류 발생: {e}", ephemeral=True)

    @bot.tree.command(name="스크림목록", description="스크림 요청을 확인합니다.")
    async def 스크림목록(interaction: Interaction):
        target = interaction.guild.id
        if target in scrim_requests:
            from_id = scrim_requests[target]['from']
            msg = scrim_requests[target]['info']
            await interaction.response.send_message(f"📋 요청됨: {msg} (from {from_id})", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 요청이 없습니다.", ephemeral=True)
