import re
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MedicationValidator:
    """Валидатор для данных о лекарствах"""
    
    @staticmethod
    def validate_name(name):
        """
        Валидирует название лекарства
        Возвращает: (is_valid, error_message)
        """
        if not name or not name.strip():
            return False, "❌ Название лекарства не может быть пустым"
        
        name = name.strip()
        
        # Проверка длины
        if len(name) > 50:
            return False, "❌ Название слишком длинное (максимум 50 символов)"
        
        if len(name) < 2:
            return False, "❌ Название слишком короткое (минимум 2 символа)"
        
        # Проверка на допустимые символы
        if not re.match(r'^[a-zA-Zа-яА-ЯёЁ0-9\s\-\.\,\(\)]+$', name):
            return False, "❌ Название содержит недопустимые символы"
        
        return True, name

    @staticmethod
    def validate_dosage(dosage):
        """
        Валидирует дозировку
        Возвращает: (is_valid, error_message)
        """
        if not dosage or not dosage.strip():
            return False, "❌ Дозировка не может быть пустой"
        
        dosage = dosage.strip()
        
        # Проверка длины
        if len(dosage) > 30:
            return False, "❌ Дозировка слишком длинная (максимум 30 символов)"
        
        if len(dosage) < 1:
            return False, "❌ Дозировка слишком короткая"
        
        # Проверка на допустимые символы
        if not re.match(r'^[a-zA-Zа-яА-ЯёЁ0-9\s\-\.\,\(\)\/мгмлтабкапсул]+$', dosage, re.IGNORECASE):
            return False, "❌ Дозировка содержит недопустимые символы"
        
        return True, dosage

    @staticmethod
    def validate_schedule(schedule_str):
        """
        Валидирует расписание времени приема
        Возвращает: (is_valid, error_message, times_list)
        """
        if not schedule_str or not schedule_str.strip():
            return False, "❌ Расписание не может быть пустым", None
        
        schedule_str = schedule_str.strip()
        
        # Разделяем по запятой
        time_strings = [t.strip() for t in schedule_str.split(',')]
        valid_times = []
        
        for time_str in time_strings:
            # Проверка формата ЧЧ:ММ
            if not re.match(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$', time_str):
                return False, f"❌ Неверный формат времени: '{time_str}'. Используйте ЧЧ:ММ (например: 08:00)", None
            
            # Преобразуем в объект времени для проверки
            try:
                hour, minute = map(int, time_str.split(':'))
                if hour > 23 or minute > 59:
                    return False, f"❌ Неверное время: '{time_str}'", None
                
                valid_times.append(time_str)
            except ValueError:
                return False, f"❌ Ошибка в формате времени: '{time_str}'", None
        
        # Проверяем что есть хотя бы одно время
        if not valid_times:
            return False, "❌ Не указано ни одного времени приема", None
        
        # Проверяем максимальное количество времен
        if len(valid_times) > 6:
            return False, "❌ Слишком много времени приема (максимум 6 раз в день)", None
        
        # Проверяем дубликаты
        if len(valid_times) != len(set(valid_times)):
            return False, "❌ Обнаружены дублирующиеся времени приема", None
        
        # Сортируем времена
        valid_times.sort()
        
        return True, ", ".join(valid_times), valid_times

    @staticmethod
    def validate_complete_medication(name, dosage, schedule):
        """
        Комплексная валидация всех данных лекарства
        Возвращает: (is_valid, error_message, validated_data)
        """
        # Валидируем название
        is_valid_name, name_msg = MedicationValidator.validate_name(name)
        if not is_valid_name:
            return False, name_msg, None
        
        # Валидируем дозировку
        is_valid_dosage, dosage_msg = MedicationValidator.validate_dosage(dosage)
        if not is_valid_dosage:
            return False, dosage_msg, None
        
        # Валидируем расписание
        is_valid_schedule, schedule_msg, times_list = MedicationValidator.validate_schedule(schedule)
        if not is_valid_schedule:
            return False, schedule_msg, None
        
        validated_data = {
            'name': name_msg,  # уже очищенное название
            'dosage': dosage_msg,  # уже очищенная дозировка
            'schedule': schedule_msg,  # уже отформатированное расписание
            'times_list': times_list  # список времен для планировщика
        }
        
        return True, "✅ Все данные корректны", validated_data

class UserInputValidator:
    """Валидатор для пользовательского ввода"""
    
    @staticmethod
    def sanitize_input(text, max_length=100):
        """
        Очищает пользовательский ввод от потенциально опасных символов
        """
        if not text:
            return ""
        
        # Удаляем лишние пробелы
        text = text.strip()
        
        # Ограничиваем длину
        if len(text) > max_length:
            text = text[:max_length]
        
        # Заменяем потенциально опасные символы
        text = text.replace('<', '&lt;').replace('>', '&gt;')
        text = text.replace('"', '&quot;').replace("'", '&#39;')
        
        return text

    @staticmethod
    def validate_time_input(time_input):
        """
        Валидирует ввод времени с подсказками
        """
        # Примеры правильного ввода
        examples = [
            "08:00",
            "08:00, 20:00", 
            "09:30, 14:00, 21:15",
            "07:00, 12:00, 18:00, 22:00"
        ]
        
        is_valid, message, times_list = MedicationValidator.validate_schedule(time_input)
        
        if not is_valid:
            error_message = f"{message}\n\n💡 **Примеры правильного формата:**\n"
            for example in examples:
                error_message += f"• `{example}`\n"
            error_message += "\nВведите время в формате ЧЧ:ММ через запятую:"
            
            return False, error_message, None
        
        return True, "✅ Расписание корректно", times_list