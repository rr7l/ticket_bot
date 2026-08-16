import discord
from discord.ext import commands
from discord import app_commands
import os
import sqlite3
import asyncio
import io
from datetime import datetime, timezone


# =========================================================
# R7L SYSTEM V2
# =========================================================

TOKEN = os.getenv("TOKEN")

OWNER_ID = 761892443427176478
SERVER_ID = 1536080830680793140

CATEGORY_ID = 1538465258367090688
LOG_CHANNEL_ID = 1536495698785210518

SUPPORT_ROLE_IDS = [
    1538464963515908136,
    1538651115745443961,
    1538464931211513876,
    1538651215251112057,
    1538651253582729327
]


# =========================================================
# IMAGES
# =========================================================

# صورة الـSetup
PANEL_IMAGE_URL = (
    "https://cdn.discordapp.com/attachments/"
    "1535099454690955276/1538472641311154196/"
    "r7l_Cc_.png"
    "?ex=6a83768d&is=6a82250d&"
    "hm=8756e8902ef53b60d45c927b1816ba60a8f8202ff294a8b955ceffbdc3dfdfc2"
)

# الصورة داخل التكت
TICKET_IMAGE_URL = (
    "https://cdn.discordapp.com/attachments/"
    "1538662158613745785/1538667021040881704/"
    "asd.png"
    "?ex=6a8382d4&is=6a823154&"
    "hm=4f17e0415ac169cff6678786b0e22a60bb75242fa195d643132433567e161368"
)

# صورة اللوقات
# استخدمنا صورة الـSetup مؤقتًا
LOG_IMAGE_URL = PANEL_IMAGE_URL


DB_FILE = "r7l_system.db"


# =========================================================
# BOT
# =========================================================

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect(
    DB_FILE,
    check_same_thread=False
)

db.row_factory = sqlite3.Row


db.execute("""
CREATE TABLE IF NOT EXISTS counters (
    guild_id INTEGER PRIMARY KEY,
    number INTEGER NOT NULL
)
""")


db.execute("""
CREATE TABLE IF NOT EXISTS tickets (
    channel_id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    ticket_number INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    ticket_type TEXT NOT NULL,
    claimed_by INTEGER,
    created_at TEXT NOT NULL,
    close_requested_at TEXT,
    closed_at TEXT,
    status TEXT NOT NULL DEFAULT 'open'
)
""")


db.execute("""
CREATE TABLE IF NOT EXISTS ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    ticket_number INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    rating INTEGER NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL
)
""")


db.commit()


# =========================================================
# HELPERS
# =========================================================

def current_time():
    return datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d %H:%M:%S UTC")


def get_ticket(channel_id):
    return db.execute(
        """
        SELECT *
        FROM tickets
        WHERE channel_id = ?
        """,
        (channel_id,)
    ).fetchone()


def get_user_ticket(guild_id, user_id):
    return db.execute(
        """
        SELECT *
        FROM tickets
        WHERE guild_id = ?
        AND user_id = ?
        AND status = 'open'
        LIMIT 1
        """,
        (guild_id, user_id)
    ).fetchone()


def update_ticket(channel_id, **values):
    if not values:
        return

    fields = ", ".join(
        f"{key} = ?"
        for key in values
    )

    params = list(values.values())
    params.append(channel_id)

    db.execute(
        f"""
        UPDATE tickets
        SET {fields}
        WHERE channel_id = ?
        """,
        params
    )

    db.commit()


def get_next_number(guild_id):
    row = db.execute(
        """
        SELECT number
        FROM counters
        WHERE guild_id = ?
        """,
        (guild_id,)
    ).fetchone()

    if row is None:
        number = 1

        db.execute(
            """
            INSERT INTO counters
            (guild_id, number)
            VALUES (?, ?)
            """,
            (guild_id, number)
        )
    else:
        number = row["number"] + 1

        db.execute(
            """
            UPDATE counters
            SET number = ?
            WHERE guild_id = ?
            """,
            (number, guild_id)
        )

    db.commit()

    return number


