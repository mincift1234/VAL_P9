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
scrim_profiles: Dict[str, Dict] = {}  # {custom_id: profile data}

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
    custom_id = None
    for row in ws.iter_rows(min_row=2, max_col=2):
        label = row[0].value
        content = row[1].value
        if not label or content is None:
            continue
        if label == "코치":
            profile["coach"] = content
        elif label == "감독":
            profile["manager"] = content
        elif label == "식별ID":
            custom_id = str(content).strip()
        elif label.startswith("선수"):
            if "(" in content and ")" in content:
                name, tier = content.split("(")
                profile["players"].append({"name": name.strip(), "tier": tier.replace(")", "").strip()})
            else:
                profile["players"].append({"name": content.strip(), "tier": "-"})
        elif label == "비고":
            profile["note"] = content
    return custom_id, profile

def format_scrim_embed(profile: Dict, title: str) -> discord.Embed:
    embed = discord.Embed(title=f"📨 {title} 스크림 프로필", color=discord.Color.blue())
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
        file_path = "scrim_template_with_id.xlsx"
        if not os.path.exists(file_path):
            await interaction.response.send_message("❌ 템플릿 파일이 존재하지 않습니다.", ephemeral=True)
            return
        file = discord.File(file_path, filename="스크림정보양식_with_ID.xlsx")
        await interaction.response.send_message(
            content="📎 아래 템플릿을 작성해 `/스크림정보업로드` 명령어로 다시 업로드해주세요.\n(식별ID 항목을 반드시 입력해주세요)",
            file=file,
            ephemeral=True
        )

    @bot.tree.command(name="스크림정보업로드", description="스크림 팀 정보를 업로드하고 저장합니다.")
    async def 스크림정보업로드(interaction: Interaction, 파일: discord.Attachment):
        if not 파일.filename.endswith(".xlsx"):
            await interaction.response.send_message("❌ .xlsx 형식의 엑셀 파일만 업로드 가능합니다.", ephemeral=True)
            return
        path = f"/tmp/{interaction.id}_scrim.xlsx"
        async with aiohttp.ClientSession() as session:
            async with session.get(파일.url) as resp:
                if resp.status == 200:
                    with open(path, "wb") as f:
                        f.write(await resp.read())
        try:
            custom_id, profile = parse_scrim_profile(path)
            if not custom_id:
                await interaction.response.send_message("❌ 엑셀 파일에 '식별ID' 항목이 필요합니다.", ephemeral=True)
                return
            scrim_profiles[custom_id] = profile
            await interaction.response.send_message(f"✅ 팀 정보가 식별 ID `{custom_id}` 기준으로 저장되었습니다.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 오류 발생: {e}", ephemeral=True)

    @bot.tree.command(name="스크림정보확인", description="스크림 팀 정보를 식별 ID로 확인합니다.")
    @app_commands.describe(식별ID="해당 팀의 고유 식별 ID")
    async def 스크림정보확인(interaction: Interaction, 식별ID: str):
        try:
            profile = scrim_profiles.get(식별ID)
            if not profile:
                await interaction.response.send_message("❌ 해당 ID로 등록된 팀 정보가 없습니다.", ephemeral=True)
                return
            embed = format_scrim_embed(profile, f"ID: {식별ID}")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 오류 발생: {e}", ephemeral=True)
