from enum import Enum, auto
import os
from dotenv import load_dotenv

load_dotenv()

def get_flag(country_code):
    offset = 127397
    return "".join(chr(ord(char.upper()) + offset) for char in country_code)

CHATGPT_TOKEN = os.getenv("CHATGPT_TOKEN")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PROXY = os.getenv("PROXY")
TRAN_BUTTONS=[
    [get_flag('UA'), get_flag('GB'), get_flag('PL'), get_flag('DE'), get_flag('FR'), get_flag('ES')],
    [get_flag('IT'), get_flag('PT'), get_flag('RO'), get_flag('CZ'), get_flag('CN'), get_flag('TR'), get_flag('GE')],
    ['Закінчити']
]
RECOM_TYPES = {
        'Фільми': 'films',
        'Книги': 'books',
        'Музика': 'music'
    }
RECOM_START_BUTTONS = {'new': '✨ Підібрати', 'favs': '💾 Збережені'}
RECOM_TYPES_BUTTONS = {
    'Фільми': '🎬 Фільми',
    'Книги': '📖 Книги',
    'Музика': '🎵 Музика'
}
RECOM_GENRES_BUTTONS= {
    'Фільми': [
        ["Бойовик", "Комедія","Драма"],
        ["Фентезі", "Жахи", "Детектив"],
        ["Мелодрама", "Наукова фантастика"],
        ["Трилер", "Вестерн", "Пригоди"],
        ["Анімація", "Документальний"]
    ],
    'Музика': [
        ["Поп-музика", "Хіп-хоп/Реп","Афробіт"],
        ["Рок","R&B","Кантрі","K-pop","Гіперпоп"],
        ["Електронна танцювальна музика"],
        ["Латиноамериканська музика","Джаз"],
        ["Інді/Альтернатива","Класична музика"]
    ],
    'Книги': [
        ["Детектив","Трилер","Фентезі"],
        ["Романтезі","Любовний роман"],
        ["Психологія та саморозвиток"],
        ["Наукова фантастика","Жахи"],
        ["Історичний роман","Біографія"],
        ["Young Adult","Темна академія"],
        ["Сучасна проза"]
    ]
}
RECOM_NAV_BUTTONS = ["🔄 Змінити категорію", "🔄 Змінити жанр", "❌ Закінчити"]

class TranStates(Enum):
    CHOOSING_LANGUAGE = auto()
    TYPING_TEXT = auto()

class RecomStates(Enum):
    CHOOSING_MODE = auto() #recom_mode_callback
    CHOOSING_TYPE = auto() #recom_type_callback
    CHOOSING_GENRE = auto() #recom_genre_callback
    REMOVE_FAV = auto() #recom_remove_fav
    WAITING_FOR_ACTION = auto() #recom_action_callback

