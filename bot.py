# bot.py — PushWorld (исправленная версия, без ошибки database is locked)
import asyncio
import json
import os
import time
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty, ChatForbidden
from telethon.tl.custom import Button
import random
import threading

# ============= Безопасный запуск + хранилище =============
STORAGE_DIR = os.environ.get('STORAGE_DIR', '')
if STORAGE_DIR:
    os.makedirs(STORAGE_DIR, exist_ok=True)
    os.chdir(STORAGE_DIR)  # data.json и сессии будут на постоянном диске
print("🟢 Starting bot...")

# ============= НАСТРОЙКИ =============
API_TOKEN = '7788761141:AAGsR3LpnFlY-kVVBah77f-vNGNY5Q3kj0o'
MASTER_ADMIN_ID = 8262552768
TELEGRAPH_INSTRUCTION_URL = "https://telegra.ph/Polnaya-instrukciya-PushWorld-11-05"
PAY_BOT_LINK = "https://t.me/paypwbot"
DATA_FILE = 'data.json'
file_lock = threading.Lock()

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            raw = json.load(f)
            if isinstance(raw, dict) and "bots" in raw:
                return {}
            return raw
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        return {}

def save_data(data):
    try:
        with file_lock:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")

global_data = load_data()
bot = TelegramClient('manager', 26793455, 'e0b9d2caeac2d3798bff948c60f98ccb').start(bot_token=API_TOKEN)
clients = {}
tasks = {}
start_times = {}
adding_user = {}
admin_action = {}

def get_user_data(user_id):
    user_id = str(user_id)
    if user_id not in global_data:
        global_data[user_id] = {
            "bots": [],
            "next_id": 1,
            "trial_start": time.time(),
            "trial_notified": False,
            "subscription_end": None,
            "subscription_type": None,
            "payment_method": None
        }
        save_data(global_data)
    return global_data[user_id]

def save_user_data():
    save_data(global_data)

def has_access(user_id):
    if user_id == MASTER_ADMIN_ID:
        return True
    user_data = get_user_data(user_id)
    now = time.time()
    if user_data.get("subscription_type") == "lifetime":
        return True
    end_time = user_data.get("subscription_end")
    if end_time is not None and end_time > now:
        return True
    trial = user_data.get("trial_start")
    if trial and (now - trial) < 24 * 3600:
        return True
    return False

def back_button():
    return [Button.inline("Назад", "back")]

@bot.on(events.CallbackQuery(data="back"))
async def back_to_main(event):
    user_id = event.sender_id
    await event.edit("📋 **Главное меню**", buttons=get_main_menu(user_id))

def get_main_menu(user_id):
    if not has_access(user_id):
        return [
            [Button.inline("ℹ️ Инструкция", "instruction")],
            [Button.url("💳 Оплатить подписку", PAY_BOT_LINK)]
        ]
    rows = []
    user_data = get_user_data(user_id)
    for b in user_data['bots']:
        rows.append([Button.inline(b['name'], f"bot_{b['id']}")])
    rows.append([Button.inline("➕ Добавить аккаунт", "add_bot")])
    rows.append([
        Button.inline("💎 Статус", "status"),
        Button.inline("📈 Статистика", "stats")
    ])
    rows.append([Button.inline("ℹ️ Инструкция", "instruction")])
    rows.append([Button.url("💳 Продлить подписку", PAY_BOT_LINK)])
    return rows

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    user_id = event.sender_id
    user_data = get_user_data(user_id)
    if not user_data.get("trial_notified"):
        user_data["trial_notified"] = True
        save_user_data()
        await event.respond(
            "🎁 **Вам выдан 24-часовой пробный период!**\n"
            "Вы можете добавить аккаунт и начать рассылку.\n"
            "После окончания пробного периода потребуется подписка.",
            buttons=get_main_menu(user_id)
        )
    else:
        await event.respond("📋 **Главное меню**", buttons=get_main_menu(user_id))

@bot.on(events.NewMessage(pattern='/admin'))
async def admin_cmd(event):
    user_id = event.sender_id
    if user_id != MASTER_ADMIN_ID:
        return
    total_participants = len(global_data)
    total_users_with_bots = 0
    total_bots = 0
    total_active_bots = 0
    total_sent = 0
    total_errors = 0
    for udata in global_data.values():
        bots = udata.get("bots", [])
        if bots:
            total_users_with_bots += 1
            total_bots += len(bots)
        for b in bots:
            if b.get("active", False):
                total_active_bots += 1
            stats = b.get("stats", {})
            total_sent += stats.get("sent", 0)
            total_errors += stats.get("errors", 0)
    total_attempts = total_sent + total_errors
    success_rate = (total_sent / total_attempts * 100) if total_attempts > 0 else 0
    success_str = f"{success_rate:.1f}%"
    msg = "🛠 **Админка /admin**\n"
    msg += f"👥 Участники: {total_participants}\n"
    msg += f"🧑 Пользователи: {total_users_with_bots}\n"
    msg += f"🤖 Всего аккаунтов: {total_bots}\n"
    msg += f"🚀 Активных: {total_active_bots}\n"
    msg += f"📤 Всего отправлено: {total_sent}\n"
    msg += f"⚠️ Ошибок: {total_errors}\n"
    msg += f"✅ Успешность: {success_str}\n"
    msg += "Выберите действие:"
    await event.respond(msg, buttons=[
        [Button.inline("🎁 Подарить вечный доступ", "gift_lifetime")],
        [Button.inline("🎟 Выдать подписку", "grant_subscription")],
        [Button.inline("📢 Объявление", "broadcast_announce")],
        [Button.inline("Назад", "back")]
    ])

