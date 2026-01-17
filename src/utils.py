import os
import re
import pycountry

from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram import (Update, BotCommand, BotCommandScopeChat, MenuButtonCommands, InlineKeyboardButton,
                      InlineKeyboardMarkup)

from config import RECOM_TYPES_BUTTONS, RECOM_GENRES_BUTTONS, RECOM_TYPES
from db import get_quantity, get_black_list


def load_message(name: str) -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    message_path = os.path.join(current_dir, 'resources', 'messages', f'{name}.txt')
    with open(message_path, "r", encoding="utf-8") as file:
        return file.read()


async def send_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None):
    text = text.encode('utf8').decode('utf8')
    return await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )


async def send_image(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    image_path = os.path.join(current_dir, 'resources', 'images', f'{name}.jpg')
    with open(image_path, 'rb') as image:
        return await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=image
        )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, commands: dict):
    command_list = [
        BotCommand(command=key, description=value)
        for key, value in commands.items()
    ]
    await context.bot.set_my_commands(
        command_list,
        scope=BotCommandScopeChat(chat_id=update.effective_chat.id)
    )
    await context.bot.set_chat_menu_button(
        menu_button=MenuButtonCommands(),
        chat_id=update.effective_chat.id
    )


def load_prompt(name: str):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(current_dir, 'resources', 'prompts', f'{name}.txt')
    with open(prompt_path, "r", encoding="utf-8") as file:
        return file.read()


async def send_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, buttons: dict):
    text = text.encode('utf8', errors='surrogatepass').decode('utf8')
    keyboard = []
    for key, value in buttons.items():
        button = InlineKeyboardButton(str(value), callback_data=str(key))
        keyboard.append([button])
    reply_markup = InlineKeyboardMarkup(keyboard)
    return await context.bot.send_message(
        chat_id=update.effective_message.chat_id,
        text=text,
        reply_markup=reply_markup,
        message_thread_id=update.effective_message.message_thread_id
    )


def get_alpha2(emoji):

    return ''.join(chr(ord(c) - 127397) for c in emoji)


async def translator(service, text, lang, flag):
    result = await service.add_message(
        message_text=f"Переклади наступний текст на {lang}. Поверни ТІЛЬКИ переклад без зайвих пояснень:\n{text}"
    )
    result = f"✅ {lang} {flag}:\n\n{result}"
    return result


def get_country_name(code):
    try:
        country = pycountry.countries.get(alpha_2=get_alpha2(code))
        return country.name
    except AttributeError:
        return "<Невідома країна>"


async def get_type_inline_keyboard(user_id, mode, favs=False):
    buttons = []
    for db_name, label in RECOM_TYPES_BUTTONS.items():
        count = await get_quantity(user_id, db_name)
        if mode == 'favs' and count == 0:
            continue
        display_text = f"{label} ({count})" if mode == 'favs' else label
        buttons.append([InlineKeyboardButton(display_text, callback_data=f"type_{db_name}")])
    if mode == 'favs' or favs:
        buttons.extend(get_nav_buttons("type"))
    else:
        buttons.extend(get_nav_buttons("exit"))
    return InlineKeyboardMarkup(buttons)


async def get_genre_inline_keyboard(user_id, item_type, mode):
    buttons = []
    for row in RECOM_GENRES_BUTTONS[item_type]:
        for genre in row:
            count = await get_quantity(user_id, item_type, genre)
            if mode == 'favs' and count == 0:
                continue
            text = f"{genre} ({count})" if mode == 'favs' else genre
            buttons.append(InlineKeyboardButton(text, callback_data=f"genre_{genre}"))
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.extend(get_nav_buttons("genre"))
    return InlineKeyboardMarkup(keyboard)


async def get_favs_inline_del_keyboard(favs):
    buttons = []
    for i, label in favs.items():
        buttons.append([InlineKeyboardButton(label, callback_data=f"del_{i}")])
    buttons.extend(get_nav_buttons("result"))
    return InlineKeyboardMarkup(buttons)


async def send_favs_list(query, context, favs):
    item_type = context.user_data.get('recom_type')
    genre = context.user_data.get('recom_genre')
    type_label = RECOM_TYPES_BUTTONS.get(item_type, "")

    text = (f"💾 Збережені\n\n"
            f"{type_label} -> {genre}\n\n"
            f"⚠️ Щоб видалити, натисніть на назву...")

    reply_markup = await get_favs_inline_del_keyboard(favs)
    await query.edit_message_text(text, reply_markup=reply_markup)


def get_nav_buttons(step: str):
    btn_cancel = InlineKeyboardButton("❌ Завершити", callback_data="nav_exit")
    btn_back_type = InlineKeyboardButton("⬅️ До категорій", callback_data="nav_back_type")
    btn_back_genre = InlineKeyboardButton("⬅️ До жанрів", callback_data="nav_back_genre")
    btn_start = InlineKeyboardButton("🔄 На початок", callback_data="nav_back_start")

    if step == "exit":
        return [[btn_cancel]]
    elif step == "type":
        return [[btn_start, btn_cancel]]
    elif step == "genre":
        return [[btn_start, btn_back_type], [btn_cancel]]
    elif step == "result":
        return [[btn_back_type, btn_back_genre], [btn_start, btn_cancel]]
    return []


async def recom_gpt(service, user_id, item_type, genre):
    prompt = (load_prompt(f'recom//{RECOM_TYPES[item_type]}')).replace("genre", genre)
    black_list = await get_black_list(user_id, item_type, genre)
    message_text = "\n".join(black_list)

    max_retries = 3
    attempts = 0
    ai_recom = None
    pattern = r"^.+, .+, \d{4}$"
    while attempts < max_retries:
        attempts += 1
        try:
            result = await service.send_question(
                prompt_text=prompt,
                message_text=message_text
            )
            result = result.strip()
            if re.match(pattern, result):
                ai_recom = result
                return ai_recom
        except Exception:
            pass

    if not ai_recom:
        return ""