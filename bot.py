import discord
from discord.ext import commands
from discord import app_commands
import os
import sqlite3
import asyncio
import io
from datetime import datetime


# =========================================================
# CONFIG
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

DB_PATH = os.getenv("DB_PATH", "tickets.db")


# =========================================================
# BOT
# =========================================================

intents = discord.Intents.all()

client = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row

db.execute("""
CREATE TABLE IF NOT EXISTS settings (
    guild_id INTEGER PRIMARY KEY,
    panel_channel_id INTEGER,
    panel_message_id INTEGER,
    panel_title TEXT,
    panel_description TEXT,
    panel_image TEXT
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS ticket_counter (
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
    closed_at TEXT,
    close_requested_at TEXT,
    status TEXT NOT NULL
)
""")

db.commit()


# =========================================================
# DATABASE FUNCTIONS
# =========================================================

def get_next_ticket_number(guild_id: int):
    row = db.execute(
        "SELECT number FROM ticket_counter WHERE guild_id = ?",
        (guild_id,)
    ).fetchone()

    if row is None:
        number = 1

        db.execute(
            "INSERT INTO ticket_counter (guild_id, number) VALUES (?, ?)",
            (guild_id, number)
        )
    else:
        number = row["number"] + 1

        db.execute(
            "UPDATE ticket_counter SET number = ? WHERE guild_id = ?",
            (number, guild_id)
        )

    db.commit()

    return number


def get_open_ticket(guild_id: int, user_id: int):
    return db.execute(
        """
        SELECT *
        FROM tickets
        WHERE guild_id = ?
        AND user_id = ?
        AND status = 'open'
        """,
        (guild_id, user_id)
    ).fetchone()


def get_ticket(channel_id: int):
    return db.execute(
        """
        SELECT *
        FROM tickets
        WHERE channel_id = ?
        """,
        (channel_id,)
    ).fetchone()


def update_ticket(channel_id: int, **values):
    if not values:
        return

    fields = ", ".join(
        f"{key} = ?"
        for key in values.keys()
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


# =========================================================
# HELPERS
# =========================================================

def is_support(member: discord.Member):
    return any(
        role.id in SUPPORT_ROLE_IDS
        for role in member.roles
    )


def clean_username(username: str):
    allowed = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789-_"
    )

    cleaned = "".join(
        char if char in allowed else "-"
        for char in username
    )

    cleaned = cleaned.strip("-")

    if not cleaned:
        cleaned = "user"

    return cleaned[:60]


def get_ticket_type_name(ticket_type: str):
    names = {
        "support": "دعم واستفسار",
        "complaint": "شكوى",
        "partnership": "شراكة"
    }

    return names.get(
        ticket_type,
        ticket_type
    )


def black_embed(
    title=None,
    description=None
):
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.from_rgb(0, 0, 0)
    )


async def get_log_channel(guild: discord.Guild):
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

