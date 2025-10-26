import logging
import time
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
import os
from database import Database
import pytz
from datetime import datetime

logger = logging.getLogger(__name__)

class MedicationScheduler:
    def __init__(self, bot_token, db):
        self.bot_token = bot_token
        self.db = db
        # Указываем московский часовой пояс
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Moscow'))
    
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
            
            # Добавляем время отправки уведомления в callback_data
            current_timestamp = int(time.time())
            
            # Создаем кнопку подтверждения
            keyboard = [
                [InlineKeyboardButton("✅ Я принял(а) лекарство ✅", callback_data=f"taken_{medication_name}_{current_timestamp}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await bot.send_message(
                chat_id=user_id,
                text=reminder_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            logger.info(f"Sent reminder to user {user_id} for {medication_name} at {current_timestamp}")
            
        except Exception as e:
            logger.error(f"Error sending reminder to {user_id}: {e}")
    
    async def handle_medication_taken(self, query, medication_name, reminder_sent_time):
        """Обрабатывает подтверждение приема лекарства с учетом времени задержки"""
        user = query.from_user
        current_time = int(time.time())
        delay_seconds = current_time - reminder_sent_time
        delay_minutes = delay_seconds // 60
        
        logger.info(f"User {user.id} confirmed {medication_name} with delay: {delay_minutes} minutes")
        
        # Разные реакции в зависимости от времени задержки
        if delay_minutes <= 5:
            # Вовремя (до 5 минут)
            response = self._get_timely_response(user.first_name, medication_name)
        elif delay_minutes <= 30:
            # Небольшая задержка (5-30 минут)
            response = self._get_small_delay_response(user.first_name, medication_name, delay_minutes)
        elif delay_minutes <= 60:
            # Средняя задержка (30-60 минут)
            response = self._get_medium_delay_response(user.first_name, medication_name, delay_minutes)
        else:
            # Большая задержка (более 1 часа)
            response = self._get_large_delay_response(user.first_name, medication_name, delay_minutes)
        
        # Обновляем сообщение с напоминанием
        await query.edit_message_text(
            response,
            parse_mode='Markdown'
        )
    
    def _get_timely_response(self, user_name, medication_name):
        """Реакция на своевременный прием"""
        timely_praises = [
            f"✅ **Идеально вовремя!** ✅\n\n💊 **{medication_name}** - принято точно по расписанию! 💊\n\n"
            f"Потрясающе, {user_name}! 🎯 Ты образец дисциплины!",
            
            f"✅ **Супер пунктуально!** ✅\n\n💊 **{medication_name}** - принято вовремя! 💊\n\n"
            f"Великолепно, {user_name}! ⭐ Такой подход к лечению восхищает!",
            
            f"✅ **Безупречно!** ✅\n\n💊 **{medication_name}** - принято точно в срок! 💊\n\n"
            f"Браво, {user_name}! 👏 Твоя ответственность впечатляет!",
            
            f"✅ **Абсолютно вовремя!** ✅\n\n💊 **{medication_name}** - принято по расписанию! 💊\n\n"
            f"Молодец, {user_name}! 💪 Регулярность - ключ к успешному лечению!"
        ]
        return random.choice(timely_praises)
    
    def _get_small_delay_response(self, user_name, medication_name, delay_minutes):
        """Реакция на небольшую задержку (5-30 минут)"""
        small_delay_responses = [
            f"✅ **Лекарство принято!** ✅\n\n💊 **{medication_name}** - принято с небольшой задержкой ({delay_minutes} мин) 💊\n\n"
            f"Хорошо, {user_name}! 😊 Но старайся принимать вовремя - это важно для эффективности лечения!",
            
            f"✅ **Принято!** ✅\n\n💊 **{medication_name}** - задержка {delay_minutes} минут 💊\n\n"
            f"Неплохо, {user_name}! 📝 Завтра постарайся уложиться в срок - твое здоровье этого стоит!",
            
            f"✅ **Лекарство принято!** ✅\n\n💊 **{medication_name}** - небольшая задержка {delay_minutes} мин 💊\n\n"
            f"Справился, {user_name}! 🌟 Помни: регулярный прием в одно время усиливает эффект лекарств!"
        ]
        return random.choice(small_delay_responses)
    
    def _get_medium_delay_response(self, user_name, medication_name, delay_minutes):
        """Реакция на среднюю задержку (30-60 минут)"""
        medium_delay_responses = [
            f"⚠️ **Лекарство принято с опозданием** ⚠️\n\n💊 **{medication_name}** - задержка {delay_minutes} минут 💊\n\n"
            f"{user_name}, такое опоздание может снизить эффективность лечения! ⏰ Постарайся завтра принять вовремя!",
            
            f"⚠️ **Принято с задержкой** ⚠️\n\n💊 **{medication_name}** - опоздание на {delay_minutes} мин 💊\n\n"
            f"{user_name}, помни что регулярность приема критически важна! 🔬 Завтра поставь будильник напоминание!",
            
            f"⚠️ **Значительная задержка** ⚠️\n\n💊 **{medication_name}** - принято через {delay_minutes} минут 💊\n\n"
            f"{user_name}, твое здоровье требует внимания! 💊 Постарайся не пропускать время приема - это влияет на результат лечения!"
        ]
        return random.choice(medium_delay_responses)
    
    def _get_large_delay_response(self, user_name, medication_name, delay_minutes):
        """Реакция на большую задержку (более 1 часа)"""
        delay_hours = delay_minutes // 60
        delay_remaining_minutes = delay_minutes % 60
        
        time_text = f"{delay_hours} ч {delay_remaining_minutes} мин" if delay_hours > 0 else f"{delay_minutes} мин"
        
        large_delay_responses = [
            f"🚨 **Критическая задержка!** 🚨\n\n💊 **{medication_name}** - принято через {time_text} 💊\n\n"
            f"{user_name}, такая задержка серьезно снижает эффективность лечения! 🏥 Обсуди с врачом возможность скорректировать график!",
            
            f"🚨 **Опасно опоздал!** 🚨\n\n💊 **{medication_name}** - задержка {time_text} 💊\n\n"
            f"{user_name}, пропуск времени приема может быть опасен! 📞 Если возникают сложности с графиком - проконсультируйся с врачом!",
            
            f"🚨 **Серьезное нарушение графика!** 🚨\n\n💊 **{medication_name}** - опоздание на {time_text} 💊\n\n"
            f"{user_name}, для эффективного лечения необходим регулярный прием! 💡 Рассмотри возможность установки дополнительных напоминаний!"
        ]
        return random.choice(large_delay_responses)
    
    def schedule_medication_reminders(self):
        """Создает напоминания для всех активных лекарств"""
        # Очищаем старые задания
        self.scheduler.remove_all_jobs()
        
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