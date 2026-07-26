import asyncio
import sqlite3
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# --- ASOSIY SOZLAMALAR ---
BOT_TOKEN = "8736896110:AAEr98TC0jYGOZlcOOSMG_9CBoCf4R4HErI"
KANAL_ID = "@kinokodlari_HD"  # Masalan: @topkinokod_kanal
ADMIN_ID = 8926774561  # O'zingizning Telegram ID raqamingiz (@userinfobot orqali olingan)

# Botni HTML formatda xabarlar yuboradigan qilib sozlaymiz (Server uchun proxy shart emas)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- MA'LUMOTLAR BAZASI BILAN ISHLASH ---
def baza_yaratish():
    conn = sqlite3.connect("kinolar.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kinolar (
            kod TEXT PRIMARY KEY,
            nomi TEXT,
            link TEXT
        )
    """)
    conn.commit()
    conn.close()

# Kanalga a'zolikni tekshirish funksiyasi
async def azomi(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=KANAL_ID, user_id=user_id)
        return member.status in ["creator", "administrator", "member"]
    except Exception:
        return False

# Start buyrug'i kelganda
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    
    if await azomi(user_id):
        await message.answer("🍿 <b>Xush kelibsiz!</b> Kino kodini yuboring (Masalan: 101):")
    else:
        builder = InlineKeyboardBuilder()
        builder.button(text="Kanallarga a'zo bo'lish 📢", url=f"https://t.me{KANAL_ID.replace('@', '')}")
        builder.button(text="Tekshirish ✅", callback_data="check_sub")
        builder.adjust(1)
        
        await message.answer(
            "<b>Botdan foydalanish uchun homiy kanalimizga a'zo bo'ling! 👇</b>",
            reply_markup=builder.as_markup()
        )

# Tekshirish tugmasi bosilganda
@dp.callback_query(F.data == "check_sub")
async def check_subscription(callback: types.CallbackQuery):
    if await azomi(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer("Rahmat! Endi kino kodini yuborishingiz mumkin: 🍿")
    else:
        await callback.answer("Siz hali kanalga a'zo bo'lmadingiz! ❌", show_alert=True)

# Admin uchun yeni kino qo'shish buyrug'i
# Format: /add [kod] [nomi] [link]
@dp.message(Command("add"))
async def add_movie(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        args = message.text.split(" ", 3)
        if len(args) < 4:
            await message.answer("❌ Xatolik! Format: <code>/add kod nomi link_yoki_faylid</code>")
            return
            
        kod = args[1].strip()
        nomi = args[2].strip()
        link = args[3].strip()
        
        conn = sqlite3.connect("kinolar.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO kinolar VALUES (?, ?, ?)", (kod, nomi, link))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ <b>Kino muvaffaqiyatli qo'shildi!</b>\n\n<b>Kod:</b> {kod}\n<b>Nomi:</b> {nomi}")
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {e}")

# Kino kodini qidirish va yuborish
@dp.message()
async def send_movie(message: types.Message):
    user_id = message.from_user.id
    
    if not await azomi(user_id):
        await start_cmd(message)
        return

    kod = message.text.strip()
    
    conn = sqlite3.connect("kinolar.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nomi, link FROM kinolar WHERE kod=?", (kod,))
    natija = cursor.fetchone()
    conn.close()
    
    if natija:
        nomi, link = natija
        await message.answer(f"🎬 <b>Kino nomi:</b> {nomi}\n\n🍿 <b>Tomosha qilish:</b> {link}")
    else:
        await message.answer("Afsuski, bunday kodli kino topilmadi. Boshqa kod yozib ko'ring. 😔")

async def main():
    baza_yaratish()
    print("Bot muvaffaqiyatli ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
