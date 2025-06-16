import os
import requests
from datetime import datetime, timedelta
import json
import telebot
from telebot import types
from bs4 import BeautifulSoup
import feedparser
import yfinance as yf
import openai

# Конфигурация
TELEGRAM_TOKEN = ''
RBC_RSS_URL = ''
FOREX_API = ''
CRYPTO_API = ''
STOCK_API = yf  # Yahoo Finance
FORBES_URL = ''
TELEGRAM_PREMIUM_API = ''

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_TOKEN)

NEWSAPI_KEY = ''
OPENAI_API_KEY = ''
openai.api_key = OPENAI_API_KEY

def get_finance_news_ru():
    url = 'https://newsapi.org/v2/everything'
    params = {
        'q': 'финансовый рынок OR фондовый рынок OR экономика',
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
        all_text += f"{title}. {desc} "

    if not all_text.strip():
        return "Нет данных для суммирования."

    prompt = (
        "Сделай краткую выжимку из следующих новостей на русском языке в 5 предложениях:\n\n"
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
        return f"\n📝 ВЫЖИМКА ИЗ НОВОСТЕЙ:\n {summary}"

    except Exception as e:
        return "Ошибка при вызове OpenAI:", e

# Клавиатуры
def create_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton('📈 Акции'))
    keyboard.add(types.KeyboardButton('💱 Валюты'))
    keyboard.add(types.KeyboardButton('📰 Новостная выжимка'))
    keyboard.add(types.KeyboardButton('📰 Последняя новость с Пульса'))
    keyboard.add(types.KeyboardButton('ℹ️ О боте'))
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


# Функции для получения данных
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


def get_stock_price(ticker):
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




def get_market_news():
    try:
        # Используем альтернативный RSS-источник от РБК
        rbc_url = "https://www.rbc.ru/v10/ajax/get-news-feed/project/rbcnews.uploaded/lastDate/{}/limit/10"

        # Получаем текущую дату в нужном формате
        last_date = int(datetime.now().timestamp())
        url = rbc_url.format(last_date)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(url, headers=headers)
        data = response.json()

        news_items = []
        for item in data.get('items', [])[:10]:  # Берем 10 последних новостей
            # Проверяем, что новость не старше 24 часов
            news_time = datetime.fromtimestamp(item['publish_date_t'])
            if datetime.now() - news_time < timedelta(days=1):
                news_items.append({
                    'title': item.get('title', 'Без названия'),
                    'link': item.get('link_url', 'https://www.rbc.ru'),
                    'published': news_time.strftime('%Y-%m-%d %H:%M:%S')
                })

        return news_items if news_items else None
    except Exception as e:
        print(f"Error getting RBC news: {e}")
        return None


def get_forbes_news():
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }

        response = requests.get('https://www.forbes.com/business/', headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')

        news_items = []

        # Новый селектор для Forbes 2023
        articles = soup.select('article.stream-item')[:5]

        for article in articles:
            try:
                title = article.select_one('h3').text.strip()
                link = article.find('a')['href']

                # Убедимся, что ссылка полная
                if not link.startswith('http'):
                    link = 'https://www.forbes.com' + link

                # Попробуем получить время публикации
                time_tag = article.find('time')
                pub_time = time_tag['datetime'] if time_tag else 'Недавно'

                news_items.append({
                    'title': title,
                    'link': link,
                    'published': pub_time
                })
            except Exception as e:
                print(f"Error parsing Forbes article: {e}")
                continue

        return news_items if news_items else None
    except Exception as e:
        print(f"Error getting Forbes news: {e}")
        return None


@bot.message_handler(func=lambda message: message.text == '📰 Новости рынка')
def show_market_news(message):
    try:
        news = get_finance_news_ru()
        forbes_news = get_forbes_news()

        if not news and not forbes_news:
            bot.send_message(message.chat.id, "Не удалось загрузить новости. Попробуйте позже.")
            return

        response = "<b>📰 Последние финансовые новости</b>\n\n"+get_finance_news_ru()

        # Разбиваем сообщение, если оно слишком длинное
        if len(response) > 4000:
            part1 = response[:4000]
            part2 = response[4000:]
            bot.send_message(message.chat.id, part1, parse_mode='HTML', disable_web_page_preview=True)
            bot.send_message(message.chat.id, part2, parse_mode='HTML', disable_web_page_preview=True)
        else:
            bot.send_message(message.chat.id, response, parse_mode='HTML', disable_web_page_preview=True)

    except Exception as e:
        print(f"Error in show_market_news: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при получении новостей. Попробуйте позже.")


def get_forbes_news():
    try:
        response = requests.get(FORBES_URL, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.text, 'html.parser')

        news_items = []
        articles = soup.find_all('article', limit=5)

        for article in articles:
            title = article.find('h3').text.strip()
            link = article.find('a')['href']
            if not link.startswith('http'):
                link = 'https://www.forbes.com' + link
            news_items.append({'title': title, 'link': link})

        return news_items if news_items else None
    except Exception as e:
        print(f"Error getting Forbes news: {e}")
        return None


def get_tinkoff_pulse_news():
    try:
        # URL API, которое использует мобильное приложение Тинькофф
        url = "https://api.tinkoff.ru/v1/news_feed"

        # Параметры запроса для получения последних новостей
        params = {
            'category': 'all',
            'count': 1,  # Получаем только последнюю новость
            'sessionId': 'anonymous',  # Анонимный доступ
            'appName': 'invest',
            'appVersion': '6.24.0',
            'platform': 'web'
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Origin': 'https://www.tinkoff.ru',
            'Referer': 'https://www.tinkoff.ru/invest/social/'
        }

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        # Извлекаем последнюю новость
        if data.get('payload') and data['payload'].get('news') and len(data['payload']['news']) > 0:
            news_item = data['payload']['news'][0]

            # Форматируем время публикации
            publish_time = datetime.fromtimestamp(news_item['publishDate'] / 1000).strftime('%d.%m.%Y %H:%M')

            return {
                'title': news_item.get('title', 'Без названия'),
                'text': news_item.get('text', ''),
                'author': news_item.get('author', {}).get('name', 'Аноним'),
                'time': publish_time,
                'link': f"https://www.tinkoff.ru/invest/social/profile/{news_item['author']['id']}/post/{news_item['id']}/",
                'source': 'Тинькофф Пульс'
            }

        return None

    except Exception as e:
        print(f"Ошибка при получении новостей: {str(e)}")
        return None


@bot.message_handler(func=lambda message: message.text == '📰 Последняя новость с Пульса')
def send_tinkoff_news(message):
    news = get_tinkoff_pulse_news()

    if news:
        # Формируем красивое сообщение
        response = (
            f"<b>📰 {news['title']}</b>\n\n"
            f"{news['text']}\n\n"
            f"👤 <b>Автор:</b> {news['author']}\n"
            f"🕒 <b>Опубликовано:</b> {news['time']}\n"
            f"🔗 <a href='{news['link']}'>Читать на Пульсе</a>"
        )

        # Отправляем сообщение с поддержкой HTML-разметки
        bot.send_message(
            message.chat.id,
            response,
            parse_mode='HTML',
            disable_web_page_preview=False
        )
    else:
        bot.send_message(
            message.chat.id,
            "⚠️ Не удалось получить последнюю новость с Тинькофф Пульса.\n"
            "Попробуйте позже или проверьте доступность сервиса."
        )


# Обработчики команд
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        "📊 <b>Финансовый помощник</b>\n\n"
        "Я предоставляю актуальную информацию о:\n"
        "- Курсах валют 💱\n"
        "- Стоимости акций 📈\n"
        "- Новостная выжимка 📰\n\n"
        "Выберите интересующий вас раздел:",
        parse_mode='HTML',
        reply_markup=create_main_keyboard()
    )


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