async def create_transcript(
    channel: discord.TextChannel
):
    lines = []

    ticket = get_ticket(
        channel.id
    )

    lines.append("R7L TICKET TRANSCRIPT")
    lines.append("=" * 70)
    lines.append("")

    if ticket:
        lines.append(
            f"Ticket: ticket-{ticket['ticket_number']:03d}・"
            f"{ticket['username']}"
        )

        lines.append(
            f"Type: {get_ticket_type_name(ticket['ticket_type'])}"
        )

        lines.append(
            f"Owner: {ticket['username']} "
            f"({ticket['user_id']})"
        )

        lines.append(
            "Claimed By: "
            + (
                str(ticket["claimed_by"])
                if ticket["claimed_by"]
                else "None"
            )
        )

        lines.append(
            f"Created: {ticket['created_at']}"
        )

        lines.append(
            f"Closed: {ticket['closed_at'] or 'Unknown'}"
        )

    lines.append("")
    lines.append("=" * 70)
    lines.append("")

    async for message in channel.history(
        limit=None,
        oldest_first=True
    ):
        timestamp = message.created_at.strftime(
            "%Y-%m-%d %H:%M:%S"
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

        for attachment in message.attachments:
            lines.append(
                f"Attachment: {attachment.url}"
            )

        if message.embeds:
            lines.append(
                f"Embeds: {len(message.embeds)}"
            )

        lines.append("-" * 70)

    return io.BytesIO(
        "\n".join(lines).encode("utf-8")
    )


# =========================================================
# SEND TRANSCRIPT
# =========================================================

async def send_transcript_to_user(
    user: discord.User,
    ticket_data
):
    guild = client.get_guild(
        ticket_data["guild_id"]
    )

    if not guild:
        return False

    channel = guild.get_channel(
        ticket_data["channel_id"]
    )

    if not channel:
        return False

    try:
        transcript = await create_transcript(
            channel
        )

        transcript.seek(0)

        filename = (
            f"ticket-{ticket_data['ticket_number']:03d}-"
            f"{clean_username(ticket_data['username'])}.txt"
        )

        file = discord.File(
            transcript,
            filename=filename
        )

        await user.send(
            content="نسخة من محادثة التكت:",
            file=file
        )

        return True

    except Exception as error:
        print(
            f"Transcript DM Error: {error}"
        )
        return False


# =========================================================
# RATING
# =========================================================

class RatingView(discord.ui.View):

    def __init__(self, ticket_data):
        super().__init__(
            timeout=3600
        )

        self.ticket_data = ticket_data

        for number in range(1, 6):

            button = discord.ui.Button(
                label=str(number),
                style=discord.ButtonStyle.secondary,
                custom_id=(
                    f"rating_{number}_"
                    f"{ticket_data['channel_id']}"
                )
            )

            button.callback = (
                self.make_callback(number)
            )

            self.add_item(button)

    def make_callback(self, number):

        async def callback(
            interaction: discord.Interaction
        ):
            await interaction.response.send_modal(
                RatingNoteModal(
                    self.ticket_data,
                    number
                )
            )

        return callback


class RatingNoteModal(
    discord.ui.Modal,
    title="ملاحظة التقييم"
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
        ticket_data,
        rating
    ):
        super().__init__()

        self.ticket_data = ticket_data
        self.rating = rating

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):
        note = self.note.value.strip()

        guild = client.get_guild(
            self.ticket_data["guild_id"]
        )

        log_channel = None

        if guild:
            log_channel = await get_log_channel(
                guild
            )

        embed = black_embed(
            title="Ticket Rating",
            description="تم استلام تقييم تذكرة."
        )

        embed.add_field(
            name="Ticket",
            value=(
                f"ticket-"
                f"{self.ticket_data['ticket_number']:03d}"
                f"・{self.ticket_data['username']}"
            ),
            inline=False
        )

        embed.add_field(
            name="Type",
            value=get_ticket_type_name(
                self.ticket_data["ticket_type"]
            ),
            inline=True
        )

        embed.add_field(
            name="Rating",
            value=f"{self.rating}/5",
            inline=True
        )

        embed.add_field(
            name="Claimed By",
            value=(
                str(self.ticket_data["claimed_by"])
                if self.ticket_data["claimed_by"]
                else "None"
            ),
            inline=True
        )

        embed.add_field(
            name="Note",
            value=note if note else "No note",
            inline=False
        )

        if log_channel:
            try:
                await log_channel.send(
                    embed=embed
                )
            except Exception:
                pass

        await interaction.response.send_message(
            "تم تسجيل تقييمك. سيتم إرسال نسخة من محادثة التكت لك.",
            ephemeral=True
        )

        await send_transcript_to_user(
            interaction.user,
            self.ticket_data
        )

        await asyncio.sleep(2)

        if guild:
            channel = guild.get_channel(
                self.ticket_data["channel_id"]
            )

            if channel:
                try:
                    await channel.delete(
                        reason="Ticket rating completed"
                    )
                except Exception:
                    pass


async def send_rating_dm(
    user: discord.User,
    ticket_data
):
    try:
        embed = black_embed(
            title="Ticket Rating",
            description=(
                "شكرًا لتواصلك معنا.\n\n"
                "نأمل تقييم تجربتك من 1 إلى 5."
            )
        )

        embed.add_field(
            name="Ticket",
            value=(
                f"ticket-"
                f"{ticket_data['ticket_number']:03d}"
                f"・{ticket_data['username']}"
            ),
            inline=False
        )

        await user.send(
            embed=embed,
            view=RatingView(
                ticket_data
            )
        )

        return True

    except Exception as error:
        print(
            f"Rating DM Error: {error}"
        )
        return False