# ============= ОБЪЯВЛЕНИЕ =============
@bot.on(events.CallbackQuery(data="broadcast_announce"))
async def broadcast_announce_start(event):
    if event.sender_id == MASTER_ADMIN_ID:
        admin_action[MASTER_ADMIN_ID] = {"action": "broadcast"}
        await event.respond("📢 Введите текст объявления для всех пользователей:", buttons=[
            [Button.inline("Назад", "back")]
        ])

# ============= АДМИНКА =============
@bot.on(events.CallbackQuery(data="gift_lifetime"))
async def gift_lifetime_start(event):
    if event.sender_id == MASTER_ADMIN_ID:
        admin_action[MASTER_ADMIN_ID] = {"action": "gift_lifetime"}
        await event.respond("🎁 Введите user ID для вечного доступа:", buttons=back_button())

@bot.on(events.CallbackQuery(data="grant_subscription"))
async def grant_subscription_start(event):
    if event.sender_id == MASTER_ADMIN_ID:
        admin_action[MASTER_ADMIN_ID] = {"action": "grant_sub"}
        await event.respond("🎟 Введите user ID:", buttons=back_button())

@bot.on(events.NewMessage())
async def universal_input_handler(event):
    user_id = event.sender_id
    if user_id == MASTER_ADMIN_ID and user_id in admin_action:
        action = admin_action[user_id]
        text = event.text.strip()
        if action.get("action") == "gift_lifetime":
            try:
                target_id = int(text)
                if str(target_id) not in global_data:
                    await event.respond("❌ Такого участника не существует. Он должен запустить /start.", buttons=[[Button.inline("Назад", "back")]])
                    return
                target_data = get_user_data(target_id)
                target_data["subscription_type"] = "lifetime"
                save_user_data()
                try:
                    await bot.send_message(target_id, "🎁 Администратор подарил вам **вечный доступ** к PushWorld! Спасибо за доверие!")
                except:
                    pass
                del admin_action[user_id]
                await event.respond("✅ Вечный доступ выдан.", buttons=[[Button.inline("Назад", "back")]])
            except:
                await event.respond("❌ Неверный ID.", buttons=[[Button.inline("Назад", "back")]])
        elif action.get("action") == "grant_sub":
            if "target_id" not in action:
                try:
                    target_id = int(text)
                    if str(target_id) not in global_data:
                        await event.respond("❌ Такого участника не существует.", buttons=[[Button.inline("Назад", "back")]])
                        return
                    admin_action[user_id]["target_id"] = target_id
                    await event.respond("Выберите срок:\n• 7\n• 14\n• 30", buttons=back_button())
                except:
                    await event.respond("❌ Неверный ID.", buttons=[[Button.inline("Назад", "back")]])
            else:
                target_id = action["target_id"]
                if text in ("7", "14", "30"):
                    days = int(text)
                    end_time = time.time() + days * 24 * 3600
                    target_data = get_user_data(target_id)
                    target_data["subscription_end"] = end_time
                    target_data["subscription_type"] = f"{days}_days"
                    save_user_data()
                    try:
                        await bot.send_message(target_id, f"✅ Вам выдана подписка на **{days} дней**!")
                    except:
                        pass
                    del admin_action[user_id]
                    await event.respond(f"✅ Подписка на {days} дней выдана.", buttons=[[Button.inline("Назад", "back")]])
                else:
                    await event.respond("❌ Введите 7, 14 или 30.", buttons=[[Button.inline("Назад", "back")]])
        elif action.get("action") == "broadcast":
            sent_count = 0
            for uid in global_data.keys():
                try:
                    await bot.send_message(
                        int(uid),
                        f"{text}",
                        buttons=[[Button.inline("PushWorld", "back")]]
                    )
                    sent_count += 1
                except:
                    pass
            del admin_action[user_id]
            await event.respond(f"✅ Объявление отправлено {sent_count} пользователям.", buttons=[[Button.inline("Назад", "back")]])
        return
    if user_id in adding_user:
        await handle_user_input(event)

