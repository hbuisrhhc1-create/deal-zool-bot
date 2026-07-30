import warnings
warnings.filterwarnings("ignore")

import os
import string
import difflib
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from duckduckgo_search import DDGS
from flask import Flask
import threading

# --- הגדרות הבוט ישירות בקובץ ---
TELEGRAM_TOKEN = os.environ.get("TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_CHAT_ID_RAW = os.environ.get("ADMIN_CHAT_ID", "0")
ADMIN_CHAT_ID = int(ADMIN_CHAT_ID_RAW) if ADMIN_CHAT_ID_RAW.lstrip('-').isdigit() else 0

BUSINESS_NAME = "העסק שלי"
WELCOME_TEXT = "שלום רב וברוכים הבאים! 🛒\nנשמח לעמוד לשירותכם. לחצו על הכפתור למטה כדי להתחיל:"
NOT_FOUND_MESSAGE = "מצטערים, לא מצאנו מענה לשאלה שלך. העברנו את הפנייה ישירות לצוות הניהול שלנו."

# --- מאגר המידע (המילון) מובנה ישירות בקוד ---
KNOWLEDGE_BASE = {
    "-מה שעות הפעילות?": "ימים א'-ד' בין השעות 6:30-23:00, חמישי 6:30-0:00, שישי 6:30-15:30, שבת 18:00-22:00.",
    "-איך אפשר ליצור קשר?": "אפשר לפנות אלינו ישירות דרך הבוט או להגיע אלינו לחנות.",
    "-האם יש משלוחים?": "כן, אנחנו מציעים משלוחים. צור קשר לפרטים נוספים.",
    "-איך אפשר לשלם?": "ניתן לשלם בכרטיס אשראי או במזומן.",
    "מה כתובת העסק?": "אנחנו נמצאים ברחוב הראשי.",
    "האם יש חניה?": "כן, יש חניה בשפע בסביבת החנות לשימוש הלקוחות."
}

bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

pending_replies = {}
last_bot_messages = {}
last_user_questions = {}

def normalize_text(text):
    if not text:
        return ""
    text = text.strip()
    for p in string.punctuation + "؟،؛«»":
        text = text.replace(p, "")
    return " ".join(text.split())

def get_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for question in KNOWLEDGE_BASE.keys():
        if question.startswith("-"):
            markup.add(KeyboardButton(question))
    markup.add(KeyboardButton("📌 שאלות נפוצות"))
    return markup

def get_inline_questions_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    for question in list(KNOWLEDGE_BASE.keys()):
        if question.startswith("-"):
            markup.add(InlineKeyboardButton(text=question, callback_data=f"ask_{question}"))
    return markup

def get_start_button_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text="🚀 התחל / Start", callback_data="start_bot"))
    return markup

def get_back_to_menu_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text="🔙 חזרה לתפריט הראשי", callback_data="back_to_menu"))
    return markup

@bot.message_handler(commands=['start', 'help', 'menu', 'popular'])
def send_welcome(message):
    bot.send_message(
        message.chat.id, 
        WELCOME_TEXT, 
        reply_markup=get_start_button_keyboard()
    )
    last_bot_messages[message.chat.id] = WELCOME_TEXT
    last_user_questions[message.chat.id] = "/start"

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    if call.data == "start_bot":
        markup_inline = get_inline_questions_keyboard()
        text_to_send = "📌 **תפריט ראשי - בחר שאלה מהרשימה:**"
        try:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text_to_send, reply_markup=markup_inline, parse_mode="Markdown")
        except Exception:
            bot.send_message(call.message.chat.id, text_to_send, reply_markup=markup_inline, parse_mode="Markdown")
        last_bot_messages[call.message.chat.id] = text_to_send

    elif call.data == "back_to_menu":
        markup_inline = get_inline_questions_keyboard()
        text_to_send = "📌 **בחר שאלה נוספת מהרשימה:**"
        try:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text_to_send, reply_markup=markup_inline, parse_mode="Markdown")
        except Exception:
            bot.send_message(call.message.chat.id, text_to_send, reply_markup=markup_inline, parse_mode="Markdown")
        last_bot_messages[call.message.chat.id] = text_to_send

    elif call.data.startswith('ask_'):
        question_key = call.data.replace('ask_', '')
        if question_key in KNOWLEDGE_BASE:
            answer = KNOWLEDGE_BASE[question_key]
            text_to_send = f"📌 **{question_key}**\n\n{answer}"
            try:
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text_to_send, reply_markup=get_back_to_menu_keyboard(), parse_mode="Markdown")
            except Exception:
                bot.send_message(call.message.chat.id, text_to_send, reply_markup=get_back_to_menu_keyboard(), parse_mode="Markdown")
            last_bot_messages[call.message.chat.id] = text_to_send
            last_user_questions[call.message.chat.id] = question_key

