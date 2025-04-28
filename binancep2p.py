import asyncio
from datetime import datetime
from typing import Optional, Dict
import sqlite3
import aiohttp
import re
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
    InlineQueryHandler
)

# Configuration
BOT_TOKEN = '7640687485:AAEh8tI6GhuJ9_MgYsjUIcCLQG-ILD9I3_Q'
ADMIN_IDS = [898505692]
DATABASE_NAME = 'bot_users.db'
FIAT_CURRENCIES = ['ETB', 'USD', 'EUR', 'GBP']
CRYPTO_CURRENCIES = ['USDT', 'BTC', 'ETH', 'TON', 'BNB', 'SOL']

# Initialize database
def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            last_interaction TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rates (
            currency_pair TEXT PRIMARY KEY,
            rate REAL,
            last_updated TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Rate Providers
class RateProviders:
    @staticmethod
    async def get_binance_p2p_rate(fiat: str, crypto: str, trade_type: str, amount: float):
        url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
        payload = {
            "page": 1,
            "rows": 10,
            "asset": crypto,
            "fiat": fiat,
            "tradeType": trade_type,
            "transAmount": str(amount)
        }
        headers = {'Content-Type': 'application/json'}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                data = await response.json()
                for offer in data.get('data', []):
                    try:
                        adv = offer.get('adv', {})
                        price = float(adv.get('price', 0))
                        return price
                    except (ValueError, AttributeError):
                        continue
                return None

    @staticmethod
    async def get_crypto_rate(base: str, target: str):
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={base}{target}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return float(data['price'])
                return None

    @staticmethod
    async def get_bank_rate(fiat_from: str, fiat_to: str):
        # This would be replaced with actual bank API calls
        # Mock rates for demonstration
        rates = {
            'USDETB': 56.5,
            'EURETB': 61.2,
            'GBPETB': 71.8
        }
        return rates.get(f"{fiat_from}{fiat_to}", None)

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌟 Welcome to CryptoRateBot!\n\n"
        "Available commands:\n"
        "/rate [amount][currency] - Get exchange rates\n"
        "/convert [amount][from] to [to] - Convert between currencies\n"
        "/bankrate [from] [to] - Get bank exchange rates\n\n"
        "Examples:\n"
        "`/rate 5000 ETB`\n"
        "`/rate 100 USDT`\n"
        "`/convert 50 USD to ETB`\n"
        "`/bankrate USD ETB`",
        parse_mode='Markdown'
    )

async def handle_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = ' '.join(context.args) if context.args else ''
        if not query:
            raise ValueError("Please specify amount and currency")
        
        # Parse input (e.g., "5000 ETB" or "100 USDT")
        match = re.match(r'^(\d+\.?\d*)\s*([a-zA-Z]+)?$', query)
        if not match:
            raise ValueError("Invalid format. Use: /rate [amount][currency]")
        
        amount = float(match.group(1))
        currency = (match.group(2) or 'ETB').upper()
        
        if currency in FIAT_CURRENCIES:
            # Fiat currency (get crypto rates)
            usdt_price = await RateProviders.get_binance_p2p_rate(currency, 'USDT', 'BUY', amount)
            btc_price = await RateProviders.get_crypto_rate('BTC', currency)
            
            response = f"💱 Exchange Rates for {amount} {currency}:\n\n"
            response += f"🔹 USDT: {usdt_price:.2f} {currency}\n" if usdt_price else ""
            response += f"🔹 BTC: {btc_price:.2f} {currency}\n" if btc_price else ""
            
        elif currency in CRYPTO_CURRENCIES:
            # Crypto currency (get fiat rates)
            usd_price = await RateProviders.get_crypto_rate(currency, 'USDT')
            etb_price = await RateProviders.get_binance_p2p_rate('ETB', currency, 'SELL', amount)
            
            response = f"💱 Exchange Rates for {amount} {currency}:\n\n"
            response += f"🔹 USD: {usd_price * amount:.2f}\n" if usd_price else ""
            response += f"🔹 ETB: {etb_price * amount:.2f}\n" if etb_price else ""
            
        else:
            raise ValueError(f"Unsupported currency: {currency}")
        
        response += "\n🔄 Last updated: " + datetime.now().strftime("%H:%M:%S")
        await update.message.reply_text(response)
        
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)}")

