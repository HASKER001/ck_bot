import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from apscheduler.schedulers.background import BackgroundScheduler
import random
import datetime
import json
import os

# ==========================================
# --- НАСТРОЙКИ (УЖЕ ВПИСАНЫ ТВОИ ДАННЫЕ) ---
# ==========================================
TOKEN = os.environ.get("VK_TOKEN")
GROUP_ID = "240126179" 
ADMIN_ID = 829383686  # Твой цифровой ID (Владелец)

# ==========================================
# --- БАЗА ДАННЫХ ---
# ==========================================
DATA_FILE = "family_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"players": {}, "tasks": {}, "rules": "Лидер еще не установил правила."}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

db = load_data()

# ==========================================
# --- ИНИЦИАЛИЗАЦИЯ ВК ---
# ==========================================
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()

def send_msg(peer_id, message):
    try:
        vk.messages.send(
            peer_id=peer_id,
            message=message,
            random_id=random.getrandbits(64)
        )
    except Exception as e:
        print(f"Ошибка отправки сообщения в {peer_id}: {e}")

def get_rank(completed_tasks):
    """Вычисление ранга на основе выполненных заданий"""
    if completed_tasks < 3: return "🍪 Печенька"
    elif completed_tasks < 10: return "🔫 Свояк"
    elif completed_tasks < 25: return "💼 Браток"
    elif completed_tasks < 50: return "👑 Элита семьи"
    else: return "🌟 Легенда"

# ==========================================
# --- АВТОМАТИЧЕСКИЕ УВЕДОМЛЕНИЯ ---
# ==========================================
def payday_reminder():
    """Рассылка за 40 минут до PayDay"""
    reminder_text = "📢 [СЕМЬЯ] Внимание, состав! До PayDay осталось 40 минут!\n\nЗаходим в игру, занимаем посты и не уходим в АФК без ескейпа! 🚀"
    for player_id in db["players"].keys():
        send_msg(int(player_id), reminder_text)

# Запуск расписания
scheduler = BackgroundScheduler(timezone="Europe/Moscow")
scheduler.add_job(payday_reminder, 'cron', minute=20)
scheduler.start()

# ==========================================
# --- ОСНОВНАЯ ЛОГИКА БОТА ---
# ==========================================
longpoll = VkBotLongPoll(vk_session, GROUP_ID)
print("Бот Black Russia Family успешно запущен с расширенным функционалом!")

