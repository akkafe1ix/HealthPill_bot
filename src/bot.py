import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from dotenv import load_dotenv
from database import Database
from scheduler import MedicationScheduler
from validators import MedicationValidator, UserInputValidator  

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загружаем токен из .env
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Инициализируем базу данных и планировщик
db = Database()
scheduler = MedicationScheduler(BOT_TOKEN, db)

# Хранилище для данных пользователей
user_sessions = {}

def get_main_menu_keyboard():
    """Возвращает клавиатуру главного меню"""
    keyboard = [
        [InlineKeyboardButton("💊 Добавить лекарство", callback_data="add_medication")],
        [InlineKeyboardButton("📋 Мои лекарства", callback_data="my_medications")],
        [InlineKeyboardButton("🗑️ Удалить лекарство", callback_data="delete_medication")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def edit_or_reply_message(message, text, reply_markup=None, parse_mode='Markdown'):
    """Универсальная функция для редактирования или отправки сообщения"""
    try:
        # Пытаемся отредактировать существующее сообщение
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return message
    except Exception as e:
        # Если редактирование невозможно, отправляем новое сообщение
        logger.debug(f"Cannot edit message, sending new one: {e}")
        return await message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.message.from_user
    
    # Добавляем пользователя в базу
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # Отправляем приветственную картинку
    try:
        photo_file = open('assets/Hello.jpg', 'rb')
        await update.message.reply_photo(
            photo=photo_file,
            caption=f"**Добро пожаловать, {user.first_name}!**\n\nЯ твой персональный помощник для регулярного приема лекарств!",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error sending welcome photo: {e}")
        await update.message.reply_text(
            f"**Добро пожаловать, {user.first_name}!**\n\nЯ твой персональный помощник для регулярного приема лекарств!"
        )
    
    # Отправляем основное меню
    text = "💊 **ГЛАВНОЕ МЕНЮ** 💊\n\nВыберите действие:"
    await update.message.reply_text(text, reply_markup=get_main_menu_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на inline-кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "main_menu":
        await show_main_menu(query)
    elif data == "add_medication":
        await start_add_medication(query)
    elif data == "my_medications":
        await my_medications(query)
    elif data == "delete_medication":
        await delete_medication_start(query)
    elif data == "help":
        await help_button(query)
    elif data.startswith("delete_"):
        medication_id = data.split("_")[1]
        await delete_medication_confirm(query, medication_id)
    elif data.startswith("taken_"):
        parts = data.split("_")
        medication_name = parts[1]
        reminder_sent_time = int(parts[2])
        await scheduler.handle_medication_taken(query, medication_name, reminder_sent_time)

async def show_main_menu(query):
    """Показывает главное меню с очисткой предыдущего сообщения"""
    text = "💊 **ГЛАВНОЕ МЕНЮ** 💊\n\nВыберите действие:"
    await edit_or_reply_message(query.message, text, get_main_menu_keyboard())

async def start_add_medication(query):
    """Начинает процесс добавления лекарства"""
    user_id = query.from_user.id
    user_sessions[user_id] = {'step': 'name'}
    
    keyboard = [[InlineKeyboardButton("🔙", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "💊 **ДОБАВЛЕНИЕ ЛЕКАРСТВА** 💊\n\n"
        "Введите название лекарства:\n\n"
        "🔒 *Ограничения:* 2-50 символов"
    )
    await edit_or_reply_message(query.message, text, reply_markup)

async def handle_medication_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод названия лекарства с валидацией"""
    user_id = update.message.from_user.id
    
    if user_id not in user_sessions or user_sessions[user_id]['step'] != 'name':
        await update.message.reply_text("💊 **ГЛАВНОЕ МЕНЮ** 💊\n\nВыберите действие:", reply_markup=get_main_menu_keyboard())
        return
    
    medication_name = UserInputValidator.sanitize_input(update.message.text)
    
    # Валидируем название
    is_valid, error_message = MedicationValidator.validate_name(medication_name)
    
    if not is_valid:
        keyboard = [[InlineKeyboardButton("🔙", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"{error_message}\n\nПопробуйте еще раз:",
            reply_markup=reply_markup
        )
        return
    
    user_sessions[user_id]['name'] = medication_name
    user_sessions[user_id]['step'] = 'dosage'
    
    keyboard = [[InlineKeyboardButton("🔙", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"✅ **Название:** {medication_name}\n\n"
        "Теперь введите дозировку (например: '500 мг', '1 таблетка'):\n\n"
        "💡 *Максимум 30 символов*"
    )
    await update.message.reply_text(text, reply_markup=reply_markup)

async def handle_medication_dosage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод дозировки с валидацией"""
    user_id = update.message.from_user.id
    
    if user_id not in user_sessions or user_sessions[user_id]['step'] != 'dosage':
        await update.message.reply_text("💊 **ГЛАВНОЕ МЕНЮ** 💊\n\nВыберите действие:", reply_markup=get_main_menu_keyboard())
        return
    
    dosage = UserInputValidator.sanitize_input(update.message.text)
    
    # Валидируем дозировку
    is_valid, error_message = MedicationValidator.validate_dosage(dosage)
    
    if not is_valid:
        keyboard = [[InlineKeyboardButton("🔙", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"{error_message}\n\nПопробуйте ввести дозировку еще раз:",
            reply_markup=reply_markup
        )
        return
    
    user_sessions[user_id]['dosage'] = dosage
    user_sessions[user_id]['step'] = 'schedule'
    
    keyboard = [[InlineKeyboardButton("🔙", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    schedule_examples = "💡 **Примеры:**\n• 08:00\n• 08:00, 20:00\n• 09:30, 14:00, 21:15"
    
    text = (
        f"📋 **Дозировка:** {dosage}\n\n"
        "Теперь введите расписание в формате ЧЧ:ММ:\n"
        "Например: '08:00, 20:00' для приема утром и вечером\n\n"
        f"{schedule_examples}"
    )
    await update.message.reply_text(text, reply_markup=reply_markup)

async def handle_medication_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод расписания с валидацией и сохраняет лекарство"""
    user_id = update.message.from_user.id
    
    if user_id not in user_sessions or user_sessions[user_id]['step'] != 'schedule':
        await update.message.reply_text("💊 **ГЛАВНОЕ МЕНЮ** 💊\n\nВыберите действие:", reply_markup=get_main_menu_keyboard())
        return
    
    schedule_input = UserInputValidator.sanitize_input(update.message.text)
    name = user_sessions[user_id]['name']
    dosage = user_sessions[user_id]['dosage']
    
    # Валидируем расписание
    is_valid, error_message, times_list = MedicationValidator.validate_schedule(schedule_input)
    
    if not is_valid:
        keyboard = [[InlineKeyboardButton("🔙", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            error_message,
            reply_markup=reply_markup
        )
        return
    
    # Комплексная валидация всех данных
    is_valid_complete, final_message, validated_data = MedicationValidator.validate_complete_medication(
        name, dosage, schedule_input
    )
    
    if not is_valid_complete:
        keyboard = [[InlineKeyboardButton("🔙", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            final_message,
            reply_markup=reply_markup
        )
        return
    
    # Сохраняем лекарство в базу
    medication_id = db.add_medication(
        user_id=user_id,
        name=validated_data['name'],
        dosage=validated_data['dosage'],
        schedule=validated_data['schedule']
    )
    
    # Перезапускаем планировщик для нового лекарства
    scheduler.schedule_medication_reminders()
    
    # Очищаем сессию пользователя
    if user_id in user_sessions:
        del user_sessions[user_id]
    
    # Форматируем расписание для красивого отображения
    schedule_display = validated_data['schedule']
    
    success_text = (
        f"✅ **ЛЕКАРСТВО ДОБАВЛЕНО** ✅\n\n"
        f"💊 **Название:** {validated_data['name']}\n"
        f"📋 **Дозировка:** {validated_data['dosage']}\n"
        f"⏰ **Расписание:** {schedule_display}\n\n"
        f"Я буду напоминать вам в указанное время!"
    )
    
    await update.message.reply_text(success_text)
    
    # Показываем главное меню
    await update.message.reply_text("💊 **ГЛАВНОЕ МЕНЮ** 💊\n\nВыберите действие:", reply_markup=get_main_menu_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await send_help_message(update.message)

async def help_button(query):
    """Обработчик кнопки помощи"""
    await send_help_message(query.message)

async def send_help_message(message):
    """Отправляет сообщение помощи"""
    help_text = """
💊 **КАК ПОЛЬЗОВАТЬСЯ БОТОМ** 💊

📋 **Добавить лекарство** - введи название, дозировку и расписание
📋 **Мои лекарства** - посмотри все свои активные лекарства  
🗑️ **Удалить лекарство** - выбери лекарство для удаления
⏰ **Напоминания** - бот автоматически напомнит о приеме
✅ **Подтверждение приема** - нажимай "Я принял(а)" когда выпьешь лекарство

⏰ **Формат времени:** "08:00, 20:00" для приема утром и вечером

🔒 **Ограничения:**
• Название: 2-50 символов
• Дозировка: 1-30 символов  
• Время: формат ЧЧ:ММ, максимум 6 раз в день

💡 **Примеры времени:**
• 08:00
• 08:00, 20:00
• 09:30, 14:00, 21:15
    """
    
    keyboard = [[InlineKeyboardButton("🔙", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_or_reply_message(message, help_text, reply_markup)

async def my_medications(query):
    """Показывает все лекарства пользователя"""
    user_id = query.from_user.id
    medications = db.get_user_medications(user_id)
    
    if not medications:
        keyboard = [[InlineKeyboardButton("🔙", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await edit_or_reply_message(
            query.message,
            "📭 **У вас пока нет добавленных лекарств.**",
            reply_markup
        )
        return
    
    medications_text = "💊 **ВАШИ ЛЕКАРСТВА** 💊\n\n"
    for med_id, name, dosage, schedule in medications:
        medications_text += f"💊 **{name}**\n"
        medications_text += f"  📋 Дозировка: {dosage}\n"
        medications_text += f"  ⏰ Расписание: {schedule}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_or_reply_message(query.message, medications_text, reply_markup)

async def delete_medication_start(query):
    """Начинает процесс удаления лекарства"""
    user_id = query.from_user.id
    medications = db.get_user_medications(user_id)
    
    if not medications:
        keyboard = [[InlineKeyboardButton("🔙", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await edit_or_reply_message(
            query.message,
            "📭 **У вас нет лекарств для удаления.**",
            reply_markup
        )
        return
    
    # Создаем кнопки для каждого лекарства
    keyboard = []
    for med_id, name, dosage, schedule in medications:
        keyboard.append([InlineKeyboardButton(f"🗑️ {name} ({dosage})", callback_data=f"delete_{med_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙", callback_data="main_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_or_reply_message(
        query.message,
        "🗑️ **ВЫБЕРИТЕ ЛЕКАРСТВО ДЛЯ УДАЛЕНИЯ** 🗑️",
        reply_markup
    )

async def delete_medication_confirm(query, medication_id):
    """Подтверждает и удаляет выбранное лекарство"""
    user_id = query.from_user.id
    
    # Получаем информацию о лекарстве перед удалением
    medication = db.get_medication(medication_id, user_id)
    
    if not medication:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await edit_or_reply_message(
            query.message,
            "❌ **ЛЕКАРСТВО НЕ НАЙДЕНО** ❌",
            reply_markup
        )
        return
    
    med_id, name, dosage, schedule = medication
    
    # Удаляем лекарство
    success = db.delete_medication(medication_id, user_id)
    
    if success:
        # Перезапускаем планировщик
        scheduler.schedule_medication_reminders()
        
        success_text = (
            f"✅ **ЛЕКАРСТВО УДАЛЕНО** ✅\n\n"
            f"💊 **Название:** {name}\n"
            f"📋 **Дозировка:** {dosage}\n"
            f"⏰ **Расписание:** {schedule}"
        )
        
        await edit_or_reply_message(query.message, success_text)
        
        # Показываем главное меню через секунду
        await query.message.reply_text("💊 **ГЛАВНОЕ МЕНЮ** 💊\n\nВыберите действие:", reply_markup=get_main_menu_keyboard())
    else:
        keyboard = [[InlineKeyboardButton("🔙", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await edit_or_reply_message(
            query.message,
            "❌ **ЛЕКАРСТВО НЕ НАЙДЕНО** ❌",
            reply_markup
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает все текстовые сообщения"""
    user_id = update.message.from_user.id
    
    # Если пользователь в процессе добавления лекарства
    if user_id in user_sessions:
        step = user_sessions[user_id]['step']
        
        if step == 'name':
            await handle_medication_name(update, context)
        elif step == 'dosage':
            await handle_medication_dosage(update, context)
        elif step == 'schedule':
            await handle_medication_schedule(update, context)
    else:
        # Если не в процессе - показываем главное меню
        await update.message.reply_text("💊 **ГЛАВНОЕ МЕНЮ** 💊\n\nВыберите действие:", reply_markup=get_main_menu_keyboard())

def main():
    """Основная функция запуска бота"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики кнопок
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Обработчик всех текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Запускаем планировщик напоминаний
    scheduler.start()
    
    # Запускаем бота
    logger.info("Бот запускается...")
    application.run_polling()

if __name__ == '__main__':
    main()