def ticket_channel_name(number, username):
    username = "".join(
        char if char.isalnum() or char in "-_"
        else "-"
        for char in username
    )

    username = username.strip("-")

    if not username:
        username = "user"

    return f"ticket-{number:03d}・{username[:50]}"


def ticket_type_name(ticket_type):
    names = {
        "support": "دعم واستفسار",
        "complaint": "شكوى",
        "partnership": "شراكة"
    }

    return names.get(
        ticket_type,
        ticket_type
    )


def is_support(member):
    if not isinstance(member, discord.Member):
        return False

    return any(
        role.id in SUPPORT_ROLE_IDS
        for role in member.roles
    )


def make_embed(
    title=None,
    description=None
):
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.from_rgb(
            35,
            35,
            35
        )
    )


async def get_log_channel(guild):
    channel = guild.get_channel(
        LOG_CHANNEL_ID
    )

    if channel:
        return channel

    try:
        return await guild.fetch_channel(
            LOG_CHANNEL_ID
        )
    except Exception:
        return None


# =========================================================
# LOG SYSTEM
# =========================================================

async def send_log(
    guild,
    title,
    fields
):
    channel = await get_log_channel(
        guild
    )

    if not channel:
        return

    embed = make_embed(
        title,
        "R7L System"
    )

    for name, value, inline in fields:
        embed.add_field(
            name=name,
            value=value,
            inline=inline
        )

    if LOG_IMAGE_URL:
        embed.set_thumbnail(
            url=LOG_IMAGE_URL
        )

    embed.set_footer(
        text="R7L System"
    )

    embed.timestamp = datetime.now(
        timezone.utc
    )

    try:
        await channel.send(
            embed=embed
        )
    except Exception as error:
        print(
            "LOG ERROR:",
            error
        )


# =========================================================
# TRANSCRIPT
# =========================================================

async def create_transcript(channel):
    ticket = get_ticket(
        channel.id
    )

    if not ticket:
        return None

    lines = []

    lines.append(
        "R7L SYSTEM V2 - TICKET TRANSCRIPT"
    )

    lines.append(
        "=" * 70
    )

    lines.append(
        f"Ticket: #{ticket['ticket_number']:03d}"
    )

    lines.append(
        f"Username: {ticket['username']}"
    )

    lines.append(
        f"Type: {ticket_type_name(ticket['ticket_type'])}"
    )

    lines.append(
        f"User ID: {ticket['user_id']}"
    )

    lines.append(
        f"Claimed By: {ticket['claimed_by'] or 'None'}"
    )

    lines.append(
        f"Created: {ticket['created_at']}"
    )

    lines.append(
        f"Closed: {ticket['closed_at'] or 'None'}"
    )

    lines.append(
        "=" * 70
    )

    lines.append("")

    async for message in channel.history(
        limit=None,
        oldest_first=True
    ):
        time = message.created_at.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        lines.append(
            f"[{time}] {message.author} "
            f"({message.author.id})"
        )

        if message.content:
            lines.append(
                message.content
            )

        for attachment in message.attachments:
            lines.append(
                f"Attachment: {attachment.url}"
            )

        lines.append(
            "-" * 70
        )

    data = "\n".join(
        lines
    ).encode("utf-8")

    filename = (
        f"ticket-{ticket['ticket_number']:03d}-"
        f"{ticket['username']}.txt"
    )

    return discord.File(
        io.BytesIO(data),
        filename=filename
    )


# =========================================================
# RATING
# =========================================================