for event in longpoll.listen():
    if event.type == VkBotEventType.MESSAGE_NEW:
        text = event.message.text.strip()
        text_lower = text.lower()
        peer_id = event.message.peer_id
        user_id = event.message.from_id
        
        # Регистрация нового игрока в базе бота
        u_id_str = str(user_id)
        if u_id_str not in db["players"]:
            db["players"][u_id_str] = {"nickname": "Не указан", "balance": 0, "completed_tasks": 0}
            save_data(db)

        # ==========================================
        # УПРАВЛЕНИЕ ДЛЯ АДМИНА (ТЕБЯ)
        # ==========================================
        if user_id == ADMIN_ID:
            
            # 1. Добавить задание
            if text_lower.startswith("+задание"):
                try:
                    parts = text[9:].split("|")
                    task_name = parts[0].strip()
                    reward = int(parts[1].strip())
                    
                    # Генерация ID задания
                    task_id = str(len(db["tasks"]) + 1)
                    db["tasks"][task_id] = {"name": task_name, "reward": reward}
                    save_data(db)
                    
                    send_msg(peer_id, f"✅ Задание #{task_id} добавлено!\n📝 {task_name}\n💰 Награда: {reward} руб.")
                except:
                    send_msg(peer_id, "❌ Ошибка. Пиши так: +задание Привезти 5 фур материалов | 50000")
                continue

            # 2. Выдать зарплату
            elif text_lower.startswith("+зп"):
                try:
                    parts = text.split()
                    target_id = parts[1]
                    amount = int(parts[2])
                    
                    if target_id in db["players"]:
                        db["players"][target_id]["balance"] += amount
                        save_data(db)
                        send_msg(peer_id, f"💵 Игроку [id{target_id}|Брату] начислена зп/премия: {amount} руб.")
                        send_msg(int(target_id), f"💰 Лидер выдал тебе зарплату/премию: {amount} руб.\nТвой новый баланс: {db['players'][target_id]['balance']} руб.")
                    else:
                        send_msg(peer_id, "❌ Этот игрок еще не писал боту.")
                except:
                    send_msg(peer_id, "❌ Ошибка. Пиши так: +зп [ID_ВК] [Сумма]")
                continue

            # 3. Штраф игроку
            elif text_lower.startswith("-штраф"):
                try:
                    parts = text.split(maxsplit=3)
                    target_id = parts[1]
                    amount = int(parts[2])
                    reason = parts[3] if len(parts) > 3 else "Нарушение правил семьи"
                    
                    if target_id in db["players"]:
                        db["players"][target_id]["balance"] -= amount
                        save_data(db)
                        send_msg(peer_id, f"🚫 Игрок [id{target_id}|Оштрафован] на {amount} руб. Причина: {reason}")
                        send_msg(int(target_id), f"⚠️ Лидер выписал тебе штраф: -{amount} руб.\nПричина: {reason}\nБудь внимательнее!")
                    else:
                        send_msg(peer_id, "❌ Этот игрок еще не писал боту.")
                except:
                    send_msg(peer_id, "❌ Ошибка. Пиши так: -штраф [ID_ВК] [Сумма] [Причина]")
                continue

            # 4. Подтвердить выполнение
            elif text_lower.startswith("+выполнено"):
                try:
                    parts = text.split()
                    target_id = parts[1]
                    task_id = parts[2]
                    
                    if task_id in db["tasks"] and target_id in db["players"]:
                        reward = db["tasks"][task_id]["reward"]
                        t_name = db["tasks"][task_id]["name"]
                        
                        db["players"][target_id]["balance"] += reward
                        db["players"][target_id]["completed_tasks"] += 1
                        save_data(db)
                        
                        send_msg(peer_id, f"✅ Задание #{task_id} одобрено для [id{target_id}|игрока]. Награда {reward} руб. зачислена.")
                        send_msg(int(target_id), f"🎉 Отчет по заданию '{t_name}' одобрен лидером!\n+{reward} руб. на баланс.")
                    else:
                        send_msg(peer_id, "❌ Неверный ID игрока или задания.")
                except:
                    send_msg(peer_id, "❌ Ошибка. Пиши так: +выполнено [ID_ВК] [Номер_задания]")
                continue

            # 5. Установить правила
            elif text_lower.startswith("+правила"):
                new_rules = text[9:].strip()
                if new_rules:
                    db["rules"] = new_rules
                    save_data(db)
                    send_msg(peer_id, "✅ Правила семьи успешно обновлены!")
                else:
                    send_msg(peer_id, "❌ Напиши текст после команды. Пример: +правила 1. Не ДМить...")
                continue

            # 6. Сброс всех заданий
            elif text_lower == "+сброс_заданий":
                db["tasks"] = {}
                save_data(db)
                send_msg(peer_id, "🗑️ Все текущие задания удалены. Список чист.")
                continue

            # 7. Admin-панель
            elif text_lower == "админка":
                msg = "👑 --- ПАНЕЛЬ ОВНЕРА --- 👑\n\n"
                msg += "⚙️ КОМАНДЫ:\n"
                msg += "• `+задание [Текст] | [Награда]` — создать квест\n"
                msg += "• `+выполнено [ID_VK] [№_квеста]` — выдать награду\n"
                msg += "• `+зп [ID_VK] [Сумма]` — начислить зп\n"
                msg += "• `-штраф [ID_VK] [Сумма] [Причина]` — снять деньги\n"
                msg += "• `+правила [Текст]` — задать правила\n"
                msg += "• `+сброс_заданий` — удалить все квесты\n\n"
                msg += "📊 СОСТАВ (ID ВК | Ник | Баланс):\n"
                for p_id, p_info in db["players"].items():
                    msg += f"• [id{p_id}|{p_info['nickname']}] | 💰 {p_info['balance']} | 🏆 {p_info['completed_tasks']}\n"
                send_msg(peer_id, msg)
                continue

        # ==========================================
        # ФУНКЦИОНАЛ ДЛЯ ОБЫЧНЫХ ИГРОКОВ СЕМЬИ
        # ==========================================
        
        # 1. Поставить игровой ник
        if text_lower.startswith("ник"):
            nick = text[4:].strip()
            if nick:
                db["players"][u_id_str]["nickname"] = nick
                save_data(db)
                send_msg(peer_id, f"🤝 Ник изменен на: {nick}. Твой профиль обновлен.")
            else:
                send_msg(peer_id, "❌ Напиши: ник Твой_Ник_На_Сервере")
                
        # 2. Задания
        elif text_lower == "задания":
            if not db["tasks"]:
                send_msg(peer_id, "📋 На данный момент актуальных заданий от лидера нет. Отдыхаем!")
            else:
                msg = "⚔️ Актуальные задания семьи:\n\n"
                for t_id, t_info in db["tasks"].items():
                    msg += f"📌 Задание #{t_id}: {t_info['name']}\n💰 Награда: {t_info['reward']} руб.\n\n"
                msg += "📸 Выполнил? Кидай скрин с /time лидеру в ЛС."
                send_msg(peer_id, msg)

        # 3. Личный баланс
        elif text_lower == "баланс":
            p_info = db["players"][u_id_str]
            rank = get_rank(p_info['completed_tasks'])
            send_msg(peer_id, f"💳 Твой семейный счет:\n\n"
                             f"👤 Ник: {p_info['nickname']}\n"
                             f"🎖 Ранг активности: {rank}\n"
                             f"💵 Доступно к выплате: {p_info['balance']} руб.\n"
                             f"📈 Выполнено квестов: {p_info['completed_tasks']}\n\n"
                             f"ℹ️ Твой ID ВК для лидера: {user_id}")

        # 4. Топ игроков
        elif text_lower == "топ":
            sorted_players = sorted(db["players"].items(), key=lambda x: x[1]["completed_tasks"], reverse=True)
            msg = "🏆 ТОП АКТИВНЫХ ИГРОКОВ СЕМЬИ 🏆\n\n"
            for i, (p_id, p_info) in enumerate(sorted_players[:10], start=1):
                msg += f"{i}. {p_info['nickname']} — {p_info['completed_tasks']} квестов\n"
            send_msg(peer_id, msg)

        # 5. Правила
        elif text_lower == "правила":
            send_msg(peer_id, f"📜 ПРАВИЛА СЕМЬИ:\n\n{db['rules']}")
                             
        # 6. Общее меню помощи
        elif text_lower in ["команды", "помощь", "начать", "меню"]:
            msg = "🚗 На связи семейный бот Black Russia! 🚗\n\n"
            msg += "Доступные команды:\n"
            msg += "• `ник [Ник]` — привязать игровой никнейм\n"
            msg += "• `задания` — посмотреть квесты от лидера\n"
            msg += "• `баланс` — твоя зарплата и ранг\n"
            msg += "• `топ` — рейтинг игроков семьи\n"
            msg += "• `правила` — устав семьи\n\n"
            msg += "🔔 Бот автоматически напомнит тебе за 40 минут до PayDay!"
            if user_id == ADMIN_ID:
                msg += "\n\n👑 Тебе также доступна команда `админка`."
            send_msg(peer_id, msg)
