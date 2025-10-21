import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from dotenv import load_dotenv
from database import Database
from scheduler import MedicationScheduler

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
scheduler = MedicationScheduler(BOT_TOKEN)

# Хранилище для данных пользователей
user_sessions = {}

def get_main_menu_keyboard():
    """Возвращает клавиатуру главного меню"""
    keyboard = [
        [InlineKeyboardButton("💊 Добавить лекарство 💊", callback_data="add_medication")],
        [InlineKeyboardButton("📋 Мои лекарства 📋", callback_data="my_medications")],
        [InlineKeyboardButton("🗑️ Удалить лекарство 🗑️", callback_data="delete_medication")],
        [InlineKeyboardButton("ℹ️ Помощь ℹ️", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

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
    
    text = f"Привет, {user.first_name}! 👋\n\nЯ помогу тебе не забывать принимать лекарства вовремя.\n\n💊 **Выберите действие:** 💊"
    
    await update.message.reply_text(text, reply_markup=get_main_menu_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на inline-кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "main_menu":
        await query.message.reply_text("💊 **Главное меню** 💊\n\nВыберите действие:", reply_markup=get_main_menu_keyboard())
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
        # Обработка кнопки "Принял лекарство"
        medication_name = data.split("_", 1)[1]  # Берем все после "taken_"
        await scheduler.handle_medication_taken(query, medication_name)

async def start_add_medication(query):
    """Начинает процесс добавления лекарства"""
    user_id = query.from_user.id
    user_sessions[user_id] = {'step': 'name'}
    
    keyboard = [[InlineKeyboardButton("❌ Отмена ❌", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        "💊 **Добавляем новое лекарство!** 💊\n\n"
        "Введите название лекарства:",
        reply_markup=reply_markup
    )

async def handle_medication_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод названия лекарства"""
    user_id = update.message.from_user.id
    
    if user_id not in user_sessions or user_sessions[user_id]['step'] != 'name':
        await update.message.reply_text("💊 **Главное меню** 💊\n\nВыберите действие:", reply_markup=get_main_menu_keyboard())
        return
    
    medication_name = update.message.text
    user_sessions[user_id]['name'] = medication_name
    user_sessions[user_id]['step'] = 'dosage'
    
    keyboard = [[InlineKeyboardButton("❌ Отмена ❌", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📝 **Название:** {medication_name}\n\n"
        "Теперь введите дозировку (например: '500 мг', '1 таблетка'):",
        reply_markup=reply_markup
    )

async def handle_medication_dosage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод дозировки"""
    user_id = update.message.from_user.id
    
    if user_id not in user_sessions or user_sessions[user_id]['step'] != 'dosage':
        await update.message.reply_text("💊 **Главное меню** 💊\n\nВыберите действие:", reply_markup=get_main_menu_keyboard())
        return
    
    dosage = update.message.text
    user_sessions[user_id]['dosage'] = dosage
    user_sessions[user_id]['step'] = 'schedule'
    
    keyboard = [[InlineKeyboardButton("❌ Отмена ❌", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📋 **Дозировка:** {dosage}\n\n"
        "Теперь введите расписание в формате ЧЧ:ММ:\n"
        "Например: '08:00, 20:00' для приема утром и вечером",
        reply_markup=reply_markup
    )

async def handle_medication_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод расписания и сохраняет лекарство"""
    user_id = update.message.from_user.id
    
    if user_id not in user_sessions or user_sessions[user_id]['step'] != 'schedule':
        await update.message.reply_text("💊 **Главное меню** 💊\n\nВыберите действие:", reply_markup=get_main_menu_keyboard())
        return
    
    schedule = update.message.text
    name = user_sessions[user_id]['name']
    dosage = user_sessions[user_id]['dosage']
    
    # Сохраняем лекарство в базу
    medication_id = db.add_medication(
        user_id=user_id,
        name=name,
        dosage=dosage,
        schedule=schedule
    )
    
    # Перезапускаем планировщик для нового лекарства
    scheduler.schedule_medication_reminders()
    
    # Очищаем сессию пользователя
    if user_id in user_sessions:
        del user_sessions[user_id]
    
    await update.message.reply_text(
        f"✅ **Лекарство успешно добавлено!** ✅\n\n"
        f"💊 **Название:** {name}\n"
        f"📋 **Дозировка:** {dosage}\n"
        f"⏰ **Расписание:** {schedule}\n\n"
        f"Я буду напоминать вам в указанное время!"
    )
    
    # Показываем главное меню
    await update.message.reply_text("💊 **Главное меню** 💊\n\nВыберите действие:", reply_markup=get_main_menu_keyboard())

async def help_button(query):
    """Показывает помощь через кнопку"""
    help_text = """
💊 **Как пользоваться ботом:** 💊

📋 **Добавить лекарство** - введи название, дозировку и расписание

📋 **Мои лекарства** - посмотри все свои активные лекарства

🗑️ **Удалить лекарство** - выбери лекарство для удаления

⏰ **Напоминания** - бот автоматически напомнит о приеме

✅ **Подтверждение приема** - нажимай "Я принял(а)" когда выпьешь лекарство

⏰ **Формат времени:** "08:00, 20:00" для приема утром и вечером
    """
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(help_text, reply_markup=reply_markup)

async def my_medications(query):
    """Показывает все лекарства пользователя"""
    user_id = query.from_user.id
    medications = db.get_user_medications(user_id)
    
    if not medications:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "📭 У вас пока нет добавленных лекарств.",
            reply_markup=reply_markup
        )
        return
    
    medications_text = "💊 **Ваши лекарства:** 💊\n\n"
    for med_id, name, dosage, schedule in medications:
        medications_text += f"• **{name}**\n"
        medications_text += f"  Дозировка: {dosage}\n"
        medications_text += f"  Расписание: {schedule}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(medications_text, reply_markup=reply_markup)

async def delete_medication_start(query):
    """Начинает процесс удаления лекарства"""
    user_id = query.from_user.id
    medications = db.get_user_medications(user_id)
    
    if not medications:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "📭 У вас нет лекарств для удаления.",
            reply_markup=reply_markup
        )
        return
    
    # Создаем кнопки для каждого лекарства
    keyboard = []
    for med_id, name, dosage, schedule in medications:
        keyboard.append([InlineKeyboardButton(f"🗑️ {name} ({dosage})", callback_data=f"delete_{med_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        "🗑️ **Выберите лекарство для удаления:** 🗑️",
        reply_markup=reply_markup
    )

async def delete_medication_confirm(query, medication_id):
    """Удаляет выбранное лекарство"""
    user_id = query.from_user.id
    
    # Получаем информацию о лекарстве перед удалением
    medication = db.get_medication(medication_id, user_id)
    
    if not medication:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "❌ Лекарство не найдено. ❌",
            reply_markup=reply_markup
        )
        return
    
    med_id, name, dosage, schedule = medication
    
    # Удаляем лекарство
    success = db.delete_medication(medication_id, user_id)
    
    if success:
        # Перезапускаем планировщик
        scheduler.schedule_medication_reminders()
        
        await query.message.reply_text(
            f"✅ **Лекарство удалено!** ✅\n\n"
            f"💊 **Название:** {name}\n"
            f"📋 **Дозировка:** {dosage}\n"
            f"⏰ **Расписание:** {schedule}"
        )
        
        # Показываем главное меню
        await query.message.reply_text("💊 **Главное меню** 💊\n\nВыберите действие:", reply_markup=get_main_menu_keyboard())
    else:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "❌ Не удалось удалить лекарство. ❌",
            reply_markup=reply_markup
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
💊 **Как пользоваться ботом:** 💊

📋 **Добавить лекарство** - введи название, дозировку и расписание

📋 **Мои лекарства** - посмотри все свои активные лекарства

🗑️ **Удалить лекарство** - выбери лекарство для удаления

⏰ **Напоминания** - бот автоматически напомнит о приеме

✅ **Подтверждение приема** - нажимай "Я принял(а)" когда выпьешь лекарство

⏰ **Формат времени:** "08:00, 20:00" для приема утром и вечером
    """
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(help_text, reply_markup=reply_markup)

async def debug_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для отладки - показывает содержимое БД"""
    user_id = update.message.from_user.id
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Показываем пользователей
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    
    # Показываем лекарства
    cursor.execute("SELECT * FROM medications WHERE user_id = ?", (user_id,))
    medications = cursor.fetchall()
    
    debug_text = f"👥 **Пользователи:** {users}\n\n"
    debug_text += f"💊 **Твои лекарства:** {medications}"
    
    await update.message.reply_text(debug_text)
    conn.close()

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
        await update.message.reply_text("💊 **Главное меню** 💊\n\nВыберите действие:", reply_markup=get_main_menu_keyboard())

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
    application.add_handler(CommandHandler("debug", debug_db))
    
    # Запускаем планировщик напоминаний
    scheduler.start()
    
    # Запускаем бота
    logger.info("Бот запускается...")
    application.run_polling()

if __name__ == '__main__':
    main()