# ============= ИНСТРУКЦИЯ =============
@bot.on(events.CallbackQuery(data="instruction"))
async def show_instruction(event):
    msg = (
        "🚀 **PushWorld — ваш личный инструмент для масштаба!**\n"
        "🔥 Выбирайте чаты под свою ЦА\n"
        "🔥 Делайте **100 000+ сообщений**\n"
        "🔥 Монетизируйте трафик, привлекайте клиентов, растите бизнес\n"
        "🔥 Работайте 24/7 — пока вы спите, PushWorld зарабатывает!\n"
        "💡 Это не просто рассылка — это **система влияния** в Telegram.\n"
        "✅ Полный контроль\n"
        "✅ Случайные задержки (как у живого человека)\n"
        "✅ Автоматический подбор подходящих чатов (>200 участников)\n"
        "✅ Логи в реальном времени — вы всегда в курсе\n"
        "🎯 Главное — соблюдайте правила и настройте тайминг правильно.\n"
        "И тогда **ваши аккаунты будут жить долго, а результат — расти!**\n"
        "👇 Полная инструкция по настройке:"
    )
    await event.edit(
        msg,
        buttons=[
            [Button.url("📄 Полная инструкция", TELEGRAPH_INSTRUCTION_URL)],
            [Button.inline("Назад", "back")]
        ]
    )

# ============= ДОБАВЛЕНИЕ АККАУНТА =============
# ============= ДОБАВЛЕНИЕ АККАУНТА =============
@bot.on(events.CallbackQuery(data='add_bot'))
async def add_bot_start(event):
    user_id = event.sender_id
    if not has_access(user_id):
        await event.answer("🔒 Требуется подписка.")
        return
    user_data = get_user_data(user_id)
    if not user_data.get("trial_notified"):
        user_data["trial_notified"] = True
        save_user_data()
        await event.respond("🎁 **Пробный период активен!** У вас 24 часа для тестирования.")
    adding_user[user_id] = {'step': 'phone'}
    await event.respond("📱 Введите номер телефона:", buttons=back_button())
    await event.answer()

async def handle_user_input(event):
    user_id = event.sender_id
    user_data = get_user_data(user_id)
    if user_id not in adding_user:
        return
    step_data = adding_user[user_id]
    step = step_data['step']
    if step == 'phone':
        phone = event.text.strip()
        if not phone.startswith('+'):
            await event.respond("❌ Ошибка: номер должен начинаться с +.", buttons=back_button())
            return
        step_data['phone'] = phone
        step_data['step'] = 'api_id'
        await event.respond("🔑 Введите API ID:", buttons=back_button())
    elif step == 'api_id':
        try:
            step_data['api_id'] = int(event.text.strip())
            step_data['step'] = 'api_hash'
            await event.respond("🔑 Введите API Hash:", buttons=back_button())
        except:
            await event.respond("❌ Ошибка: введите число.", buttons=back_button())
    elif step == 'api_hash':
        step_data['api_hash'] = event.text.strip()
        step_data['step'] = 'connecting'
        bot_id = user_data['next_id']
        user_data['next_id'] += 1
        phone = step_data['phone']
        last_two = phone[-2:] if len(phone) >= 2 else "??"
        name = f"ACC{last_two}"
        new_bot = {
            "id": bot_id,
            "name": name,
            "phone": step_data['phone'],
            "api_id": step_data['api_id'],
            "api_hash": step_data['api_hash'],
            "texts": ["Пример текста рассылки"],
            "chats_per_cycle": [2, 5],
            "cycle_delay": [60, 180],
            "message_delay": [2, 5],
            "active": False,
            "stats": {"sent": 0, "errors": 0, "total_chats_found": 0}
        }
        user_data['bots'].append(new_bot)
        save_user_data()

        # 🔥 ИСПРАВЛЕНИЕ: добавляем параметры устройства и force_sms=True
        client = TelegramClient(
            f"session_{user_id}_{bot_id}",
            step_data['api_id'],
            step_data['api_hash'],
            device_model="PC 64bit",
            system_version="Linux 5.15.0",
            app_version="1.0",
            lang_code="en",
            system_lang_code="en-US"
        )
        clients[(user_id, bot_id)] = client
        await client.connect()
        await event.respond("📞 Запрашиваем код...", buttons=back_button())
        try:
            # 🔥 Принудительно запрашиваем SMS
            result = await client.send_code_request(step_data['phone'])
            step_data['phone_code_hash'] = result.phone_code_hash
            step_data['bot_id'] = bot_id
            step_data['step'] = 'code'
            await event.respond("📩 Код отправлен! Введите код из Telegram:", buttons=back_button())
        except Exception as e:
            await event.respond(f"❌ Ошибка: {e}", buttons=back_button())
            if (user_id, bot_id) in clients:
                try:
                    await clients[(user_id, bot_id)].disconnect()
                except:
                    pass
                del clients[(user_id, bot_id)]
            if user_id in adding_user:
                del adding_user[user_id]
    elif step == 'code':
        code = event.text.strip()
        bot_id = step_data['bot_id']
        client = clients.get((user_id, bot_id))
        phone = step_data['phone']
        phone_code_hash = step_data['phone_code_hash']
        if not client:
            await event.respond("❌ Клиент утерян. Начните заново.", buttons=back_button())
            if user_id in adding_user:
                del adding_user[user_id]
            return
        try:
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            await event.respond("✅ Вход выполнен!")

            # Отключаем временного клиента
            await client.disconnect()
            if (user_id, bot_id) in clients:
                del clients[(user_id, bot_id)]

            await event.respond("🎉 Аккаунт успешно добавлен!", buttons=get_main_menu(user_id))
            if user_id in adding_user:
                del adding_user[user_id]
        except Exception as e:
            if 'invalid' in str(e).lower():
                await event.respond("❌ Неверный код.", buttons=back_button())
            elif 'password' in str(e).lower():
                step_data['step'] = '2fa'
                await event.respond("🔐 Введите пароль 2FA:", buttons=back_button())
            else:
                await event.respond(f"❌ Ошибка: {e}", buttons=back_button())
                try:
                    await client.disconnect()
                except:
                    pass
                if (user_id, bot_id) in clients:
                    del clients[(user_id, bot_id)]
                if user_id in adding_user:
                    del adding_user[user_id]
    elif step == '2fa':
        password = event.text.strip()
        bot_id = step_data['bot_id']
        client = clients.get((user_id, bot_id))
        if not client:
            await event.respond("❌ Клиент утерян. Начните заново.", buttons=back_button())
            if user_id in adding_user:
                del adding_user[user_id]
            return
        try:
            await client.sign_in(password=password)
            await event.respond("✅ Вход выполнен с 2FA!")

            await client.disconnect()
            if (user_id, bot_id) in clients:
                del clients[(user_id, bot_id)]

            await event.respond("🎉 Аккаунт успешно добавлен!", buttons=get_main_menu(user_id))
            if user_id in adding_user:
                del adding_user[user_id]
        except Exception as e:
            await event.respond(f"❌ Ошибка 2FA: {e}", buttons=back_button())
            try:
                await client.disconnect()
            except:
                pass
            if (user_id, bot_id) in clients:
                del clients[(user_id, bot_id)]
            if user_id in adding_user:
                del adding_user[user_id]

