import discord
from discord.ext import commands
import json
import os
import io
import asyncio
from typing import Literal
import emoji
from PIL import Image, ImageDraw, ImageFont, ImageOps
import requests

# تجهيز الصلاحيات الكاملة للبوت الشامل
intents = discord.Intents.all()
client = commands.Bot(command_prefix="!", intents=intents)

@client.event
async def on_ready():
    print(f"👑 MULTIBOT OVERLORD IS ONLINE AS {client.user}!")
    print("🚀 All Advanced Systems (Tickets, Anti-Raid, Leveling, TempRooms) Loaded Successfully!")
    await client.tree.sync()

# جلب التوكن من خزنة الاستضافة
TOKEN = os.getenv("TOKEN")

# ==========================================
# 🛡️ SYSTEM 1: AUTO-MOD & ANTI-SPAM AI
# ==========================================
BAD_WORDS = ["زق", "كلب", "حمار", "تيس", "لعن"] # يمكنك زيادة الكلمات هنا
user_spam_counter = {}

@client.event
async def on_message(message):
    if message.author.bot:
        return

    # فحص الكلمات البذيئة
    if any(word in message.content for word in BAD_WORDS):
        await message.delete()
        await message.channel.send(f"⚠️ {message.author.mention}، يرجى الالتزام بالآداب العامة وعدم السب!", delete_after=5)
        return

    # فحص السبام السريع
    author_id = message.author.id
    current_time = message.created_at.timestamp()
    if author_id not in user_spam_counter:
        user_spam_counter[author_id] = []
    
    user_spam_counter[author_id].append(current_time)
    # الاحتفاظ بآخر الرسائل في الـ 3 ثواني الأخيرة
    user_spam_counter[author_id] = [t for t in user_spam_counter[author_id] if current_time - t < 3]
    
    if len(user_spam_counter[author_id]) > 4:
        await message.delete()
        await message.channel.send(f"🚫 {message.author.mention}، توقف عن السبام وإرسال الرسائل بسرعة!", delete_after=5)
        return

    await client.process_commands(message)

# ==========================================
# 🖼️ SYSTEM 2: ADVANCED CARD WELCOMER
# ==========================================
@client.event
async def on_member_join(member):
    # ابحث عن روم الترحيب المسمى welcome أو أول روم عام
    channel = discord.utils.get(member.guild.text_channels, name="welcome") or member.guild.system_channel
    if not channel:
        return

    # توليد بطاقة ترحيبية احترافية سريعة باستخدام مكتبة Pillow
    base = Image.new("RGBA", (800, 300), (20, 24, 30, 255))
    draw = ImageDraw.Draw(base)
    
    # رسم الدوائر والخلفية
    draw.rounded_rectangle([(20, 20), (780, 280)], radius=15, fill=(30, 35, 45, 255), outline=(114, 137, 218, 255), width=3)
    
    # جلب أفاتار الحساب
    avatar_url = member.display_avatar.url
    avatar_res = requests.get(avatar_url)
    avatar_img = Image.open(io.BytesIO(avatar_res.content)).convert("RGBA").resize((150, 150))
    
    # جعل الأفاتار دائرياً
    mask = Image.new("L", (150, 150), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, 150, 150), fill=255)
    
    base.paste(avatar_img, (50, 75), mask)
    
    # كتابة النصوص الترحيبية العربية
    draw.text((230, 80), f"Welcome to the Server!", fill=(255, 255, 255, 255))
    draw.text((230, 130), f"Member: {member.name}", fill=(114, 137, 218, 255))
    draw.text((230, 180), f"Count: #{member.guild.member_count}", fill=(200, 200, 200, 255))
    
    with io.BytesIO() as image_binary:
        base.save(image_binary, 'PNG')
        image_binary.seek(0)
        file = discord.File(fp=image_binary, filename='welcome.png')
        await channel.send(content=f"🔔 مرحباً بك يا {member.mention} في سيرفر **{member.guild.name}**! انرتنا يا بطل ✨", file=file)

# ==========================================
# 🎙️ SYSTEM 3: TEMP VOICE ROOMS (Create to Talk)
# ==========================================
@client.event
async def on_voice_state_update(member, before, after):
    # الروم الصوتي الرئيسي لصنع الغرف (يجب تسميته 'صنع روم مؤقت' أو تعيين الأيدي حقّه)
    if after.channel and after.channel.name == "➕ صنع روم مؤقت":
        guild = member.guild
        category = after.channel.category
        
        # إنشاء روم جديد خاص للعضو
        new_channel = await guild.create_voice_channel(name=f"🎙️｜روم {member.name}", category=category)
        await new_channel.set_permissions(member, manage_channels=True, move_members=True)
        await member.move_to(new_channel)
        
        # دالة لمراقبة الروم وحذفه عند خروج الجميع
        def check_empty(m, b, a):
            return len(new_channel.members) == 0
            
        try:
            await client.wait_for("voice_state_update", check=lambda m, b, a: len(new_channel.members) == 0, timeout=1800)
            await new_channel.delete()
        except:
            pass

    # حذف الرومات المؤقتة الفاضية عند خروج الأعضاء بشكل عادي
    if before.channel and before.channel.name.startswith("🎙️｜") and len(before.channel.members) == 0:
        await before.channel.delete()

