import discord
from discord.ext import commands
import json
import os
import io
import asyncio
from typing import Literal
from PIL import Image, ImageDraw, ImageFont, ImageOps
import requests

intents = discord.Intents.all()
client = commands.Bot(command_prefix="!", intents=intents)

@client.event
async def on_ready():
    print(f"👑 MULTIBOT OVERLORD V2 IS ONLINE AS {client.user}!")
    await client.tree.sync()

# جلب الإعدادات والرموز السرية من ريلواي
TOKEN = os.getenv("TOKEN")
TEMP_VOICE_ID = os.getenv("TEMP_VOICE_ID") # أيدي الروم الصوتي الرئيسي لصنع الغرف
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID") # أيدي روم السجلات العام
SUPPORT_ROLE_ID = os.getenv("SUPPORT_ROLE_ID") # أيدي رتبة الدعم الفني
CATEGORY_ID = os.getenv("CATEGORY_ID") # أيدي قسم التذاكر

# ==========================================
# 🛡️ SYSTEM 1: AUTO-MOD & ANTI-SPAM (أسلوب راقي)
# ==========================================
BAD_WORDS = ["زق", "كلب", "حمار", "تيس", "لعن"]
user_spam_counter = {}

@client.event
async def on_message(message):
    if message.author.bot: return

    if any(word in message.content for word in BAD_WORDS):
        await message.delete()
        await message.channel.send(f"✨ عذراً {message.author.mention}، يرجى الحفاظ على رقي شات السيرفر، طاب يومك! 🌸", delete_after=3)
        return

    author_id = message.author.id
    current_time = message.created_at.timestamp()
    if author_id not in user_spam_counter: user_spam_counter[author_id] = []
    user_spam_counter[author_id].append(current_time)
    user_spam_counter[author_id] = [t for t in user_spam_counter[author_id] if current_time - t < 3]
    
    if len(user_spam_counter[author_id]) > 4:
        await message.delete()
        await message.channel.send(f"⏳ {message.author.mention}، يرجى مهلاً وإرسال الرسائل بهدوء لتجنب التداخل.", delete_after=3)
        return

    await client.process_commands(message)

# ==========================================
# 🖼️ SYSTEM 2: LUXURY CARD WELCOMER (تصميم فخم)
# ==========================================
@client.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="welcome") or member.guild.system_channel
    if not channel: return

    # إنشاء بطاقة فخمة جداً بخلفية زجاجية مودرن
    base = Image.new("RGBA", (850, 320), (24, 28, 37, 255))
    draw = ImageDraw.Draw(base)
    
    # رسم إطار ذهبي فخم ومضيء
    draw.rounded_rectangle([(15, 15), (835, 305)], radius=20, fill=(35, 41, 55, 255), outline=(212, 175, 55, 255), width=2)
    
    # جلب الأفاتار وجعله دائرياً بإطار ذهبي
    try:
        avatar_url = member.display_avatar.url
        avatar_res = requests.get(avatar_url)
        avatar_img = Image.open(io.BytesIO(avatar_res.content)).convert("RGBA").resize((160, 160))
        mask = Image.new("L", (160, 160), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, 160, 160), fill=255)
        base.paste(avatar_img, (50, 80), mask)
        draw.ellipse((48, 78, 212, 242), outline=(212, 175, 55, 255), width=3)
    except: pass
    
    # النصوص الترحيبية المنسقة والراقية
    draw.text((250, 85), f"WELCOME TO THE EMPIRE", fill=(212, 175, 55, 255))
    draw.text((250, 140), f"العضو: {member.name}", fill=(255, 255, 255, 255))
    draw.text((250, 195), f"العضو رقم: #{member.guild.member_count}", fill=(170, 180, 195, 255))
    
    with io.BytesIO() as image_binary:
        base.save(image_binary, 'PNG')
        image_binary.seek(0)
        file = discord.File(fp=image_binary, filename='welcome_luxury.png')
        await channel.send(content=f"👑 انرت عالمنا الفخم يا بطل {member.mention}! يسعدنا انضمامك إلينا ✨", file=file)

# ==========================================
# 🎙️ SYSTEM 3: TEMP VOICE ROOMS (بواسطة الأيدي)
# ==========================================
@client.event
async def on_voice_state_update(member, before, after):
    if after.channel and str(after.channel.id) == TEMP_VOICE_ID:
        guild = member.guild
        category = after.channel.category
        new_channel = await guild.create_voice_channel(name=f"🎙️｜روم {member.name}", category=category)
        await new_channel.set_permissions(member, manage_channels=True, move_members=True)
        await member.move_to(new_channel)
        
        while len(new_channel.members) > 0:
            await asyncio.sleep(5)
        await new_channel.delete()

    if before.channel and before.channel.name.startswith("🎙️｜") and len(before.channel.members) == 0:
        await before.channel.delete()

