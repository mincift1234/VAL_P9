import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from dotenv import load_dotenv
import os
from typing import List

# 환경 변수에서 토큰 불러오기
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# 기본 설정
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# 티어 및 포지션 목록
티어목록 = ['언랭', '브론즈', '실버', '골드', '플래티넘', '다이아몬드', '초월자', '불멸', '레디언트']
포지션목록 = ['전략가', '타격대', '감시자', '척후대']
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

# 참여 버튼 뷰 클래스
class PartyJoinView(View):
    def __init__(self, max_players: int, leader: discord.Member, 허용티어: List[str], 필수포지션: List[str]):
        super().__init__(timeout=None)
        self.max_players = max_players
        self.leader = leader
        self.허용티어 = 허용티어
        self.필수포지션 = 필수포지션
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
        티어역할 = [t for t in self.허용티어 if t in user_roles]
        포지션역할 = [p for p in self.필수포지션 if p in user_roles]

        if not 티어역할:
            await interaction.response.send_message("❌ 티어 조건이 맞지 않습니다.", ephemeral=True)
            return
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

        # 최대 인원 도달 시 음성 채널 생성
        if len(self.players) == self.max_players:
            guild = interaction.guild
            category = discord.utils.get(guild.categories, name="랭크")
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
        await interaction.message.delete()
        await interaction.response.send_message("🛑 파티가 종료되었습니다.", ephemeral=True)

    async def clear_party(self):
        if self.voice_channel:
            try:
                await self.voice_channel.delete()
            except Exception:
                pass

# /등록 명령어
@bot.tree.command(name="등록", description="티어 / 포지션 / 게임모드를 등록하고 역할을 부여합니다.")
@app_commands.describe(
    티어="티어 선택 (랭크일 경우 필수)",
    포지션="자신의 포지션 선택",
    게임모드="일반, 신속, 랭크, 스돌 중 선택"
)
@app_commands.choices(티어=티어옵션, 포지션=포지션옵션, 게임모드=모드옵션)
async def 등록(interaction: discord.Interaction,
              티어: app_commands.Choice[str],
              포지션: app_commands.Choice[str],
              게임모드: app_commands.Choice[str]):

    await interaction.response.defer(ephemeral=True)
    user = interaction.user
    guild = interaction.guild

    티어 = 티어.value
    포지션 = 포지션.value
    게임모드 = 게임모드.value

    if 게임모드 == "랭크":
        부여할역할 = [티어, 포지션, 게임모드]
    else:
        부여할역할 = [포지션, 게임모드]

    모든역할 = 티어목록 + 포지션목록 + 모드목록
    제거대상 = [
        role for role in user.roles
        if role.name in 모든역할 and role.position < guild.me.top_role.position
    ]
    if 제거대상:
        await user.remove_roles(*제거대상)

    역할들 = []
    for 이름 in 부여할역할:
        역할 = discord.utils.get(guild.roles, name=이름)
        if 역할:
            역할들.append(역할)

    if 역할들:
        await user.add_roles(*역할들)
        await interaction.followup.send(f"✅ 역할 등록 완료: {', '.join(r.name for r in 역할들)}", ephemeral=True)
    else:
        await interaction.followup.send("❌ 역할을 찾을 수 없습니다. 관리자에게 문의하세요.", ephemeral=True)

# /파티생성 명령어
@bot.tree.command(name="파티생성", description="현재 티어와 포지션을 기반으로 파티를 생성합니다.")
@app_commands.describe(
    인원="파티 인원수 (2~5명)",
    현재티어="본인의 현재 티어",
    포지션="필요한 포지션들 (쉼표로 구분: 감시자,척후대)"
)
@app_commands.choices(현재티어=티어옵션)
async def 파티생성(interaction: discord.Interaction,
                인원: int,
                현재티어: app_commands.Choice[str],
                포지션: str):

    if not (2 <= 인원 <= 5):
        await interaction.response.send_message("❌ 인원수는 2~5명 사이여야 합니다.", ephemeral=True)
        return

    포지션리스트 = [p.strip() for p in 포지션.split(",") if p.strip() in 포지션목록]
    if not 포지션리스트:
        await interaction.response.send_message("❌ 유효한 포지션이 없습니다. 예: 감시자,전략가", ephemeral=True)
        return

    기준티어 = 현재티어.value
    허용티어 = get_허용티어(기준티어)

    embed = discord.Embed(
        title="🎯 신규 파티 모집",
        description=f"""
👤 리더: {interaction.user.mention}  
👥 인원: {인원}명  
🏆 티어 조건: {' / '.join(허용티어)}  
🎯 포지션: {', '.join(포지션리스트)}  
        """,
        color=discord.Color.green()
    )

    view = PartyJoinView(max_players=인원, leader=interaction.user, 허용티어=허용티어, 필수포지션=포지션리스트)
    await interaction.response.send_message(embed=embed, view=view)

# 수동 동기화 명령어
@bot.tree.command(name="sync", description="명령어 수동 동기화")
async def sync(interaction: discord.Interaction):
    await bot.tree.sync()
    await interaction.response.send_message("✅ 명령어 동기화 완료", ephemeral=True)

# 봇 실행
bot.run(TOKEN)
