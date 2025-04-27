import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = '7640687485:AAEh8tI6GhuJ9_MgYsjUIcCLQG-ILD9I3_Q'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome!\n\nUse:\n/price [amount]\nExample: `/price 5000`\n\nThis will show P2P Buy/Sell rates in ETB for your limit.", parse_mode='Markdown'
    )

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("⚠️ Please provide the amount.\nExample: `/price 5000`", parse_mode='Markdown')
        return

    try:
        amount = float(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Invalid amount. Example: `/price 5000`", parse_mode='Markdown')
        return

    buy_info = fetch_p2p_price(trade_type="BUY", amount=amount)
    sell_info = fetch_p2p_price(trade_type="SELL", amount=amount)

    response = f"💵 *Binance P2P (ETB)* for *{amount} ETB*:\n\n"
    response += f"🔵 *Buy* Price: `{buy_info}`\n"
    response += f"🟠 *Sell* Price: `{sell_info}`\n"

    await update.message.reply_text(response, parse_mode='Markdown')

def fetch_p2p_price(trade_type, amount):
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    payload = {
        "page": 1,
        "rows": 20,  # Increase to fetch more offers
        "payTypes": [],
        "asset": "USDT",
        "fiat": "ETB",
        "tradeType": trade_type
    }
    headers = {'Content-Type': 'application/json'}

    response = requests.post(url, json=payload, headers=headers)
    data = response.json()

    # Debugging - Print the raw response from Binance
    print("Binance API Response:", data)

    offers_found = []
    
    for offer in data['data']:
        min_limit = float(offer['adv']['minSingleTransAmount'])
        max_limit = float(offer['adv']['maxSingleTransAmount'])

        # Debugging - Check the limits for each offer
        print(f"Offer Limits: {min_limit} <= {amount} <= {max_limit}")

        if min_limit <= amount <= max_limit:
            price = offer['adv']['price']
            offers_found.append(f"{price} ETB (Limits: {min_limit} - {max_limit})")

    if not offers_found:
        return "No offer found for your amount."
    
    return '\n'.join(offers_found)

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('price', get_price))

    print("Bot is running...")
    app.run_polling()