def search_the_web(query):
    try:
        focused_query = f"{query} {BUSINESS_NAME}"
        with DDGS() as ddgs:
            results = [r['body'] for r in ddgs.text(focused_query, max_results=3)]
            if results:
                combined_results = "\n\n".join(results)
                if any(w in combined_results for w in [w for w in query.split() if len(w) > 2]) or BUSINESS_NAME in combined_results:
                    return combined_results
    except Exception as e:
        print(f"Search error: {e}")
    return None

@bot.message_handler(func=lambda message: message.chat.id == ADMIN_CHAT_ID)
def handle_admin_messages(message):
    user_text = message.text or message.caption or ""

    if message.reply_to_message:
        replied_msg_id = message.reply_to_message.message_id
        if replied_msg_id in pending_replies:
            target_user_chat_id = pending_replies[replied_msg_id]
            admin_answer = user_text.strip()
            try:
                bot.send_message(target_user_chat_id, f"💬 תשובה מהצוות:\n\n{admin_answer}")
                bot.reply_to(message, "✅ התשובה נשלחה ללקוח בהצלחה!")
            except Exception as e:
                bot.reply_to(message, f"❌ שגיאה בשליחת התשובה ללקוח: {e}")
            return

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.chat.id == ADMIN_CHAT_ID:
        return

    user_text = message.text.strip() if message.text else ""
    markup = get_main_keyboard()
    normalized_knowledge_base = {normalize_text(k): v for k, v in KNOWLEDGE_BASE.items()}
    lower_user_text = user_text.lower()
    chat_id = message.chat.id

    forward_triggers = ["תגיד לצוות", "תאמר לצוות", "תגיד למנהל", "תאמר למנהל"]
    if any(lower_user_text.startswith(trigger) for trigger in forward_triggers):
        bot.reply_to(message, "הבקשה שלך הועברה ישירות לצוות הניהול.", reply_markup=markup)
        if ADMIN_CHAT_ID:
            try:
                user_handle = f"@{message.from_user.username}" if message.from_user.username else "אין שם משתמש"
                prev_q = last_user_questions.get(chat_id, "לא ידוע")
                prev_a = last_bot_messages.get(chat_id, "אין תיעוד")
                alert_text = (
                    f"📨 **הודעה ייעודית לצוות משתמש!**\n"
                    f"👤 שם: {message.from_user.first_name}\n"
                    f"🔗 טג: {user_handle}\n"
                    f"🆔 מזהה: `{chat_id}`\n"
                    f"❓ שאלה אחרונה: {prev_q}\n"
                    f"🤖 תשובה אחרונה: {prev_a}\n"
                    f"💬 תוכן ההודעה: {user_text}"
                )
                sent_alert = bot.send_message(ADMIN_CHAT_ID, alert_text, parse_mode="Markdown")
                pending_replies[sent_alert.message_id] = chat_id
            except Exception as e:
                print(f"Error: {e}")
        return

    error_triggers = ["יש טעות", "טעות", "תעות", "לא נכון", "שגוי", "שגיה", "זה לא נכון", "יש תקלה", "בעיה"]
    if any(trigger in lower_user_text for trigger in error_triggers):
        bot.reply_to(message, "תודה על העדכון! העברתי את הדיווח לצוות הניהול לבדיקה.", reply_markup=markup)
        if ADMIN_CHAT_ID:
            try:
                user_handle = f"@{message.from_user.username}" if message.from_user.username else "אין שם משתמש"
                prev_q = last_user_questions.get(chat_id, "לא ידוע")
                prev_a = last_bot_messages.get(chat_id, "אין תיעוד")
                alert_text = (
                    f"⚠️ **דיווח על טעות/תקלה!**\n"
                    f"👤 שם: {message.from_user.first_name}\n"
                    f"🔗 טג: {user_handle}\n"
                    f"🆔 מזהה: `{chat_id}`\n"
                    f"❓ שאלה: {prev_q}\n"
                    f"🤖 תשובה: {prev_a}\n"
                    f"💬 דיווח: {user_text}"
                )
                sent_alert = bot.send_message(ADMIN_CHAT_ID, alert_text, parse_mode="Markdown")
                pending_replies[sent_alert.message_id] = chat_id
            except Exception as e:
                print(f"Error: {e}")
        return

    if user_text == "📌 שאלות נפוצות":
        popular_questions = [q for q in KNOWLEDGE_BASE.keys() if q.startswith("-")]
        popular_text = "📌 **השאלות הנפוצות ביותר:**\n\n" + "\n".join([f"• {q}" for q in popular_questions])
        markup_inline = get_inline_questions_keyboard()
        sent = bot.reply_to(message, popular_text, reply_markup=markup_inline)
        last_bot_messages[chat_id] = popular_text
        last_user_questions[chat_id] = "📌 שאלות נפוצות"
        return

    if any(g in lower_user_text for g in ["שלום", "היי", "הלו", "מה נשמע", "בוקר טוב", "ערב טוב"]):
        greet_text = "שלום רב! לחץ על כפתור ההתחלה כדי לפתוח את התפריט:"
        sent = bot.reply_to(message, greet_text, reply_markup=get_start_button_keyboard())
        last_bot_messages[chat_id] = greet_text
        last_user_questions[chat_id] = user_text
        return

    clean_user_text = normalize_text(user_text)
    matched_key = None
    if clean_user_text in normalized_knowledge_base:
        matched_key = clean_user_text
    else:
        close_matches = difflib.get_close_matches(clean_user_text, list(normalized_knowledge_base.keys()), n=1, cutoff=0.7)
        if close_matches:
            matched_key = close_matches[0]

    if matched_key:
        original_key = [k for k in KNOWLEDGE_BASE.keys() if normalize_text(k) == matched_key][0]
        answer = KNOWLEDGE_BASE[original_key]
        bot.send_chat_action(chat_id, 'typing')
        sent = bot.reply_to(message, answer, reply_markup=markup)
        last_bot_messages[chat_id] = answer
        last_user_questions[chat_id] = original_key
    else:
        bot.send_chat_action(chat_id, 'typing')
        web_result = search_the_web(user_text)
        if web_result:
            reply_to_send = f"מצאתי את המידע הבא:\n\n{web_result}"
            bot.reply_to(message, reply_to_send, reply_markup=markup)
            last_bot_messages[chat_id] = reply_to_send
            last_user_questions[chat_id] = user_text
        else:
            bot.reply_to(message, NOT_FOUND_MESSAGE, reply_markup=markup)
            last_bot_messages[chat_id] = NOT_FOUND_MESSAGE
            last_user_questions[chat_id] = user_text
            
        if ADMIN_CHAT_ID:
            try:
                user_handle = f"@{message.from_user.username}" if message.from_user.username else "אין שם משתמש"
                prev_a = last_bot_messages.get(chat_id, NOT_FOUND_MESSAGE)
                sent_alert = bot.send_message(
                    ADMIN_CHAT_ID, 
                    f"❓ **שאלה חדשה שלא נמצאה:**\n"
                    f"👤 שם: {message.from_user.first_name}\n"
                    f"🔗 טג: {user_handle}\n"
                    f"🆔 מזהה: `{chat_id}`\n"
                    f"🤖 התשובה האחרונה: {prev_a}\n"
                    f"תוכן הודעת המשתמש: {user_text}",
                    parse_mode="Markdown"
                )
                pending_replies[sent_alert.message_id] = chat_id
            except Exception as e:
                print(f"Error: {e}")

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running successfully!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.start()
    
    if bot:
        print("Single-file Bot Engine is running successfully...")
        bot.infinity_polling(allowed_updates=['message', 'edited_message', 'callback_query'])
    else:
        print("Error: TELEGRAM_TOKEN is missing!")
