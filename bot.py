import discord
from discord.ext import commands
import json
import os
import io

intents = discord.Intents.all()
client = commands.Bot(command_prefix="!", intents=intents)

@client.event
async def on_ready():
    print(f"🔥 Ticket Overlord is ONLINE as {client.user}!")
    await client.tree.sync()

# جلب الإعدادات من الخزنة السرية
TOKEN = os.getenv("TOKEN")

# دالة لتسجيل المحادثة بصيغة احترافية (Transcript)
async def generate_transcript(channel: discord.TextChannel):
    transcript_text = f"--- TICKET TRANSCRIPT FOR #{channel.name} ---\n\n"
    async for message in channel.history(limit=None, oldest_first=True):
        if not message.author.bot:
            attachments = f" [Attachments: {', '.join([a.url for a in message.attachments])}]" if message.attachments else ""
            transcript_text += f"[{message.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {message.author}: {message.content}{attachments}\n"
    return transcript_text

# نافذة التحكم بالتذكرة بعد فتحها
class TicketControlView(discord.ui.View):
    def __init__(self, role_id, log_channel_id, user_id):
        super().__init__(timeout=None)
        self.role_id = role_id
        self.log_channel_id = log_channel_id
        self.user_id = user_id

    @discord.ui.button(label="استلام التذكرة", style=discord.ButtonStyle.green, emoji="✋", custom_id="claim_ticket")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(self.role_id)
        if role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ هذا الخيار مخصص لطاقم الدعم فقط!", ephemeral=True)
        
        embed = discord.Embed(title="⚡ تذكرة مستلمة", description=f"قام الإداري {interaction.user.mention} باستلام التذكرة وسيتم الرد عليك فوراً.", color=discord.Color.green())
        await interaction.channel.edit(name=f"🔓-استلام-{interaction.user.name}")
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(embed=embed)

    @discord.ui.button(label="قفل التذكرة", style=discord.ButtonStyle.red, emoji="🔒", custom_id="close_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(self.role_id)
        if role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ لا يمكنك قفل التذكرة إلا إذا كنت من طاقم الدعم!", ephemeral=True)
        
        user = interaction.guild.get_member(self.user_id)
        if user:
            await interaction.channel.set_permissions(user, view_channel=False)
        
        embed = discord.Embed(title="🔒 تذكرة مغلقة", description=f"تم قفل التذكرة بواسطة {interaction.user.mention}.\nيمكن للإدارة الآن حذف التذكرة وأرشفتها.", color=discord.Color.red())
        await interaction.channel.edit(name=f"🔒-مغلقة-{user.name if user else 'عضو'}")
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="أرشفة وحذف", style=discord.ButtonStyle.grey, emoji="🗑️", custom_id="delete_ticket")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(self.role_id)
        if role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ خيار الحذف النهائي مخصص للإدارة فقط!", ephemeral=True)
        
        await interaction.response.send_message("🔄 جاري توليد الأرشيف وحذف الغرفة خلال ثوانٍ...", ephemeral=True)
        
        # إنشاء الأرشيف (Transcript)
        transcript = await generate_transcript(interaction.channel)
        log_channel = interaction.guild.get_channel(self.log_channel_id)
        
        if log_channel:
            file_data = io.BytesIO(transcript.encode('utf-8'))
            discord_file = discord.File(fp=file_data, filename=f"transcript-{interaction.channel.name}.txt")
            
            log_embed = discord.Embed(title="📦 تذكرة مؤرشفة", color=discord.Color.dark_grey())
            log_embed.add_field(name="اسم التذكرة", value=interaction.channel.name, inline=True)
            log_embed.add_field(name="حُذفت بواسطة", value=interaction.user.mention, inline=True)
            await log_channel.send(embed=log_embed, file=discord_file)
            
        await interaction.channel.delete()

