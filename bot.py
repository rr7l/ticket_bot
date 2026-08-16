import discord
from discord.ext import commands
import os
import asyncio

intents = discord.Intents.all()
client = commands.Bot(command_prefix="!", intents=intents)

@client.event
async def on_ready():
    print(f"Control Panel is ONLINE as {client.user}!")
    await client.tree.sync()

TOKEN = os.getenv("TOKEN")
CATEGORY_ID = os.getenv("CATEGORY_ID")
SUPPORT_ROLE_ID = os.getenv("SUPPORT_ROLE_ID")

# النوافذ المنبثقة البسيطة
class EditModal(discord.ui.Modal, title="تعديل البيانات"):
    input_text = discord.ui.TextInput(label="أدخل التعديل الجديد", style=discord.TextStyle.paragraph)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"تم حفظ التعديل: {self.input_text.value}", ephemeral=True)

class SearchModal(discord.ui.Modal, title="البحث"):
    search_query = discord.ui.TextInput(label="أدخل كلمة البحث")
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"نتائج البحث عن {self.search_query.value}: لا توجد نتائج.", ephemeral=True)

class BroadcastModal(discord.ui.Modal, title="نشر إعلان"):
    broadcast_msg = discord.ui.TextInput(label="اكتب نص الإعلان", style=discord.TextStyle.paragraph)
    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(description=self.broadcast_msg.value, color=discord.Color.from_rgb(24, 28, 37))
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("تم النشر بنجاح.", ephemeral=True)

class TicketControlView(discord.ui.View):
    def __init__(self, role_id, user_id):
        super().__init__(timeout=None)
        self.role_id = int(role_id) if role_id else None
        self.user_id = user_id

    @discord.ui.button(label="استلام التذكرة", style=discord.ButtonStyle.green, custom_id="c_claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.role_id and not interaction.user.guild_permissions.administrator:
            role = interaction.guild.get_role(self.role_id)
            if role not in interaction.user.roles: return await interaction.response.send_message("مخصص للدعم فقط.", ephemeral=True)
        await interaction.channel.edit(name=f"مستلمة-{interaction.user.name}")
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send("تم استلام التذكرة وسيتم الرد عليك.")

    @discord.ui.button(label="حذف التذكرة", style=discord.ButtonStyle.red, custom_id="c_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.role_id and not interaction.user.guild_permissions.administrator:
            role = interaction.guild.get_role(self.role_id)
            if role not in interaction.user.roles: return await interaction.response.send_message("مخصص للإدارة فقط.", ephemeral=True)
        await interaction.response.send_message("جاري الحذف...", ephemeral=True)
        await asyncio.sleep(2)
        await interaction.channel.delete()

# نظام القوائم الستة الصافية
class ControlDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="اضغط هنا للتذكرة", description="فتح تذكرة دعم فني جديدة"),
            discord.SelectOption(label="اضغط هنا للتحميل", description="روابط تحميل ملفات السيرفر المعتمدة"),
            discord.SelectOption(label="اضغط هنا للتعديل", description="تعديل البيانات والإعدادات السريعة"),
            discord.SelectOption(label="اضغط هنا للبحث", description="البحث الذكي عن الأعضاء والملفات"),
            discord.SelectOption(label="اضغط هنا للنشر", description="كتابة ونشر إعلان رسمي عبر البوت"),
            discord.SelectOption(label="اضغط هنا للشارات", description="عرض شارات وتوثيق حسابك الحالي")
        ]
        super().__init__(placeholder="اختر الإجراء المطلوب...", options=options, custom_id="clean_master_select")

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        selected = self.values

        if selected == "اضغط هنا للتذكرة":
            category = interaction.guild.get_channel(int(CATEGORY_ID)) if CATEGORY_ID else None
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True),
            }
            if SUPPORT_ROLE_ID:
                role = interaction.guild.get_role(int(SUPPORT_ROLE_ID))
                if role: overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)

            channel_ticket = await interaction.guild.create_text_channel(name=f"تيكت-{user.name}", category=category, overwrites=overwrites)
            await channel_ticket.send(content=f"{user.mention}", embed=discord.Embed(description="يرجى كتابة طلبك بوضوح وسيتم الرد عليك.", color=discord.Color.blue()), view=TicketControlView(SUPPORT_ROLE_ID, user.id))
            await interaction.response.send_message(f"تم فتح التذكرة في: {channel_ticket.mention}", ephemeral=True)

        elif selected == "اضغط هنا للتحميل":
            await interaction.response.send_message("📥 روابط التحميل الرسمية: [ضع الروابط هنا لاحقاً عبر الكود]", ephemeral=True)

        elif selected == "اضغط هنا للتعديل":
            if not user.guild_permissions.administrator: return await interaction.response.send_message("مخصص للإدارة فقط.", ephemeral=True)
            await interaction.response.send_modal(EditModal())

        elif selected == "اضغط هنا للبحث":
            await interaction.response.send_modal(SearchModal())

        elif selected == "اضغط هنا للنشر":
            if not user.guild_permissions.administrator: return await interaction.response.send_message("مخصص للإدارة فقط.", ephemeral=True)
            await interaction.response.send_modal(BroadcastModal())

        elif selected == "اضغط هنا للشارات":
            embed = discord.Embed(title=f"شارات: {user.name}", color=discord.Color.gold())
            embed.add_field(name="التوثيق", value="حساب مؤكد في السيرفر")
            embed.set_thumbnail(url=user.display_avatar.url)
            await interaction.response.send_message(embed=embed, ephemeral=True)

class MasterControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ControlDropdown())

@client.tree.command(name="control_setup", description="إرسال لوحة التحكم الصافية")
@discord.app_commands.default_permissions(administrator=True)
async def control_setup(interaction: discord.Interaction, title: str, description: str, image_url: str = None, channel: discord.TextChannel = None):
    await interaction.response.defer(ephemeral=True)
    if not channel: channel = interaction.channel
    embed = discord.Embed(title=title, description=description, color=discord.Color.from_rgb(24, 28, 37))
    if image_url: embed.set_image(url=image_url)
    await channel.send(embed=embed, view=MasterControlView())
    await interaction.followup.send("تم إرسال اللوحة بنجاح.", ephemeral=True)

if TOKEN: client.run(TOKEN)