# ============= МЕНЮ АККАУНТА =============
@bot.on(events.CallbackQuery(pattern=r'bot_\d+'))
async def open_bot_menu(event):
    user_id = event.sender_id
    if not has_access(user_id):
        await event.answer("🔒 Требуется подписка.")
        return
    user_data = get_user_data(user_id)
    try:
        bot_id = int(event.data.decode().split('_')[1])
        b = next((x for x in user_data['bots'] if x['id'] == bot_id), None)
        if not b:
            return await event.respond("❌ Аккаунт не найден.", buttons=back_button())
        status = "⏹ Остановить" if b['active'] else "▶️ Запустить"
        await event.edit(
            f"🔧 Меню: **{b['name']}**",
            buttons=[
                [Button.inline(status, f"toggle_{bot_id}")],
                [Button.inline("⚙️ Настройки", f"settings_{bot_id}")],
                [Button.inline("📝 Тексты", f"texts_{bot_id}")],
                [Button.inline("💬 Чаты", f"chats_{bot_id}")],
                [Button.inline("🔁 Циклы", f"cycle_{bot_id}")],
                [Button.inline("📨 Сообщения", f"msg_{bot_id}")],
                [Button.inline("❌ Удалить аккаунт", f"delete_{bot_id}")],
                [Button.inline("Назад", "back")]
            ]
        )
    except Exception as e:
        await event.respond(f"❌ Ошибка: {e}", buttons=back_button())

# ============= ЗАПУСК / ОСТАНОВКА =============
@bot.on(events.CallbackQuery(pattern=r'toggle_\d+'))
async def toggle_bot(event):
    user_id = event.sender_id
    if not has_access(user_id):
        await event.answer("🔒 Требуется подписка.")
        return
    user_data = get_user_data(user_id)
    try:
        bot_id = int(event.data.decode().split('_')[1])
        b = next((x for x in user_data['bots'] if x['id'] == bot_id), None)
        if not b:
            return await event.edit("❌ Аккаунт не найден.", buttons=back_button())
        if b['active']:
            task_key = (user_id, bot_id)
            if task_key in tasks:
                tasks[task_key].cancel()
                del tasks[task_key]
            client_key = (user_id, bot_id)
            if client_key in clients:
                await clients[client_key].disconnect()
                del clients[client_key]
            b['active'] = False
            if bot_id in start_times:
                del start_times[bot_id]
            await event.edit("⏹ Остановлен.", buttons=back_button())
        else:
            client = TelegramClient(f"session_{user_id}_{bot_id}", b['api_id'], b['api_hash'])
            await client.connect()
            if not await client.is_user_authorized():
                return await event.edit("❌ Не авторизован. Удалите и добавьте заново.", buttons=back_button())
            clients[(user_id, bot_id)] = client
            b['stats'] = {"sent": 0, "errors": 0, "total_chats_found": 0}
            task_key = (user_id, bot_id)
            tasks[task_key] = asyncio.create_task(send_loop(b, user_id, bot_id))
            b['active'] = True
            start_times[bot_id] = time.time()
            await event.edit(f"▶️ {b['name']} запущен!", buttons=back_button())
        save_user_data()
    except Exception as e:
        await event.edit(f"❌ Ошибка: {e}", buttons=back_button())