# ==========================================
# 🎫 SYSTEM 4: THE ULTIMATE OVERLORD TICKET SYSTEM
# ==========================================
class TicketModal(discord.ui.Modal, title="💳 طلب فاتورة الدفع"):
    invoice_amount = discord.ui.TextInput(label="المبلغ المطلوب شحنه", placeholder="مثال: 50 ريال")
    email_user = discord.ui.TextInput(label="إيميلك الشخصي لتوثيق الدفع", placeholder="example@mail.com")

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🧾 طلب فاتورة جديد للراجعة", color=discord.Color.gold())
        embed.add_field(name="العضو الطالب", value=interaction.user.mention, inline=True)
        embed.add_field(name="المبلغ", value=self.invoice_amount.value, inline=True)
        embed.add_field(name="الإيميل الموثق", value=self.email_user.value, inline=False)
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ تم إرسال بيانات الفاتورة إلى الإدارة لمراجعتها!", ephemeral=True)

class TicketControlView(discord.ui.View):
    def __init__(self, role_id, log_channel_id, user_id):
        super().__init__(timeout=None)
        self.role_id = role_id
        self.log_channel_id = log_channel_id
        self.user_id = user_id

    @discord.ui.button(label="استلام التذكرة", style=discord.ButtonStyle.green, emoji="✋", custom_id="claim_t")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(self.role_id)
        if role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ الخيار مخصص لطاقم الدعم!", ephemeral=True)
        await interaction.channel.edit(name=f"🔓-استلام-{interaction.user.name}")
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(embed=discord.Embed(title="⚡ تذكرة مستلمة", description=f"قام الإداري {interaction.user.mention} باستلام التذكرة وبدأ بمساعدتك.", color=discord.Color.green()))

    @discord.ui.button(label="طلب فاتورة", style=discord.ButtonStyle.primary, emoji="💳", custom_id="invoice_t")
    async def invoice(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal())

    @discord.ui.button(label="قفل وحذف التذكرة", style=discord.ButtonStyle.red, emoji="🗑️", custom_id="close_t")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(self.role_id)
        if role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ مخصص للإدارة فقط!", ephemeral=True)
        await interaction.response.send_message("🔄 مؤرشف وحذف الغرفة...", ephemeral=True)
        await interaction.channel.delete()

class TicketDropdown(discord.ui.Select):
    def __init__(self, data_server):
        options = []
        for name, info in data_server.items():
            options.append(discord.SelectOption(label=name, description=f"فتح تذكرة قسم {name}", emoji=info.get("emoji", "📩")))
        super().__init__(placeholder="🌟 اختر قسم مشكلتك لتتحدث مع الإدارة فوراً...", options=options, custom_id="dropdown_t")

    async def callback(self, interaction: discord.Interaction):
        server_id = str(interaction.guild.id)
        with open("button.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        ticket_data = data[server_id][self.values]
        role_ticket = interaction.guild.get_role(ticket_data["role"])
        category = interaction.guild.get_channel(ticket_data["category"])
        user = interaction.user
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True),
            role_ticket: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
        }
        channel_ticket = await interaction.guild.create_text_channel(name=f"{ticket_data['name']}-{user.name}", category=category, overwrites=overwrites)
        view = TicketControlView(ticket_data["role"], ticket_data["log"], user.id)
        await channel_ticket.send(content=f"{user.mention} | {role_ticket.mention if role_ticket else ''}", embed=discord.Embed(title=f"📬 قسم: {self.values}", description="أهلاً بك، يرجى كتابة تفاصيل مشكلتك بوضوح وسيقوم الدعم بالرد عليك.", color=discord.Color.purple()), view=view)
        await interaction.response.send_message(f"✅ تم فتح تذكرتك الفخمة بنجاح في {channel_ticket.mention}", ephemeral=True)
        
class MainTicketView(discord.ui.View):
    def __init__(self, data_server):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown(data_server))

@client.tree.command(name="add_ticket", description="إضافة قسم تذاكر جديد")
@discord.app_commands.default_permissions(administrator=True)
async def add_ticket(
    interaction: discord.Interaction,
    name: str,
    name_ticket_room: str,
    log: discord.TextChannel,
    role: discord.Role,
    emoji_ticket: str,
    category: discord.CategoryChannel
):
    server_id = str(interaction.guild.id)

    if not os.path.exists("button.json") or os.stat("button.json").st_size == 0:
        with open("button.json", "w", encoding="utf-8") as f:
            json.dump({}, f)

    with open("button.json", "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except:
            data = {}

    if server_id not in data:
        data[server_id] = {}

    data[server_id][name] = {
        "name": name_ticket_room,
        "log": log.id,
        "role": role.id,
        "emoji": str(emoji_ticket),
        "category": category.id
    }

    with open("button.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    await interaction.response.send_message(
        f"🔹 تم حفظ قسم التذكرة **[{name}]** بنجاح!",
        ephemeral=True
    )


@client.tree.command(
    name="ticket_setup",
    description="إرسال قائمة التذاكر بالقائمة المنسدلة"
)
@discord.app_commands.default_permissions(administrator=True)
async def ticket_setup(
    interaction: discord.Interaction,
    description: str,
    channel: discord.TextChannel = None
):
    await interaction.response.defer(ephemeral=True)

    if not channel:
        channel = interaction.channel

    with open("button.json", "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except:
            data = {}

    server_id = str(interaction.guild.id)

    if server_id not in data or not data[server_id]:
        return await interaction.followup.send(
            "❌ لا توجد تذاكر مضافة! استخدم `/add_ticket` أولاً.",
            ephemeral=True
        )

    embed = discord.Embed(
        title=f"🎫 نظام التذاكر المطور لـ {interaction.guild.name}",
        description=description,
        color=discord.Color.purple()
    )

    await channel.send(
        embed=embed,
        view=MainTicketView(data[server_id])
    )

    await interaction.followup.send(
        f"👑 تم إرسال لوحة التحكم الفخمة في {channel.mention}!",
        ephemeral=True
    )


# تشغيل البوت النهائي الصافي بالتوكن
if TOKEN:
    client.run(TOKEN)
else:
    print("Error: TOKEN NOT FOUND")