async def handle_convert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = ' '.join(context.args) if context.args else ''
        if not query:
            raise ValueError("Please specify conversion parameters")
        
        # Parse input (e.g., "100 USD to ETB")
        match = re.match(r'^(\d+\.?\d*)\s*([a-zA-Z]+)\s+to\s+([a-zA-Z]+)$', query, re.IGNORECASE)
        if not match:
            raise ValueError("Invalid format. Use: /convert [amount][from] to [to]")
        
        amount = float(match.group(1))
        from_curr = match.group(2).upper()
        to_curr = match.group(3).upper()
        
        # Determine conversion path
        if from_curr in CRYPTO_CURRENCIES and to_curr in CRYPTO_CURRENCIES:
            # Crypto to crypto
            rate = await RateProviders.get_crypto_rate(from_curr, to_curr)
            result = amount * rate
        elif from_curr in FIAT_CURRENCIES and to_curr in FIAT_CURRENCIES:
            # Fiat to fiat (bank rate)
            rate = await RateProviders.get_bank_rate(from_curr, to_curr)
            result = amount * rate
        elif from_curr in CRYPTO_CURRENCIES and to_curr in FIAT_CURRENCIES:
            # Crypto to fiat
            if to_curr == 'ETB':
                rate = await RateProviders.get_binance_p2p_rate(to_curr, from_curr, 'SELL', amount)
                result = amount * rate
            else:
                usd_rate = await RateProviders.get_crypto_rate(from_curr, 'USDT')
                result = amount * usd_rate
        elif from_curr in FIAT_CURRENCIES and to_curr in CRYPTO_CURRENCIES:
            # Fiat to crypto
            if from_curr == 'ETB':
                rate = await RateProviders.get_binance_p2p_rate(from_curr, to_curr, 'BUY', amount)
                result = amount / rate
            else:
                usd_rate = await RateProviders.get_crypto_rate(to_curr, 'USDT')
                result = amount / usd_rate
        else:
            raise ValueError("Unsupported currency pair")
        
        if not rate:
            raise ValueError("Could not fetch conversion rate")
            
        response = (f"🔁 Conversion: {amount} {from_curr} = {result:.2f} {to_curr}\n"
                   f"📊 Rate: 1 {from_curr} = {rate:.6f} {to_curr}\n"
                   f"🔄 Last updated: {datetime.now().strftime('%H:%M:%S')}")
        
        await update.message.reply_text(response)
        
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)}")

async def handle_bank_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) != 2:
            raise ValueError("Please specify two currencies (e.g., /bankrate USD ETB)")
        
        from_curr = context.args[0].upper()
        to_curr = context.args[1].upper()
        
        if from_curr not in FIAT_CURRENCIES or to_curr not in FIAT_CURRENCIES:
            raise ValueError("Bank rates only available for fiat currencies")
        
        rate = await RateProviders.get_bank_rate(from_curr, to_curr)
        if not rate:
            raise ValueError("Could not fetch bank rate")
            
        response = (f"🏦 Bank Exchange Rate:\n"
                   f"1 {from_curr} = {rate:.2f} {to_curr}\n"
                   f"🔄 Last updated: {datetime.now().strftime('%H:%M:%S')}")
        
        await update.message.reply_text(response)
        
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)}")

# Main Application
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('rate', handle_rate))
    app.add_handler(CommandHandler('convert', handle_convert))
    app.add_handler(CommandHandler('bankrate', handle_bank_rate))

    print("Bot is running...")
    app.run_polling()
