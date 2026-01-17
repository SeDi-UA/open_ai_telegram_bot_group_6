import logging
import warnings
from random import choice

from telegram import (Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton,
                      InlineKeyboardMarkup)
from telegram.error import BadRequest
from telegram.ext import (ContextTypes, ConversationHandler, CommandHandler, MessageHandler,
                          filters, CallbackQueryHandler)
from telegram.warnings import PTBUserWarning

from config import (CHATGPT_TOKEN, TRAN_BUTTONS, RECOM_TYPES_BUTTONS,
                    TranStates, RecomStates)
from gpt import ChatGPTService
from db import get_quantity, set_user_history, get_favorites, update_action_null, get_quality
from utils import (send_image, send_text, load_message, show_main_menu, load_prompt, send_text_buttons,
                   translator, get_country_name, get_type_inline_keyboard, get_genre_inline_keyboard,
                   send_favs_list, get_nav_buttons, recom_gpt)

chatgpt_service = ChatGPTService(CHATGPT_TOKEN)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_image(update, context, "start")
    await send_text(update, context, load_message("start"), ReplyKeyboardRemove())
    await show_main_menu(
        update,
        context,
        {
            'start': 'Головне меню',
            'random': 'Дізнатися випадковий факт',
            'gpt': 'Запитати ChatGPT',
            'talk': 'Діалог з відомою особистістю',
            'translate': 'Переклад на обрану мову',
            'recommendation': 'Надає рекомендації щодо фільмів, книг чи музики'
        }
    )
    return ConversationHandler.END


async def random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_image(update, context, "random")
    message_to_delete = await send_text(update, context, "Шукаю випадковий факт ...")
    try:
        prompt = load_prompt("random")
        fact = await chatgpt_service.send_question(
            prompt_text=prompt,
            message_text="Розкажи про випадковий факт"
        )
        buttons = {
            'random': 'Хочу ще один факт',
            'start': 'Закінчити'
        }
        await send_text_buttons(update, context, fact, buttons)
    except Exception as e:
        logger.error(f"Помилка в обробнику /random: {e}")
        await send_text(update, context, "Помилка при отриманні випадкового факту.")
    finally:
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=message_to_delete.message_id
        )


async def random_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == 'random':
        await random(update, context)
    elif data == 'start':
        await start(update, context)


async def gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await send_image(update, context, "gpt")
    chatgpt_service.set_prompt(load_prompt("gpt"))
    await send_text(update, context, "Задайте питання ...")
    context.user_data["conversation_state"] = "gpt"


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    conversation_state = context.user_data.get("conversation_state")
    if conversation_state == "gpt":
        waiting_message = await send_text(update, context, "...")
        try:
            response = await chatgpt_service.add_message(message_text)
            await send_text(update, context, response)
        except Exception as e:
            logger.error(f"Помилка при отриманні відповіді від ChatGPT: {e}")
            await send_text(update, context, "Виникла помилка при обробці вашого повідомлення.")
        finally:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=waiting_message.message_id
            )
    if conversation_state == "talk":
        personality = context.user_data.get("selected_personality")
        if personality:
            prompt = load_prompt(personality)
            chatgpt_service.set_prompt(prompt)
        else:
            await send_text(update, context, "Спочатку оберіть особистість для розмови!")
            return
        waiting_message = await send_text(update, context, "...")
        try:
            response = await chatgpt_service.add_message(message_text)
            buttons = {"start": "Закінчити"}
            personality_name = personality.replace("talk_", "").replace("_", " ").title()
            await send_text_buttons(update, context, f"{personality_name}: {response}", buttons)
        except Exception as e:
            logger.error(f"Помилка при отриманні відповіді від ChatGPT: {e}")
            await send_text(update, context, "Виникла помилка при отриманні відповіді!")
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=waiting_message.message_id
            )
        finally:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=waiting_message.message_id
            )
    if not conversation_state:
        intent_recognized = await inter_random_input(update, context, message_text)
        if not intent_recognized:
            await show_funny_response(update)
        return


async def talk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await send_image(update, context, "talk")
    personalities = {
        'talk_linus_torvalds': "Linus Torvalds (Linux, Git)",
        'talk_guido_van_rossum': "Guido van Rossum (Python)",
        'talk_mark_zuckerberg': "Mark Zuckerberg (Meta, Facebook)",
        'start': "Закінчити",
    }
    await send_text_buttons(update, context, "Оберіть особистість для спілкування ...", personalities)


