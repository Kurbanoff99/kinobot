import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ApplicationHandlerStop
)

# .env yoki Server Environment Variables'dan yuklanadigan ma'lumotlar
TOKEN = os.environ.get('TOKEN')
BAZA_KANAL_ID = int(os.environ.get('BAZA_KANAL_ID', '0'))  # ID raqam bo'lgani uchun int() qilamiz
MAJBURIY_KANAL_ID = os.environ.get('MAJBURIY_KANAL_ID')    # Masalan: @mening_kanalim
ADMIN_ID = os.environ.get('ADMIN_ID')
PORT = int(os.environ.get('PORT', '8443'))
SERVER_URL = os.environ.get('SERVER_URL')                  # Masalan: https://onrender.com

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Kinolar va ularning kanaldagi Message ID (Xabar raqami) lug'ati
# Yangi kino yuklaganingizda ushbu ro'yxatga kod va xabar ID-sini qo'shib borasiz
KINO_BAZASI = {
    "kino1": 45,
    "kino2": 46,
    "avatar": 52,
    "rembo": 60
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if str(user_id) == str(ADMIN_ID):
        await update.message.reply_text('Xush kelibsiz, Admin! 🛠\nYangi kinolarni KINO_BAZASI ro‘yxatiga qo‘shib qo‘yishni unutmang.')
    
    await update.message.reply_text(
        "Salom! Kinolarni yuklab olish uchun kino kodini yuboring.\n"
        "Masalan: kino1 yoki avatar"
    )

async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Majburiy kanalga a'zolikni tekshirish"""
    if not MAJBURIY_KANAL_ID:
        return
    
    try:
        user_id = update.effective_user.id
        chat = await context.bot.get_chat_member(chat_id=MAJBURIY_KANAL_ID, user_id=user_id)
        if chat.status in ['left', 'kicked']:
            await update.message.reply_text(
                f"⚠️ Botdan foydalanish uchun rasmiy kanalimizga a'zo bo'ling:\n"
                f"👉 {MAJBURIY_KANAL_ID}"
            )
            raise ApplicationHandlerStop
    except Exception as e:
        logger.error(f"Kanal tekshirishda xatolik: {e}")

async def kino_yuboruvchi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Foydalanuvchi kod yozganda kinoni maxfiy kanaldan ko'chirib beradi"""
    await check_membership(update, context)
    
    kino_kodi = update.message.text.strip().lower()

    if kino_kodi in KINO_BAZASI:
        message_id = KINO_BAZASI[kino_kodi]
        try:
            # Bot kinoni maxfiy kanaldan foydalanuvchiga nusxalab yuboradi
            await context.bot.copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=BAZA_KANAL_ID,
                message_id=message_id
            )
        except Exception as e:
            logger.error(f"Kinoni yuborishda xatolik: {e}")
            await update.message.reply_text("❌ Kechirasiz, faylni yuborishda texnik xatolik yuz berdi.")
    else:
        await update.message.reply_text("🔍 Bunday kodli kino topilmadi. Kodni to'g'ri yozganingizni tekshiring.")

def main() -> None:
    """Botni ishga tushirish (Webhook va Polling rejimi)"""
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, kino_yuboruvchi))

    if SERVER_URL:
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"{SERVER_URL}/{TOKEN}"
        )
    else:
        application.run_polling()

if __name__ == "__main__":
    main()