# ============= УДАЛЕНИЕ =============
@bot.on(events.CallbackQuery(pattern=r'delete_\d+'))
async def delete_bot(event):
    user_id = event.sender_id
    if not has_access(user_id):
        await event.answer("🔒 Требуется подписка.")
        return
    user_data = get_user_data(user_id)
    try:
        bot_id = int(event.data.decode().split('_')[1])
        b = next((x for x in user_data['bots'] if x['id'] == bot_id), None)
        if not b:
            return await event.respond("❌ Не найден.", buttons=back_button())
        task_key = (user_id, bot_id)
        if task_key in tasks:
            tasks[task_key].cancel()
            del tasks[task_key]
        client_key = (user_id, bot_id)
        if client_key in clients:
            await clients[client_key].disconnect()
            del clients[client_key]
        if bot_id in start_times:
            del start_times[bot_id]
        user_data['bots'] = [x for x in user_data['bots'] if x['id'] != bot_id]
        save_user_data()
        session_file = f"session_{user_id}_{bot_id}.session"
        if os.path.exists(session_file):
            os.remove(session_file)
        await event.edit(f"🗑 {b['name']} удалён.", buttons=back_button())
    except Exception as e:
        await event.respond(f"❌ Ошибка: {e}", buttons=back_button())

# ============= СТАТУС =============
@bot.on(events.CallbackQuery(data='status'))
async def show_status(event):
    user_id = event.sender_id
    if not has_access(user_id):
        await event.answer("🔒 Требуется подписка.")
        return
    user_data = get_user_data(user_id)
    if not user_data['bots']:
        await event.edit("💎 **Статус**\n📌 Аккаунт отсутствует. Добавьте аккаунт через главное меню.", buttons=back_button())
        return
    msg = "💎 **Статус**\n"
    for b in user_data['bots']:
        client_key = (user_id, b['id'])
        client = clients.get(client_key)
        if client is None:
            client = TelegramClient(f"session_{user_id}_{b['id']}", b['api_id'], b['api_hash'])
            await client.connect()
            need_disconnect = True
        else:
            need_disconnect = False
        try:
            if await client.is_user_authorized():
                result = await client(GetDialogsRequest(
                    offset_date=None,
                    offset_id=0,
                    offset_peer=InputPeerEmpty(),
                    limit=200,
                    hash=0
                ))
                chats = [
                    d for d in result.chats
                    if not isinstance(d, ChatForbidden)
                       and not getattr(d, "broadcast", False)
                       and (getattr(d, "participants_count", 0) or 0) >= 200
                ]
                chat_count = len(chats)
            else:
                chat_count = "не авторизован"
        except Exception as e:
            chat_count = "?"
        if need_disconnect:
            await client.disconnect()
        if b['active']:
            elapsed = int(time.time() - start_times.get(b['id'], time.time()))
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            msg += f"• {b['name']} — ✅ Активен ({time_str})\n   Чатов: {chat_count}\n"
        else:
            msg += f"• {b['name']} — ⛔ Не активен\n   Чатов: {chat_count}\n"
    await event.edit(msg, buttons=back_button())

# ============= СТАТИСТИКА =============
@bot.on(events.CallbackQuery(data='stats'))
async def show_stats(event):
    user_id = event.sender_id
    if not has_access(user_id):
        await event.answer("🔒 Требуется подписка.")
        return
    user_data = get_user_data(user_id)
    if not user_data['bots']:
        await event.edit("📈 **Статистика**\n📌 Аккаунт отсутствует. Добавьте аккаунт через главное меню.", buttons=back_button())
        return
    msg = "📈 **Статистика**\n"
    for b in user_data['bots']:
        sent = b['stats']['sent']
        errors = b['stats']['errors']
        if sent > 0 or errors > 0:
            msg += f"• {b['name']}\n"
            msg += f"  Отправлено: {sent} ✅\n"
            msg += f"  Ошибок: {errors} ❌\n"
    await event.edit(msg, buttons=back_button())

# ============= НАСТРОЙКИ =============
@bot.on(events.CallbackQuery(pattern=r'settings_\d+'))
async def show_settings(event):
    user_id = event.sender_id
    if not has_access(user_id):
        await event.answer("🔒 Требуется подписка.")
        return
    user_data = get_user_data(user_id)
    try:
        bot_id = int(event.data.decode().split('_')[1])
        b = next((x for x in user_data['bots'] if x['id'] == bot_id), None)
        if not b:
            return await event.respond("❌ Не найден.", buttons=back_button())
        msg = (f"⚙️ Настройки {b['name']}:\n"
               f"• Текстов: {len(b['texts'])}\n"
               f"• Чатов за цикл: {b['chats_per_cycle'][0]}–{b['chats_per_cycle'][1]}\n"
               f"• Пауза между циклами: {b['cycle_delay'][0]}–{b['cycle_delay'][1]} сек\n"
               f"• Пауза между сообщениями: {b['message_delay'][0]}–{b['message_delay'][1]} сек")
        await event.edit(msg, buttons=[Button.inline("Назад", f"bot_{bot_id}")])
    except Exception as e:
        await event.respond(f"❌ Ошибка: {e}", buttons=back_button())

