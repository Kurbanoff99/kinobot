import uuid
import telegram
from telegram.constants import ChatAction
from utils import *
import logging
import os
import requests
from web_scrappers.netnaija import netnaija_web_scrapper
from web_scrappers.tfpdl import tfpdl
from web_scrappers.torrent_1337x import search_torrent1337x
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, InputMediaPhoto
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ApplicationHandlerStop,
    CommandHandler,
    InvalidCallbackData,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters
)

# .env yoki Server Environment Variables'dan ma'lumotlarni olish
TOKEN = os.environ.get('TOKEN')
api_key = os.environ.get('tmdbApiKey')
KANAL_ID = os.environ.get('KANAL_ID')
ADMIN_ID = os.environ.get('ADMIN_ID')
PORT = int(os.environ.get('PORT', '8443'))
SERVER_URL = os.environ.get('SERVER_URL') # Masalan: https://onrender.com

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

ResultsCache = {}
ResultsPerPage = 1
LinksCache = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_user.id) == str(ADMIN_ID):
        await update.message.reply_text('Xush kelibsiz, Admin!')
    await update.message.reply_text('Welcome To Terader Movie Hub! Send me a movie name.')

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kanalga a'zolikni tekshirish"""
    if not KANAL_ID:
        return
    try:
        chat = await context.bot.get_chat_member(user_id=update.effective_user.id, chat_id=KANAL_ID)
        if chat.status in ['left', 'kicked']:
            await update.message.reply_text('Botdan foydalanish uchun kanalimizga a\'zo bo\'ling!')
            await update.message.reply_text(parse_mode='HTML', text=f'https://t.me{KANAL_ID.replace("@", "")}')
            raise ApplicationHandlerStop
    except Exception as e:
        logger.error(f"Kanal tekshirishda xatolik: {e}")

async def handle_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.message.chat_id
    
    try:
        pagination_id, page = data.split('-')[1].split(':')
    except ValueError:
        return

    if page == "0":
        return

    cache_key = ResultsCache.get(user_id, None)
    if cache_key:
        results = cache_key.get(pagination_id)
        if not results:
            await query.answer(text="Message Expired\nPlease resend request", show_alert=True)
            return
        pages_length = int(len(results))
        results = results.get(page)
        await query.answer()
    else:
        await query.answer(text="Message Expired\nPlease resend request", show_alert=True)
        return

    page = int(page)
    button_labels = []
    if page > 1: button_labels.append('<< Prev')
    button_labels.append(f'🗒 {page}/{pages_length}')
    if pages_length > page: button_labels.append('Next >>')

    buttons = []
    for label in button_labels:
        if label == '<< Prev':
            buttons.append(InlineKeyboardButton(text=label, callback_data=f'page-{pagination_id}:{page-1}'))
        elif label == 'Next >>':
            buttons.append(InlineKeyboardButton(text=label, callback_data=f'page-{pagination_id}:{page+1}'))
        else:
            buttons.append(InlineKeyboardButton(text=label, callback_data=f'page-{pagination_id}:0'))

    reply_markup = InlineKeyboardMarkup([buttons])
    movie_poster_url = f'https://tmdb.org{results["poster_path"]}'
    file_obj = await get_raw_image(movie_poster_url)

    title_key = 'title' if results.get('title') else 'name'
    release_date_key = 'release_date' if results.get('title') else 'first_air_date'
    link_prefix = 'm' if title_key == 'title' else 's'
    link = f"/{link_prefix}_{results['id']}"

    movie_caption = f"🎬Title: {results[title_key]}\n📃Click to view: {link}\n🔤Language: {results['original_language']}\n🎯Released: {month_converter(results[release_date_key])}\n✅Voted: {results['vote_average']}"

    if file_obj:
        await update.effective_user.send_chat_action(action=ChatAction.UPLOAD_PHOTO)
        try:
            await update.effective_message.edit_media(media=InputMediaPhoto(media=file_obj, caption=movie_caption), reply_markup=reply_markup)
        except telegram.error.BadRequest:
            pass
    else:
        await update.effective_user.send_chat_action(action=ChatAction.TYPING)
        await update.effective_message.edit_caption(caption=movie_caption, reply_markup=reply_markup)

async def movie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.effective_message.text
    if not ('_ ' in text or '_' in text): return
    category, movie_id = text.split('_')
    category = "movie" if category == '/m' else "tv"

    req = requests.get(f'https://themoviedb.org{category}/{movie_id}?api_key={api_key}')
    if req.status_code == 200:
        req = req.json()
        movie_poster_url = f'https://tmdb.org{req["poster_path"]}'
        file_obj = await get_raw_image(movie_poster_url)
        imdb_link = f'IMDB LINK: https://imdb.com{req["imdb_id"]}\n' if req.get("imdb_id") else ''
        title_key, release_date_key = get_movie_type(req)
        
        caption = f'🎬Title: {req.get(title_key)}\n🎯Released: {req.get(release_date_key)}\nOverview: {req.get("overview")[:200]}\n{imdb_link}Voted: {req.get("vote_average")}\nTagline: {req.get("tagline")}\n'
        genre = ','.join([items['name'] for items in req.get('genres', [])[:6]])

        if file_obj:
            await update.effective_user.send_chat_action(action=ChatAction.UPLOAD_PHOTO)
            await update.effective_message.reply_photo(photo=file_obj, caption=f'{caption} 🎭Genres: {genre}')
        else:
            await update.effective_user.send_chat_action(action=ChatAction.TYPING)
            await update.effective_message.reply_text(text=f'{caption} 🎭Genres: {genre}')

def main() -> None:
    """Botni serverda ishga tushirish (Webhook yoki Polling)"""
    application = Application.builder().token(TOKEN).build()

    # Handlerlarni ro'yxatdan o'tkazish
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_pagination, pattern=r"^page-"))
    application.add_handler(MessageHandler(filters.Regex(r"^/(m|s)_"), movie))

    # Serverga joylashganda Webhook yoqiladi, localda esa oddiy ishlaydi
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
