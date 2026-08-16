import discord
from discord.ext import commands
from discord import app_commands
import os
import sqlite3
import asyncio
import io
from datetime import datetime, timezone


# =========================================================
# R7L TICKET SYSTEM V4
# =========================================================

TOKEN = os.getenv("TOKEN")

BOT_OWNER_ID = 761892443427176478

SERVER_ID = 1529410168935284746

CATEGORY_ID = 1538682765644668999
LOG_CHANNEL_ID = 1538682615974985798

SUPPORT_ROLE_IDS = [
    1535386085679562862,
    1535386575633129602,
    1536534015832629368,
    1535388542593667152,
    1535388446254698586
]
# =========================================================
# IMAGES
# =========================================================

PANEL_IMAGE_URL = (
    "https://cdn.discordapp.com/attachments/"
    "1535099454690955276/1538472641311154196/"
    "r7l_Cc_.png"
    "?ex=6a83768d&is=6a82250d&"
    "hm=8756e8902ef53b60d45c927b1816ba60a8f8202ff294a8b955ceffbdc3dfdfc2"
)

TICKET_IMAGE_URL = (
    "https://cdn.discordapp.com/attachments/"
    "1538662158613745785/1538667021040881704/"
    "asd.png"
    "?ex=6a8382d4&is=6a823154&"
    "hm=4f17e0415ac169cff6678786b0e22a60bb75242fa195d643132433567e161368"
)

LOG_IMAGE_URL = PANEL_IMAGE_URL


# =========================================================
# DATABASE
# =========================================================