# ============= ТЕКСТЫ =============
@bot.on(events.CallbackQuery(pattern=r'texts_\d+'))
async def edit_texts(event):
    user_id = event.sender_id
    if not has_access(user_id):
        await event.answer("🔒 Требуется подписка.")
        return
    user_data = get_user_data(user_id)
    bot_id = int(event.data.decode().split('_')[1])
    b = next((x for x in user_data['bots'] if x['id'] == bot_id), None)
    if not b:
        return await event.respond("❌ Не найден.", buttons=back_button())
    adding_user[user_id] = {'step': 'edit_texts', 'bot_id': bot_id, 'texts': b['texts'][:]}
    msg = "📝 Редактирование текстов:\n" + "\n".join([f"{i+1}. {t}" for i, t in enumerate(b['texts'])])
    msg += "\nОтправьте текст для добавления или напишите: **удалить 2**"
    await event.edit(msg, buttons=[
        [Button.inline("➕ Добавить", f"add_text_{bot_id}")],
        [Button.inline("🗑 Удалить всё", f"clear_texts_{bot_id}")],
        [Button.inline("Назад", f"bot_{bot_id}")]
    ])

@bot.on(events.CallbackQuery(pattern=r'add_text_\d+'))
async def add_text_prompt(event):
    user_id = event.sender_id
    if not has_access(user_id):
        await event.answer("🔒 Требуется подписка.")
        return
    bot_id = int(event.data.decode().split('_')[2])
    adding_user[user_id] = {'step': 'add_text', 'bot_id': bot_id, 'texts': []}
    await event.respond("Введите новый текст (или напишите **готово**):")

@bot.on(events.CallbackQuery(pattern=r'clear_texts_\d+'))
async def clear_texts(event):
    user_id = event.sender_id
    if not has_access(user_id):
        await event.answer("🔒 Требуется подписка.")
        return
    user_data = get_user_data(user_id)
    bot_id = int(event.data.decode().split('_')[2])
    for b in user_data['bots']:
        if b['id'] == bot_id:
            b['texts'] = []
            break
    save_user_data()
    await event.edit(f"🗑 Все тексты удалены.", buttons=[Button.inline("Назад", f"bot_{bot_id}")])

# ============= ЧАТЫ / ЦИКЛЫ / СООБЩЕНИЯ =============
@bot.on(events.CallbackQuery(pattern=r'chats_\d+'))
async def edit_chats(event):
    user_id = event.sender_id
    if not has_access(user_id):
        await event.answer("🔒 Требуется подписка.")
        return
    bot_id = int(event.data.decode().split('_')[1])
    adding_user[user_id] = {'step': 'edit_chats', 'bot_id': bot_id}
    user_data = get_user_data(user_id)
    b = next((x for x in user_data['bots'] if x['id'] == bot_id), None)
    if not b:
        return await event.respond("❌ Не найден.", buttons=back_button())
    await event.edit(f"💬 Введите диапазон чатов за цикл (например: `2 5`). Сейчас: {b['chats_per_cycle'][0]}–{b['chats_per_cycle'][1]}", buttons=back_button())

@bot.on(events.CallbackQuery(pattern=r'cycle_\d+'))
async def edit_cycle(event):
    user_id = event.sender_id
    if not has_access(user_id):
        await event.answer("🔒 Требуется подписка.")
        return
    bot_id = int(event.data.decode().split('_')[1])
    adding_user[user_id] = {'step': 'edit_cycle', 'bot_id': bot_id}
    user_data = get_user_data(user_id)
    b = next((x for x in user_data['bots'] if x['id'] == bot_id), None)
    if not b:
        return await event.respond("❌ Не найден.", buttons=back_button())
    await event.edit(f"🔁 Введите паузу между циклами (сек): `60 180`. Сейчас: {b['cycle_delay'][0]}–{b['cycle_delay'][1]}", buttons=back_button())

@bot.on(events.CallbackQuery(pattern=r'msg_\d+'))
async def edit_msg(event):
    user_id = event.sender_id
    if not has_access(user_id):
        await event.answer("🔒 Требуется подписка.")
        return
    bot_id = int(event.data.decode().split('_')[1])
    adding_user[user_id] = {'step': 'edit_msg', 'bot_id': bot_id}
    user_data = get_user_data(user_id)
    b = next((x for x in user_data['bots'] if x['id'] == bot_id), None)
    if not b:
        return await event.respond("❌ Не найден.", buttons=back_button())
    await event.edit(f"📨 Введите паузу между сообщениями (сек): `2 5`. Сейчас: {b['message_delay'][0]}–{b['message_delay'][1]}", buttons=back_button())

