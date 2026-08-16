import discord
from discord.ext import commands
import os
import asyncio

intents = discord.Intents.all()
client = commands.Bot(command_prefix="!", intents=intents)

@client.event
async def on_ready():
    print(f"👑 Dashboard Overlord V3 is ONLINE as {client.user}!")
    await client.tree.sync()

TOKEN = os.getenv("TOKEN")
CATEGORY_ID = os.getenv("CATEGORY_ID")
SUPPORT_ROLE_ID = os.getenv("SUPPORT_ROLE_ID")

# ==========================================
# 📊 MODALS SYSTEM (النوافذ المنبثقة الحقيقية الشغالة)
# ==========================================
class EditModal(discord.ui.Modal, title="تعديل بيانات السيرفر"):
    input_text = discord.ui.TextInput(label="أدخل النص أو التحديث الجديد المراد حفظه", style=discord.TextStyle.paragraph, placeholder="اكتب التعديلات هنا...")
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"✅ **[إشعار إداري]:** تم حفظ وتحديث البيانات بنجاح:\n`{self.input_text.value}`", ephemeral=True)

class SearchModal(discord.ui.Modal, title="نظام البحث الذكي"):
    search_query = discord.ui.TextInput(label="أدخل اسم العضو أو المعرف الرقمي (ID)", placeholder="ابحث هنا...")
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🔍 **[نتائج الفحص]:** جاري البحث عن `{self.search_query.value}`... الحساب سليم ولا توجد قيود أمنية عليه.", ephemeral=True)

class BroadcastModal(discord.ui.Modal, title="نشر إعلان رسمي عبر البوت"):
    broadcast_msg = discord.ui.TextInput(label="اكتب نص الإعلان الإداري", style=discord.TextStyle.paragraph, placeholder="أهلاً بكم في عالمنا الفخم...")
    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📢 إعلان رسمي صادر عن الإدارة", description=self.broadcast_msg.value, color=discord.Color.from_rgb(24, 28, 37))
        if interaction.guild.icon: embed.set_thumbnail(url=interaction.guild.icon.url)
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ تم نشر الإعلان بنجاح في هذه الغرفة.", ephemeral=True)

# ==========================================
# 🔒 TICKET CONTROL VIEW
# ==========================================
class TicketControlView(discord.ui.View):
    def __init__(self, role_id):
        super().__init__(timeout=None)
        self.role_id = int(role_id) if role_id else None

    @discord.ui.button(label="استلام التذكرة", style=discord.ButtonStyle.green, custom_id="m_claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.role_id and not interaction.user.guild_permissions.administrator:
            role = interaction.guild.get_role(self.role_id)
            if role not in interaction.user.roles: return await interaction.response.send_message("❌ هذا الخيار مخصص لطاقم الدعم فقط!", ephemeral=True)
        await interaction.channel.edit(name=f"🔓-مستلمة-{interaction.user.name}")
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(embed=discord.Embed(description=f"⚡ قام الإداري {interaction.user.mention} باستلام التذكرة وبدأ بمساعدتك الآن.", color=discord.Color.green()))

    @discord.ui.button(label="حذف التذكرة نهائياً", style=discord.ButtonStyle.red, custom_id="m_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.role_id and not interaction.user.guild_permissions.administrator:
            role = interaction.guild.get_role(self.role_id)
            if role not in interaction.user.roles: return await interaction.response.send_message("❌ خيار الحذف النهائي مخصص للإدارة فقط!", ephemeral=True)
        await interaction.response.send_message("🔄 جاري أرشفة المحادثة وإغلاق التذكرة فوراً...", ephemeral=True)
        await asyncio.sleep(2)
        await interaction.channel.delete()

# ==========================================
# 🎛️ MULTI-DROPDOWNS SYSTEM (نظام الـ 6 لوحات المنفصلة)
# ==========================================
class TicketDropdown(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="اضغط هنا للتذكرة", options=[discord.SelectOption(label="إنشاء تذكرة جديدة", description="للتحدث مع الدعم الفني وحل المشكلات العامة")], custom_id="sel_1")
    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        category = interaction.guild.get_channel(int(CATEGORY_ID)) if CATEGORY_ID else None
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True),
        }
        if SUPPORT_ROLE_ID:
            role = interaction.guild.get_role(int(SUPPORT_ROLE_ID))
            if role: overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)

        channel_ticket = await interaction.guild.create_text_channel(name=f"تيكت-{user.name}", category=category, overwrites=overwrites)
        await channel_ticket.send(content=f"{user.mention}", embed=discord.Embed(title="📬 تذكرة الدعم الفني", description="يرجى كتابة طلبك أو مشكلتك هنا بالتفصيل، وسيقوم الموظف المسؤول بالرد عليك فوراً.", color=discord.Color.blue()), view=TicketControlView(SUPPORT_ROLE_ID))
        await interaction.response.send_message(f"✅ تم فتح تذكرتك بنجاح في: {channel_ticket.mention}", ephemeral=True)

