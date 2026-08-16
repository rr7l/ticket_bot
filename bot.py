import discord
from discord.ext import commands
import os
import asyncio
import random

intents = discord.Intents.all()
client = commands.Bot(command_prefix="!", intents=intents)

@client.event
async def on_ready():
    print(f"👑 MASTER MULTIBOT IS ONLINE AS {client.user}!")
    await client.tree.sync()

TOKEN = os.getenv("TOKEN")
CATEGORY_ID = os.getenv("CATEGORY_ID")
SUPPORT_ROLE_ID = os.getenv("SUPPORT_ROLE_ID")

# ==========================================
# 🛡️ SECTION 1: SYSTEM & MODERATION (الإدارة والسيستم)
# ==========================================
@client.tree.command(name="clear", description="لتنظيف شات السيرفر وحذف الرسائل")
@discord.app_commands.default_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 تم تنظيف الغرفة وحذف {len(deleted)} رسالة بنجاح.", ephemeral=True)

@client.tree.command(name="mute", description="إعطاء ميوت لعضو في السيرفر")
@discord.app_commands.default_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int):
    duration = asyncio.subprocess.timedelta(minutes=minutes)
    await member.timeout(duration, reason="عقوبة إدارية")
    await interaction.response.send_message(f"🔒 تم تطبيق الميوت على {member.mention} لمدة {minutes} دقيقة.", ephemeral=True)

# ==========================================
# 🎮 SECTION 2: GAMES & ENTERTAINMENT (الألعاب والترفيه)
# ==========================================
@client.tree.command(name="game_guess", description="لعبة تخمين الرقم العشوائي")
async def game_guess(interaction: discord.Interaction, number: int):
    secret = random.randint(1, 10)
    if number == secret:
        await interaction.response.send_message(f"🎉 كفووو! تخمينك صحيح الرقم هو {secret} فعلاً! 🏆")
    else:
        await interaction.response.send_message(f"❌ خطأ! تخمينك غير صحيح، الرقم السري كان {secret}. جرب حظك مرة أخرى!")

# ==========================================
# 🎵 SECTION 3: MUSIC & AUDIO SYSTEM (الميوزك والقرآن)
# ==========================================
@client.tree.command(name="join", description="لجعل البوت يدخل رومك الصوتي")
async def join(interaction: discord.Interaction):
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        await channel.connect()
        await interaction.response.send_message(f"🔊 تم الاتصال بنجاح في: {channel.name}")
    else:
        await interaction.response.send_message("❌ يجب أن تكون متصلاً بروم صوتي أولاً!", ephemeral=True)

@client.tree.command(name="leave", description="لإخراج البوت من الروم الصوتي")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 تم الخروج من الروم الصوتي بنجاح.")
    else:
        await interaction.response.send_message("❌ البوت غير متصل بأي روم صوتي حالياً.", ephemeral=True)

# ==========================================
# 🎛️ SECTION 4: THE LUXURY DASHBOARD (لوحة الكنترول)
# ==========================================
class ServicesDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="اضغط هنا للتذكرة", description="فتح تذكرة دعم فني جديدة والتحدث مع الإدارة"),
            discord.SelectOption(label="اضغط هنا للشارات", description="عرض شارات التوثيق والرتب الخاصة بحسابك")
        ]
        super().__init__(placeholder="🛠️ خدمات الأعضاء والدعم الفني...", options=options, custom_id="srv_sel")

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        if self.values[0] == "اضغط هنا للتذكرة":
            category = interaction.guild.get_channel(int(CATEGORY_ID)) if CATEGORY_ID else None
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            }
            channel_ticket = await interaction.guild.create_text_channel(name=f"تيكت-{user.name}", category=category, overwrites=overwrites)
            await channel_ticket.send(content=f"{user.mention}", embed=discord.Embed(description="يرجى كتابة طلبك بوضوح وسيتم الرد عليك فوراً.", color=discord.Color.blue()))
            await interaction.response.send_message(f"✅ تم فتح تذكرتك في: {channel_ticket.mention}", ephemeral=True)
        elif self.values[0] == "اضغط هنا للشارات":
            embed = discord.Embed(title=f"🎖️ بطاقة هوية: {user.name}", color=discord.Color.gold())
            embed.add_field(name="الحالة الأمنية", value="👑 حساب موثق ونشط")
            await interaction.response.send_message(embed=embed, ephemeral=True)

class AdminDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="اضغط هنا للبحث", description="للبحث السريع عن الأعضاء والبيانات"),
            discord.SelectOption(label="اضغط هنا للنشر", description="خاص بالإدارة لبث ونشر إعلان رسمي عبر البوت")
        ]
        super().__init__(placeholder="⚙️ خيارات الإدارة والتحكم المتقدم...", options=options, custom_id="adm_sel")

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        if not user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ مخصص لمسؤولي السيرفر فقط!", ephemeral=True)
        await interaction.response.send_message(f"⚙️ تم تفعيل الخيار الإداري: **[{self.values[0]}]** بنجاح.", ephemeral=True)

class MasterControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ServicesDropdown())
        self.add_item(AdminDropdown())

@client.tree.command(name="control_setup", description="إرسال لوحة التحكم الملكية الشاملة")
@discord.app_commands.default_permissions(administrator=True)
async def control_setup(interaction: discord.Interaction, title: str, description: str, image_url: str = None, channel: discord.TextChannel = None):
    await interaction.response.defer(ephemeral=True)
    if not channel: channel = interaction.channel
    embed = discord.Embed(title=title, description=description, color=discord.Color.from_rgb(24, 28, 37))
    if image_url: embed.set_image(url=image_url)
    await channel.send(embed=embed, view=MasterControlView())
    await interaction.followup.send("✅ تم إرسال لوحة التحكم المتكاملة بنجاح وبسرعة صاروخية!", ephemeral=True)

if TOKEN: client.run(TOKEN)