@bot.message_handler(func=lambda message: message.text in ['🇷🇺 Российские акции', '🇺🇸 Американские акции'])
def show_stocks(message):
    if message.text == '🇷🇺 Российские акции':
        stocks = {
            'SBER': 'Сбербанк',
            'GAZP': 'Газпром',
            'LKOH': 'Лукойл',
            'YNDX': 'Яндекс',
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
    for ticker, name in stocks.items():
        price = get_stock_price(ticker)
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



@bot.message_handler(func=lambda message: message.text == '📰 Новости рынка')
def show_market_news(message):
    news = get_market_news()
    forbes_news = get_forbes_news()

    if news or forbes_news:
        response = "<b>Последние новости рынка:</b>\n\n"
        """
        response += "<u>РБК:</u>\n"
        for item in news[:5]:
            response += f"• <a href='{item['link']}'>{item['title']}</a>\n"
        """
        response += "\n<u>Forbes:</u>\n"
        for item in forbes_news[:5]:
            response += f"• <a href='{item['link']}'>{item['title']}</a>\n"

        bot.send_message(message.chat.id, response, parse_mode='HTML', disable_web_page_preview=True)
    else:
        bot.send_message(message.chat.id, "Не удалось получить новости. Попробуйте позже.")


@bot.message_handler(func=lambda message: message.text == 'ℹ️ О боте')
def about_bot(message):
    bot.send_message(
        message.chat.id,
        "🤖 <b>Финансовый помощник</b>\n\n"
        "Этот бот предоставляет актуальную финансовую информацию из проверенных источников:\n"
        "- Курсы валют с exchangerate-api.com\n"
        "- Котировки акций с Yahoo Finance\n"
        "- Новости с РБК и Forbes\n"
        "- Цены на Telegram Premium с fragment.com\n\n"
        "Данные обновляются в реальном времени.\n\n"
        "Для начала работы выберите интересующий раздел в меню.",
        parse_mode='HTML'
    )


# Запуск бота
if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()