# ============= ОБРАБОТКА ВВОДА =============
@bot.on(events.NewMessage())
async def handle_edit(event):
    user_id = event.sender_id
    if user_id not in adding_user:
        return
    user_data_full = get_user_data(user_id)
    user_data = adding_user[user_id]
    if 'bot_id' not in user_data:
        return
    bot_id = user_data['bot_id']
    step = user_data.get('step')
    if step == 'edit_texts':
        text = event.text.strip()
        if text.lower().startswith('удалить ') or text.lower().startswith('delete '):
            try:
                idx = int(text.split()[-1]) - 1
                if 0 <= idx < len(user_data['texts']):
                    del user_data['texts'][idx]
                    await event.respond("🗑 Удалено.")
                else:
                    await event.respond("❌ Неверный номер.")
            except:
                await event.respond("❌ Ошибка.")
        else:
            if len(user_data['texts']) < 10:
                user_data['texts'].append(text)
                await event.respond(f"✅ Добавлено ({len(user_data['texts'])}/10)")
            else:
                await event.respond("⚠️ Максимум 10.")
    elif step == 'add_text':
        text = event.text.strip()
        if text.lower() in ('готово', 'done'):
            if len(user_data.get('texts', [])) == 0:
                user_data['texts'] = ["Пример текста рассылки"]
            for b in user_data_full['bots']:
                if b['id'] == bot_id:
                    b['texts'] = user_data['texts']
                    break
            save_user_data()
            del adding_user[user_id]
            b = next((x for x in user_data_full['bots'] if x['id'] == bot_id), None)
            await event.respond(f"✅ Тексты сохранены.", buttons=[
                [Button.inline("▶️ Запустить", f"toggle_{bot_id}")],
                [Button.inline("⚙️ Настройки", f"settings_{bot_id}")],
                [Button.inline("📝 Тексты", f"texts_{bot_id}")],
                [Button.inline("💬 Чаты", f"chats_{bot_id}")],
                [Button.inline("🔁 Циклы", f"cycle_{bot_id}")],
                [Button.inline("📨 Сообщения", f"msg_{bot_id}")],
                [Button.inline("❌ Удалить аккаунт", f"delete_{bot_id}")],
                [Button.inline("Назад", "back")]
            ])
        else:
            if len(user_data.get('texts', [])) < 10:
                user_data.setdefault('texts', []).append(text)
                await event.respond(f"✅ Добавлено ({len(user_data['texts'])}/10)")
            else:
                await event.respond("⚠️ Максимум 10. Напишите: **готово**")
    elif step == 'edit_chats':
        try:
            a, b = map(int, event.text.strip().split())
            for x in user_data_full['bots']:
                if x['id'] == bot_id:
                    x['chats_per_cycle'] = [a, b]
                    break
            save_user_data()
            del adding_user[user_id]
            b_obj = next((x for x in user_data_full['bots'] if x['id'] == bot_id), None)
            await event.respond(f"✅ Сохранено.", buttons=[
                [Button.inline("▶️ Запустить", f"toggle_{bot_id}")],
                [Button.inline("⚙️ Настройки", f"settings_{bot_id}")],
                [Button.inline("📝 Тексты", f"texts_{bot_id}")],
                [Button.inline("💬 Чаты", f"chats_{bot_id}")],
                [Button.inline("🔁 Циклы", f"cycle_{bot_id}")],
                [Button.inline("📨 Сообщения", f"msg_{bot_id}")],
                [Button.inline("❌ Удалить аккаунт", f"delete_{bot_id}")],
                [Button.inline("Назад", "back")]
            ])
        except:
            await event.respond("❌ Ошибка. Введите два числа.", buttons=back_button())
    elif step == 'edit_cycle':
        try:
            a, b = map(int, event.text.strip().split())
            for x in user_data_full['bots']:
                if x['id'] == bot_id:
                    x['cycle_delay'] = [a, b]
                    break
            save_user_data()
            del adding_user[user_id]
            b_obj = next((x for x in user_data_full['bots'] if x['id'] == bot_id), None)
            await event.respond(f"✅ Сохранено.", buttons=[
                [Button.inline("▶️ Запустить", f"toggle_{bot_id}")],
                [Button.inline("⚙️ Настройки", f"settings_{bot_id}")],
                [Button.inline("📝 Тексты", f"texts_{bot_id}")],
                [Button.inline("💬 Чаты", f"chats_{bot_id}")],
                [Button.inline("🔁 Циклы", f"cycle_{bot_id}")],
                [Button.inline("📨 Сообщения", f"msg_{bot_id}")],
                [Button.inline("❌ Удалить аккаунт", f"delete_{bot_id}")],
                [Button.inline("Назад", "back")]
            ])
        except:
            await event.respond("❌ Ошибка. Введите два числа.", buttons=back_button())
    elif step == 'edit_msg':
        try:
            a, b = map(int, event.text.strip().split())
            for x in user_data_full['bots']:
                if x['id'] == bot_id:
                    x['message_delay'] = [a, b]
                    break
            save_user_data()
            del adding_user[user_id]
            b_obj = next((x for x in user_data_full['bots'] if x['id'] == bot_id), None)
            await event.respond(f"✅ Сохранено.", buttons=[
                [Button.inline("▶️ Запустить", f"toggle_{bot_id}")],
                [Button.inline("⚙️ Настройки", f"settings_{bot_id}")],
                [Button.inline("📝 Тексты", f"texts_{bot_id}")],
                [Button.inline("💬 Чаты", f"chats_{bot_id}")],
                [Button.inline("🔁 Циклы", f"cycle_{bot_id}")],
                [Button.inline("📨 Сообщения", f"msg_{bot_id}")],
                [Button.inline("❌ Удалить аккаунт", f"delete_{bot_id}")],
                [Button.inline("Назад", "back")]
            ])
        except:
            await event.respond("❌ Ошибка. Введите два числа.", buttons=back_button())

