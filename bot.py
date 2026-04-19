"""
========================================
EARNHUB - TELEGRAM BOT
========================================

Telegram bot for EarnHub platform
- User registration
- Main menu with earning options
- Web app integration
- Balance and withdraw info
- Referral management

Setup:
1. Create bot with @BotFather
2. Set webhook to your server
3. pip install python-telegram-bot

Environment Variables:
TELEGRAM_BOT_TOKEN=your_token
BOT_USERNAME=your_bot_username
WEB_APP_URL=https://yourdomain.com
API_BASE_URL=https://api.yourdomain.com
"""

import os
import logging
from datetime import datetime
import requests
import json

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, ContextTypes, CommandHandler,
    MessageHandler, filters, CallbackQueryHandler,
    ConversationHandler
)
from telegram.error import TelegramError

# ========================================
# CONFIGURATION
# ========================================

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN')
WEB_APP_URL = os.getenv('WEB_APP_URL', 'https://earnhub.example.com')
API_BASE_URL = os.getenv('API_BASE_URL', 'https://api.earnhub.example.com')
BOT_USERNAME = os.getenv('BOT_USERNAME', 'earnhub_bot')

# Conversation states
MAIN_MENU, WITHDRAW_AMOUNT, WITHDRAW_METHOD, WITHDRAW_ACCOUNT = range(4)

