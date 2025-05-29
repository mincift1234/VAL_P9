import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from dotenv import load_dotenv
import os
from typing import List, Optional
from keep_alive import keep_alive

# 환경 변수에서 토큰 불러오기
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# 기본 설정
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# 티어 및 포지션 목록
티어목록 = ['언랭', '브론즈', '실버', '골드', '플래티넘', '다이아몬드', '초월자', '불멸', '레디언트']
포지션목록 = ['전략가', '타격대', '감시자', '척후대', '상관없음']
모드목록 = ['일반', '신속', '랭크', '스돌']

# 자동완성용 선택지
티어옵션 = [app_commands.Choice(name=t, value=t) for t in 티어목록]
포지션옵션 = [app_commands.Choice(name=p, value=p) for p in 포지션목록]
모드옵션 = [app_commands.Choice(name=m, value=m) for m in 모드목록]

# 티어 조건 범위 계산 함수
def get_허용티어(기준):
    idx = 티어목록.index(기준)
    return 티어목록[max(0, idx-1): min(len(티어목록), idx+2)]

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

class PartyJoinView(View):
    def __init__(self, max_players: int, leader: discord.Member, 허용티어: List[str], 필수포지션: List[str], 모드: str):
        super().__init__(timeout=None)
        self.max_players = max_players
        self.leader = leader
        self.허용티어 = 허용티어
        self.필수포지션 = 필수포지션
        self.모드 = 모드
        self.players: List[discord.Member] = [leader]
        self.voice_channel = None

        self.join_button = Button(label=f"참여 (1/{max_players})", style=discord.ButtonStyle.green)
        self.join_button.callback = self.join_party
        self.add_item(self.join_button)

        self.close_button = Button(label="파티 종료", style=discord.ButtonStyle.danger)
        self.close_button.callback = self.end_party
        self.add_item(self.close_button)

    async def join_party(self, interaction: discord.Interaction):
        user = interaction.user

        if user in self.players:
            await interaction.response.send_message("⚠️ 이미 참여 중입니다.", ephemeral=True)
            return

        user_roles = [r.name for r in user.roles]
        if self.모드 == "랭크":
            티어역할 = [t for t in self.허용티어 if t in user_roles]
            if not 티어역할:
                await interaction.response.send_message("❌ 티어 조건이 맞지 않습니다.", ephemeral=True)
                return

        포지션역할 = [p for p in self.필수포지션 if p == '상관없음' or p in user_roles]
        if not 포지션역할:
            await interaction.response.send_message("❌ 필요한 포지션이 아닙니다.", ephemeral=True)
            return

        if len(self.players) >= self.max_players:
            await interaction.response.send_message("❌ 인원이 이미 가득 찼습니다.", ephemeral=True)
            return

        self.players.append(user)
        self.join_button.label = f"참여 ({len(self.players)}/{self.max_players})"

        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"✅ {user.mention}님이 파티에 참여했습니다!", ephemeral=True)

        if len(self.players) == self.max_players:
            guild = interaction.guild
            category = discord.utils.get(guild.categories, name=self.모드)
            if category:
                overwrites = {guild.default_role: discord.PermissionOverwrite(connect=False)}
                for member in self.players:
                    overwrites[member] = discord.PermissionOverwrite(connect=True, view_channel=True)

                existing_channels = [ch.name for ch in category.voice_channels]
                count = 1
                while f"파티 {count}" in existing_channels:
                    count += 1

                self.voice_channel = await guild.create_voice_channel(
                    name=f"파티 {count}",
                    category=category,
                    user_limit=self.max_players,
                    overwrites=overwrites
                )
                await interaction.followup.send(f"📞 음성 채널이 생성되었습니다: {self.voice_channel.mention}", ephemeral=True)

    async def end_party(self, interaction: discord.Interaction):
        if interaction.user != self.leader:
            await interaction.response.send_message("❌ 리더만 종료할 수 있습니다.", ephemeral=True)
            return

        await self.clear_party()
        try:
            await interaction.message.delete()
        except Exception:
            pass
        await interaction.response.send_message("🛑 파티가 종료되었습니다.", ephemeral=True)

    async def clear_party(self):
        if self.voice_channel:
            try:
                await self.voice_channel.delete()
            except Exception:
                pass

@app_commands.choices(현재티어=티어옵션, 게임모드=모드옵션)
@bot.tree.command(name="파티생성", description="현재 티어와 포지션을 기반으로 파티를 생성합니다.")
@app_commands.describe(
    인원="파티 인원수 (본인 포함 2~5명)",
    포지션="필요한 포지션들 (쉼표로 구분: 감시자,척후대/상관없음)",
    게임모드="일반, 신속, 랭크, 스돌 중 선택"
)
@app_commands.choices(게임모드=모드옵션)
async def 파티생성(interaction: discord.Interaction,
                인원: int,
                현재티어: Optional[app_commands.Choice[str]],
                포지션: str,
                게임모드: app_commands.Choice[str]):

    if not (2 <= 인원 <= 5):
        await interaction.response.send_message("❌ 인원수는 본인 포함 3~5명이어야 합니다.", ephemeral=True)
        return

    포지션리스트 = [p.strip() for p in 포지션.split(",") if p.strip() in 포지션목록]
    if not 포지션리스트:
        await interaction.response.send_message("❌ 유효한 포지션이 없습니다. 예: 감시자,전략가", ephemeral=True)
        return

    모드 = 게임모드.value

    if 모드 == "랭크":
        if 현재티어 is None:
            await interaction.response.send_message("❌ 랭크 모드에서는 현재 티어를 지정해야 합니다.", ephemeral=True)
            return
        기준티어 = 현재티어.value
        허용티어 = get_허용티어(기준티어)
        조건텍스트 = f"🏆 티어 조건: {' / '.join(허용티어)}"
    else:
        허용티어 = []
        조건텍스트 = "🏆 티어 조건 없음"

    embed = discord.Embed(
        title=f"🎯 {모드} 모드 파티 모집",
        description=f"""
👤 리더: {interaction.user.mention} 

👥 인원: {인원}명  

{조건텍스트}  

🎯 포지션: {', '.join(포지션리스트)}  
        """,
        color=discord.Color.blue()
    )

    view = PartyJoinView(
        max_players=인원,
        leader=interaction.user,
        허용티어=허용티어,
        필수포지션=포지션리스트,
        모드=모드
    )

    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="역할생성", description="파티 기능에 필요한 티어/포지션/모드 역할들을 생성합니다.")
async def 역할생성(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    guild = interaction.guild
    생성된역할 = []

    역할이름목록 = 티어목록 + 포지션목록 + 모드목록

    for 이름 in 역할이름목록:
        if not discord.utils.get(guild.roles, name=s이름):
            await guild.create_role(name=이름)
            생성된역할.append(이름)

    if 생성된역할:
        await interaction.followup.send(f"✅ 다음 역할들이 생성되었습니다: {', '.join(생성된역할)}", ephemeral=True)
    else:
        await interaction.followup.send("✅ 모든 역할이 이미 존재합니다.", ephemeral=True)

keep_alive()
# 봇 실행
bot.run(TOKEN)
