import os
import json
import re
import logging
import asyncio
from uvicorn import Config, Server
from fastapi import FastAPI
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ApplicationHandlerStop
)

# .env yoki Render boshqaruv panelidan olinadigan o'zgaruvchilar
TOKEN = os.environ.get('TOKEN')
BAZA_KANAL_ID = int(os.environ.get('BAZA_KANAL_ID', '0'))
MAJBURIY_KANAL_ID = os.environ.get('MAJBURIY_KANAL_ID')
ADMIN_ID = os.environ.get('ADMIN_ID')
PORT = int(os.environ.get('PORT', 10000)) # Render default porti 10000

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

USERS_FILE = "bot_users.json"
MOVIES_FILE = "movies_db.json"

# FastAPI veb-server yaratish (Render port xatosini yo'qotish uchun)
app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "Bot is running successfully"}

def load_data(file_name, default_factory):
    if os.path.exists(file_name):
        with open(file_name, "r") as f:
            return json.load(f)
    return default_factory()

def save_data(file_name, data):
    with open(file_name, "w") as f:
        json.dump(data, f, indent=4)

users_list = load_data(USERS_FILE, list)
KINO_BAZASI = load_data(MOVIES_FILE, dict)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in users_list:
        users_list.append(user_id)
        save_data(USERS_FILE, users_list)

    if str(user_id) == str(ADMIN_ID):
        await update.message.reply_text(
            "👑 Admin paneliga xush kelibsiz!\n\n"
            "Buyruqlar:\n"
            "📊 /stat - Bot statistikasini ko'rish\n"
            "📢 /send [matn] - Barcha foydalanuvchilarga reklama yuborish\n"
            "❌ /del [kod] - Kinoni bazadan o'chirish\n\n"
            "💡 Yangi kino qo'shish uchun uni maxfiy kanalga yuklang va tavsifning eng tagiga raqamli kodini (masalan: 101) yozib qo'ying!"
        )
    else:
        await update.message.reply_text("Salom! Kinolarni yuklab olish uchun kino kodini yuboring.")

# --- AVTOMATIK KINO QO'SHISH ---
async def auto_add_movie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    channel_post = update.channel_post
    if channel_post.chat.id != BAZA_KANAL_ID:
        return
    tavsif = channel_post.text or channel_post.caption
    if tavsif:
        kodlar = re.findall(r'\b\d+\b', tavsif)
        if kodlar:
            kino_kodi = kodlar[-1] 
            message_id = channel_post.message_id
            KINO_BAZASI[kino_kodi] = message_id
            save_data(MOVIES_FILE, KINO_BAZASI)
            logger.info(f"Avtomatik qo'shildi: {kino_kodi} -> {message_id}")

# --- ADMIN BUYRUQLARI ---
async def admin_stat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_user.id) != str(ADMIN_ID): return
    text = f"📊 **Bot Statistikasi:**\n\n👤 Jami a'zolar: {len(users_list)} ta\n🎬 Jami kinolar: {len(KINO_BAZASI)} ta"
    await update.message.reply_text(text, parse_mode="Markdown")

async def admin_delete_movie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_user.id) != str(ADMIN_ID): return
    if not context.args:
        await update.message.reply_text("⚠️ Ishlatish: `/del kino_kodi`", parse_mode="Markdown")
        return
    kino_kodi = context.args[0].lower()
    if kino_kodi in KINO_BAZASI:
        del KINO_BAZASI[kino_kodi]
        save_data(MOVIES_FILE, KINO_BAZASI)
        await update.message.reply_text(f"🗑 `{kino_kodi}` bazadan o'chirildi.", parse_mode="Markdown")
    else:
        await update.message.reply_text("🔍 Bunday kino topilmadi.")

async def admin_send_reklama(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_user.id) != str(ADMIN_ID): return
    text_to_send = update.message.text[6:].strip()
    if not text_to_send:
        await update.message.reply_text("⚠️ Reklama matnini kiriting.")
        return
    await update.message.reply_text("📢 Reklama yuborilmoqda...")
    yuborildi, xato = 0, 0
    for uid in users_list:
        try:
            await context.bot.send_message(chat_id=uid, text=text_to_send)
            yuborildi += 1
        except Exception:
            xato += 1
    await update.message.reply_text(f"✅ Tugadi!\n✨ Muvaffaqiyatli: {yuborildi}\n❌ Bloklaganlar: {xato}")

# --- FOYDALANUVCHI FUNKSIYALARI ---
async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not MAJBURIY_KANAL_ID: return
    try:
        user_id = update.effective_user.id
        chat = await context.bot.get_chat_member(chat_id=MAJBURIY_KANAL_ID, user_id=user_id)
        if chat.status in ['left', 'kicked']:
            await update.message.reply_text(f"⚠️ Botdan foydalanish uchun rasmiy kanalimizga a'zo bo'ling:\n👉 {MAJBURIY_KANAL_ID}")
            raise ApplicationHandlerStop
    except Exception as e:
        logger.error(f"Kanal tekshirishda xatolik: {e}")

async def kino_yuboruvchi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await check_membership(update, context)
    kino_kodi = update.message.text.strip().lower()

    if kino_kodi in KINO_BAZASI:
        message_id = KINO_BAZASI[kino_kodi]
        try:
            await context.bot.copy_message(chat_id=update.effective_chat.id, from_chat_id=BAZA_KANAL_ID, message_id=message_id)
        except Exception as e:
            logger.error(f"Kinoni yuborishda xatolik: {e}")
            await update.message.reply_text("❌ Faylni yuborishda texnik xatolik yuz berdi.")
    else:
        await update.message.reply_text("🔍 Bunday kodli kino topilmadi. Kodni to'g'ri yozganingizni tekshiring.")

async def run_bot():
    """Telegram Botni Polling rejimida orqa fonda boshlash"""
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stat", admin_stat))
    application.add_handler(CommandHandler("del", admin_delete_movie))
    application.add_handler(CommandHandler("send", admin_send_reklama))
    
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL, auto_add_movie))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, kino_yuboruvchi))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    logger.info("Telegram Bot Polling rejimida muvaffaqiyatli ishga tushdi.")

if __name__ == "__main__":
    # Botni asinxron ishga tushirish
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot())
    
    # Render portini tinglaydigan Uvicorn Veb Serverini yoqish
    config = Config(app=app, host="0.0.0.0", port=PORT, log_level="info")
    server = Server(config)
    loop.run_until_complete(server.serve())
