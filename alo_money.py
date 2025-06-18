import requests
import telebot
from telebot import types
import yfinance as yf
import openai
import sqlite3
import time
import schedule
import threading
from datetime import datetime


TELEGRAM_TOKEN = '----'
RBC_RSS_URL = 'https://rssexport.rbc.ru/rbcnews/news/30/full.rss'
FOREX_API = 'https://api.exchangerate-api.com/v4/latest/USD'
CRYPTO_API = 'https://api.coingecko.com/api/v3/simple/price'
STOCK_API = yf  # Yahoo Finance
FORBES_URL = 'https://www.forbes.com/business/'
NEWSAPI_KEY = '----'
OPENAI_API_KEY = '----'
openai.api_key = OPENAI_API_KEY


bot = telebot.TeleBot(TELEGRAM_TOKEN)


conn = sqlite3.connect('database.db', check_same_thread=False)
cursor = conn.cursor()

stocks = {
    'SBER': 'Сбербанк',
    'GAZP': 'Газпром',
    'T': 'Т-банк',
    'YDEX': 'Яндекс',
    'VTBR': 'ВТБ',
    'AAPL': 'Apple',
    'MSFT': 'Microsoft',
    'GOOGL': 'Alphabet',
    'AMZN': 'Amazon',
    'TSLA': 'Tesla'
    }

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    join_date TEXT
)
''')
conn.commit()


def create_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton('📈 Акции'))
    keyboard.add(types.KeyboardButton('💱 Валюты'))
    keyboard.add(types.KeyboardButton('📰 Новостная выжимка'))
    keyboard.add(types.KeyboardButton('🔍 Найти новости по тикерам'))
    keyboard.add(types.KeyboardButton('ℹ️ О боте'))
    return keyboard
def ticker_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for key in stocks.keys():
        keyboard.add(types.KeyboardButton(key))
    keyboard.add(types.KeyboardButton('🔙 Назад'))
    return keyboard


def create_stocks_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton('🇷🇺 Российские акции'))
    keyboard.add(types.KeyboardButton('🇺🇸 Американские акции'))
    keyboard.add(types.KeyboardButton('🔙 Назад'))
    return keyboard


def create_currency_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton('💵 USD/RUB'))
    keyboard.add(types.KeyboardButton('💶 EUR/RUB'))
    keyboard.add(types.KeyboardButton('💷 GBP/RUB'))
    keyboard.add(types.KeyboardButton('💴 CNY/RUB'))
    keyboard.add(types.KeyboardButton('₿ Криптовалюты'))
    keyboard.add(types.KeyboardButton('🔙 Назад'))
    return keyboard



def get_currency_rates():
    try:
        response = requests.get(FOREX_API)
        data = response.json()
        usd_rub = data['rates']['RUB']
        eur_rub = data['rates']['RUB'] / data['rates']['EUR']
        gbp_rub = data['rates']['RUB'] / data['rates']['GBP']
        cny_rub = data['rates']['RUB'] / data['rates']['CNY']

        return {
            'USD/RUB': round(usd_rub, 2),
            'EUR/RUB': round(eur_rub, 2),
            'GBP/RUB': round(gbp_rub, 2),
            'CNY/RUB': round(cny_rub, 2),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        print(f"Error getting currency rates: {e}")
        return None


def get_crypto_prices():
    try:
        params = {
            'ids': 'bitcoin,ethereum,tether,binancecoin',
            'vs_currencies': 'usd,rub'
        }
        response = requests.get(CRYPTO_API, params=params)
        data = response.json()

        result = {}
        for crypto, rates in data.items():
            result[crypto] = {
                'USD': rates['usd'],
                'RUB': rates['rub']
            }
        return result
    except Exception as e:
        print(f"Error getting crypto prices: {e}")
        return None


def get_stock_price_rus(ticker):
    url = f"https://scanner.tradingview.com/russia/scan"
    payload = {
        "filter": [{"left": "name", "operation": "equal", "right": ticker}],
        "columns": ["close"],
        "symbols": {"query": {"types": []}, "tickers": []}
    }
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://ru.tradingview.com/"}
    response = requests.post(url, json=payload, headers=headers).json()

    if response.get("data"):
        return response["data"][0]["d"][0]
    return None


def get_stock_price_eng(ticker):
    try:
        stock = STOCK_API.Ticker(ticker)
        hist = stock.history(period='1d')
        if not hist.empty:
            last_price = hist['Close'].iloc[-1]
            return last_price
        return None
    except Exception as e:
        print(f"Error getting stock price for {ticker}: {e}")
        return None

def get_cuurent_news(ticker):
    try:
        url = 'https://newsapi.org/v2/everything'
        params = {
            'q': f'{stocks[ticker]}',
            'language': 'ru',
            'sortBy': 'publishedAt',
            'pageSize': 10,
            'apiKey': NEWSAPI_KEY
        }

        response = requests.get(url, params=params)
        if response.status_code != 200:
            return f"Ошибка NewsAPI: {response.status_code} {response.text}"

        data = response.json()
        articles = data.get('articles', [])

        all_text = ""
        for article in articles:
            title = article.get('title', '')
            desc = article.get('description', '')
            if title or desc:
                all_text += f"{title}. {desc}   "

        if not all_text.strip():
            return "Нет данных для суммирования."

        prompt = (
                f"Сделай краткую выжимку из следующих новостей на русском языке, в формате дайджеста, если новость не содержит информацию о {stocks[ticker]}, то информацию о ней не следует выдавать, не выделяй текст шрифтами, не используй специальные символы и смайлики, на каждую новость оставляй ссылку, весь текст не больше 1500 символов:\n\n"
                + all_text
        )
        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Ты помогаешь делать краткие новости."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.5,
            )

            summary = response.choices[0].message.content.strip()
            return f"📝 Актуальные новости по теме {stocks[ticker]}.\n{summary}"

        except Exception as e:
            return f"Ошибка при вызове OpenAI: {str(e)}"

    except Exception as e:
        return f"Неожиданная ошибка: {str(e)}"



def get_finance_news_ru():
    try:
        url = 'https://newsapi.org/v2/everything'
        params = {
            'q': 'ценные бумаги OR фондовый рынок OR финансовые инвестиции',
            'language': 'ru',
            'sortBy': 'publishedAt',
            'pageSize': 10,
            'apiKey': NEWSAPI_KEY
        }

        response = requests.get(url, params=params)
        if response.status_code != 200:
            return f"Ошибка NewsAPI: {response.status_code} {response.text}"

        data = response.json()
        articles = data.get('articles', [])

        all_text = ""
        for article in articles:
            title = article.get('title', '')
            desc = article.get('description', '')
            if title or desc:
                all_text += f"{title}. {desc} "

        if not all_text.strip():
            return "Нет данных для суммирования."

        prompt = (
                "Сделай краткую выжимку из следующих новостей на русском языке, в формате дайджеста, не выделяй текст шрифтами, не используй специальные символы и смайлики, на каждую новость оставляй ссылку, весь текст не больше 1500 символов:\n\n"
                + all_text
        )

        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Ты помогаешь делать краткие новости."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.5,
            )

            summary = response.choices[0].message.content.strip()
            return f"📝 ВЫЖИМКА ИЗ НОВОСТЕЙ:\n\n{summary}"

        except Exception as e:
            return f"Ошибка при вызове OpenAI: {str(e)}"

    except Exception as e:
        return f"Неожиданная ошибка: {str(e)}"



@bot.message_handler(func=lambda message: message.text == '📰 Новостная выжимка')
def show_news_summary(message):
    try:
        summary = get_finance_news_ru()


        if len(summary) > 4000:
            parts = [summary[i:i + 4000] for i in range(0, len(summary), 4000)]
            for part in parts:
                bot.send_message(message.chat.id, part, parse_mode='HTML', disable_web_page_preview=True)
        else:
            bot.send_message(message.chat.id, summary, parse_mode='HTML', disable_web_page_preview=True)

    except Exception as e:
        print(f"Error in show_news_summary: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при получении новостной выжимки. Попробуйте позже.")


@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    bot.send_message(
        message.chat.id,
        "📊 <b>Финансовый помощник Alo,business?_bot</b>\n\n"
        "Я предоставляю актуальную информацию о:\n"
        "- Курсах валют 💱\n"
        "- Стоимости акций 📈\n"
        "- Актуальные новсоти компаний"
        "- Новостная выжимка 📰\n\n"
        "Выберите интересующий вас раздел:",
        parse_mode='HTML',
        reply_markup=create_main_keyboard()

    )
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, last_name, join_date)
            VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, join_date))
        conn.commit()
        bot.reply_to(message, "✅ Вы подписались на рассылку!")
    else:
        bot.reply_to(message, "❌ Вы уже подписаны.")


def send_broadcast(message_text=f"📢 Рассылка от бота!\n{get_finance_news_ru()}"):
    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    for user in users:
        try:
            bot.send_message(user[0], message_text)
        except Exception as e:
            print(f"Ошибка при отправке пользователю {user[0]}: {e}")


def scheduled_broadcast():
    while True:
        schedule.run_pending()
        time.sleep(1)



schedule.every().day.at("19:00").do(send_broadcast) #здесь меняется время


@bot.message_handler(func=lambda message: message.text == '🔙 Назад')
def back_to_main(message):
    bot.send_message(
        message.chat.id,
        "Главное меню:",
        reply_markup=create_main_keyboard()
    )


@bot.message_handler(func=lambda message: message.text == '📈 Акции')
def stocks_menu(message):
    bot.send_message(
        message.chat.id,
        "Выберите тип акций:",
        reply_markup=create_stocks_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == '🔍 Найти новости по тикерам')
def news_finder(message):
    bot.send_message(
        message.chat.id,
        "Выберите тикер акций для поиска новостей:",
        reply_markup=ticker_keyboard()
    )
@bot.message_handler(func=lambda message: message.text in stocks.keys())
def show_currency_rate(message):
    ticker = message.text
    response = get_cuurent_news(ticker)
    bot.send_message(message.chat.id, response, parse_mode='HTML')


@bot.message_handler(func=lambda message: message.text in ['🇷🇺 Российские акции', '🇺🇸 Американские акции'])
def show_stocks(message):
    if message.text == '🇷🇺 Российские акции':
        stocks = {
            'SBER': 'Сбербанк',
            'GAZP': 'Газпром',
            'T': 'Т-банк',
            'YDEX': 'Яндекс',
            'VTBR': 'ВТБ'
        }
    else:
        stocks = {
            'AAPL': 'Apple',
            'MSFT': 'Microsoft',
            'GOOGL': 'Alphabet',
            'AMZN': 'Amazon',
            'TSLA': 'Tesla'
        }

    response = f"<b>{message.text[2:]} - текущие цены:</b>\n\n"
    if message.text == '🇷🇺 Российские акции':
        for ticker, name in stocks.items():
            price = get_stock_price_rus(ticker)
            if price:
                response += f"{name} ({ticker}): <b>{price:.2f} ₽</b>\n"
            else:
                response += f"{name} ({ticker}): данные недоступны\n"
    else:
        for ticker, name in stocks.items():
            price = get_stock_price_eng(ticker)
            if price:
                response += f"{name} ({ticker}): <b>{price:.2f} $</b>\n"
            else:
                response += f"{name} ({ticker}): данные недоступны\n"

    response += "\nДанные могут задерживаться на 15-20 минут."
    bot.send_message(message.chat.id, response, parse_mode='HTML')


@bot.message_handler(func=lambda message: message.text == '💱 Валюты')
def currency_menu(message):
    bot.send_message(
        message.chat.id,
        "Выберите валютную пару:",
        reply_markup=create_currency_keyboard()
    )


@bot.message_handler(func=lambda message: message.text in ['💵 USD/RUB', '💶 EUR/RUB', '💷 GBP/RUB', '💴 CNY/RUB'])
def show_currency_rate(message):
    pair = message.text[2:]
    rates = get_currency_rates()

    if rates:
        rate = rates.get(pair)
        if rate:
            response = f"<b>Курс {pair}</b>\n\n" \
                       f"1 {pair.split('/')[0]} = <b>{rate}</b> {pair.split('/')[1]}\n\n" \
                       f"<i>Обновлено: {rates['timestamp']}</i>"
            bot.send_message(message.chat.id, response, parse_mode='HTML')
        else:
            bot.send_message(message.chat.id, "Не удалось получить данные по этой валютной паре.")
    else:
        bot.send_message(message.chat.id, "В данный момент курсы валют недоступны. Попробуйте позже.")


@bot.message_handler(func=lambda message: message.text == '₿ Криптовалюты')
def show_crypto_prices(message):
    prices = get_crypto_prices()

    if prices:
        response = "<b>Курсы криптовалют:</b>\n\n"
        for crypto, rates in prices.items():
            response += f"<b>{crypto.capitalize()}</b>\n" \
                        f"USD: {rates['USD']:.2f} $\n" \
                        f"RUB: {rates['RUB']:.2f} ₽\n\n"

        response += f"<i>Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
        bot.send_message(message.chat.id, response, parse_mode='HTML')
    else:
        bot.send_message(message.chat.id, "Не удалось получить данные о криптовалютах.")



@bot.message_handler(func=lambda message: message.text == 'ℹ️ О боте')
def about_bot(message):
    bot.send_message(
        message.chat.id,
        "🤖 <b>Alo,business?_bot</b>\n\n"
        "Этот бот предоставляет актуальную финансовую информацию из проверенных источников:\n"
        "- Курсы валют \n"
        "- Котировки акций \n"
        "- Новостная выжимка\n"
        "- Новости из мира акций по тикерам \n"
        "Данные обновляются в реальном времени.\n\n"
        "Для начала работы выберите интересующий раздел в меню.",
        parse_mode='HTML'
    )


if __name__ == '__main__':
    print("Бот запущен...")
    threading.Thread(target=scheduled_broadcast).start()
    bot.infinity_polling()