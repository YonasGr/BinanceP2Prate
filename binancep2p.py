import requests
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, InlineQueryHandler

BOT_TOKEN = '7640687485:AAEh8tI6GhuJ9_MgYsjUIcCLQG-ILD9I3_Q'
ADMIN_USER_ID = 898505692  # Replace this with your actual Telegram user ID

# Store user IDs who have started the bot
user_ids = set()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_ids.add(update.message.from_user.id)  # Add the user to the list of users
    introduction_text = """
    👋 *Welcome to the Binance P2P Price Bot!*

    My name is *Yonas*, and I created this bot to provide real-time P2P price updates for Binance in Ethiopian Birr (ETB).

    🔹 You can use the following commands:
    - `/price [amount]`: Get the latest buy and sell price for the specified amount in ETB.
    
    This bot is designed to help you find the best offers on Binance P2P, whether you are buying or selling cryptocurrency.

    📊 I use the Binance API to fetch real-time offers and show you the best rates within your specified limits.

    If you have any questions or need further assistance, feel free to reach out!

    Let's get started! 👇
    contact me here:- @Yoniprof
    """

    await update.message.reply_text(introduction_text, parse_mode='Markdown')

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

# Inline query handler
async def inline_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query  # This gets the text the user typed
    if not query:  # If no query, just return an empty list
        return

    try:
        amount = float(query)
    except ValueError:
        await update.inline_query.answer([], switch_pm_text="Please type a valid amount.", switch_pm_parameter="start")
        return

    buy_info = fetch_p2p_price(trade_type="BUY", amount=amount)
    sell_info = fetch_p2p_price(trade_type="SELL", amount=amount)

    if buy_info == "No offer found for your amount." and sell_info == "No offer found for your amount.":
        results = [
            InlineQueryResultArticle(
                id='1',
                title="No results",
                input_message_content=InputTextMessageContent("Sorry, no offers found for this amount."),
            )
        ]
    else:
        results = [
            InlineQueryResultArticle(
                id='1',
                title="P2P Price",
                input_message_content=InputTextMessageContent(
                    f"💵 *Binance P2P (ETB)* for *{amount} ETB*:\n\n"
                    f"🔵 *Buy* Price: `{buy_info}`\n"
                    f"🟠 *Sell* Price: `{sell_info}`\n"
                ),
            )
        ]

    await update.inline_query.answer(results)

# Admin panel command
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if the user is the admin
    if update.message.from_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ You are not authorized to access the admin panel.")
        return

    # Generate stats and admin options
    stats_text = f"📊 *Bot Stats:*\n"
    stats_text += f"Total users who have interacted with the bot: {len(user_ids)}\n"

    admin_text = """
    🛠 *Admin Panel*:
    - `/stats`: View bot statistics
    - `/send_message [message]`: Send a message to all users
    """

    await update.message.reply_text(stats_text + admin_text, parse_mode='Markdown')

# Send a message to all users
async def send_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ You are not authorized to send messages to all users.")
        return

    if len(context.args) < 1:
        await update.message.reply_text("⚠️ Please provide the message to send.\nExample: `/send_message Hello, this is an update!`")
        return

    message = ' '.join(context.args)
    for user_id in user_ids:
        try:
            await context.bot.send_message(user_id, message)
        except Exception as e:
            print(f"Failed to send message to {user_id}: {e}")

    await update.message.reply_text(f"✅ Message sent to {len(user_ids)} users.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add handlers for /start, /price, /admin, /send_message, and inline queries
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('price', get_price))
    app.add_handler(CommandHandler('admin', admin))
    app.add_handler(CommandHandler('send_message', send_message))
    app.add_handler(InlineQueryHandler(inline_price))

    print("Bot is running...")
    app.run_polling()
