import asyncio
from datetime import datetime
from typing import Optional
import sqlite3
import aiohttp
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

BOT_TOKEN = '7640687485:AAEh8tI6GhuJ9_MgYsjUIcCLQG-ILD9I3_Q'
ADMIN_IDS = [898505692 ]  # Replace with your Telegram user ID
DATABASE_NAME = 'bot_users.db'

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
    conn.commit()
    conn.close()

init_db()

async def track_user(update: Update):
    user = update.effective_user
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users 
        (user_id, username, first_name, last_name, last_interaction) 
        VALUES (?, ?, ?, ?, ?)
    ''', (user.id, user.username, user.first_name, user.last_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await track_user(update)
    await update.message.reply_text(
        "👋 Welcome!\nUse:\n\n"
        "/price [amount] [coin] [payment_method]\n"
        "Example:\n"
        "`/price 5000 USDT`\n"
        "`/price 10000 BTC Telebirr`\n",
        parse_mode='Markdown'
    )

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("⚠️ Usage: `/price [amount] [currency/payment method] [coin]`", parse_mode='Markdown')
        return

    try:
        amount = float(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Amount must be a number!", parse_mode='Markdown')
        return
    
    if len(args) >= 2:
        second_word = args[1].lower()
    else:
        second_word = "etb"

    # Default values
    coin = "USDT"
    pay_type = None
    treating_as = "etb"  # or 'usdt'

    if second_word == "etb":
        treating_as = "etb"
    elif second_word == "usdt":
        treating_as = "usdt"
    else:
        # Maybe second word is payment method or coin
        if second_word.upper() in ["BTC", "ETH", "BNB", "USDT"]:
            coin = second_word.upper()
        else:
            pay_type = second_word

    # Check if there’s a third argument
    if len(args) >= 3:
        third_word = args[2]
        if third_word.upper() in ["BTC", "ETH", "BNB", "USDT"]:
            coin = third_word.upper()
        else:
            pay_type = third_word

    if treating_as == "etb":
        # Amount is ETB, fetch by ETB limits
        buy_info = await fetch_p2p_price(trade_type="BUY", amount=amount, asset=coin, pay_type=pay_type)
        sell_info = await fetch_p2p_price(trade_type="SELL", amount=amount, asset=coin, pay_type=pay_type)

        response = f"💵 *{coin} Binance P2P (ETB)* for *{amount} ETB*\n\n"
        response += f"🔵 *Buy*: `{buy_info}`\n"
        response += f"🟠 *Sell*: `{sell_info}`\n\n"
        response += "🔔 Powered by @Yoniprof"
    
    else:
        # Amount is USDT, need to calculate total ETB
        buy_price = await fetch_first_price(trade_type="BUY", asset=coin, pay_type=pay_type)
        sell_price = await fetch_first_price(trade_type="SELL", asset=coin, pay_type=pay_type)

        if buy_price is None or sell_price is None:
            await update.message.reply_text("⚠️ No offers available right now.", parse_mode='Markdown')
            return

        total_buy_etb = amount * float(buy_price)
        total_sell_etb = amount * float(sell_price)

        response = f"💵 *{amount} {coin}* Binance P2P Estimated in ETB\n\n"
        response += f"🔵 *Buy*: {buy_price} ETB\n"
        response += f"🟠 *Sell*: {sell_price} ETB\n\n"
        response += f"💰 *Total to pay for {amount} {coin}*: {total_buy_etb:.2f} ETB\n"
        response += f"💵 *Total to get if selling {amount} {coin}*: {total_sell_etb:.2f} ETB\n\n"
        response += "🔔 Powered by @Yoniprof"

    keyboard = [
        [InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh|{amount}|{coin}|{pay_type or 'none'}|{treating_as}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_markup)

async def fetch_first_price(trade_type, asset="USDT", pay_type=None):
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    payload = {
        "page": 1,
        "rows": 1,
        "payTypes": [pay_type] if pay_type else [],
        "asset": asset,
        "fiat": "ETB",
        "tradeType": trade_type
    }
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        data = response.json()
        offer = data['data'][0]
        price = offer['adv']['price']
        return price
    except Exception as e:
        return None

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await track_user(update)
    query = update.callback_query
    await query.answer()

    data = query.data.split('|')
    if len(data) != 4:
        await query.edit_message_text("⚠️ Invalid refresh request")
        return

    try:
        amount = float(data[1])
        coin = data[2]
        pay_type = data[3] if data[3] != 'none' else None

        buy_info = await fetch_p2p_price(trade_type="BUY", amount=amount, asset=coin, pay_type=pay_type)
        sell_info = await fetch_p2p_price(trade_type="SELL", amount=amount, asset=coin, pay_type=pay_type)

        response = f"💵 *{coin} Binance P2P (ETB)* for *{amount} ETB*\n\n"
        response += f"🔵 *Buy*: `{buy_info}`\n"
        response += f"🟠 *Sell*: `{sell_info}`\n\n"
        response += f"🕰 Updated at {datetime.now().strftime('%H:%M:%S')}\n\n"
        response += "🔔 Powered by @Yoniprof"

        await query.edit_message_text(response, parse_mode='Markdown', reply_markup=query.message.reply_markup)
    except Exception as e:
        await query.edit_message_text(f"⚠️ Error refreshing data: {str(e)}")

async def fetch_p2p_price(trade_type: str, amount: float, asset: str = "USDT", pay_type: Optional[str] = None) -> str:
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    payload = {
        "page": 1,
        "rows": 10,
        "payTypes": [pay_type] if pay_type else [],
        "asset": asset,
        "fiat": "ETB",
        "tradeType": trade_type
    }
    headers = {'Content-Type': 'application/json'}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=5) as response:
                data = await response.json()
                
                for offer in data.get('data', []):
                    try:
                        adv = offer.get('adv', {})
                        min_limit = float(adv.get('minSingleTransAmount', 0))
                        max_limit = float(adv.get('maxSingleTransAmount', float('inf')))
                        if min_limit <= amount <= max_limit:
                            price = adv.get('price', 'N/A')
                            return f"{price} ETB (Limits: {min_limit} - {max_limit})"
                    except (ValueError, AttributeError):
                        continue
                
                return "❌ No matching offers found within your amount range."
    except asyncio.TimeoutError:
        return "⚠️ Request timeout. Please try again later."
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# Admin commands
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⚠️ You are not authorized to use this command.")
        return

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Get total users
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    # Get active users (last 30 days)
    cursor.execute("SELECT COUNT(*) FROM users WHERE last_interaction > datetime('now', '-30 days')")
    active_users = cursor.fetchone()[0]
    
    conn.close()

    await update.message.reply_text(
        f"📊 Bot Statistics:\n\n"
        f"👥 Total users: {total_users}\n"
        f"🟢 Active users (last 30 days): {active_users}\n\n"
        f"Admin commands:\n"
        f"/stats - Show bot statistics\n"
        f"/broadcast - Send message to all users\n"
        f"/export_users - Export user data as CSV"
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⚠️ You are not authorized to use this command.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Usage: /broadcast <your message>")
        return

    message = " ".join(context.args)
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    total = len(users)
    success = 0
    failed = 0

    await update.message.reply_text(f"📢 Starting broadcast to {total} users...")

    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=message)
            success += 1
        except Exception as e:
            print(f"Failed to send to {user[0]}: {str(e)}")
            failed += 1
        await asyncio.sleep(0.1)  # Rate limiting

    await update.message.reply_text(
        f"📢 Broadcast completed:\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}"
    )

async def export_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⚠️ You are not authorized to use this command.")
        return

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    conn.close()

    csv_data = "user_id,username,first_name,last_name,last_interaction\n"
    for user in users:
        csv_data += f"{user[0]},{user[1] or ''},{user[2] or ''},{user[3] or ''},{user[4]}\n"

    await update.message.reply_document(
        document=bytes(csv_data, 'utf-8'),
        filename="bot_users.csv",
        caption="📊 User data export"
    )

async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /price command in groups"""
    if update.message.text.startswith('/price'):
        # Extract command without the slash
        await get_price(update, context)


if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # User commands
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('price', get_price))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Admin commands
    app.add_handler(CommandHandler('stats', admin_stats))
    app.add_handler(CommandHandler('broadcast', broadcast))
    app.add_handler(CommandHandler('export_users', export_users))

        # Group handling
    app.add_handler(MessageHandler(
        filters.TEXT & (~filters.COMMAND) & filters.ChatType.GROUPS,
        handle_group_messages
    ))

    print("Bot is running...")
    app.run_polling()