DB_FILE = "r7l_system.db"

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
    claimed_at TEXT,

    close_requested_by INTEGER,
    close_requested_at TEXT,

    closed_by INTEGER,
    closed_at TEXT,

    message_count INTEGER DEFAULT 0,

    rating INTEGER,
    rating_note TEXT,

    log_message_id INTEGER,

    status TEXT NOT NULL DEFAULT 'open',

    created_at TEXT NOT NULL
)
""")

db.commit()


# =========================================================
# DATABASE MIGRATION
# =========================================================

def ensure_column(table, column, definition):
    columns = db.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    names = [
        row["name"]
        for row in columns
    ]

    if column not in names:
        db.execute(
            f"""
            ALTER TABLE {table}
            ADD COLUMN {column} {definition}
            """
        )

        db.commit()


ensure_column("tickets", "claimed_at", "TEXT")
ensure_column("tickets", "close_requested_by", "INTEGER")
ensure_column("tickets", "close_requested_at", "TEXT")
ensure_column("tickets", "closed_by", "INTEGER")
ensure_column("tickets", "closed_at", "TEXT")
ensure_column("tickets", "message_count", "INTEGER DEFAULT 0")
ensure_column("tickets", "rating", "INTEGER")
ensure_column("tickets", "rating_note", "TEXT")
ensure_column("tickets", "log_message_id", "INTEGER")


# =========================================================
# BOT
# =========================================================

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# HELPERS
# =========================================================

def now():
    return datetime.now(timezone.utc)


def now_text():
    return now().strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


def get_ticket(channel_id):
    return db.execute(
        """
        SELECT *
        FROM tickets
        WHERE channel_id = ?
        """,
        (channel_id,)
    ).fetchone()


def get_open_ticket(guild_id, user_id):
    return db.execute(
        """
        SELECT *
        FROM tickets
        WHERE guild_id = ?
        AND user_id = ?
        AND status = 'open'
        LIMIT 1
        """,
        (
            guild_id,
            user_id
        )
    ).fetchone()


def update_ticket(channel_id, **values):
    if not values:
        return

    fields = ", ".join(
        f"{key} = ?"
        for key in values
    )

    params = list(
        values.values()
    )

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


def get_next_ticket_number(guild_id):
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
            (
                guild_id,
                number
            )
        )

    else:
        number = row["number"] + 1

        db.execute(
            """
            UPDATE counters
            SET number = ?
            WHERE guild_id = ?
            """,
            (
                number,
                guild_id
            )
        )

    db.commit()

    return number


def clean_username(username):
    username = "".join(
        char
        if char.isalnum()
        or char in "-_"
        else "-"
        for char in username
    )

    username = username.strip("-")

    return username or "user"


def make_channel_name(number, username):
    return (
        f"ticket-{number:03d}・"
        f"{clean_username(username)[:50]}"
    )


def type_name(ticket_type):
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


def format_user(guild, user_id):
    if not user_id:
        return "غير محدد"

    member = guild.get_member(user_id)

    if member:
        return (
            f"{member.mention}\n"
            f"`{member.id}`"
        )

    return f"`{user_id}`"


def format_date(value):
    return value or "غير محدد"


def calculate_duration(created_at, closed_at):
    if not created_at or not closed_at:
        return "غير محددة"

    try:
        created = datetime.strptime(
            created_at,
            "%Y-%m-%d %H:%M:%S UTC"
        )

        closed = datetime.strptime(
            closed_at,
            "%Y-%m-%d %H:%M:%S UTC"
        )

        seconds = int(
            (closed - created).total_seconds()
        )

        if seconds < 60:
            return f"{seconds} ثانية"

        minutes = seconds // 60

        if minutes < 60:
            return f"{minutes} دقيقة"

        hours = minutes // 60
        remaining = minutes % 60

        if remaining:
            return (
                f"{hours} ساعة "
                f"و {remaining} دقيقة"
            )

        return f"{hours} ساعة"

    except Exception:
        return "غير محددة"


def base_embed(title, description=None):
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.from_rgb(
            35,
            35,
            35
        )
    )

    embed.set_footer(
        text="R7L System"
    )

    return embed


# =========================================================
# LOG CHANNEL
# =========================================================

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
        "R7L SYSTEM - TICKET TRANSCRIPT"
    )

    lines.append(
        "=" * 80
    )

    lines.append(
        f"Ticket Number : #{ticket['ticket_number']:03d}"
    )

    lines.append(
        f"Channel       : {channel.name}"
    )

    lines.append(
        f"Channel ID    : {channel.id}"
    )

    lines.append(
        f"Owner         : {ticket['username']}"
    )

    lines.append(
        f"Owner ID      : {ticket['user_id']}"
    )

    lines.append(
        f"Type          : {type_name(ticket['ticket_type'])}"
    )

    lines.append(
        f"Created       : {ticket['created_at']}"
    )

    lines.append(
        f"Claimed By    : {ticket['claimed_by'] or 'None'}"
    )

    lines.append(
        f"Claimed At    : {ticket['claimed_at'] or 'None'}"
    )

    lines.append(
        f"Closed By     : {ticket['closed_by'] or 'None'}"
    )

    lines.append(
        f"Closed At     : {ticket['closed_at'] or 'None'}"
    )

    lines.append(
        "=" * 80
    )

    lines.append("")

    async for message in channel.history(
        limit=None,
        oldest_first=True
    ):

        timestamp = message.created_at.strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

        lines.append(
            f"[{timestamp}] "
            f"{message.author} "
            f"({message.author.id})"
        )

        if message.content:
            lines.append(
                message.content
            )

        if message.attachments:
            for attachment in message.attachments:
                lines.append(
                    f"Attachment: {attachment.url}"
                )

        if message.embeds:
            lines.append(
                "[Embed]"
            )

        lines.append(
            "-" * 80
        )

    content = "\n".join(
        lines
    ).encode(
        "utf-8"
    )

    filename = (
        f"ticket-{ticket['ticket_number']:03d}-"
        f"{clean_username(ticket['username'])}.txt"
    )

    return discord.File(
        io.BytesIO(content),
        filename=filename
    )


# =========================================================
# FINAL LOG
# =========================================================

def build_final_log(guild, ticket):
    embed = base_embed(
        f"R7L・Ticket #{ticket['ticket_number']:03d}"
    )

    embed.description = (
        "تم إغلاق التكت وتسجيل بياناته بالكامل."
    )

    embed.add_field(
        name="👤 صاحب التكت",
        value=format_user(
            guild,
            ticket["user_id"]
        ),
        inline=True
    )

    embed.add_field(
        name="🎫 نوع التكت",
        value=type_name(
            ticket["ticket_type"]
        ),
        inline=True
    )

    embed.add_field(
        name="📌 الحالة",
        value="`CLOSED`",
        inline=True
    )

    embed.add_field(
        name="🆔 رقم التكت",
        value=f"`#{ticket['ticket_number']:03d}`",
        inline=True
    )

    embed.add_field(
        name="📁 Channel ID",
        value=f"`{ticket['channel_id']}`",
        inline=True
    )

    embed.add_field(
        name="💬 عدد الرسائل",
        value=f"`{ticket['message_count'] or 0}`",
        inline=True
    )

    embed.add_field(
        name="🕐 وقت الإنشاء",
        value=f"`{format_date(ticket['created_at'])}`",
        inline=False
    )

    embed.add_field(
        name="📥 المستلم",
        value=(
            format_user(
                guild,
                ticket["claimed_by"]
            )
            if ticket["claimed_by"]
            else "لم يتم الاستلام"
        ),
        inline=True
    )

    embed.add_field(
        name="🕐 وقت الاستلام",
        value=f"`{format_date(ticket['claimed_at'])}`",
        inline=True
    )

    embed.add_field(
        name="⏱️ مدة التكت",
        value=f"`{calculate_duration(ticket['created_at'], ticket['closed_at'])}`",
        inline=True
    )

    embed.add_field(
        name="🔒 طلب الإغلاق بواسطة",
        value=(
            format_user(
                guild,
                ticket["close_requested_by"]
            )
            if ticket["close_requested_by"]
            else "لم يتم طلب الإغلاق"
        ),
        inline=True
    )

    embed.add_field(
        name="🕐 وقت طلب الإغلاق",
        value=f"`{format_date(ticket['close_requested_at'])}`",
        inline=True
    )

    embed.add_field(
        name="🔐 أغلق التكت",
        value=(
            format_user(
                guild,
                ticket["closed_by"]
            )
            if ticket["closed_by"]
            else "غير محدد"
        ),
        inline=True
    )

    embed.add_field(
        name="🕐 وقت الإغلاق",
        value=f"`{format_date(ticket['closed_at'])}`",
        inline=True
    )

    rating = (
        f"{ticket['rating']}/5"
        if ticket["rating"]
        else "بانتظار التقييم"
    )

    embed.add_field(
        name="⭐ التقييم",
        value=f"`{rating}`",
        inline=True
    )

    note = ticket["rating_note"] or "بانتظار التقييم"

    embed.add_field(
        name="📝 ملاحظة العضو",
        value=note[:1024],
        inline=False
    )

    if LOG_IMAGE_URL:
        embed.set_thumbnail(
            url=LOG_IMAGE_URL
        )

    embed.timestamp = now()

    return embed


async def send_final_log(
    guild,
    ticket,
    transcript_file=None
):
    log_channel = await get_log_channel(
        guild
    )

    if not log_channel:
        print(
            "LOG CHANNEL NOT FOUND"
        )
        return None

    embed = build_final_log(
        guild,
        ticket
    )

    try:
        if transcript_file:
            message = await log_channel.send(
                embed=embed,
                file=transcript_file
            )
        else:
            message = await log_channel.send(
                embed=embed
            )

        update_ticket(
            ticket["channel_id"],
            log_message_id=message.id
        )

        return message

    except Exception as error:
        print(
            "FINAL LOG ERROR:",
            error
        )

        return None


async def update_final_log(
    guild,
    ticket
):
    if not ticket["log_message_id"]:
        return

    log_channel = await get_log_channel(
        guild
    )

    if not log_channel:
        return

    try:
        message = await log_channel.fetch_message(
            ticket["log_message_id"]
        )

        await message.edit(
            embed=build_final_log(
                guild,
                ticket
            )
        )

    except Exception as error:
        print(
            "LOG UPDATE ERROR:",
            error
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

        for rating in range(1, 6):

            button = discord.ui.Button(
                label=str(rating),
                style=discord.ButtonStyle.secondary,
                custom_id=(
                    f"r7l_rating:"
                    f"{channel_id}:"
                    f"{rating}"
                )
            )

            button.callback = self.rating_callback

            self.add_item(
                button
            )

    async def rating_callback(self, interaction):
        custom_id = interaction.data["custom_id"]

        parts = custom_id.split(":")

        channel_id = int(parts[1])
        rating = int(parts[2])

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

        if ticket["rating"]:
            return await interaction.response.send_message(
                "تم تقييم هذا التكت مسبقًا.",
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

    def __init__(self, channel_id, rating):
        super().__init__()

        self.channel_id = channel_id
        self.rating = rating

    async def on_submit(self, interaction):
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
            else "لا توجد ملاحظة"
        )

        update_ticket(
            self.channel_id,
            rating=self.rating,
            rating_note=note
        )

        ticket = get_ticket(
            self.channel_id
        )

        guild = bot.get_guild(
            ticket["guild_id"]
        )

        if guild:
            await update_final_log(
                guild,
                ticket
            )

        await interaction.response.send_message(
            "تم تسجيل تقييمك، شكرًا لك.",
            ephemeral=True
        )

        channel = None

        if guild:
            channel = guild.get_channel(
                self.channel_id
            )

        if channel:
            try:
                transcript = await create_transcript(
                    channel
                )

                if transcript:
                    await interaction.user.send(
                        content=(
                            "تم إغلاق تكتك.\n"
                            "هذه نسخة من المحادثة."
                        ),
                        file=transcript
                    )

            except Exception as error:
                print(
                    "TRANSCRIPT DM ERROR:",
                    error
                )

        await asyncio.sleep(2)

        if channel:
            try:
                await channel.delete(
                    reason="R7L Ticket Completed"
                )

            except Exception as error:
                print(
                    "CHANNEL DELETE ERROR:",
                    error
                )


async def send_rating_dm(user, ticket):
    try:
        embed = base_embed(
            "R7L Support",
            "تم إغلاق تكتك.\n\n"
            "نحتاج تقييمك لتجربتك معنا."
        )

        embed.add_field(
            name="Ticket",
            value=(
                f"#{ticket['ticket_number']:03d}"
            ),
            inline=True
        )

        embed.add_field(
            name="Type",
            value=type_name(
                ticket["ticket_type"]
            ),
            inline=True
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
# CLOSE TICKET
# =========================================================

async def finish_ticket(channel, closed_by):
    ticket = get_ticket(
        channel.id
    )

    if not ticket:
        return

    if ticket["status"] != "open":
        return

    closed_time = now_text()

    closed_by_id = (
        closed_by.id
        if hasattr(closed_by, "id")
        else None
    )

    update_ticket(
        channel.id,
        status="closed",
        closed_by=closed_by_id,
        closed_at=closed_time
    )

    # حساب الرسائل
    try:
        count = 0

        async for _ in channel.history(
            limit=None
        ):
            count += 1

        update_ticket(
            channel.id,
            message_count=count
        )

    except Exception:
        pass

    ticket = get_ticket(
        channel.id
    )

    # حفظ الـ Transcript قبل حذف التكت
    transcript = None

    try:
        transcript = await create_transcript(
            channel
        )

    except Exception as error:
        print(
            "TRANSCRIPT ERROR:",
            error
        )

    # لوق واحد فقط
    await send_final_log(
        channel.guild,
        ticket,
        transcript
    )

    # إرسال التقييم للعضو
    member = channel.guild.get_member(
        ticket["user_id"]
    )

    if not member:
        try:
            member = await bot.fetch_user(
                ticket["user_id"]
            )
        except Exception:
            member = None

    if member:
        await send_rating_dm(
            member,
            ticket
        )

    try:
        await channel.send(
            embed=base_embed(
                "Ticket Closed",
                "تم إغلاق التكت.\n"
                "تم إرسال التقييم إلى الخاص."
            )
        )

    except Exception:
        pass


# =========================================================
# AUTOMATIC CLOSE
# =========================================================

async def automatic_close(channel_id):
    await asyncio.sleep(180)

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

    # لو المستلم رد خلال الثلاث دقائق
    # يتم إلغاء طلب الإغلاق
    claimed_by = ticket["claimed_by"]

    if claimed_by:

        requested_time = None

        try:
            requested_time = datetime.strptime(
                ticket["close_requested_at"],
                "%Y-%m-%d %H:%M:%S UTC"
            ).replace(
                tzinfo=timezone.utc
            )

        except Exception:
            pass

        if requested_time:

            async for message in channel.history(
                limit=30
            ):

                if (
                    message.author.id == claimed_by
                    and
                    message.created_at > requested_time
                ):

                    update_ticket(
                        channel_id,
                        close_requested_at=None,
                        close_requested_by=None
                    )

                    try:
                        await channel.send(
                            embed=base_embed(
                                "Close Request Cancelled",
                                "تم إلغاء طلب الإغلاق لأن المستلم قام بالرد."
                            )
                        )

                    except Exception:
                        pass

                    return

    # لم يرد المستلم
    await finish_ticket(
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
                content=(
                    "فقط الموظف المستلم "
                    "يستطيع إغلاق التكت."
                ),
                view=None
            )

        await interaction.response.edit_message(
            content="جاري إغلاق التكت...",
            view=None
        )

        await finish_ticket(
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
            content="تم إلغاء الإغلاق.",
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
        label="استلام",
        style=discord.ButtonStyle.secondary,
        custom_id="r7l_claim"
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

        if ticket["status"] != "open":
            return await interaction.response.send_message(
                "التكت مغلق.",
                ephemeral=True
            )

        if ticket["claimed_by"]:
            return await interaction.response.send_message(
                "التكت مستلم بالفعل.",
                ephemeral=True
            )

        update_ticket(
            interaction.channel.id,
            claimed_by=interaction.user.id,
            claimed_at=now_text()
        )

        await interaction.response.send_message(
            embed=base_embed(
                "Ticket Claimed",
                f"تم استلام التكت بواسطة "
                f"{interaction.user.mention}."
            )
        )

    @discord.ui.button(
        label="فك الاستلام",
        style=discord.ButtonStyle.secondary,
        custom_id="r7l_unclaim"
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
                "فقط الموظف المستلم يستطيع فك الاستلام.",
                ephemeral=True
            )

        update_ticket(
            interaction.channel.id,
            claimed_by=None,
            claimed_at=None
        )

        await interaction.response.send_message(
            embed=base_embed(
                "Ticket Unclaimed",
                "تم فك استلام التكت."
            )
        )

    @discord.ui.button(
        label="طلب إغلاق",
        style=discord.ButtonStyle.secondary,
        custom_id="r7l_request_close"
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
                "تم طلب الإغلاق مسبقًا.",
                ephemeral=True
            )

        update_ticket(
            interaction.channel.id,
            close_requested_by=interaction.user.id,
            close_requested_at=now_text()
        )

        await interaction.response.send_message(
            embed=base_embed(
                "Close Request",
                "تم إرسال طلب الإغلاق.\n"
                "إذا لم يرد المستلم خلال 3 دقائق، "
                "سيتم إغلاق التكت تلقائيًا."
            )
        )

        asyncio.create_task(
            automatic_close(
                interaction.channel.id
            )
        )

    @discord.ui.button(
        label="إغلاق",
        style=discord.ButtonStyle.danger,
        custom_id="r7l_close"
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
            embed=form_review(
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
        placeholder="رابط دعوة السيرفر",
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
            embed=form_review(
                "شراكة",
                data
            ),
            view=FormConfirmView(
                "partnership",
                data
            ),
            ephemeral=True
        )


def form_review(title, data):
    embed = base_embed(
        "مراجعة الطلب",
        "تأكد من البيانات قبل إنشاء التكت."
    )

    if title == "شكوى":

        embed.add_field(
            name="على من الشكوى؟",
            value=data["target"],
            inline=False
        )

        embed.add_field(
            name="سبب الشكوى؟",
            value=data["reason"],
            inline=False
        )

        embed.add_field(
            name="تفاصيل الشكوى؟",
            value=data["details"],
            inline=False
        )

    else:

        embed.add_field(
            name="اسم السيرفر",
            value=data["server_name"],
            inline=True
        )

        embed.add_field(
            name="نوعه",
            value=data["server_type"],
            inline=True
        )

        embed.add_field(
            name="الرابط",
            value=data["invite"],
            inline=False
        )

        embed.add_field(
            name="عدد الأعضاء",
            value=data["members"],
            inline=True
        )

    return embed


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
        existing = get_open_ticket(
            interaction.guild.id,
            interaction.user.id
        )

        if existing:

            channel = interaction.guild.get_channel(
                existing["channel_id"]
            )

            if channel:
                return await interaction.response.edit_message(
                    content=(
                        f"لديك تكت مفتوح بالفعل: "
                        f"{channel.mention}"
                    ),
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
                "تعذر إنشاء التكت.",
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
# TICKET SELECT
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
        existing = get_open_ticket(
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
                closed_at=now_text()
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

            await interaction.response.send_modal(
                ComplaintModal()
            )

            return

        if selected == "partnership":

            await interaction.response.send_modal(
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

    existing = get_open_ticket(
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

        print(
            "CATEGORY NOT FOUND"
        )

        return None

    number = get_next_ticket_number(
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
        name=make_channel_name(
            number,
            user.name
        ),
        category=category,
        overwrites=overwrites,
        reason="R7L Ticket System"
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
            claimed_at,
            close_requested_by,
            close_requested_at,
            closed_by,
            closed_at,
            message_count,
            rating,
            rating_note,
            log_message_id,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            channel.id,
            guild.id,
            number,
            user.id,
            user.name,
            ticket_type,
            None,
            None,
            None,
            None,
            None,
            None,
            0,
            None,
            None,
            None,
            "open",
            now_text()
        )
    )

    db.commit()

    embed = base_embed(
        f"Ticket #{number:03d}",
        "مرحبًا بك في تذكرة الدعم.\n"
        "اكتب طلبك بوضوح وسيقوم أحد أعضاء الفريق بالرد عليك."
    )

    embed.add_field(
        name="نوع الطلب",
        value=type_name(
            ticket_type
        ),
        inline=True
    )

    embed.add_field(
        name="صاحب التذكرة",
        value=user.mention,
        inline=True
    )

    embed.add_field(
        name="المستلم",
        value="غير مستلمة",
        inline=True
    )

    if form_data:

        if ticket_type == "complaint":

            embed.add_field(
                name="على من الشكوى؟",
                value=form_data["target"],
                inline=False
            )

            embed.add_field(
                name="سبب الشكوى؟",
                value=form_data["reason"],
                inline=False
            )

            embed.add_field(
                name="تفاصيل الشكوى؟",
                value=form_data["details"],
                inline=False
            )

        elif ticket_type == "partnership":

            embed.add_field(
                name="اسم السيرفر",
                value=form_data["server_name"],
                inline=True
            )

            embed.add_field(
                name="نوعه",
                value=form_data["server_type"],
                inline=True
            )

            embed.add_field(
                name="الرابط",
                value=form_data["invite"],
                inline=False
            )

            embed.add_field(
                name="عدد الأعضاء",
                value=form_data["members"],
                inline=True
            )

    if TICKET_IMAGE_URL:

        embed.set_image(
            url=TICKET_IMAGE_URL
        )

    await channel.send(
        content=user.mention,
        embed=embed,
        view=TicketControlView()
    )

    return channel


# =========================================================
# MESSAGE COUNTER
# =========================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if message.guild:

        ticket = get_ticket(
            message.channel.id
        )

        if ticket and ticket["status"] == "open":

            update_ticket(
                message.channel.id,
                message_count=(
                    ticket["message_count"] or 0
                ) + 1
            )

            # إذا المستلم رد بعد طلب الإغلاق
            if (
                ticket["close_requested_at"]
                and
                ticket["claimed_by"]
                and
                message.author.id
                == ticket["claimed_by"]
            ):

                requested_time = None

                try:

                    requested_time = datetime.strptime(
                        ticket["close_requested_at"],
                        "%Y-%m-%d %H:%M:%S UTC"
                    ).replace(
                        tzinfo=timezone.utc
                    )

                except Exception:
                    pass

                if (
                    requested_time
                    and
                    message.created_at > requested_time
                ):

                    update_ticket(
                        message.channel.id,
                        close_requested_at=None,
                        close_requested_by=None
                    )

                    try:

                        await message.channel.send(
                            embed=base_embed(
                                "Close Request Cancelled",
                                "تم إلغاء طلب الإغلاق لأن المستلم قام بالرد."
                            )
                        )

                    except Exception:
                        pass

    await bot.process_commands(
        message
    )


# =========================================================
# SETUP COMMAND
# =========================================================

@bot.tree.command(
    name="ticket-setup",
    description="إرسال نظام التكت"
)
@app_commands.describe(
    channel="الروم الذي تريد إرسال النظام فيه"
)
async def ticket_setup(
    interaction,
    channel: discord.TextChannel
):

    if interaction.user.id != BOT_OWNER_ID:

        return await interaction.response.send_message(
            "هذا الأمر مخصص لمالك البوت.",
            ephemeral=True
        )

    if interaction.guild.id != SERVER_ID:

        return await interaction.response.send_message(
            "هذا السيرفر غير معتمد للنظام.",
            ephemeral=True
        )

    embed = discord.Embed(
        color=discord.Color.from_rgb(
            35,
            35,
            35
        )
    )

    embed.set_image(
        url=PANEL_IMAGE_URL
    )

    await channel.send(
        embed=embed,
        view=TicketPanelView()
    )

    await interaction.response.send_message(
        f"تم إرسال نظام التكت في {channel.mention}.",
        ephemeral=True
    )


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    print(
        f"R7L TICKET SYSTEM ONLINE AS {bot.user}"
    )

    # لوحة التكت
    bot.add_view(
        TicketPanelView()
    )

    # أزرار التكتات
    bot.add_view(
        TicketControlView()
    )

    # استرجاع أزرار التقييم بعد إعادة تشغيل البوت
    try:

        pending_ratings = db.execute(
            """
            SELECT channel_id
            FROM tickets
            WHERE status = 'closed'
            AND rating IS NULL
            """
        ).fetchall()

        for row in pending_ratings:

            bot.add_view(
                RatingView(
                    row["channel_id"]
                )
            )

        print(
            f"Restored {len(pending_ratings)} rating views."
        )

    except Exception as error:

        print(
            "RATING VIEW RESTORE ERROR:",
            error
        )

    # مزامنة الأمر الوحيد
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
            "R7L ticket command synced."
        )

    except Exception as error:

        print(
            "COMMAND SYNC ERROR:",
            error
        )


# =========================================================
# START
# =========================================================

if not TOKEN:

    raise RuntimeError(
        "TOKEN is missing from Railway Variables."
    )

bot.run(
    TOKEN
)