async def talk_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "start":
        context.user_data.pop("conversation_state", None)
        context.user_data.pop("selected_personality", None)
        await start(update, context)
        return
    if data.startswith("talk_"):
        context.user_data.clear()
        context.user_data["selected_personality"] = data
        context.user_data["conversation_state"] = "talk"
        prompt = load_prompt(data)
        chatgpt_service.set_prompt(prompt)
        personality_name = data.replace("talk_", "").replace("_", " ").title()
        await send_image(update, context, data)
        buttons = {'start': "Закінчити"}
        await send_text_buttons(
            update,
            context,
            f"Hello, I`m {personality_name}."
            f"\nI heard you wanted to ask me something. "
            f"\nYou can ask questions in your native language.",
            buttons
        )


async def inter_random_input(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text):
    message_text_lower = message_text.lower()
    if any(keyword in message_text_lower for keyword in ['факт', 'цікав', 'random', 'випадков']):
        await send_text(
            update,
            context,
            text="Схоже, ви цікавитесь випадковими фактами! Зараз покажу вам один..."
        )
        await random(update, context)
        return True

    elif any(keyword in message_text_lower for keyword in ['gpt', 'чат', 'питання', 'запита', 'дізнатися']):
        await send_text(
            update,
            context,
            text="Схоже, у вас є питання! Переходимо до режиму спілкування з ChatGPT..."
        )
        await gpt(update, context)
        return True

    elif any(keyword in message_text_lower for keyword in ['розмов', 'говори', 'спілкува', 'особист', 'talk']):
        await send_text(
            update,
            context,
            text="Схоже, ви хочете поговорити з відомою особистістю! Зараз покажу вам доступні варіанти..."
        )
        await talk(update, context)
        return True
    return False


async def show_funny_response(update: Update):
    funny_responses = [
        "Хмм... Цікаво, але я не зрозумів, що саме ви хочете. Може спробуєте одну з команд з меню?",
        "Дуже цікаве повідомлення! Але мені потрібні чіткіші інструкції. Ось доступні команди:",
        "Ой, здається, ви мене застали зненацька! Я вмію багато чого, але мені потрібна конкретна команда:",
        "Вибачте, мої алгоритми не розпізнали це як команду. Ось що я точно вмію:",
        "Це повідомлення таке ж загадкове, як єдиноріг у дикій природі! Спробуйте одну з цих команд:",
        "Я намагаюся зрозуміти ваше повідомлення... Але краще скористайтесь однією з команд:",
        "О! Випадкове повідомлення! Я теж вмію бути випадковим, але краще використовуйте команди:",
        "Гм, не спрацювало. Може спробуємо ці команди?",
        "Це повідомлення прекрасне, як веселка! Але для повноцінного спілкування спробуйте:",
        "Згідно з моїми розрахунками, це повідомлення не відповідає жодній з моїх команд. Ось вони:",
    ]
    random_response = choice(funny_responses)
    available_commands = """
    - Не знаєте, що обрати? Почніть з /start,
    - Спробуйте команду /gpt, щоб задати питання,
    """
    full_message = f"{random_response}\n{available_commands}"
    await update.message.reply_text(full_message)


async def translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await send_image(update, context, "translate")
    reply_markup = ReplyKeyboardMarkup(TRAN_BUTTONS, resize_keyboard=True)
    await update.message.reply_text("Оберіть мову, на яку потрібно перекласти:",reply_markup=reply_markup)
    return TranStates.CHOOSING_LANGUAGE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start(update, context)


async def select_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang_code = update.message.text
    if lang_code == "Закінчити":
        return await start(update, context)
    lang = get_country_name(lang_code)
    context.user_data['target_lang_code'] = lang_code
    reply_markup = ReplyKeyboardMarkup([['Закінчити']], resize_keyboard=True)
    await update.message.reply_text(
        f"Ви обрали мову {lang} {lang_code}.\nНапишіть текст, який необхідно перекласти:",
        reply_markup=reply_markup
    )
    return TranStates.TYPING_TEXT