# =========================================================
# CLOSE REQUEST TIMER
# =========================================================

async def close_request_timer(
    channel_id: int
):
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

    guild = client.get_guild(
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
        closed_by=None
    )


# =========================================================
# CLOSE TICKET
# =========================================================

async def close_ticket(
    channel: discord.TextChannel,
    closed_by=None
):
    ticket = get_ticket(
        channel.id
    )

    if not ticket:
        return

    if ticket["status"] != "open":
        return

    closed_at = datetime.utcnow().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    update_ticket(
        channel.id,
        status="closed",
        closed_at=closed_at
    )

    try:
        await channel.set_permissions(
            channel.guild.default_role,
            view_channel=False
        )

        owner = channel.guild.get_member(
            ticket["user_id"]
        )

        if owner:
            await channel.set_permissions(
                owner,
                view_channel=True,
                send_messages=False,
                read_message_history=True
            )

        for role_id in SUPPORT_ROLE_IDS:
            role = channel.guild.get_role(
                role_id
            )

            if role:
                await channel.set_permissions(
                    role,
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True
                )

        embed = black_embed(
            title="Ticket Closed",
            description=(
                "تم إغلاق التكت.\n\n"
                "سيتم إرسال التقييم إلى الخاص."
            )
        )

        if closed_by:
            embed.add_field(
                name="Closed By",
                value=closed_by.mention,
                inline=False
            )

        await channel.send(
            embed=embed
        )

    except Exception as error:
        print(
            f"Close Channel Error: {error}"
        )

    log_channel = await get_log_channel(
        channel.guild
    )

    if log_channel:

        log_embed = black_embed(
            title="Ticket Closed",
            description="تم إغلاق تذكرة."
        )

        log_embed.add_field(
            name="Ticket",
            value=(
                f"ticket-"
                f"{ticket['ticket_number']:03d}"
                f"・{ticket['username']}"
            ),
            inline=False
        )

        log_embed.add_field(
            name="Type",
            value=get_ticket_type_name(
                ticket["ticket_type"]
            ),
            inline=True
        )

        log_embed.add_field(
            name="Claimed By",
            value=(
                str(ticket["claimed_by"])
                if ticket["claimed_by"]
                else "None"
            ),
            inline=True
        )

        if closed_by:
            log_embed.add_field(
                name="Closed By",
                value=str(closed_by),
                inline=True
            )

        try:
            await log_channel.send(
                embed=log_embed
            )
        except Exception:
            pass

    user = channel.guild.get_member(
        ticket["user_id"]
    )

    if not user:
        try:
            user = await client.fetch_user(
                ticket["user_id"]
            )
        except Exception:
            user = None

    if user:
        updated_ticket = get_ticket(
            channel.id
        )

        sent = await send_rating_dm(
            user,
            updated_ticket
        )

        if not sent:
            try:
                await channel.send(
                    "تعذر إرسال التقييم إلى الخاص. سيتم حذف التكت."
                )

                await asyncio.sleep(10)

                await channel.delete(
                    reason="Could not send rating DM"
                )

            except Exception:
                pass


# =========================================================
# TICKET BUTTONS
# =========================================================