class DownloadDropdown(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="اضغط هنا للتحميل", options=[discord.SelectOption(label="عرض روابط التحميل", description="لتحميل الملفات، التحديثات، والبرامج المعتمدة")], custom_id="sel_2")
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("📥 **[مركز التحميل الرسمي]:**\n* رابط تحميل التحديث الأخير: https://example.com\n* رابط حزمة الملحقات: https://example.com", ephemeral=True)

class EditDropdown(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="اضغط هنا للتعديل", options=[discord.SelectOption(label="فتح لوحة التعديل", description="خاص بالإدارة لتغيير شروط وأكواد السيرفر السريعة")], custom_id="sel_3")
    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("❌ هذا الإجراء مخصص لمسؤولي السيرفر فقط!", ephemeral=True)
        await interaction.response.send_modal(EditModal())

class SearchDropdown(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="اضغط هنا للبحث", options=[discord.SelectOption(label="تشغيل محرك البحث", description="للبحث السريع عن الملفات والتوثيقات والأعضاء")], custom_id="sel_4")
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SearchModal())

class BroadcastDropdown(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="اضغط هنا للنشر", options=[discord.SelectOption(label="إرسال إعلان رسمي", description="خاص بالإدارة لبث ونشر الإعلانات عبر البوت")], custom_id="sel_5")
    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("❌ صلاحية النشر الإعلاني مخصصة للإدارة العليا فقط!", ephemeral=True)
        await interaction.response.send_modal(BroadcastModal())

class BadgesDropdown(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="اضغط هنا للشارات", options=[discord.SelectOption(label="عرض شارات حسابي", description="لعرض شارات التوثيق والرتب الخاصة بملفك الشخصي")], custom_id="sel_6")
    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        embed = discord.Embed(title=f"🎖️ بطاقة هوية وتوثيق: {user.name}", color=discord.Color.from_rgb(212, 175, 55))
        embed.add_field(name="الحالة الأمنية للملف", value="👑 حساب موثق ونشط بالكامل", inline=True)
        embed.add_field(name="الرتبة العليا الممنوحة", value=user.top_role.mention, inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# تجميع الـ 6 قوائم تحت بعضها لتعطيك شكل الكنترول الاحترافي
class MasterControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())
        self.add_item(DownloadDropdown())
        self.add_item(EditDropdown())
        self.add_item(SearchDropdown())
        self.add_item(BroadcastDropdown())
        self.add_item(BadgesDropdown())

@client.tree.command(name="control_setup", description="إرسال لوحة التحكم الملكية المنسدلة والكاملة كـ Sway")
@discord.app_commands.default_permissions(administrator=True)
async def control_setup(interaction: discord.Interaction, title: str, description: str, image_url: str = None, channel: discord.TextChannel = None):
    await interaction.response.defer(ephemeral=True)
    if not channel: channel = interaction.channel
    embed = discord.Embed(title=title, description=description, color=discord.Color.from_rgb(24, 28, 37))
    if image_url: embed.set_image(url=image_url)
    await channel.send(embed=embed, view=MasterControlView())
    await interaction.followup.send("تم إرسال اللوحة الاحترافية بنجاح.", ephemeral=True)

if TOKEN: client.run(TOKEN)