async def tran_proc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_to_delete = await send_text(update, context, "Перекладаю ⏳ ...")
    try:
        text_to_tran = update.message.text
        if text_to_tran == "Закінчити":
            return await start(update, context)
        target_lang_code = context.user_data.get('target_lang_code')
        target_lang = get_country_name(target_lang_code)
        translated_text = await translator(chatgpt_service, text_to_tran, target_lang, target_lang_code)
        reply_markup = ReplyKeyboardMarkup(TRAN_BUTTONS, resize_keyboard=True)
        await update.message.reply_text(translated_text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Помилка в обробнику /tran_proc: {e}")
        await send_text(update, context, "Помилка при перекладі.")
    finally:
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=message_to_delete.message_id
        )
    return TranStates.CHOOSING_LANGUAGE


tran_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("translate", translate)],
        states={
            TranStates.CHOOSING_LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_lang)],
            TranStates.TYPING_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, tran_proc)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )


async def start_recom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    total_saved = await get_quantity(user_id)
    context.user_data['total_saved'] = total_saved
    query = update.callback_query
    if total_saved == 0:
        context.user_data['recom_mode'] = 'new'
        kb = await get_type_inline_keyboard(user_id, 'new')
        if query:
            text = "⚠️ Ви все видалили\n\n✨ Оберіть категорію для підбору:"
            await query.edit_message_text(text, reply_markup=kb)
        else:
            text = "✨ Оберіть категорію для підбору:"
            msg = await send_image(update, context, "recom2")
            context.user_data['recom_img_id'] = msg.message_id
            await context.bot.send_message(user_id, text, reply_markup=kb)
        return RecomStates.CHOOSING_TYPE

    buttons = [
        [InlineKeyboardButton("✨ Підібрати", callback_data="mode_new")],
        [InlineKeyboardButton(f"💾 Збережені ({total_saved})", callback_data="mode_favs")]
    ]
    kb = InlineKeyboardMarkup(buttons)
    text = "Оберіть режим роботи:"
    if query:
        await query.edit_message_text(text, reply_markup=kb)
    else:
        msg = await send_image(update, context, "recom2")
        context.user_data['recom_img_id'] = msg.message_id
        await update.message.reply_text(text, reply_markup=kb)
    return RecomStates.CHOOSING_MODE


async def recom_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("mode_"):
        mode = query.data.replace("mode_", "")
        context.user_data['recom_mode'] = mode
    else:
        mode = context.user_data.get('recom_mode')

    is_favs = bool(context.user_data.get('total_saved', 0))
    kb = await get_type_inline_keyboard(query.from_user.id, mode, is_favs)
    previous_type = context.user_data.pop('recom_previous_type', None)
    if previous_type:
        text = f"⚠️ Категорія {previous_type} тепер пуста\n\n💾 Подивимось щось інше?"
    else:
        text = "💾 Оберіть категорію:" if mode == 'favs' else "✨ Що підберемо?"
    await query.edit_message_text(text, reply_markup=kb)
    return RecomStates.CHOOSING_TYPE


async def recom_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, if_error=False):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data.startswith("type_"):
        item_type = query.data.replace("type_", "")
        context.user_data['recom_type'] = item_type
    else:
        item_type = context.user_data.get('recom_type')
    mode = context.user_data.get('recom_mode')
    kb = await get_genre_inline_keyboard(user_id, item_type, mode)
    previous_genre = context.user_data.pop('recom_previous_genre', None)
    genre = RECOM_TYPES_BUTTONS.get(item_type, item_type)
    if if_error:
        text = f"⚠️ Вибачте, сталася помилка\n\n💾 Оберіть інший жанр:\n\n\t{genre}"
    elif previous_genre:
        text = f"⚠️ Жанр {previous_genre} тепер пустий\n\n💾 Оберіть інший жанр:\n\n\t{genre}"
    else:
        text = f"💾 Оберіть жанр:\n\n\t{genre}"
    await query.edit_message_text(text, reply_markup=kb)
    return RecomStates.CHOOSING_GENRE


async def recom_genre_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    genre = query.data.replace("genre_", "")
    context.user_data['recom_genre'] = genre
    return await get_result(update, context)


