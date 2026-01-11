from enum import Enum
import os
from dotenv import load_dotenv

from utils import get_flag

load_dotenv()

CHATGPT_TOKEN = os.getenv("CHATGPT_TOKEN")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PROXY = os.getenv("PROXY")
TRANSLATE_BUTTONS=[
        [get_flag('UA'), get_flag('GB'), get_flag('PL'), get_flag('DE'), get_flag('FR'), get_flag('ES')],
        [get_flag('IT'), get_flag('PT'), get_flag('RO'), get_flag('CZ'), get_flag('CN'), get_flag('TR'), get_flag('GE')]
]
class States(Enum):
    CHOOSING_LANGUAGE = 0
    TYPING_TEXT = 1