# ========================================
# START & REGISTRATION
# ========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    user = update.effective_user
    user_id = f'tg_{user.id}'
    
    # Get referral code if provided
    referral_code = None
    if context.args:
        referral_code = context.args[0]
    
    try:
        # Register or login user
        registration_data = {
            'id': user_id,
            'name': user.first_name or 'Telegram User',
            'provider': 'telegram',
            'referredBy': referral_code
        }
        
        response = requests.post(
            f'{API_BASE_URL}/api/user/register',
            json=registration_data,
            timeout=5
        )
        
        if response.status_code in [200, 201]:
            user_data = response.json().get('user', {})
            
            welcome_text = f"""
🎉 Welcome to **EarnHub** {user.first_name}!

You're all set to start earning. Here's what you can do:

✅ **Watch Videos** - Earn 5 points per video
✅ **Click Ads** - Earn 3 points per click
✅ **Install Apps** - Earn 20 points per app
✅ **Join Channels** - Earn 10 points per join
👥 **Refer Friends** - Earn 20 points per referral

Your Referral Code: `{user_data.get('referralCode', 'N/A')}`

Use the menu below to get started!
            """
            
            await show_main_menu(update, context, welcome_text)
        else:
            error_text = response.json().get('message', 'Registration failed')
            await update.message.reply_text(
                f'❌ Error: {error_text}',
                parse_mode='Markdown'
            )
    
    except requests.RequestException as e:
        logger.error(f'API request error: {e}')
        await update.message.reply_text(
            '❌ Connection error. Please try again later.',
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f'Start command error: {e}')
        await update.message.reply_text(
            '❌ An error occurred. Please try again.',
            parse_mode='Markdown'
        )

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, welcome_text: str = None) -> int:
    """Show main menu with options"""
    
    text = welcome_text or """
🏠 **EarnHub Menu**

Choose an option below to get started!
    """
    
    # Web App button
    web_app = WebAppInfo(url=WEB_APP_URL)
    
    keyboard = [
        [InlineKeyboardButton("🎬 Open Web App", web_app=web_app)],
        [
            InlineKeyboardButton("💰 Balance", callback_data='check_balance'),
            InlineKeyboardButton("📤 Withdraw", callback_data='start_withdraw')
        ],
        [
            InlineKeyboardButton("👥 Referral", callback_data='show_referral'),
            InlineKeyboardButton("ℹ️ Help", callback_data='show_help')
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    return MAIN_MENU

# ========================================
# CALLBACK HANDLERS
# ========================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle button clicks"""
    query = update.callback_query
    user_id = f'tg_{query.from_user.id}'
    
    await query.answer()
    
    if query.data == 'check_balance':
        return await handle_balance(update, context)
    
    elif query.data == 'start_withdraw':
        return await handle_withdraw_start(update, context)
    
    elif query.data == 'show_referral':
        return await handle_referral(update, context)
    
    elif query.data == 'show_help':
        return await handle_help(update, context)
    
    elif query.data == 'back_to_menu':
        return await show_main_menu(update, context)
    
    elif query.data.startswith('withdraw_method_'):
        method = query.data.replace('withdraw_method_', '')
        context.user_data['withdraw_method'] = method
        return await handle_withdraw_account(update, context)

async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show user balance"""
    user_id = f'tg_{update.callback_query.from_user.id}'
    
    try:
        response = requests.get(
            f'{API_BASE_URL}/api/user/{user_id}',
            timeout=5
        )
        
        if response.status_code == 200:
            user = response.json()
            balance_text = f"""
💰 **Your Account Balance**

Balance: `₹{user.get('balance', 0)}`
Total Earned: `₹{user.get('totalEarned', 0)}`
Member Since: {user.get('createdAt', 'Unknown')[:10]}

🎯 Earn more by:
• Watching videos (+5 pts)
• Clicking ads (+3 pts)
• Installing apps (+20 pts)
• Joining channels (+10 pts)
• Referring friends (+20 pts)

Minimum withdraw: ₹100
            """
            
            keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                balance_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.callback_query.edit_message_text('❌ User not found')
    
    except Exception as e:
        logger.error(f'Balance check error: {e}')
        await update.callback_query.edit_message_text('❌ Error fetching balance')
    
    return MAIN_MENU

async def handle_withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start withdraw process"""
    user_id = f'tg_{update.callback_query.from_user.id}'
    
    try:
        response = requests.get(
            f'{API_BASE_URL}/api/user/{user_id}',
            timeout=5
        )
        
        if response.status_code == 200:
            user = response.json()
            balance = user.get('balance', 0)
            
            if balance < 100:
                await update.callback_query.edit_message_text(
                    f'❌ Minimum withdraw amount is ₹100\nYour balance: ₹{balance}',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]])
                )
                return MAIN_MENU
            
            # Ask for withdrawal method
            withdraw_text = f"""
💳 **Withdraw Money**

Your Balance: ₹{balance}

Select payment method:
            """
            
            keyboard = [
                [InlineKeyboardButton("bKash", callback_data='withdraw_method_bkash')],
                [InlineKeyboardButton("Nagad", callback_data='withdraw_method_nagad')],
                [InlineKeyboardButton("Payoneer", callback_data='withdraw_method_payoneer')],
                [InlineKeyboardButton("⬅️ Cancel", callback_data='back_to_menu')]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.edit_message_text(
                withdraw_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            context.user_data['user_id'] = user_id
            context.user_data['user_balance'] = balance
            return WITHDRAW_METHOD
        else:
            await update.callback_query.edit_message_text('❌ User not found')
    
    except Exception as e:
        logger.error(f'Withdraw start error: {e}')
        await update.callback_query.edit_message_text('❌ Error starting withdrawal')
    
    return MAIN_MENU

async def handle_withdraw_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask for account details"""
    query = update.callback_query
    
    account_text = f"""
💳 **Withdraw Setup**

Payment Method: {context.user_data.get('withdraw_method', 'Unknown').upper()}

Send your account/phone number:
    """
    
    keyboard = [[InlineKeyboardButton("⬅️ Cancel", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        account_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return WITHDRAW_ACCOUNT

async def handle_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process withdrawal"""
    user_id = context.user_data.get('user_id')
    method = context.user_data.get('withdraw_method')
    account = update.message.text
    
    # Ask for amount
    amount_text = """
💰 **Enter Amount**

Send the amount you want to withdraw (in ₹):
    """
    
    await update.message.reply_text(amount_text)
    context.user_data['withdraw_account'] = account
    
    return WITHDRAW_AMOUNT

async def handle_final_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Finalize withdrawal request"""
    try:
        amount = float(update.message.text)
        user_id = context.user_data.get('user_id')
        method = context.user_data.get('withdraw_method')
        account = context.user_data.get('withdraw_account')
        
        if amount < 100 or amount > 100000:
            await update.message.reply_text(
                '❌ Amount must be between ₹100 and ₹100,000'
            )
            return WITHDRAW_AMOUNT
        
        # Submit withdrawal request
        withdraw_data = {
            'userId': user_id,
            'amount': amount,
            'method': method,
            'account': account
        }
        
        response = requests.post(
            f'{API_BASE_URL}/api/withdraw/request',
            json=withdraw_data,
            timeout=5
        )
        
        if response.status_code == 201:
            success_text = f"""
✅ **Withdrawal Request Submitted**

Amount: ₹{amount}
Method: {method.upper()}
Account: {account}

Status: Pending

⏱️ We'll process it within 24 hours.
You'll be notified once it's completed.
            """
            
            keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data='back_to_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                success_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            error = response.json().get('message', 'Error processing withdrawal')
            await update.message.reply_text(f'❌ {error}')
    
    except ValueError:
        await update.message.reply_text('❌ Please enter a valid amount')
        return WITHDRAW_AMOUNT
    except Exception as e:
        logger.error(f'Final withdraw error: {e}')
        await update.message.reply_text('❌ Error processing withdrawal')
    
    return MAIN_MENU

async def handle_referral(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show referral information"""
    user_id = f'tg_{update.callback_query.from_user.id}'
    
    try:
        response = requests.get(
            f'{API_BASE_URL}/api/user/{user_id}',
            timeout=5
        )
        
        if response.status_code == 200:
            user = response.json()
            referral_code = user.get('referralCode', 'N/A')
            referral_link = f'https://t.me/{BOT_USERNAME}?start={referral_code}'
            
            referral_text = f"""
👥 **Referral Program**

Your Referral Code: `{referral_code}`

Share your link:
`{referral_link}`

Earn ₹20 for each friend who joins!

📊 Stats:
• Referrals: Check in web app
• Bonus Earned: Check in web app

💡 Tips for more referrals:
• Share on social media
• Message friends directly
• Post in communities
            """
            
            keyboard = [
                [InlineKeyboardButton("🔗 Open Web App", web_app=WebAppInfo(url=WEB_APP_URL))],
                [InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.edit_message_text(
                referral_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    except Exception as e:
        logger.error(f'Referral check error: {e}')
        await update.callback_query.edit_message_text('❌ Error fetching referral info')
    
    return MAIN_MENU

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show help information"""
    help_text = """
❓ **EarnHub Help**

**How to Earn:**
🎬 Videos: Watch for 10 seconds (+5 pts)
📢 Ads: Click advertiser link (+3 pts)
📱 Apps: Install and open (+20 pts)
📲 Channels: Join community (+10 pts)
👥 Referral: Invite friends (+20 pts each)

**Withdraw:**
💰 Minimum: ₹100
💳 Methods: bKash, Nagad, Payoneer
⏱️ Processing: 24 hours

**Tips:**
✅ Complete tasks daily
✅ Refer friends for bonus
✅ Keep app open for rewards
✅ Join channels for updates

**Problems?**
📧 Email: support@earnhub.com
💬 Chat: Message @Support_Bot

Need more help? Use the web app!
    """
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        help_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return MAIN_MENU

# ========================================
# MESSAGE HANDLERS
# ========================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle text messages"""
    if context.user_data.get('waiting_for_account'):
        return await handle_withdraw_account(update, context)
    elif context.user_data.get('waiting_for_amount'):
        return await handle_final_withdraw(update, context)
    else:
        await show_main_menu(update, context)
        return MAIN_MENU

# ========================================
# CONVERSATION FALLBACK
# ========================================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel conversation"""
    await update.message.reply_text('Cancelled. Use /menu to see options.')
    return ConversationHandler.END

# ========================================
# MAIN FUNCTION
# ========================================

def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('menu', show_main_menu))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start polling
    logger.info('🤖 EarnHub Bot started')
    application.run_polling()

if __name__ == '__main__':
    main()