class RatingView(discord.ui.View):

    def __init__(self, channel_id):
        super().__init__(
            timeout=None
        )

        self.channel_id = channel_id

        for number in range(1, 6):
            button = discord.ui.Button(
                label=str(number),
                style=discord.ButtonStyle.secondary,
                custom_id=(
                    f"r7l_rating:"
                    f"{channel_id}:"
                    f"{number}"
                )
            )

            button.callback = (
                self.rating_button
            )

            self.add_item(button)

    async def rating_button(
        self,
        interaction
    ):
        parts = interaction.data[
            "custom_id"
        ].split(":")

        channel_id = int(
            parts[1]
        )

        rating = int(
            parts[2]
        )

        ticket = get_ticket(
            channel_id
        )

        if not ticket:
            return await interaction.response.send_message(
                "التكت غير موجود.",
                ephemeral=True
            )

        if ticket["user_id"] != interaction.user.id:
            return await interaction.response.send_message(
                "هذا التقييم مخصص لصاحب التكت.",
                ephemeral=True
            )

        await interaction.response.send_modal(
            RatingModal(
                channel_id,
                rating
            )
        )


class RatingModal(
    discord.ui.Modal,
    title="تقييم التكت"
):

    note = discord.ui.TextInput(
        label="هل لديك ملاحظة؟",
        placeholder="اكتب ملاحظتك أو اتركها فارغة",
        required=False,
        max_length=1000,
        style=discord.TextStyle.paragraph
    )

    def __init__(
        self,
        channel_id,
        rating
    ):
        super().__init__()

        self.channel_id = channel_id
        self.rating = rating

    async def on_submit(
        self,
        interaction
    ):
        ticket = get_ticket(
            self.channel_id
        )

        if not ticket:
            return await interaction.response.send_message(
                "التكت غير موجود.",
                ephemeral=True
            )

        note = (
            self.note.value.strip()
            if self.note.value
            else ""
        )

        if not note:
            note = "لا توجد ملاحظة"

        db.execute(
            """
            INSERT INTO ratings
            (
                guild_id,
                channel_id,
                ticket_number,
                user_id,
                rating,
                note,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket["guild_id"],
                ticket["channel_id"],
                ticket["ticket_number"],
                ticket["user_id"],
                self.rating,
                note,
                current_time()
            )
        )

        db.commit()

        guild = bot.get_guild(
            ticket["guild_id"]
        )

        await send_log(
            guild,
            "Ticket Rated",
            [
                (
                    "Ticket",
                    f"#{ticket['ticket_number']:03d}・"
                    f"{ticket['username']}",
                    False
                ),
                (
                    "Type",
                    ticket_type_name(
                        ticket["ticket_type"]
                    ),
                    True
                ),
                (
                    "Rating",
                    f"{self.rating}/5",
                    True
                ),
                (
                    "Claimed By",
                    str(
                        ticket["claimed_by"]
                        or "None"
                    ),
                    True
                ),
                (
                    "Note",
                    note,
                    False
                )
            ]
        )

        channel = (
            guild.get_channel(
                self.channel_id
            )
            if guild
            else None
        )

        if channel:
            try:
                file = await create_transcript(
                    channel
                )

                if file:
                    await interaction.user.send(
                        content=(
                            "تم إغلاق تكتك.\n"
                            "هذه نسخة من المحادثة."
                        ),
                        file=file
                    )

            except Exception as error:
                print(
                    "TRANSCRIPT ERROR:",
                    error
                )

        await interaction.response.send_message(
            "تم تسجيل تقييمك.",
            ephemeral=True
        )

        await asyncio.sleep(2)

        if channel:
            try:
                await channel.delete(
                    reason="Ticket rating completed"
                )
            except Exception as error:
                print(
                    "DELETE ERROR:",
                    error
                )


async def send_rating(
    user,
    ticket
):
    try:
        embed = make_embed(
            "R7L Support",
            "تم إغلاق تذكرتك.\n\n"
            "قيّم تجربتك من 1 إلى 5."
        )

        embed.add_field(
            name="Ticket",
            value=(
                f"#{ticket['ticket_number']:03d}・"
                f"{ticket['username']}"
            ),
            inline=False
        )

        await user.send(
            embed=embed,
            view=RatingView(
                ticket["channel_id"]
            )
        )

        return True

    except Exception as error:
        print(
            "RATING DM ERROR:",
            error
        )

        return False


# =========================================================
# CLOSE SYSTEM
# =========================================================

async def close_ticket(
    channel,
    closed_by
):
    ticket = get_ticket(
        channel.id
    )

    if not ticket:
        return

    if ticket["status"] != "open":
        return

    update_ticket(
        channel.id,
        status="closed",
        closed_at=current_time()
    )

    await send_log(
        channel.guild,
        "Ticket Closed",
        [
            (
                "Ticket",
                f"#{ticket['ticket_number']:03d}・"
                f"{ticket['username']}",
                False
            ),
            (
                "Type",
                ticket_type_name(
                    ticket["ticket_type"]
                ),
                True
            ),
            (
                "Claimed By",
                str(
                    ticket["claimed_by"]
                    or "None"
                ),
                True
            ),
            (
                "Closed By",
                str(closed_by),
                True
            )
        ]
    )

    user = channel.guild.get_member(
        ticket["user_id"]
    )

    if not user:
        try:
            user = await bot.fetch_user(
                ticket["user_id"]
            )
        except Exception:
            user = None

    if user:
        await send_rating(
            user,
            get_ticket(channel.id)
        )

    try:
        await channel.send(
            embed=make_embed(
                "Ticket Closed",
                "تم إغلاق التكت. تم إرسال التقييم إلى الخاص."
            )
        )
    except Exception:
        pass


async def automatic_close(
    channel_id
):
    await asyncio.sleep(
        180
    )

    ticket = get_ticket(
        channel_id
    )

    if not ticket:
        return

    if ticket["status"] != "open":
        return

    if not ticket["close_requested_at"]:
        return

    guild = bot.get_guild(
        ticket["guild_id"]
    )

    if not guild:
        return

    channel = guild.get_channel(
        channel_id
    )

    if not channel:
        return

    await close_ticket(
        channel,
        "Automatic"
    )


# =========================================================
# CLOSE CONFIRMATION
# =========================================================

class CloseConfirmView(
    discord.ui.View
):

    def __init__(self):
        super().__init__(
            timeout=30
        )

    @discord.ui.button(
        label="تأكيد",
        style=discord.ButtonStyle.danger
    )
    async def confirm(
        self,
        interaction,
        button
    ):
        ticket = get_ticket(
            interaction.channel.id
        )

        if not ticket:
            return await interaction.response.edit_message(
                content="التكت غير موجود.",
                view=None
            )

        if ticket["claimed_by"] != interaction.user.id:
            return await interaction.response.edit_message(
                content="فقط الموظف المستلم يستطيع إغلاق التكت.",
                view=None
            )

        await interaction.response.edit_message(
            content="جاري إغلاق التكت...",
            view=None
        )

        await close_ticket(
            interaction.channel,
            interaction.user
        )

    @discord.ui.button(
        label="إلغاء",
        style=discord.ButtonStyle.secondary
    )
    async def cancel(
        self,
        interaction,
        button
    ):
        await interaction.response.edit_message(
            content="تم إلغاء عملية الإغلاق.",
            view=None
        )


# =========================================================
# TICKET CONTROL
# =========================================================

class TicketControlView(
    discord.ui.View
):

    def __init__(self):
        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.secondary,
        custom_id="r7l_ticket_claim"
    )
    async def claim(
        self,
        interaction,
        button
    ):
        if not is_support(
            interaction.user
        ):
            return await interaction.response.send_message(
                "هذا الخيار مخصص لفريق الدعم.",
                ephemeral=True
            )

        ticket = get_ticket(
            interaction.channel.id
        )

        if not ticket:
            return await interaction.response.send_message(
                "التكت غير موجود.",
                ephemeral=True
            )

        if ticket["claimed_by"]:
            return await interaction.response.send_message(
                "التكت مستلم بالفعل.",
                ephemeral=True
            )

        update_ticket(
            interaction.channel.id,
            claimed_by=interaction.user.id
        )

        await interaction.response.send_message(
            embed=make_embed(
                "Ticket Claimed",
                f"تم استلام التكت بواسطة {interaction.user.mention}."
            )
        )

        await send_log(
            interaction.guild,
            "Ticket Claimed",
            [
                (
                    "Ticket",
                    f"#{ticket['ticket_number']:03d}・"
                    f"{ticket['username']}",
                    False
                ),
                (
                    "Staff",
                    interaction.user.mention,
                    True
                ),
                (
                    "Type",
                    ticket_type_name(
                        ticket["ticket_type"]
                    ),
                    True
                )
            ]
        )

    @discord.ui.button(
        label="Unclaim",
        style=discord.ButtonStyle.secondary,
        custom_id="r7l_ticket_unclaim"
    )
    async def unclaim(
        self,
        interaction,
        button
    ):
        if not is_support(
            interaction.user
        ):
            return await interaction.response.send_message(
                "هذا الخيار مخصص لفريق الدعم.",
                ephemeral=True
            )

        ticket = get_ticket(
            interaction.channel.id
        )

        if not ticket:
            return await interaction.response.send_message(
                "التكت غير موجود.",
                ephemeral=True
            )

        if not ticket["claimed_by"]:
            return await interaction.response.send_message(
                "التكت غير مستلم.",
                ephemeral=True
            )

        if ticket["claimed_by"] != interaction.user.id:
            return await interaction.response.send_message(
                "فقط الموظف المستلم يستطيع عمل Unclaim.",
                ephemeral=True
            )

        update_ticket(
            interaction.channel.id,
            claimed_by=None
        )

        await interaction.response.send_message(
            embed=make_embed(
                "Ticket Unclaimed",
                "تم إلغاء استلام التكت."
            )
        )

        await send_log(
            interaction.guild,
            "Ticket Unclaimed",
            [
                (
                    "Ticket",
                    f"#{ticket['ticket_number']:03d}・"
                    f"{ticket['username']}",
                    False
                ),
                (
                    "Staff",
                    interaction.user.mention,
                    True
                )
            ]
        )

    @discord.ui.button(
        label="طلب إغلاق",
        style=discord.ButtonStyle.secondary,
        custom_id="r7l_ticket_request_close"
    )
    async def request_close(
        self,
        interaction,
        button
    ):
        ticket = get_ticket(
            interaction.channel.id
        )

        if not ticket:
            return await interaction.response.send_message(
                "التكت غير موجود.",
                ephemeral=True
            )

        if interaction.user.id != ticket["user_id"]:
            return await interaction.response.send_message(
                "هذا الخيار مخصص لصاحب التكت.",
                ephemeral=True
            )

        if not ticket["claimed_by"]:
            return await interaction.response.send_message(
                "يجب استلام التكت أولاً.",
                ephemeral=True
            )

        if ticket["close_requested_at"]:
            return await interaction.response.send_message(
                "تم طلب الإغلاق مسبقاً.",
                ephemeral=True
            )

        update_ticket(
            interaction.channel.id,
            close_requested_at=current_time()
        )

        await interaction.response.send_message(
            embed=make_embed(
                "Close Request",
                "تم طلب إغلاق التكت.\n"
                "إذا لم يتم إغلاقه خلال 3 دقائق، سيتم إغلاقه تلقائياً."
            )
        )

        await send_log(
            interaction.guild,
            "Close Requested",
            [
                (
                    "Ticket",
                    f"#{ticket['ticket_number']:03d}・"
                    f"{ticket['username']}",
                    False
                ),
                (
                    "Requested By",
                    interaction.user.mention,
                    True
                ),
                (
                    "Claimed By",
                    str(ticket["claimed_by"]),
                    True
                )
            ]
        )

        asyncio.create_task(
            automatic_close(
                interaction.channel.id
            )
        )

    @discord.ui.button(
        label="إغلاق",
        style=discord.ButtonStyle.danger,
        custom_id="r7l_ticket_close"
    )
    async def close(
        self,
        interaction,
        button
    ):
        if not is_support(
            interaction.user
        ):
            return await interaction.response.send_message(
                "هذا الخيار مخصص لفريق الدعم.",
                ephemeral=True
            )

        ticket = get_ticket(
            interaction.channel.id
        )

        if not ticket:
            return await interaction.response.send_message(
                "التكت غير موجود.",
                ephemeral=True
            )

        if not ticket["claimed_by"]:
            return await interaction.response.send_message(
                "يجب استلام التكت أولاً.",
                ephemeral=True
            )

        if ticket["claimed_by"] != interaction.user.id:
            return await interaction.response.send_message(
                "فقط الموظف المستلم يستطيع إغلاق التكت.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "هل أنت متأكد من إغلاق التكت؟",
            view=CloseConfirmView(),
            ephemeral=True
        )


# =========================================================
# FORMS
# =========================================================

class ComplaintModal(
    discord.ui.Modal,
    title="شكوى"
):

    target = discord.ui.TextInput(
        label="على من الشكوى؟",
        placeholder="اسم المستخدم",
        max_length=100
    )

    reason = discord.ui.TextInput(
        label="سبب الشكوى؟",
        placeholder="اكتب السبب باختصار",
        max_length=500
    )

    details = discord.ui.TextInput(
        label="تفاصيل الشكوى؟",
        placeholder="اكتب التفاصيل",
        max_length=1500,
        style=discord.TextStyle.paragraph
    )

    async def on_submit(
        self,
        interaction
    ):
        data = {
            "target": self.target.value,
            "reason": self.reason.value,
            "details": self.details.value
        }

        await interaction.response.send_message(
            embed=form_review_embed(
                "شكوى",
                data
            ),
            view=FormConfirmView(
                "complaint",
                data
            ),
            ephemeral=True
        )


class PartnershipModal(
    discord.ui.Modal,
    title="شراكة"
):

    server_name = discord.ui.TextInput(
        label="اسم السيرفر",
        placeholder="اسم السيرفر",
        max_length=100
    )

    server_type = discord.ui.TextInput(
        label="نوعه",
        placeholder="Community / Gaming / Store",
        max_length=100
    )

    invite = discord.ui.TextInput(
        label="رابطه",
        placeholder="رابط دعوة ديسكورد",
        max_length=200
    )

    members = discord.ui.TextInput(
        label="كم عدد الي فيه؟",
        placeholder="مثال: 500",
        max_length=20
    )

    async def on_submit(
        self,
        interaction
    ):
        data = {
            "server_name": self.server_name.value,
            "server_type": self.server_type.value,
            "invite": self.invite.value,
            "members": self.members.value
        }

        await interaction.response.send_message(
            embed=form_review_embed(
                "شراكة",
                data
            ),
            view=FormConfirmView(
                "partnership",
                data
            ),
            ephemeral=True
        )


def form_review_embed(
    title,
    data
):
    e = make_embed(
        "مراجعة الطلب",
        "تأكد من البيانات قبل إنشاء التكت."
    )

    if title == "شكوى":

        e.add_field(
            name="على من الشكوى؟",
            value=data["target"],
            inline=False
        )

        e.add_field(
            name="سبب الشكوى؟",
            value=data["reason"],
            inline=False
        )

        e.add_field(
            name="تفاصيل الشكوى؟",
            value=data["details"],
            inline=False
        )

    else:

        e.add_field(
            name="اسم السيرفر",
            value=data["server_name"],
            inline=True
        )

        e.add_field(
            name="نوعه",
            value=data["server_type"],
            inline=True
        )

        e.add_field(
            name="الرابط",
            value=data["invite"],
            inline=False
        )

        e.add_field(
            name="عدد الأعضاء",
            value=data["members"],
            inline=True
        )

    return e


class FormConfirmView(
    discord.ui.View
):

    def __init__(
        self,
        ticket_type,
        data
    ):
        super().__init__(
            timeout=120
        )

        self.ticket_type = ticket_type
        self.data = data

    @discord.ui.button(
        label="تأكيد الإرسال",
        style=discord.ButtonStyle.secondary
    )
    async def confirm(
        self,
        interaction,
        button
    ):
        existing = get_user_ticket(
            interaction.guild.id,
            interaction.user.id
        )

        if existing:

            channel = interaction.guild.get_channel(
                existing["channel_id"]
            )

            if channel:

                return await interaction.response.edit_message(
                    content=f"لديك تكت مفتوح بالفعل: {channel.mention}",
                    embed=None,
                    view=None
                )

        await interaction.response.defer(
            ephemeral=True
        )

        channel = await create_ticket(
            interaction,
            self.ticket_type,
            self.data
        )

        if channel:

            await interaction.followup.send(
                f"تم إنشاء التكت: {channel.mention}",
                ephemeral=True
            )

        else:

            await interaction.followup.send(
                "تعذر إنشاء التكت. تأكد من الـCategory والصلاحيات.",
                ephemeral=True
            )

    @discord.ui.button(
        label="تعديل",
        style=discord.ButtonStyle.secondary
    )
    async def edit(
        self,
        interaction,
        button
    ):
        if self.ticket_type == "complaint":

            await interaction.response.send_modal(
                ComplaintModal()
            )

        else:

            await interaction.response.send_modal(
                PartnershipModal()
            )


# =========================================================
# TICKET PANEL
# =========================================================

class TicketSelect(
    discord.ui.Select
):

    def __init__(self):

        options = [
            discord.SelectOption(
                label="دعم واستفسار",
                value="support",
                description="للاستفسارات والمساعدة"
            ),
            discord.SelectOption(
                label="شكوى",
                value="complaint",
                description="لتقديم شكوى"
            ),
            discord.SelectOption(
                label="شراكة",
                value="partnership",
                description="لطلب شراكة"
            )
        ]

        super().__init__(
            placeholder="اختر نوع الطلب",
            options=options,
            custom_id="r7l_ticket_select"
        )

    async def callback(
        self,
        interaction
    ):
        existing = get_user_ticket(
            interaction.guild.id,
            interaction.user.id
        )

        if existing:

            channel = interaction.guild.get_channel(
                existing["channel_id"]
            )

            if channel:

                return await interaction.response.send_message(
                    f"لديك تكت مفتوح بالفعل: {channel.mention}",
                    ephemeral=True
                )

            update_ticket(
                existing["channel_id"],
                status="closed",
                closed_at=current_time()
            )

        selected = self.values[0]

        if selected == "support":

            await interaction.response.defer(
                ephemeral=True
            )

            channel = await create_ticket(
                interaction,
                "support"
            )

            if channel:

                await interaction.followup.send(
                    f"تم إنشاء التكت: {channel.mention}",
                    ephemeral=True
                )

            return

        if selected == "complaint":

            return await interaction.response.send_modal(
                ComplaintModal()
            )

        if selected == "partnership":

            return await interaction.response.send_modal(
                PartnershipModal()
            )


class TicketPanelView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        self.add_item(
            TicketSelect()
        )


# =========================================================
# CREATE TICKET
# =========================================================

async def create_ticket(
    interaction,
    ticket_type,
    form_data=None
):
    guild = interaction.guild
    user = interaction.user

    existing = get_user_ticket(
        guild.id,
        user.id
    )

    if existing:

        return guild.get_channel(
            existing["channel_id"]
        )

    category = guild.get_channel(
        CATEGORY_ID
    )

    if not category:
        return None

    number = get_next_number(
        guild.id
    )

    overwrites = {
        guild.default_role:
            discord.PermissionOverwrite(
                view_channel=False
            ),

        user:
            discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True
            )
    }

    for role_id in SUPPORT_ROLE_IDS:

        role = guild.get_role(
            role_id
        )

        if role:

            overwrites[role] = (
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True
                )
            )

    channel = await guild.create_text_channel(
        name=ticket_channel_name(
            number,
            user.name
        ),
        category=category,
        overwrites=overwrites,
        reason="R7L System V2 Ticket"
    )

    db.execute(
        """
        INSERT INTO tickets
        (
            channel_id,
            guild_id,
            ticket_number,
            user_id,
            username,
            ticket_type,
            claimed_by,
            created_at,
            close_requested_at,
            closed_at,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            channel.id,
            guild.id,
            number,
            user.id,
            user.name,
            ticket_type,
            None,
            current_time(),
            None,
            None,
            "open"
        )
    )

    db.commit()

    e = make_embed(
        f"Ticket #{number:03d}",
        "مرحبًا بك في تذكرة الدعم.\n"
        "اكتب طلبك بوضوح وسيقوم أحد أعضاء الفريق بالرد عليك."
    )

    e.add_field(
        name="نوع الطلب",
        value=ticket_type_name(
            ticket_type
        ),
        inline=True
    )

    e.add_field(
        name="صاحب التذكرة",
        value=user.mention,
        inline=True
    )

    e.add_field(
        name="المستلم",
        value="غير مستلمة",
        inline=True
    )

    if form_data:

        if ticket_type == "complaint":

            e.add_field(
                name="على من الشكوى؟",
                value=form_data["target"],
                inline=False
            )

            e.add_field(
                name="سبب الشكوى؟",
                value=form_data["reason"],
                inline=False
            )

            e.add_field(
                name="تفاصيل الشكوى؟",
                value=form_data["details"],
                inline=False
            )

        elif ticket_type == "partnership":

            e.add_field(
                name="اسم السيرفر",
                value=form_data["server_name"],
                inline=True
            )

            e.add_field(
                name="نوعه",
                value=form_data["server_type"],
                inline=True
            )

            e.add_field(
                name="الرابط",
                value=form_data["invite"],
                inline=False
            )

            e.add_field(
                name="عدد الأعضاء",
                value=form_data["members"],
                inline=True
            )

    if TICKET_IMAGE_URL:

        e.set_image(
            url=TICKET_IMAGE_URL
        )

    e.set_footer(
        text="R7L System"
    )

    await channel.send(
        content=user.mention,
        embed=e,
        view=TicketControlView()
    )

    await send_log(
        guild,
        "Ticket Created",
        [
            (
                "Ticket",
                f"#{number:03d}・{user.name}",
                False
            ),
            (
                "Type",
                ticket_type_name(
                    ticket_type
                ),
                True
            ),
            (
                "Owner",
                user.mention,
                True
            ),
            (
                "Status",
                "Open",
                True
            )
        ]
    )

    return channel