async def get_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    mode = context.user_data.get('recom_mode')
    action_status = context.user_data.pop('recom_last_action_status', "")
    user_id = query.from_user.id
    item_type = context.user_data.get('recom_type', "")
    item_genre = context.user_data.get('recom_genre', "")
    if mode == 'favs':
        favs = await get_favorites(
            query.from_user.id,
            item_type,
            item_genre
        )
        context.user_data['recom_user_favorites_dict'] = favs
        await send_favs_list(query, context, favs)
        return RecomStates.REMOVE_FAV

    await query.edit_message_text("Шукаю...")
    ai_recom = await recom_gpt(chatgpt_service, user_id, item_type, item_genre)
    if ai_recom:
        context.user_data['current_item_name'] = ai_recom
        eval_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👎 Не цікавить", callback_data="act_ignore"),
             InlineKeyboardButton("💾 Зберегти", callback_data="act_save")],
            *get_nav_buttons("result")
        ])
        prefix = f"✅ Збережено!\n\n✨ Наступна" if action_status else "✨ Моя"
        msg_text = f"{prefix} порада для вас:\n\n{item_type} -> {item_genre}\n\n<b>{ai_recom}</b>"
        if query:
            try:
                await query.edit_message_text(text=msg_text, reply_markup=eval_kb,
                                              parse_mode='HTML')
            except BadRequest as e:
                if "Message is not modified" not in str(e): raise e
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id,text=msg_text,reply_markup=eval_kb,
                                           parse_mode='HTML')

        return RecomStates.WAITING_FOR_ACTION
    else:
        return await recom_type_callback(update, context, True)


async def recom_update_favs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = int(query.data.replace("del_", ""))
    await update_action_null(item_id, context)
    favs = context.user_data.get('recom_user_favorites_dict', {})
    favs.pop(item_id, None)
    if favs:
        await send_favs_list(query, context, favs)
        return RecomStates.REMOVE_FAV
    else:
        user_id = query.from_user.id
        item_type = context.user_data.get('recom_type')

        genres = await get_quality(user_id, item_type)
        if genres:
            context.user_data['recom_previous_genre'] = context.user_data.get('recom_genre')
            return await recom_type_callback(update, context)

        types = await get_quality(user_id)
        if types:
            context.user_data['recom_previous_type'] = item_type
            return await recom_mode_callback(update, context)

        return await start_recom(update, context)


async def recom_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action_type = query.data.replace("act_", "")

    action_val = 1 if action_type == 'save' else 0
    if action_val:
        context.user_data['total_saved'] += 1
    await set_user_history(
        query.from_user.id,
        context.user_data['current_item_name'],
        context.user_data['recom_type'],
        context.user_data['recom_genre'],
        action_val
    )
    context.user_data['recom_last_action_status'] = action_val
    return await get_result(update, context)


async def recom_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id
    if data == "nav_exit":
        try:
            await context.bot.delete_message(chat_id, context.user_data['recom_img_id'])
            await query.delete_message()
        except Exception:
            await query.edit_message_reply_markup(reply_markup=None)
        return await start(update, context)
    elif data == "nav_back_start":
        return await start_recom(update, context)
    elif data == "nav_back_type":
        return await recom_mode_callback(update, context)
    elif data == "nav_back_genre":
        return await recom_type_callback(update, context)


warnings.filterwarnings("ignore", category=PTBUserWarning)
recom_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("recommendation", start_recom)],
    states={
        RecomStates.CHOOSING_MODE: [
            CallbackQueryHandler(recom_mode_callback, pattern='^mode_'),
            CallbackQueryHandler(recom_nav_callback, pattern='^nav_')],
        RecomStates.CHOOSING_TYPE: [
            CallbackQueryHandler(recom_type_callback, pattern='^type_'),
            CallbackQueryHandler(recom_nav_callback, pattern='^nav_')],
        RecomStates.CHOOSING_GENRE: [
            CallbackQueryHandler(recom_genre_callback, pattern='^genre_'),
            CallbackQueryHandler(recom_nav_callback, pattern='^nav_')],
        RecomStates.REMOVE_FAV: [
            CallbackQueryHandler(recom_update_favs, pattern='^del_'),
            CallbackQueryHandler(recom_nav_callback, pattern='^nav_')],
        RecomStates.WAITING_FOR_ACTION: [
            CallbackQueryHandler(recom_action_callback, pattern='^act_'),
            CallbackQueryHandler(recom_nav_callback, pattern='^nav_')],
    },
    fallbacks = [CommandHandler("cancel", cancel)],
    per_chat=True,
    per_user=True,
    per_message=False,
    allow_reentry = True
)

