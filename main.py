from aiogram import Bot, Dispatcher, types, executor
from steam.guard import SteamAuthenticator
import base64
import sqlite3
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

bot = Bot(token='')
class AddAccountState(StatesGroup):
    waiting_for_login = State()
    waiting_for_shared_secret = State()

storage = MemoryStorage()
dp = Dispatcher(bot, storage=MemoryStorage())

authenticator = SteamAuthenticator()

conn = sqlite3.connect('accounts.db')
c = conn.cursor()

c.execute('''
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        steam_login TEXT,
        shared_secret TEXT
    )
''')
conn.commit()


@dp.message_handler(commands=['code'])
async def generate_code(message: types.Message):
    keyboard = types.InlineKeyboardMarkup()
    accounts = get_all_accounts()
    for account in accounts:
        keyboard.add(types.InlineKeyboardButton(text=account[1], callback_data=str(account[0])))

    await message.answer('Choose an account:', reply_markup=keyboard)


@dp.callback_query_handler(lambda callback_query: True)
async def handle_account_selection(callback_query: types.CallbackQuery):
    selected_account_id = int(callback_query.data)
    account = get_account_by_id(selected_account_id)

    code = generate_auth_code(account[2])

    await bot.send_message(callback_query.from_user.id, f"Steam Guard Code for {account[1]}: {code}")


@dp.message_handler(commands=['add_account'])
async def add_account(message: types.Message):
    await message.answer('Enter Steam login:')
    await AddAccountState.waiting_for_login.set()


@dp.message_handler(state=AddAccountState.waiting_for_login)
async def process_login(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['login'] = message.text

    await message.answer('Enter shared secret:')
    await AddAccountState.waiting_for_shared_secret.set()


@dp.message_handler(state=AddAccountState.waiting_for_shared_secret)
async def process_shared_secret(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['shared_secret'] = message.text
        add_account_to_database(data['login'], data['shared_secret'])

    await message.answer('Account added successfully!')

    await state.finish()


def add_account_to_database(steam_login: str, shared_secret: str):
    encoded_shared_secret = base64.b64encode(shared_secret.encode()).decode()

    c.execute("INSERT INTO accounts (steam_login, shared_secret) VALUES (?, ?)",
              (steam_login, encoded_shared_secret))
    conn.commit()


def get_all_accounts():
    c.execute("SELECT * FROM accounts")
    return c.fetchall()


def get_account_by_id(account_id: int):
    c.execute("SELECT * FROM accounts WHERE id=?", (account_id,))
    return c.fetchone()


def generate_auth_code(shared_secret: str):
    shared_secret = base64.b64decode(shared_secret.encode()).decode()
    return authenticator.get_code(shared_secret)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)