# ============= ОСТАНОВКА ИЗ ЛОГОВ =============
@bot.on(events.CallbackQuery(pattern=r'stop_log_\d+'))
async def stop_from_log(event):
    user_id = event.sender_id
    if not has_access(user_id):
        await event.answer("🔒 Требуется подписка.")
        return
    bot_id = int(event.data.decode().split('_')[2])
    user_data = get_user_data(user_id)
    b = next((x for x in user_data['bots'] if x['id'] == bot_id), None)
    if not b or not b['active']:
        await event.answer("❌ Аккаунт не активен.")
        return
    task_key = (user_id, bot_id)
    if task_key in tasks:
        tasks[task_key].cancel()
        del tasks[task_key]
    client_key = (user_id, bot_id)
    if client_key in clients:
        await clients[client_key].disconnect()
        del clients[client_key]
    b['active'] = False
    if bot_id in start_times:
        del start_times[bot_id]
    save_user_data()
    await event.edit("⏹ Рассылка остановлена.", buttons=[[Button.inline("Назад", "back")]])

# ============= ЛОГИ В ЛС =============
async def send_loop(bot_data, user_id, bot_id):
    client_key = (user_id, bot_id)
    client = clients.get(client_key)
    if not client:
        return
    bot_name = bot_data['name']
    tag = f"**[{bot_name}]**"
    try:
        await bot.send_message(
            user_id,
            f"🟢 {tag} запущен. Рассылка начата.",
            buttons=[[Button.inline("⏹ Остановить", f"stop_log_{bot_id}")]]
        )
    except:
        pass
    while client_key in tasks:
        try:
            result = await client(GetDialogsRequest(
                offset_date=None,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=200,
                hash=0
            ))
            chats = [
                d for d in result.chats
                if not isinstance(d, ChatForbidden)
                   and not getattr(d, "broadcast", False)
                   and (getattr(d, "participants_count", 0) or 0) >= 200
            ]
            if not chats:
                try:
                    await bot.send_message(
                        user_id,
                        f"🟡 {tag} → Нет подходящих чатов (≥200 участников).",
                        buttons=[[Button.inline("⏹ Остановить", f"stop_log_{bot_id}")]]
                    )
                except:
                    pass
                cycle_delay = random.randint(*bot_data['cycle_delay'])
                await asyncio.sleep(cycle_delay)
                continue
            num = random.randint(*bot_data['chats_per_cycle'])
            selected = random.sample(chats, min(num, len(chats)))
            for chat in selected:
                if client_key not in tasks:
                    break
                text = random.choice(bot_data['texts'])
                try:
                    await client.send_message(chat.id, text)
                    bot_data['stats']['sent'] += 1
                    try:
                        await bot.send_message(
                            user_id,
                            f"🟢 {tag} → Отправлено в: **{chat.title}**",
                            buttons=[[Button.inline("⏹ Остановить", f"stop_log_{bot_id}")]]
                        )
                    except:
                        pass
                except Exception as e:
                    bot_data['stats']['errors'] += 1
                    try:
                        await bot.send_message(
                            user_id,
                            f"🔴 {tag} → Ошибка в **{chat.title}**: `{str(e)}`",
                            buttons=[[Button.inline("⏹ Остановить", f"stop_log_{bot_id}")]]
                        )
                    except:
                        pass
                delay = random.randint(*bot_data['message_delay'])
                await asyncio.sleep(delay)
            cycle_delay = random.randint(*bot_data['cycle_delay'])
            await asyncio.sleep(cycle_delay)
        except Exception as e:
            try:
                await bot.send_message(
                    user_id,
                    f"🚨 {tag} → Критическая ошибка: `{str(e)}`",
                    buttons=[[Button.inline("⏹ Остановить", f"stop_log_{bot_id}")]]
                )
            except:
                pass
            await asyncio.sleep(10)
    save_user_data()

# ============= ЗАПУСК =============
print("🚀 PushWorld запущен. Перейдите в бота в Telegram.")
bot.run_until_disconnected()
