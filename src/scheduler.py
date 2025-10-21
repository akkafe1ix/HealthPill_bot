import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
import os
from database import Database
import pytz

logger = logging.getLogger(__name__)

class MedicationScheduler:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        # Указываем московский часовой пояс
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Moscow'))
        self.db = Database()
    
    async def send_reminder(self, user_id, medication_name, dosage, time_str):
        """Отправляет напоминание о приеме лекарства с кнопкой подтверждения"""
        try:
            bot = Bot(token=self.bot_token)
            
            reminder_text = f"""
🔔 **Время принять лекарство!**

💊 **Лекарство:** {medication_name}
📋 **Дозировка:** {dosage}
⏰ **Время:** {time_str}

Нажми кнопку ниже когда примешь лекарство!
            """
            
            # Создаем кнопку подтверждения
            keyboard = [
                [InlineKeyboardButton("✅ Я принял(а) лекарство ✅", callback_data=f"taken_{medication_name}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await bot.send_message(
                chat_id=user_id,
                text=reminder_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            logger.info(f"Sent reminder to user {user_id} for {medication_name}")
            
        except Exception as e:
            logger.error(f"Error sending reminder to {user_id}: {e}")
    
    async def handle_medication_taken(self, query, medication_name):
        """Обрабатывает подтверждение приема лекарства"""
        user = query.from_user
        
        # Случайные похвалы
        praises = [
            f"Молодец, {user.first_name}! 🎉 Ты заботишься о своем здоровье!",
            f"Отлично, {user.first_name}! 💪 Так держать!",
            f"Супер, {user.first_name}! 🌟 Ты ответственно подходишь к лечению!",
            f"Прекрасно, {user.first_name}! 😊 Регулярный прием - залог успеха!",
            f"Великолепно, {user.first_name}! ⭐ Ты следишь за своим здоровьем!",
            f"Замечательно, {user.first_name}! 💊 Еще один шаг к выздоровлению!",
            f"Браво, {user.first_name}! 👏 Ты дисциплинирован(а) в лечении!",
            f"Потрясающе, {user.first_name}! 🌈 Продолжай в том же духе!"
        ]
        
        import random
        praise = random.choice(praises)
        
        # Обновляем сообщение с напоминанием
        await query.edit_message_text(
            f"✅ **Лекарство принято!** ✅\n\n"
            f"💊 **{medication_name}** - принято вовремя! 💊\n\n"
            f"{praise}",
            parse_mode='Markdown'
        )
        
        logger.info(f"User {user.id} confirmed taking {medication_name}")
    
    def schedule_medication_reminders(self):
        """Создает напоминания для всех активных лекарств"""
        medications = self.db.get_all_medications()
        
        for user_id, name, dosage, schedule in medications:
            # Парсим расписание "08:00, 20:00" в отдельные времена
            times = [t.strip() for t in schedule.split(',')]
            
            for time_str in times:
                if ':' in time_str:  # Проверяем что это время
                    try:
                        hour, minute = map(int, time_str.split(':'))
                        
                        # Создаем задание в планировщике
                        trigger = CronTrigger(hour=hour, minute=minute, timezone='Europe/Moscow')
                        self.scheduler.add_job(
                            self.send_reminder,
                            trigger,
                            args=[user_id, name, dosage, time_str],
                            id=f"med_{user_id}_{name}_{time_str}",
                            replace_existing=True
                        )
                        
                        logger.info(f"Scheduled reminder for {name} at {time_str} (MSK)")
                    except ValueError as e:
                        logger.error(f"Error parsing time {time_str}: {e}")
    
    def start(self):
        """Запускает планировщик"""
        self.schedule_medication_reminders()
        self.scheduler.start()
        logger.info("Medication scheduler started with Moscow timezone")