class TicketView(discord.ui.View):

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
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not isinstance(
            interaction.user,
            discord.Member
        ):
            return

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
                "هذه ليست تذكرة صالحة.",
                ephemeral=True
            )

        if ticket["status"] != "open":
            return await interaction.response.send_message(
                "التذكرة مغلقة.",
                ephemeral=True
            )

        if ticket["claimed_by"]:
            return await interaction.response.send_message(
                "التذكرة مستلمة بالفعل. يجب على الموظف المستلم عمل Unclaim أولاً.",
                ephemeral=True
            )

        update_ticket(
            interaction.channel.id,
            claimed_by=interaction.user.id
        )

        embed = black_embed(
            title="Ticket Claimed",
            description=(
                f"تم استلام التكت بواسطة "
                f"{interaction.user.mention}."
            )
        )

        await interaction.response.send_message(
            embed=embed
        )

    @discord.ui.button(
        label="Unclaim",
        style=discord.ButtonStyle.secondary,
        custom_id="r7l_ticket_unclaim"
    )
    async def unclaim(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not isinstance(
            interaction.user,
            discord.Member
        ):
            return

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
                "هذه ليست تذكرة صالحة.",
                ephemeral=True
            )

        if not ticket["claimed_by"]:
            return await interaction.response.send_message(
                "التذكرة غير مستلمة.",
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
            "تم إلغاء استلام التكت."
        )

    @discord.ui.button(
        label="طلب إغلاق",
        style=discord.ButtonStyle.secondary,
        custom_id="r7l_ticket_request_close"
    )
    async def request_close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        ticket = get_ticket(
            interaction.channel.id
        )

        if not ticket:
            return await interaction.response.send_message(
                "هذه ليست تذكرة صالحة.",
                ephemeral=True
            )

        if interaction.user.id != ticket["user_id"]:
            return await interaction.response.send_message(
                "هذا الخيار مخصص لصاحب التكت.",
                ephemeral=True
            )

        if not ticket["claimed_by"]:
            return await interaction.response.send_message(
                "لا يمكن طلب إغلاق التكت قبل استلامه من أحد الموظفين.",
                ephemeral=True
            )

        if ticket["close_requested_at"]:
            return await interaction.response.send_message(
                "تم طلب إغلاق التكت مسبقًا.",
                ephemeral=True
            )

        now = datetime.utcnow().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        update_ticket(
            interaction.channel.id,
            close_requested_at=now
        )

        claimed_member = interaction.guild.get_member(
            ticket["claimed_by"]
        )

        embed = black_embed(
            title="Close Request",
            description=(
                f"صاحب التكت {interaction.user.mention} "
                "طلب إغلاق التكت.\n\n"
                "إذا لم يتم إغلاق التكت خلال 3 دقائق، "
                "سيتم إغلاقه تلقائيًا."
            )
        )

        if claimed_member:
            embed.add_field(
                name="Claimed By",
                value=claimed_member.mention,
                inline=False
            )

        await interaction.response.send_message(
            embed=embed
        )

        asyncio.create_task(
            close_request_timer(
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
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not isinstance(
            interaction.user,
            discord.Member
        ):
            return

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
                "هذه ليست تذكرة صالحة.",
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
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not isinstance(
            interaction.user,
            discord.Member
        ):
            return

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
            closed_by=interaction.user
        )

    @discord.ui.button(
        label="إلغاء",
        style=discord.ButtonStyle.secondary
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="تم إلغاء عملية الإغلاق.",
            view=None
        )


# =========================================================
# FORM REVIEW
# =========================================================

def build_form_review(
    title,
    data
):
    embed = black_embed(
        title="مراجعة الطلب",
        description=f"نوع الطلب: {title}"
    )

    if data["type"] == "complaint":

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

    elif data["type"] == "partnership":

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
            name="رابطه",
            value=data["invite"],
            inline=False
        )

        embed.add_field(
            name="عدد الأعضاء",
            value=data["members"],
            inline=True
        )

    return embed


# =========================================================
# COMPLAINT MODAL
# =========================================================

class ComplaintModal(
    discord.ui.Modal,
    title="شكوى"
):

    target = discord.ui.TextInput(
        label="على من الشكوى؟",
        placeholder="اكتب اسم المستخدم",
        required=True,
        max_length=100
    )

    reason = discord.ui.TextInput(
        label="سبب الشكوى؟",
        placeholder="اكتب السبب باختصار",
        required=True,
        max_length=500
    )

    details = discord.ui.TextInput(
        label="تفاصيل الشكوى؟",
        placeholder="اكتب التفاصيل",
        required=True,
        max_length=1500,
        style=discord.TextStyle.paragraph
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):
        data = {
            "type": "complaint",
            "target": self.target.value,
            "reason": self.reason.value,
            "details": self.details.value
        }

        await interaction.response.send_message(
            "راجع بيانات الشكوى قبل الإرسال:",
            embed=build_form_review(
                "شكوى",
                data
            ),
            view=FormConfirmView(
                "complaint",
                data
            ),
            ephemeral=True
        )


