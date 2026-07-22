# =========================================================
# FULL TELEGRAM BOT
# TEMP MAIL + AUTO OTP + 2FA (WITH REFRESH BUTTON) + UID + BIN CHECK
# =========================================================

import telebot
import sqlite3
import requests
import pyotp
import random
import string
import threading
import time
import re
import traceback

from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

# =========================================================
# CONFIG
# =========================================================
BOT_TOKEN = "8910349708:AAEtD8XgPUDUxBQOhTmkAjqPEFQ35pE0gTU"
ADMIN_ID = 1978055060

# =========================================================
# BOT
# =========================================================
bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode="HTML"
)

# =========================================================
# DATABASE
# =========================================================
conn = sqlite3.connect(
    "database.db",
    check_same_thread=False
)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    approved INTEGER DEFAULT 0,
    rejected INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS mails(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    email TEXT,
    password TEXT,
    token TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS secrets(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    secret TEXT
)
""")

conn.commit()

# =========================================================
# MEMORY
# =========================================================
login_state = {}
last_messages = {}

# =========================================================
# USER SYSTEM
# =========================================================
def add_user(user):

    username = user.username or "NONE"

    full_name = f"{user.first_name or ''} {user.last_name or ''}"

    cursor.execute("""
    INSERT OR IGNORE INTO users(
        user_id,
        username,
        full_name,
        approved,
        rejected
    )
    VALUES(?,?,?,?,?)
    """,(
        user.id,
        username,
        full_name,
        0,
        0
    ))

    conn.commit()

def is_approved(user_id):

    cursor.execute(
        "SELECT approved FROM users WHERE user_id=?",
        (user_id,)
    )

    x = cursor.fetchone()

    if x:
        return x[0] == 1

    return False

def approve_user(user_id):

    cursor.execute("""
    UPDATE users
    SET approved=1,rejected=0
    WHERE user_id=?
    """,(user_id,))

    conn.commit()

def reject_user(user_id):

    cursor.execute("""
    UPDATE users
    SET approved=0,rejected=1
    WHERE user_id=?
    """,(user_id,))

    conn.commit()

# =========================================================
# PASSWORD
# =========================================================
def random_password(length=12):

    chars = string.ascii_letters + string.digits

    return ''.join(
        random.choice(chars)
        for _ in range(length)
    )

# =========================================================
# DOMAIN
# =========================================================
def get_domain():

    r = requests.get(
        "https://api.mail.tm/domains",
        timeout=20
    )

    data = r.json()

    return data["hydra:member"][0]["domain"]

# =========================================================
# CREATE MAIL
# =========================================================
def create_mail():

    domain = get_domain()

    username = "thispersonisbrand" + str(
        random.randint(
            100000000000,
            999999999999999
        )
    )

    email = f"{username}@{domain}"

    password = random_password(length=12)

    payload = {
        "address": email,
        "password": password
    }

    r = requests.post(
        "https://api.mail.tm/accounts",
        json=payload,
        timeout=20
    )

    if r.status_code not in [200,201]:
        return None

    token_req = requests.post(
        "https://api.mail.tm/token",
        json=payload,
        timeout=20
    )

    token = token_req.json()["token"]

    return {
        "email": email,
        "password": password,
        "token": token
    }

# =========================================================
# SAVE MAIL
# =========================================================
def save_mail(user_id,email,password,token):

    cursor.execute("""
    INSERT INTO mails(
        user_id,
        email,
        password,
        token
    )
    VALUES(?,?,?,?)
    """,(
        user_id,
        email,
        password,
        token
    ))

    conn.commit()

# =========================================================
# LAST MAIL
# =========================================================
def get_last_mail(user_id):

    cursor.execute("""
    SELECT email,password,token
    FROM mails
    WHERE user_id=?
    ORDER BY id DESC
    LIMIT 1
    """,(user_id,))

    return cursor.fetchone()

# =========================================================
# MAIL LIST
# =========================================================
def get_mail_list(user_id):

    cursor.execute("""
    SELECT email,password
    FROM mails
    WHERE user_id=?
    ORDER BY id DESC
    """,(user_id,))

    return cursor.fetchall()

# =========================================================
# LOGIN MAIL
# =========================================================
def login_mail(email,password):

    payload = {
        "address": email,
        "password": password
    }

    r = requests.post(
        "https://api.mail.tm/token",
        json=payload,
        timeout=20
    )

    if r.status_code != 200:
        return None

    return r.json()["token"]

# =========================================================
# GET INBOX
# =========================================================
def get_inbox(token):

    headers = {
        "Authorization": f"Bearer {token}"
    }

    r = requests.get(
        "https://api.mail.tm/messages?page=1",
        headers=headers,
        timeout=20
    )

    if r.status_code != 200:
        return []

    data = r.json()

    return data.get(
        "hydra:member",
        []
    )

# =========================================================
# GET MESSAGE
# =========================================================
def get_message(token,message_id):

    headers = {
        "Authorization": f"Bearer {token}"
    }

    r = requests.get(
        f"https://api.mail.tm/messages/{message_id}",
        headers=headers,
        timeout=20
    )

    if r.status_code != 200:
        return None

    return r.json()

# =========================================================
# SAVE SECRET
# =========================================================
def save_secret(user_id,secret):

    cursor.execute("""
    INSERT INTO secrets(
        user_id,
        secret
    )
    VALUES(?,?)
    """,(
        user_id,
        secret
    ))

    conn.commit()

# =========================================================
# GET SAVED
# =========================================================
def get_saved(user_id):

    cursor.execute("""
    SELECT secret
    FROM secrets
    WHERE user_id=?
    """,(user_id,))

    return cursor.fetchall()

# =========================================================
# FACEBOOK UID
# =========================================================
def extract_uid(url):

    headers = {
        "User-Agent":"Mozilla/5.0"
    }

    try:

        r = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        html = r.text

        uid = None

        patterns = [
            r'"userID":"(\d+)"',
            r'"entity_id":"(\d+)"',
            r'"actorID":"(\d+)"'
        ]

        for p in patterns:

            m = re.search(p,html)

            if m:
                uid = m.group(1)
                break

        title = re.search(
            r'<title>(.*?)</title>',
            html
        )

        name = "Unknown"

        if title:
            name = title.group(1)

        return uid,name

    except:
        return None,None

# =========================================================
# AUTO OTP CHECKER
# =========================================================
def auto_checker():

    while True:

        try:

            cursor.execute("""
            SELECT user_id,email,token
            FROM mails
            """)

            rows = cursor.fetchall()

            for row in rows:

                user_id = row[0]
                email = row[1]
                token = row[2]

                inbox = get_inbox(token)

                if not inbox:
                    continue

                latest = inbox[0]

                message_id = latest["id"]

                if user_id not in last_messages:
                    last_messages[user_id] = []

                if message_id in last_messages[user_id]:
                    continue

                last_messages[user_id].append(message_id)

                full = get_message(
                    token,
                    message_id
                )

                body = ""

                if full:

                    if full.get("text"):
                        body = full["text"]

                    elif full.get("html"):
                        body = str(full["html"])

                otp = "NOT FOUND"

                otp_codes = re.findall(
                    r'\b\d{4,8}\b',
                    body
                )

                if otp_codes:
                    otp = otp_codes[0]

                sender = latest["from"]["address"]

                subject = latest.get(
                    "subject",
                    "No Subject"
                )

                bot.send_message(
                    user_id,
                    f"""
📩 NEW MAIL RECEIVED

📧 EMAIL:
<code>{email}</code>

📨 FROM:
<code>{sender}</code>

📝 SUBJECT:
<code>{subject}</code>

🔑 OTP:
<code>{otp}</code>

📩 MESSAGE:
<code>{body[:3000]}</code>
"""
                )

            time.sleep(10)

        except Exception as e:

            print(e)

            time.sleep(10)

# =========================================================
# START COMMAND
# =========================================================
@bot.message_handler(commands=['start'])
def start(message):

    user = message.from_user

    add_user(user)

    user_id = user.id

    if not is_approved(user_id):

        bot.reply_to(
            message,
            f"""
❌ NOT APPROVED

🆔 YOUR ID:
<code>{user_id}</code>
"""
        )

        bot.send_message(
            ADMIN_ID,
            f"""
🆕 APPROVE REQUEST

👤 NAME: <code>{user.first_name}</code>

🔗 USERNAME: @{user.username}

🆔 USER ID: <code>{user_id}</code>

✅ APPROVE: <code>/approve {user_id}</code>

❌ REJECT: <code>/reject {user_id}</code>
"""
        )

        return

    markup = ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    markup.row("CHECK UID")
    markup.row("GENERATE 2FA")
    markup.row("SAVE SECRET")
    markup.row("MY SAVED")

    markup.row("NEW MAIL")
    markup.row("MY MAIL")
    markup.row("MAIL LIST")

    markup.row("CHECK INBOX")
    markup.row("LOGIN MAIL")

    markup.row("BIN CHECK")

    if user_id == ADMIN_ID:
        markup.row("ADMIN PANEL")

    bot.reply_to(
        message,
        "✅ This Person Is Brand BOT ACTIVE",
        reply_markup=markup
    )

# =========================================================
# APPROVE COMMAND
# =========================================================
@bot.message_handler(commands=['approve'])
def approve(message):

    if message.from_user.id != ADMIN_ID:
        return

    try:

        uid = int(message.text.split()[1])

        approve_user(uid)

        bot.reply_to(
            message,
            "✅ USER APPROVED"
        )

        bot.send_message(
            uid,
            """
🎉 APPROVED SUCCESSFULLY

✅ NOW CLICK: /start

⚡ ALL BUTTONS WILL APPEAR
"""
        )

    except:

        bot.reply_to(
            message,
            "/approve USERID"
        )

# =========================================================
# REJECT COMMAND
# =========================================================
@bot.message_handler(commands=['reject'])
def reject(message):

    if message.from_user.id != ADMIN_ID:
        return

    try:

        uid = int(message.text.split()[1])

        reject_user(uid)

        bot.reply_to(
            message,
            "❌ USER REJECTED"
        )

        bot.send_message(
            uid,
            """
❌ YOU ARE REJECTED

🔄 CLICK:   /start

TO SEND REQUEST AGAIN
"""
        )

    except:

        bot.reply_to(
            message,
            "/reject USERID"
        )

# =========================================================
# 2FA REFRESH CALLBACK HANDLER (NEW)
# =========================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("refresh_2fa_"))
def refresh_2fa_callback(call):
    try:
        # data format: refresh_2fa_{secret}_{user_id}
        parts = call.data.split("_")
        secret = parts[2]
        original_user_id = int(parts[3])

        # Only the owner can refresh
        if call.from_user.id != original_user_id:
            bot.answer_callback_query(call.id, "❌ You cannot refresh this code!")
            return

        totp = pyotp.TOTP(secret)
        new_code = totp.now()
        remain = 30 - (int(time.time()) % 30)

        # Edit the original message with new code
        bot.edit_message_text(
            f"""
✅ 2FA GENERATED (REFRESHED)

🔑 SECRET: <code>{secret}</code>

🔢 CODE: <code>{new_code}</code>

⏳ EXPIRES: {remain} SEC
""",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML"
        )

        # Add refresh button again
        markup = InlineKeyboardMarkup()
        refresh_btn = InlineKeyboardButton(
            "🔄 REFRESH CODE",
            callback_data=f"refresh_2fa_{secret}_{original_user_id}"
        )
        markup.add(refresh_btn)
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )

        bot.answer_callback_query(call.id, f"✅ New code: {new_code}")

    except Exception as e:
        print(e)
        bot.answer_callback_query(call.id, "❌ Refresh failed")

# =========================================================
# MAIN MESSAGE HANDLER
# =========================================================
@bot.message_handler(func=lambda m: True)
def main(message):

    try:

        user_id = message.from_user.id
        text = message.text.strip()

        if not is_approved(user_id):

            bot.reply_to(
                message,
                "❌ NOT APPROVED"
            )

            return

        # =================================================
        # CHECK UID
        # =================================================
        if text == "CHECK UID":

            login_state[user_id] = {
                "step":"check_uid"
            }

            bot.reply_to(
                message,
                "🔗 SEND FACEBOOK URL OR ID LINK"
            )

            return

        # =================================================
        # GENERATE 2FA (WITH REFRESH BUTTON)
        # =================================================
        if text == "GENERATE 2FA":

            login_state[user_id] = {
                "step":"generate_2fa"
            }

            bot.reply_to(
                message,
                "🔐 SEND SECRET KEY"
            )

            return

        # =================================================
        # SAVE SECRET
        # =================================================
        if text == "SAVE SECRET":

            login_state[user_id] = {
                "step":"save_secret"
            }

            bot.reply_to(
                message,
                "🔐 SEND SECRET KEY"
            )

            return

        # =================================================
        # MY SAVED
        # =================================================
        if text == "MY SAVED":

            data = get_saved(user_id)

            if not data:

                bot.reply_to(
                    message,
                    "❌ NO SAVED SECRET"
                )

                return

            result = "🔐 SAVED SECRETS\n\n"

            for x in data:

                result += f"<code>{x[0]}</code>\n\n"

            bot.reply_to(
                message,
                result
            )

            return

        # =================================================
        # NEW MAIL
        # =================================================
        if text == "NEW MAIL":

            msg = bot.reply_to(
                message,
                "📧 CREATING MAIL..."
            )

            data = create_mail()

            if not data:

                bot.edit_message_text(
                    "❌ FAILED TO CREATE MAIL",
                    chat_id=msg.chat.id,
                    message_id=msg.message_id
                )

                return

            save_mail(
                user_id,
                data["email"],
                data["password"],
                data["token"]
            )

            bot.edit_message_text(
                f"""
✅ MAIL CREATED

📧 EMAIL:
<code>{data['email']}</code>

🔑 PASSWORD:
<code>{data['password']}</code>

📥 AUTO OTP DETECT ENABLED
""",
                chat_id=msg.chat.id,
                message_id=msg.message_id
            )

            return

        # =================================================
        # MY MAIL
        # =================================================
        if text == "MY MAIL":

            data = get_last_mail(user_id)

            if not data:

                bot.reply_to(
                    message,
                    "❌ NO MAIL FOUND"
                )

                return

            bot.reply_to(
                message,
                f"""
📧 YOUR MAIL

EMAIL:
<code>{data[0]}</code>

PASSWORD:
<code>{data[1]}</code>
"""
            )

            return

        # =================================================
        # MAIL LIST
        # =================================================
        if text == "MAIL LIST":

            mails = get_mail_list(user_id)

            if not mails:

                bot.reply_to(
                    message,
                    "❌ NO MAIL FOUND"
                )

                return

            result = "📂 YOUR MAIL LIST\n\n"

            for x in mails:

                result += f"""
📧 <code>{x[0]}</code>
🔑 <code>{x[1]}</code>

"""

            bot.reply_to(
                message,
                result[:4000]
            )

            return

        # =================================================
        # CHECK INBOX
        # =================================================
        if text == "CHECK INBOX":

            data = get_last_mail(user_id)

            if not data:

                bot.reply_to(
                    message,
                    "❌ NO MAIL"
                )

                return

            token = data[2]

            inbox = get_inbox(token)

            if not inbox:

                bot.reply_to(
                    message,
                    "📭 EMPTY INBOX"
                )

                return

            for mail in inbox[:10]:

                try:

                    msg_id = mail["id"]

                    full = get_message(
                        token,
                        msg_id
                    )

                    sender = mail["from"]["address"]

                    subject = mail.get(
                        "subject",
                        "No Subject"
                    )

                    body = ""

                    if full:

                        if full.get("text"):
                            body = full["text"]

                        elif full.get("html"):
                            body = str(full["html"])

                    otp = "NOT FOUND"

                    otp_find = re.findall(
                        r'\b\d{4,8}\b',
                        body
                    )

                    if otp_find:
                        otp = otp_find[0]

                    bot.send_message(
                        user_id,
                        f"""
📩 MAIL FOUND

📨 FROM:
<code>{sender}</code>

📝 SUBJECT:
<code>{subject}</code>

🔑 OTP:
<code>{otp}</code>

📩 MESSAGE:
<code>{body[:3000]}</code>
"""
                    )

                except Exception as e:

                    print(e)

            return

        # =================================================
        # LOGIN MAIL
        # =================================================
        if text == "LOGIN MAIL":

            login_state[user_id] = {
                "step":"login_email"
            }

            bot.reply_to(
                message,
                "📧 SEND EMAIL"
            )

            return

        # =================================================
        # BIN CHECK
        # =================================================
        if text == "BIN CHECK":

            login_state[user_id] = {
                "step":"bin_check"
            }

            bot.reply_to(
                message,
                "💳 SEND 6 DIGIT BIN"
            )

            return

        # =================================================
        # ADMIN PANEL
        # =================================================
        if text == "ADMIN PANEL" and user_id == ADMIN_ID:

            markup = ReplyKeyboardMarkup(
                resize_keyboard=True
            )

            markup.row("TOTAL USERS")
            markup.row("USER LIST")
            markup.row("APPROVED LIST")
            markup.row("REJECTED LIST")
            markup.row("BROADCAST")
            markup.row("BACK")

            bot.reply_to(
                message,
                "👑 ADMIN PANEL",
                reply_markup=markup
            )

            return

        # =================================================
        # TOTAL USERS
        # =================================================
        if text == "TOTAL USERS" and user_id == ADMIN_ID:

            cursor.execute(
                "SELECT COUNT(*) FROM users"
            )

            total = cursor.fetchone()[0]

            bot.reply_to(
                message,
                f"👥 TOTAL USERS: {total}"
            )

            return

        # =================================================
        # USER LIST
        # =================================================
        if text == "USER LIST" and user_id == ADMIN_ID:

            cursor.execute("""
            SELECT user_id,username,full_name
            FROM users
            """)

            rows = cursor.fetchall()

            result = "👥 USER LIST\n\n"

            for row in rows:

                result += f"""
👤 NAME:  <code>{row[2]}</code>

🔗 USERNAME:  @{row[1]}

🆔 ID:  <code>{row[0]}</code>

"""

            bot.reply_to(
                message,
                result[:4000]
            )

            return

        # =================================================
        # APPROVED LIST
        # =================================================
        if text == "APPROVED LIST" and user_id == ADMIN_ID:

            cursor.execute("""
            SELECT user_id,username
            FROM users
            WHERE approved=1
            """)

            rows = cursor.fetchall()

            result = "✅ APPROVED USERS\n\n"

            for row in rows:

                result += f"""
🆔 <code>{row[0]}</code>
🔗 @{row[1]}

"""

            bot.reply_to(
                message,
                result[:4000]
            )

            return

        # =================================================
        # REJECTED LIST
        # =================================================
        if text == "REJECTED LIST" and user_id == ADMIN_ID:

            cursor.execute("""
            SELECT user_id,username
            FROM users
            WHERE rejected=1
            """)

            rows = cursor.fetchall()

            result = "❌ REJECTED USERS\n\n"

            for row in rows:

                result += f"""
🆔 <code>{row[0]}</code>
🔗 @{row[1]}

"""

            bot.reply_to(
                message,
                result[:4000]
            )

            return

        # =================================================
        # BROADCAST
        # =================================================
        if text == "BROADCAST" and user_id == ADMIN_ID:

            login_state[user_id] = {
                "step":"broadcast"
            }

            bot.reply_to(
                message,
                "📢 SEND MESSAGE"
            )

            return

        # =================================================
        # LOGIN STATE (step by step)
        # =================================================
        if user_id in login_state:

            step = login_state[user_id]["step"]

            # =============================================
            # UID
            # =============================================
            if step == "check_uid":

                uid,name = extract_uid(text)

                if uid:

                    bot.reply_to(
                        message,
                        f"""
✅ PROFILE FOUND

👤 NAME:  <code>{name}</code>

🆔 UID:  <code>{uid}</code>

🔗 URL:  {text}
"""
                    )

                else:

                    bot.reply_to(
                        message,
                        "❌ UID NOT FOUND"
                    )

                del login_state[user_id]

                return

            # =============================================
            # 2FA with Refresh Button (UPDATED)
            # =============================================
            if step == "generate_2fa":

                try:
                    totp = pyotp.TOTP(text)
                    code = totp.now()
                    remain = 30 - (int(time.time()) % 30)

                    # Create inline button
                    markup = InlineKeyboardMarkup()
                    refresh_btn = InlineKeyboardButton(
                        "🔄 REFRESH CODE",
                        callback_data=f"refresh_2fa_{text}_{user_id}"
                    )
                    markup.add(refresh_btn)

                    bot.reply_to(
                        message,
                        f"""
✅ 2FA GENERATED

🔑 SECRET:  <code>{text}</code>

🔢 CODE:  <code>{code}</code>

⏳ EXPIRES:  {remain} SEC
""",
                        reply_markup=markup
                    )
                except:
                    bot.reply_to(
                        message,
                        "❌ INVALID SECRET"
                    )

                del login_state[user_id]

                return

            # =============================================
            # SAVE SECRET
            # =============================================
            if step == "save_secret":

                save_secret(
                    user_id,
                    text
                )

                bot.reply_to(
                    message,
                    "✅ SECRET SAVED"
                )

                del login_state[user_id]

                return

            # =============================================
            # LOGIN EMAIL
            # =============================================
            if step == "login_email":

                login_state[user_id]["email"] = text
                login_state[user_id]["step"] = "login_password"

                bot.reply_to(
                    message,
                    "🔑 SEND PASSWORD"
                )

                return

            # =============================================
            # LOGIN PASSWORD
            # =============================================
            if step == "login_password":

                email = login_state[user_id]["email"]

                token = login_mail(
                    email,
                    text
                )

                if not token:

                    bot.reply_to(
                        message,
                        "❌ LOGIN FAILED"
                    )

                    del login_state[user_id]

                    return

                save_mail(
                    user_id,
                    email,
                    text,
                    token
                )

                bot.reply_to(
                    message,
                    "✅ LOGIN SUCCESS"
                )

                del login_state[user_id]

                return

            # =============================================
            # BIN CHECK
            # =============================================
            if step == "bin_check":

                bin_number = text[:6]

                try:

                    r = requests.get(
                        f"https://lookup.binlist.net/{bin_number}",
                        timeout=20
                    )

                    if r.status_code != 200:

                        bot.reply_to(
                            message,
                            "❌ INVALID BIN"
                        )

                        del login_state[user_id]

                        return

                    data = r.json()

                    scheme = data.get("scheme","UNKNOWN")
                    brand = data.get("brand","UNKNOWN")
                    card_type = data.get("type","UNKNOWN")
                    bank = data.get("bank",{}).get("name","UNKNOWN")
                    country = data.get("country",{}).get("name","UNKNOWN")
                    emoji = data.get("country",{}).get("emoji","")

                    bot.reply_to(
                        message,
                        f"""
✅ BIN RESULT

💳 BIN: <code>{bin_number}</code>

🏦 BANK: <code>{bank}</code>

🌍 COUNTRY: <code>{country}</code> {emoji}

💠 SCHEME: <code>{scheme}</code>

📌 BRAND: <code>{brand}</code>

🧾 TYPE: <code>{card_type}</code>
"""
                    )

                except:

                    bot.reply_to(
                        message,
                        "❌ BIN CHECK FAILED"
                    )

                del login_state[user_id]

                return

            # =============================================
            # BROADCAST
            # =============================================
            if step == "broadcast":

                cursor.execute(
                    "SELECT user_id FROM users"
                )

                rows = cursor.fetchall()

                sent = 0

                for row in rows:

                    try:

                        bot.send_message(
                            row[0],
                            f"📢 BROADCAST\n\n{text}"
                        )

                        sent += 1

                    except:
                        pass

                bot.reply_to(
                    message,
                    f"✅ SENT TO {sent} USERS"
                )

                del login_state[user_id]

                return

        # =================================================
        # BACK BUTTON
        # =================================================
        if text == "BACK":

            markup = ReplyKeyboardMarkup(
                resize_keyboard=True
            )

            markup.row("CHECK UID")
            markup.row("GENERATE 2FA")
            markup.row("SAVE SECRET")
            markup.row("MY SAVED")

            markup.row("NEW MAIL")
            markup.row("MY MAIL")
            markup.row("MAIL LIST")

            markup.row("CHECK INBOX")
            markup.row("LOGIN MAIL")

            markup.row("BIN CHECK")

            if user_id == ADMIN_ID:
                markup.row("ADMIN PANEL")

            bot.reply_to(
                message,
                "🔙 BACK TO MAIN MENU",
                reply_markup=markup
            )

            return

    except Exception as e:

        traceback.print_exc()

# =========================================================
# AUTO OTP THREAD
# =========================================================
threading.Thread(
    target=auto_checker,
    daemon=True
).start()

# =========================================================
# RUN BOT
# =========================================================
while True:

    try:

        print("BOT RUNNING...")

        bot.infinity_polling(
            timeout=60,
            long_polling_timeout=60,
            skip_pending=True
        )

    except Exception as e:

        print(e)

        time.sleep(5)
