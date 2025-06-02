# scrim_system.py

import discord
from discord import app_commands, Interaction
from discord.ext import commands
from discord.ui import View, Button
from typing import Dict, List
import aiohttp
import openpyxl
import os

scrim_requests: Dict[int, Dict] = {}  # {target_guild_id: {from_guild_id, info}}
scrim_profiles: Dict[int, Dict] = {}  # {guild_id: profile data}

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
        scrim_requests.pop(interaction.guild.id, None)

    async def decline(self, interaction: Interaction):
        await interaction.response.send_message("❌ 스크림 요청을 거절했습니다.", ephemeral=True)
        scrim_requests.pop(interaction.guild.id, None)

def parse_scrim_profile(path: str):
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    profile = {
        "coach": None,
        "manager": None,
        "players": [],
        "note": None
    }
    for row in ws.iter_rows(min_row=2, max_col=2):
        label = row[0].value
        content = row[1].value
        if not label or content is None:
            continue
        if label == "코치":
            profile["coach"] = content
        elif label == "감독":
            profile["manager"] = content
        elif label.startswith("선수"):
            if "(" in content and ")" in content:
                name, tier = content.split("(")
                profile["players"].append({"name": name.strip(), "tier": tier.replace(")", "").strip()})
            else:
                profile["players"].append({"name": content.strip(), "tier": "-"})
        elif label == "비고":
            profile["note"] = content
    return profile

def format_scrim_embed(profile: Dict, guild_name: str) -> discord.Embed:
    embed = discord.Embed(title=f"📨 {guild_name} 스크림 요청", color=discord.Color.blue())
    embed.add_field(name="🎓 코치", value=profile.get("coach", "-"), inline=True)
    embed.add_field(name="🧑‍💼 감독", value=profile.get("manager", "-"), inline=True)
    players = profile.get("players", [])
    player_lines = [f"{p['name']} ({p['tier']})" for p in players]
    embed.add_field(name="🧑‍🎮 선수들", value="\n".join(player_lines) if player_lines else "-", inline=False)
    if profile.get("note"):
        embed.add_field(name="📝 비고", value=profile["note"], inline=False)
    return embed

def add_scrim_commands(bot: commands.Bot):

    @bot.tree.command(name="스크림정보양식", description="스크림 정보 입력용 엑셀 템플릿을 다운로드합니다.")
    async def 스크림정보양식(interaction: Interaction):
        file_path = "scrim_template_pro.xlsx"
        if not os.path.exists(file_path):
            await interaction.response.send_message("❌ 템플릿 파일이 존재하지 않습니다.", ephemeral=True)
            return

        file = discord.File(file_path, filename="스크림정보양식.xlsx")
        await interaction.response.send_message(
        content="📎 아래 템플릿을 작성해 `/스크림정보업로드` 명령어로 다시 업로드해주세요.",
        file=file,
        ephemeral=True
    )


    @bot.tree.command(name="스크림정보업로드", description="스크림 팀 정보를 업로드하고 저장합니다.")
    async def 스크림정보업로드(interaction: Interaction, 파일: discord.Attachment):
        if not 파일.filename.endswith(".xlsx"):
            await interaction.response.send_message("❌ .xlsx 형식의 엑셀 파일만 업로드 가능합니다.", ephemeral=True)
            return
        path = f"/tmp/{interaction.guild.id}_scrim.xlsx"
        async with aiohttp.ClientSession() as session:
            async with session.get(파일.url) as resp:
                if resp.status == 200:
                    with open(path, "wb") as f:
                        f.write(await resp.read())
        try:
            profile = parse_scrim_profile(path)
            scrim_profiles[interaction.guild.id] = profile
            await interaction.response.send_message("✅ 팀 정보가 성공적으로 저장되었습니다.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 오류 발생: {e}", ephemeral=True)

    @bot.tree.command(name="스크림정보확인", description="현재 서버의 스크림 팀 정보를 확인합니다.")
    async def 스크림정보확인(interaction: Interaction):
        profile = scrim_profiles.get(interaction.guild.id)
        if not profile:
            await interaction.response.send_message("❌ 등록된 팀 정보가 없습니다.", ephemeral=True)
            return
        embed = format_scrim_embed(profile, interaction.guild.name)
        await interaction.response.send_message(embed=embed, ephemeral=True)

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

            profile = scrim_profiles.get(interaction.guild.id, {})
            embed = format_scrim_embed(profile, interaction.guild.name)
            view = ScrimRequestView(interaction.guild.name, interaction.guild.id)

            for channel in target_guild.text_channels:
                if channel.permissions_for(target_guild.me).send_messages:
                    await channel.send(embed=embed, view=view)
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