# القائمة المنسدلة الاحترافية لاختيار نوع المشكلة
class TicketDropdown(discord.ui.Select):
    def __init__(self, data_server):
        options = []
        for name, info in data_server.items():
            options.append(discord.SelectOption(label=name, description=f"اضغط لفتح تذكرة {name}", emoji=info.get("emoji", "📩")))
        super().__init__(placeholder="🌟 اختر القسم المناسب لمشكلتك من هنا...", min_values=1, max_values=1, options=options, custom_id="ticket_select")

    async def callback(self, interaction: discord.Interaction):
        server_id = str(interaction.guild.id)
        with open("button.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            
        ticket_data = data[server_id][self.values[0]]
        role_ticket = interaction.guild.get_role(ticket_data["role"])
        category = interaction.guild.get_channel(ticket_data["category"])
        user = interaction.user
        
        # وضع الصلاحيات للروم الجديد
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True, read_message_history=True),
            role_ticket: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True, read_message_history=True)
        }
        
        channel_name = f"{ticket_data['name']}-{user.name}"
        if category:
            channel_ticket = await category.create_text_channel(name=channel_name, overwrites=overwrites)
        else:
            channel_ticket = await interaction.guild.create_text_channel(name=channel_name, overwrites=overwrites)
            
        embed_ticket = discord.Embed(title=f"📬 تذكرة: {self.values[0]}", description=f"مرحباً بك {user.mention} في قسم الدعم الفني.\nالرجاء كتابة مشكلتك هنا بوضوح وسيقوم فريق العمل بالرد عليك فوراً.", color=discord.Color.blue())
        embed_ticket.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
        
        view = TicketControlView(ticket_data["role"], ticket_data["log"], user.id)
        await channel_ticket.send(content=f"{user.mention} | {role_ticket.mention if role_ticket else ''}", embed=embed_ticket, view=view)
        await interaction.response.send_message(f"✅ تم فتح تذكرتك بنجاح في روم: {channel_ticket.mention}", ephemeral=True)

class MainTicketView(discord.ui.View):
    def __init__(self, data_server):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown(data_server))

@client.tree.command(name="add_ticket", description="لأضافة تذاكر جديدة للأقسام")
@discord.app_commands.default_permissions(administrator=True)
async def add_ticket(interaction: discord.Interaction, name: str, name_ticket_room: str, log: discord.TextChannel, role: discord.Role, emoji_ticket: str, category: discord.CategoryChannel):
    server_id = str(interaction.guild.id)
    
    if not os.path.exists("button.json") or os.stat("button.json").st_size == 0:
        with open("button.json", "w", encoding="utf-8") as f:
            json.dump({}, f)

    with open("button.json", "r", encoding="utf-8") as f:
        try: data = json.load(f)
        except: data = {}
            
    if server_id not in data: data[server_id] = {}
        
    data[server_id][name] = {
        "name": name_ticket_room,
        "log": log.id,
        "role": role.id,
        "emoji": str(emoji_ticket),
        "category": category.id
    }
    with open("button.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
    await interaction.response.send_message(f"🔹 تم حفظ قسم التذكرة **[{name}]** بنجاح في قاعدة البيانات!", ephemeral=True)

@client.tree.command(name="ticket_setup", description="إرسال لوحة التذاكر الفخمة بالقائمة المنسدلة")
@discord.app_commands.default_permissions(administrator=True)
async def ticket_setup(interaction: discord.Interaction, description: str, channel: discord.TextChannel = None):
    await interaction.response.defer(ephemeral=True)
    if not channel: channel = interaction.channel
        
    with open("button.json", "r", encoding="utf-8") as f:
        try: data = json.load(f)
        except: data = {}
            
    server_id = str(interaction.guild.id)
    if server_id not in data or not data[server_id]:
        return await interaction.followup.send("❌ لا توجد أي أقسام تذاكر مضافة! استخدم `/add_ticket` أولاً.", ephemeral=True)
        
    embed = discord.Embed(title=f"🎫 نظام التذاكر المطور لـ {interaction.guild.name}", description=description, color=discord.Color.purple())
    if interaction.guild.icon: embed.set_image(url=interaction.guild.icon.url)
    
    view = MainTicketView(data[server_id])
    await channel.send(embed=embed, view=view)
    await interaction.followup.send(f"👑 تم إرسال نظام التذاكر الفخم في روم {channel.mention}!", ephemeral=True)

if TOKEN:
    client.run(TOKEN)
else:
    print("Error: NO TOKEN VARIABLE FOUND")