# =========================================================
# SETUP COMMAND
# =========================================================

@bot.tree.command(
    name="ticket-setup",
    description="إرسال لوحة التكت"
)
@app_commands.describe(
    channel="الروم الذي سترسل فيه اللوحة"
)
async def ticket_setup(
    interaction,
    channel: discord.TextChannel
):
    if interaction.user.id != OWNER_ID:

        return await interaction.response.send_message(
            "هذا الأمر مخصص لمالك البوت فقط.",
            ephemeral=True
        )

    if interaction.guild.id != SERVER_ID:

        return await interaction.response.send_message(
            "هذا الأمر غير متاح في هذا السيرفر.",
            ephemeral=True
        )

    await channel.send(
        content=PANEL_IMAGE_URL,
        view=TicketPanelView()
    )

    await interaction.response.send_message(
        f"تم إرسال لوحة التكت في {channel.mention}.",
        ephemeral=True
    )


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    print(
        f"R7L SYSTEM V2 ONLINE AS {bot.user}"
    )

    bot.add_view(
        TicketPanelView()
    )

    bot.add_view(
        TicketControlView()
    )

    try:

        guild = discord.Object(
            id=SERVER_ID
        )

        bot.tree.copy_global_to(
            guild=guild
        )

        await bot.tree.sync(
            guild=guild
        )

        print(
            "Slash commands synced successfully."
        )

    except Exception as error:

        print(
            "SYNC ERROR:",
            error
        )


# =========================================================
# START
# =========================================================

if not TOKEN:

    raise RuntimeError(
        "TOKEN environment variable is missing."
    )

bot.run(TOKEN)
