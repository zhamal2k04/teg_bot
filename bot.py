import logging
import os
import csv
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.enums import ParseMode, ContentType
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.filters import Command
     
# Bot configuration
BOT_TOKEN = "7927638932:AAFgt4HIKUU3-5IuDm0-PS2h1Vk2mSqXk8s"
ADMIN_GROUP_ID = -1002459383963
CSV_FILE = "savollar.csv"
HISOBOT_PAROLI = "menga_savol_ber"  # Report password

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot initialization
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# Memory storage
kutilayotgan_savollar = {}  # {group_message_id: {user_id, chat_id, module}}
javob_kutayotganlar = {}    # {admin_id: {user_id, chat_id, group_message_id}}
foydalanuvchi_holati = {}   # {user_id: {'module': selected_module}}

# Modules
MODULLAR = ["HTML", "CSS", "Bootstrap", "WIX", "JavaScript", "Scratch"]

def csvga_yozish(user_id, module, question, content_type="text"):
    """Save questions to CSV file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        # Create file if it doesn't exist
        if not os.path.exists(CSV_FILE):
            with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["user_id", "module", "question", "content_type", "timestamp"])
        
        # Append data
        with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([user_id, module, question, content_type, timestamp])
    except Exception as e:
        logger.error(f"CSV write error: {e}")

def csvdan_oqish():
    """Read data from CSV file"""
    try:
        with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            return list(reader)
    except FileNotFoundError:
        return []

@router.message(Command("start"))
async def start_handler(message: types.Message):
    """Start message with module selection buttons"""
    builder = ReplyKeyboardBuilder()
    for module in MODULLAR:
        builder.add(types.KeyboardButton(text=module))
    builder.adjust(2)  # 2 buttons per row
    
    await message.answer(
        "👋 Junior Aloqa botga xush kelibsiz !"
        "O'zingizga kerakli modulni tanlang:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@router.message(Command("hisobot"))
async def report_password_handler(message: types.Message):
    """Ask for report password"""
    user_id = message.from_user.id
    foydalanuvchi_holati[user_id] = {'waiting_for_password': True}
    await message.answer("🔒 Hisobotni korish uchun parolni kiriting:")

@router.message(F.text == HISOBOT_PAROLI)
async def send_report_handler(message: types.Message):
    """Send report when correct password is entered"""
    user_id = message.from_user.id
    
    if user_id in foydalanuvchi_holati and foydalanuvchi_holati[user_id].get('waiting_for_password'):
        data = csvdan_oqish()
        if not data:
            await message.answer("❌ Hisobotda malumot yoq.")
            return
            
        report_text = "📊 Questions report:\n\n"
        for row in data:
            user_id, module, question, content_type, timestamp = row
            report_text += (
                f"🆔 User ID: {user_id}\n"
                f"📌 Module: {module}\n"
                f"📂 Type: {content_type}\n"
                f"🕒 Time: {timestamp}\n"
                f"❓ Question: {question}\n"
                f"{'-'*30}\n"
            )
        
        await message.answer(report_text)
        foydalanuvchi_holati.pop(user_id, None)
    else:
        await message.answer("Iltimos /hisobot ni yuboring.")

@router.message(F.text.in_(MODULLAR))
async def module_selection_handler(message: types.Message):
    """Handle module selection"""
    user_id = message.from_user.id
    module = message.text
    
    foydalanuvchi_holati[user_id] = {'module': module}
    
    await message.answer(
        f"📝 Siz <b>{module}</b> modulini tanladingiz. Marhamat, Savolingizni yuboring:",
        reply_markup=types.ReplyKeyboardRemove()
    )

@router.callback_query(F.data.startswith("javob_"))
async def answer_button_handler(callback_query: types.CallbackQuery):
    try:
        admin_id = callback_query.from_user.id
        user_id, user_chat_id = map(int, callback_query.data.split("_")[1:])

        # Check admin status
        chat_member = await bot.get_chat_member(callback_query.message.chat.id, admin_id)
        if chat_member.status not in ['administrator', 'creator']:
            await callback_query.answer("Only admins can respond.")
            return

        javob_kutayotganlar[admin_id] = {
            "user_id": user_id,
            "user_chat_id": user_chat_id,
            "group_message_id": callback_query.message.message_id
        }

        # Get admin's first name
        admin_name = callback_query.from_user.first_name

        # Edit original message to show who is responding
        await callback_query.message.edit_reply_markup(
            reply_markup=InlineKeyboardBuilder()
            .button(text=f"✓ Responding: {admin_name}", callback_data="javob_berildi")
            .adjust(1)
            .as_markup()
        )

        await bot.send_message(admin_id, "💬 Siz tanlagan savolingizga javob bering ✅):")
        await callback_query.answer(f"Hozir foydalanuvchiga xabar yubora olasiz")

    except Exception as e:
        logger.error(f"Answer button error: {e}")
        await callback_query.answer("Xatolik yuzaga keldi.")

@router.message()
async def all_messages_handler(message: types.Message):
    if message.from_user.is_bot:
        return

    admin_id = message.from_user.id
    context = javob_kutayotganlar.get(admin_id)

    # Admin response
    if context and message.chat.type == 'private':
        try:
            # Forward the response to the user (handles all media types)
            if message.content_type == ContentType.TEXT:
                await bot.send_message(
                    chat_id=context["user_chat_id"],
                    text=f"📬 Junior jamoasidan kelgan javob:\n\n{message.text}"
                )
            else:
                # Handle all other media types (photo, video, document, etc.)
                method = getattr(bot, f"send_{message.content_type}")
                await method(
                    chat_id=context["user_chat_id"],
                    **{message.content_type: getattr(message, message.content_type)[-1].file_id},
                    caption=f"📬 Junior jamoasidan kelgan javob:\n\n{message.caption}" if message.caption else None
                )
            
            # Edit original question message
            try:
                await bot.edit_message_reply_markup(
                    chat_id=ADMIN_GROUP_ID,
                    message_id=context["group_message_id"],
                    reply_markup=None
                )
            except Exception as e:
                logger.error(f"Xabarni tahrirlashda xato: {e}")

            await message.answer("✅ Xabar yuborildi!")
            
            # Clean up
            javob_kutayotganlar.pop(admin_id, None)
            kutilayotgan_savollar.pop(context["group_message_id"], None)
            
        except Exception as e:
            logger.error(f"Error sending response: {e}")
            await message.answer(f"❌ Xabarni yuborish xatosi: {e}")
        return

    # User question (handles all content types)
    if message.chat.type == 'private' and not message.text.startswith("/"):
        user_id = message.from_user.id
        user_state = foydalanuvchi_holati.get(user_id)
        
        if not user_state or 'module' not in user_state:
            await message.answer("Iltimos avval /start buyrugini yuboring")
            return
            
        module = user_state['module']

        try:
            builder = InlineKeyboardBuilder()
            builder.button(
                text="✉️ Respond",
                callback_data=f"javob_{user_id}_{message.chat.id}"
            )
            builder.adjust(1)

            # Prepare question text based on content type
            if message.content_type == ContentType.TEXT:
                question_text = message.text
                content_type = "text"
            else:
                question_text = message.caption if message.caption else f"[{message.content_type}]"
                content_type = message.content_type

            # Send message to admin group
            sent_message = await bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=f"❓ Question ({module}) @{message.from_user.username or 'user'} (ID: {user_id}):\n\n{question_text}",
                reply_markup=builder.as_markup()
            )

            # If it's a media message, forward the media to the group
            if message.content_type != ContentType.TEXT:
                method = getattr(bot, f"send_{message.content_type}")
                await method(
                    chat_id=ADMIN_GROUP_ID,
                    **{message.content_type: getattr(message, message.content_type)[-1].file_id},
                    reply_to_message_id=sent_message.message_id,
                    caption=None  # We already included caption in the text message
                )

            kutilayotgan_savollar[sent_message.message_id] = {
                "user_id": user_id,
                "user_chat_id": message.chat.id,
                "module": module
            }
            
            csvga_yozish(user_id, module, question_text, content_type)
            
            await message.answer("✅ Savolingiz Junior jamoasiga yuborildi!")
            
            foydalanuvchi_holati.pop(user_id, None)

        except Exception as e:
            logger.error(f"Error sending question: {e}")
            await message.answer("❌ Savolingizni yuborishda xatolik yuzaga keldi.")

# Error handler
@dp.errors()
async def error_handler(event, exception):
    logger.error(f"⚠️ Error occurred: {exception}")

# Main function
async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