# ==========================================
# 🎫 SYSTEM 4: LUXURY DROPDOWN TICKET SYSTEM
# ==========================================
class TicketControlView(discord.ui.View):
    def __init__(self, role_id, log_id, user_id):
        super().__init__(timeout=None)
        self.role_id = int(role_id) if role_id else None
        self.log_id = int(log_id) if log_id else None
        self.user_id = user_id

    @discord.ui.button(label="استلام التذكرة", style=discord.ButtonStyle.green, emoji="✋", custom_id="claim_premium")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.role_id and not interaction.user.guild_permissions.administrator:
            role = interaction.guild.get_role(self.role_id)
            if role not in interaction.user.roles:
                return await interaction.response.send_message("❌ هذا الخيار مخصص لطاقم الدعم المعتمد!", ephemeral=True)
        
        embed = discord.Embed(title="⚡ تذكرة مستلمة", description=f"قام الإداري {interaction.user.mention} باستلام التذكرة وهو جاهز لخدمتك الآن.", color=discord.Color.green())
        await interaction.channel.edit(name=f"🔓-مستلمة-{interaction.user.name}")
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(embed=embed)

    @discord.ui.button(label="قفل وحذف التذكرة", style=discord.ButtonStyle.red, emoji="🗑️", custom_id="close_premium")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.role_id and not interaction.user.guild_permissions.administrator:
            role = interaction.guild.get_role(self.role_id)
            if role not in interaction.user.roles:
                return await interaction.response.send_message("❌ خيار الحذف مخصص للإدارة والدعم الفني فقط!", ephemeral=True)
        
        await interaction.response.send_message("🔄 جاري إغلاق التذكرة وأرشتفها وحذف الروم خلال ثوانٍ...", ephemeral=True)
        await asyncio.sleep(3)
        await interaction.channel.delete()

class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="الدعم الفني العام", description="للمشاكل التقنية العامة والاستفسارات", emoji="🛠️"),
            discord.SelectOption(label="قسم الاشتراكات والشراء", description="لشراء الرتب، الشحن، والخدمات الفخمة", emoji="💳"),
            discord.SelectOption(label="الشكاوى والبلاغات", description="لتبليغ الإدارة عن أي مخالفات وسوء سلوك", emoji="⚠️")
        ]
        super().__init__(placeholder="👑 اختر القسم المناسب لمشكلتك من القائمة المنسدلة...", options=options, custom_id="dropdown_premium")

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

        prefix = "تيكت"
        if self.values[0] == "الدعم الفني العام": prefix = "🛠️-دعم"
        elif self.values[0] == "قسم الاشتراكات والشراء": prefix = "💳-شراء"
        elif self.values[0] == "الشكاوى والبلاغات": prefix = "⚠️-شكوى"

        channel_ticket = await interaction.guild.create_text_channel(name=f"{prefix}-{user.name}", category=category, overwrites=overwrites)
        view = TicketControlView(SUPPORT_ROLE_ID, LOG_CHANNEL_ID, user.id)
        
        embed_ticket = discord.Embed(title=f"📬 قسم: {self.values[0]}", description=f"مرحباً بك {user.mention} في الدعم الفني الخاص بنا.\nيرجى كتابة تفاصيل طلبك هنا بوضوح، وسيقوم الموظف المسؤول بالرد عليك فوراً والاستجابة لطلبك ✨.", color=discord.Color.gold())
        if interaction.guild.icon: embed_ticket.set_thumbnail(url=interaction.guild.icon.url)
        
        await channel_ticket.send(content=f"{user.mention}", embed=embed_ticket, view=view)
        await interaction.response.send_message(f"✅ تم فتح تذكرتك الفخمة بنجاح في: {channel_ticket.mention}", ephemeral=True)

class MainTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())

@client.tree.command(name="ticket_setup", description="إرسال قائمة التذاكر الفخمة الجاهزة والمعدلة")
@discord.app_commands.default_permissions(administrator=True)
async def ticket_setup(interaction: discord.Interaction, description: str, channel: discord.TextChannel = None):
    await interaction.response.defer(ephemeral=True)
    if not channel: channel = interaction.channel
        
    embed = discord.Embed(title=f"🎫 نظام الدعم الفني لـ {interaction.guild.name}", description=description, color=discord.Color.from_rgb(212, 175, 55))
    if interaction.guild.icon: embed.set_image(url=interaction.guild.icon.url)
    
    await channel.send(embed=embed, view=MainTicketView())
    await interaction.followup.send(f"👑 تم إرسال لوحة التذاكر الفخمة المنسدلة الجاهزة في روم {channel.mention}!", ephemeral=True)

if TOKEN: client.run(TOKEN)
else: print("Error: TOKEN NOT FOUND")
