import discord
from discord.ext import commands
import json
from typing import Literal
import emoji
import os

intents = discord.Intents.all()
client = commands.Bot(command_prefix="!", intents=intents)

@client.event
async def on_ready():
    print(f"ready {client.user}")
    await client.tree.sync() # هذا السطر هو المسؤول عن تفعيل أوامر الـ / بالسيرفر

colors = {
    "grey": discord.ButtonStyle.grey,
    "green": discord.ButtonStyle.green,
    "red": discord.ButtonStyle.red,
    "primary": discord.ButtonStyle.primary
}
image_extension = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
channel_ids = []

@client.tree.command(name="add_ticket", description="لأضافة تذاكر جديدة")
@discord.app_commands.default_permissions(administrator=True)
async def add_ticket(interaction: discord.Interaction, name: str, color: Literal["grey","green","red","primary"], name_ticket_room: str, log: discord.TextChannel, role: discord.Role, emoji_ticket: str, category: discord.CategoryChannel, image: discord.Attachment = None):
    server_id = str(interaction.guild.id)
    if not emoji.is_emoji(emoji_ticket):
        await interaction.response.send_message("يرجى إدخال رمز تعبيري صالح.", ephemeral=True)
        return
    
    # التأكد من وجود ملف JSON أو إنشائه
    if not os.path.exists("button.json"):
        with open("button.json", "w", encoding="utf-8") as f:
            json.dump({}, f)

    with open("button.json", "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {}
            
    if server_id not in data:
        data[server_id] = {}
        
    if name in data[server_id]:
        await interaction.response.send_message("اسم هذه التذكرة قد استخدمته بالفعل", ephemeral=True)
    else:
        ticket_data_server = {
            "color": color,
            "name": name_ticket_room,
            "log": log.id,
            "role": role.id,
            "emoji": str(emoji_ticket),
            "category": category.id
        }
        if image and image.filename.lower().endswith(image_extension):
            ticket_data_server["image"] = image.url
            reply_add = "تم اضافة التذكرة الى قائمة التذاكر"
        else:
            reply_add = "تم حفظ التذكرة في قائمة التذاكر بدون صورة"
        data[server_id][name] = ticket_data_server
        with open("button.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        await interaction.response.send_message(reply_add, ephemeral=True)

@client.tree.command(name="ticket_setup", description="لأضافة قائمة التذاكرة")
@discord.app_commands.default_permissions(administrator=True)
async def ticket_setup(interaction: discord.Interaction, descreption: str, channel: discord.TextChannel = None, image: discord.Attachment = None):
    await interaction.response.defer(ephemeral=True)
    if not channel:
        channel = interaction.channel
    
    embed = discord.Embed(title="قائمة التذاكر", description=descreption, colour=discord.Colour.dark_blue())
    embed.set_author(name=f"{interaction.guild.name} Ticket", icon_url=interaction.guild.icon)
    if image and image.filename.lower().endswith(image_extension):
        embed.set_image(url=image.url)
        reply = f"تم إرسال قائمة التذاكر في روم {channel.mention}"
    else:
        reply = f"تم إرسال قائمة التذاكر في روم {channel.mention} بدون صورة"
        
    if not os.path.exists("button.json"):
        await interaction.followup.send("لا يوجد اي تذاكر لأضافتها، استخدم /add_ticket أولاً", ephemeral=True)
        return

    with open("button.json", "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {}
            
    view = discord.ui.View(timeout=None)
    server_id = str(interaction.guild.id)
    if server_id not in data or not data[server_id]:
        await interaction.followup.send("لا يوجد اي تذاكر لأضافتها", ephemeral=True)
        return
        
    for ticket_name, ticket_data in data[server_id].items():
        role_ticket = interaction.guild.get_role(ticket_data["role"])
        button = discord.ui.Button(label=ticket_name, style=colors[ticket_data["color"]], emoji=ticket_data["emoji"])
        view.add_item(button) 
        
        async def button_callback(interaction: discord.Interaction, ticket_name=ticket_name, ticket_data=ticket_data, role_ticket=role_ticket):
            if not role_ticket or role_ticket not in interaction.guild.roles:
                await interaction.response.send_message(f"للأسف يوجد خطأ تقني لا يمكن فتح تذكرة الان يرجى الانتظار حتى يتم حل المشكلة", ephemeral=True)
                return
                
            user = interaction.user
            category_ticket_id = ticket_data["category"]
            category = interaction.guild.get_channel(category_ticket_id)
            overwrite = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True),
                role_ticket: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
            }
            if category:
                channel_ticket = await category.create_text_channel(name=f"{ticket_data['name']}-{user.name}", overwrites=overwrite)
            else:
                channel_ticket = await interaction.guild.create_text_channel(name=f"{ticket_data['name']}-{user.name}", overwrites=overwrite)
            
            channel_ids.append(channel_ticket.id)
            embed_ticket = discord.Embed(title=ticket_name, description=f"تم فتح التذكرة من {user.mention}", colour=discord.Colour.dark_blue())
            embed_ticket.set_author(name=f"{interaction.guild.name} Ticket control", icon_url=interaction.guild.icon)
            
            button_view = discord.ui.View(timeout=None)
            close_button = discord.ui.Button(label="اغلاق", style=discord.ButtonStyle.red, emoji="🔒")
            delete_button = discord.ui.Button(label="حذف", style=discord.ButtonStyle.grey, emoji="🗑")
            receive_button = discord.ui.Button(label="استلام", style=discord.ButtonStyle.green, emoji="✋")
            button_view.add_item(close_button)
            button_view.add_item(receive_button)
            button_view.add_item(delete_button)
            
            if "image" in ticket_data:
                embed_ticket.set_image(url=ticket_data["image"])
                
            async def close_callback(interaction: discord.Interaction):
                if role_ticket in interaction.user.roles or interaction.user.guild_permissions.administrator:
                    close_embed = discord.Embed(title="اغلاق تذكرة", description=f"تم اغلاق التذكرة من قبل {interaction.user.mention}", colour=discord.Colour.red())
                    overwrite = {
                        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                        user: discord.PermissionOverwrite(view_channel=False),
                        role_ticket: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
                    }
                    await channel_ticket.edit(name=f"close-{user.name}", overwrites=overwrite)
                    await interaction.response.send_message(embed=close_embed)
                    close_button.disabled = True
                    await ticket_control.edit(embed=embed_ticket, view=button_view)
                else:
                    await interaction.response.send_message(f"لا يمكن اغلاق التذكرة الا من قبل اصحاب رتبة {role_ticket.mention}", ephemeral=True)
                    
            async def delete_callback(interaction: discord.Interaction):
                log_channel = interaction.guild.get_channel(ticket_data["log"])
                if role_ticket in interaction.user.roles or interaction.user.guild_permissions.administrator:
                    if log_channel:
                        log_embed = discord.Embed(title=f"حذف تذكرة {ticket_name}", description=f"تم حذف تذكرة {user.mention} من قبل {interaction.user.mention}", colour=discord.Colour.dark_red())
                        await log_channel.send(embed=log_embed)
                    await channel_ticket.delete()
                else:
                    await interaction.response.send_message(f"لا يمكنك حذف التذكرة، هذا الأمر مخصص للإدارة فقط.", ephemeral=True)

            async def receive_callback(interaction: discord.Interaction):
                if role_ticket in interaction.user.roles or interaction.user.guild_permissions.administrator:
                    receive_embed = discord.Embed(title="استلام تذكرة", description=f"تم استلام التذكرة من قبل الإداري {interaction.user.mention} وسيتم الرد عليك قريباً.", colour=discord.Colour.green())
                    await interaction.response.send_message(embed=receive_embed)
                    receive_button.disabled = True
                    await ticket_control.edit(view=button_view)
                else:
                    await interaction.response.send_message(f"هذا الخيار مخصص للإداريين فقط.", ephemeral=True)

            close_button.callback = close_callback
            delete_button.callback = delete_callback
            receive_button.callback = receive_callback
            
            await interaction.response.send_message(f"تم فتح تذكرتك بنجاح في روم {channel_ticket.mention}", ephemeral=True)
            ticket_control = await channel_ticket.send(content=user.mention, embed=embed_ticket, view=button_view)

        button.callback = button_callback

    await channel.send(embed=embed, view=view)
    await interaction.followup.send(reply, ephemeral=True)

# تشغيل البوت بالتوكن السري من خزنة الاستضافة
TOKEN = os.getenv("TOKEN")
if TOKEN:
    client.run(TOKEN)
else:
    print("Error: TOKEN NOT FOUND")