# =========================================================
# PARTNERSHIP MODAL
# =========================================================

class PartnershipModal(
    discord.ui.Modal,
    title="شراكة"
):

    server_name = discord.ui.TextInput(
        label="اسم السيرفر",
        placeholder="اسم السيرفر",
        required=True,
        max_length=100
    )

    server_type = discord.ui.TextInput(
        label="نوعه",
        placeholder="Community / Gaming / Store",
        required=True,
        max_length=100
    )

    invite = discord.ui.TextInput(
        label="رابطه",
        placeholder="https://discord.gg/...",
        required=True,
        max_length=200
    )

    members = discord.ui.TextInput(
        label="كم عدد الي فيه؟",
        placeholder="مثال: 500",
        required=True,
        max_length=20
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):
        data = {
            "type": "partnership",
            "server_name": self.server_name.value,
            "server_type": self.server_type.value,
            "invite": self.invite.value,
            "members": self.members.value
        }

        await interaction.response.send_message(
            "راجع بيانات الشراكة قبل الإرسال:",
            embed=build_form_review(
                "شراكة",
                data
            ),
            view=FormConfirmView(
                "partnership",
                data
            ),
            ephemeral=True
        )


# =========================================================
# FORM CONFIRM
# =========================================================

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
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
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
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if self.ticket_type == "complaint":

            await interaction.response.send_modal(
                ComplaintModal()
            )

        elif self.ticket_type == "partnership":

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
            placeholder="اختر نوع التكت",
            options=options,
            custom_id="r7l_ticket_select"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        ticket_type = self.values[0]

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
                status="closed"
            )

        if ticket_type == "support":

            await interaction.response.defer(
                ephemeral=True
            )

            channel = await create_ticket(
                interaction,
                "support",
                None
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

        elif ticket_type == "complaint":

            await interaction.response.send_modal(
                ComplaintModal()
            )

        elif ticket_type == "partnership":

            await interaction.response.send_modal(
                PartnershipModal()
            )


# =========================================================
# TICKET PANEL
# =========================================================

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
    interaction: discord.Interaction,
    ticket_type: str,
    form_data=None
):
    guild = interaction.guild
    user = interaction.user

    existing = get_open_ticket(
        guild.id,
        user.id
    )

    if existing:

        channel = guild.get_channel(
            existing["channel_id"]
        )

        if channel:
            return channel

    category = guild.get_channel(
        CATEGORY_ID
    )

    if not category:
        return None

    ticket_number = get_next_ticket_number(
        guild.id
    )

    username = clean_username(
        user.name
    )

    channel_name = (
        f"ticket-{ticket_number:03d}・{username}"
    )

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=False
        ),

        user: discord.PermissionOverwrite(
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

            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True
            )

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        reason="R7L Ticket System"
    )

    created_at = datetime.utcnow().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    db.execute(
        """
        INSERT INTO tickets (
            channel_id,
            guild_id,
            ticket_number,
            user_id,
            username,
            ticket_type,
            claimed_by,
            created_at,
            closed_at,
            close_requested_at,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            channel.id,
            guild.id,
            ticket_number,
            user.id,
            user.name,
            ticket_type,
            None,
            created_at,
            None,
            None,
            "open"
        )
    )

    db.commit()

    embed = black_embed(
        title=f"Ticket #{ticket_number:03d}",
        description=(
            "يرجى كتابة طلبك بوضوح وسيتم الرد عليك من فريق الدعم."
        )
    )

    embed.add_field(
        name="Type",
        value=get_ticket_type_name(
            ticket_type
        ),
        inline=True
    )

    embed.add_field(
        name="Owner",
        value=user.mention,
        inline=True
    )

    embed.add_field(
        name="Claimed By",
        value="None",
        inline=True
    )

    embed.add_field(
        name="Status",
        value="Open",
        inline=False
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
                name="رابطه",
                value=form_data["invite"],
                inline=False
            )

            embed.add_field(
                name="عدد الأعضاء",
                value=form_data["members"],
                inline=True
            )

    await channel.send(
        content=user.mention,
        embed=embed,
        view=TicketView()
    )

    log_channel = await get_log_channel(
        guild
    )

    if log_channel:

        log_embed = black_embed(
            title="Ticket Created",
            description="تم إنشاء تكت جديد."
        )

        log_embed.add_field(
            name="Ticket",
            value=(
                f"ticket-"
                f"{ticket_number:03d}"
                f"・{user.name}"
            ),
            inline=False
        )

        log_embed.add_field(
            name="Type",
            value=get_ticket_type_name(
                ticket_type
            ),
            inline=True
        )

        log_embed.add_field(
            name="Owner",
            value=user.mention,
            inline=True
        )

        try:
            await log_channel.send(
                embed=log_embed
            )
        except Exception:
            pass

    return channel


# =========================================================
# TICKET SETUP
# =========================================================

@client.tree.command(
    name="ticket-setup",
    description="إعداد لوحة التكت"
)
@app_commands.describe(
    title="عنوان لوحة التكت",
    description="وصف لوحة التكت",
    channel="الروم الذي سترسل فيه اللوحة",
    image_url="رابط الصورة اختياري"
)
async def ticket_setup(
    interaction: discord.Interaction,
    title: str,
    description: str,
    channel: discord.TextChannel = None,
    image_url: str = None
):
    if interaction.user.id != OWNER_ID:

        return await interaction.response.send_message(
            "هذا الأمر مخصص لمالك البوت فقط.",
            ephemeral=True
        )

    if interaction.guild.id != SERVER_ID:

        return await interaction.response.send_message(
            "هذا البوت غير مخصص لهذا السيرفر.",
            ephemeral=True
        )

    existing = db.execute(
        """
        SELECT *
        FROM settings
        WHERE guild_id = ?
        """,
        (interaction.guild.id,)
    ).fetchone()

    if existing:

        existing_channel = interaction.guild.get_channel(
            existing["panel_channel_id"]
        )

        if existing_channel:

            return await interaction.response.send_message(
                f"لوحة التكت موجودة بالفعل في {existing_channel.mention}.",
                ephemeral=True
            )

    if channel is None:
        channel = interaction.channel

    embed = black_embed(
        title=title,
        description=description
    )

    if image_url:
        embed.set_image(
            url=image_url
        )

    message = await channel.send(
        embed=embed,
        view=TicketPanelView()
    )

    db.execute(
        """
        INSERT OR REPLACE INTO settings (
            guild_id,
            panel_channel_id,
            panel_message_id,
            panel_title,
            panel_description,
            panel_image
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            interaction.guild.id,
            channel.id,
            message.id,
            title,
            description,
            image_url
        )
    )

    db.commit()

    await interaction.response.send_message(
        f"تم إعداد لوحة التكت في {channel.mention}.",
        ephemeral=True
    )


# =========================================================
# READY
# =========================================================

@client.event
async def on_ready():

    print(
        f"R7L SYSTEM ONLINE AS {client.user}"
    )

    client.add_view(
        TicketPanelView()
    )

    client.add_view(
        TicketView()
    )

    try:

        guild = discord.Object(
            id=SERVER_ID
        )

        client.tree.copy_global_to(
            guild=guild
        )

        await client.tree.sync(
            guild=guild
        )

        print(
            "Slash commands synced successfully."
        )

    except Exception as error:

        print(
            f"Command sync error: {error}"
        )


# =========================================================
# ERROR HANDLING
# =========================================================

@client.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error
):
    print(
        f"Command Error: {error}"
    )

    try:

        if interaction.response.is_done():

            await interaction.followup.send(
                "حدث خطأ أثناء تنفيذ الأمر.",
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                "حدث خطأ أثناء تنفيذ الأمر.",
                ephemeral=True
            )

    except Exception:
        pass


# =========================================================
# RUN
# =========================================================

if not TOKEN:

    raise RuntimeError(
        "TOKEN environment variable is missing."
    )

client.run(TOKEN)
