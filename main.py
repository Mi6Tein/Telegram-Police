from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.ext import CallbackContext
import json
import os

# Словарь для хранения названий команд и кодовых фраз
COMMANDS = {
    "start_patrol": "зарегистрировать патруль",
    "ready_to_patrol": "я готов патрулировать",
    "end_patrol": "закончить патруль",
    "list_interns": "список стажеров",
    "list_patrol": "список патруля"
}

# Список стажеров
interns = {}

# Список доверенных пользователей (по ID)
trusted_users = [1234567890, 1234567876, 123456734]  # Замените на реальные ID доверенных пользователей

# Путь для сохранения данных
DATA_FILE = "data.json"

# Список для записи на патруль
patrol_list = []
patrol_active = False
patrol_message_id = None

# Функция для загрузки данных
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        interns = json.load(file)

    print(interns)

# Сохранение данных
async def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(interns, file, ensure_ascii=False, indent=4)

# Изменение кодовых фраз
async def set_command_phrase(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id in trusted_users:
        if len(context.args) >= 2:
            command = context.args[0]
            phrase = " ".join(context.args[1:])
            if command in COMMANDS:
                COMMANDS[command] = phrase
                await update.message.reply_text(f"Кодовая фраза для команды '{command}' обновлена на: {phrase}")
            else:
                await update.message.reply_text("Команда не найдена.")
        else:
            await update.message.reply_text("Используйте формат: /set_phrase <команда> <новая фраза>.")
    else:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")

# Обработка текстовых сообщений как команд
async def handle_text(update: Update, context: CallbackContext) -> None:
    if not (update.message and update.message.text):
        return

    text = update.message.text.strip().lower()
    # Проверяем, является ли сообщение ответом на завершение патруля
    reply_to_message = update.message.reply_to_message
    if reply_to_message and reply_to_message.message_id == context.chat_data.get("patrol_message_id"):
        # Если это ответ на патруль, вызываем confirm_patrol
        await confirm_patrol(update, context)
        return  # Завершаем обработку, чтобы не обрабатывались другие команды

    # Обработка команд
    if text == COMMANDS["list_interns"]:
        await list_interns(update, context)
    elif text == COMMANDS["start_patrol"]:
        await start_patrol(update, context)
    elif text == COMMANDS["ready_to_patrol"]:
        await add_to_patrol_list(update, context)
    elif text == COMMANDS["end_patrol"]:
        await end_patrol(update, context)
    elif text == COMMANDS["list_patrol"]:
        await list_patrol(update, context)
    else:
        # Если команда не распознана, выводим сообщение
        pass

# Добавление стажеров вручную
async def add_intern(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id in trusted_users:
        if context.args:
            user_mention = context.args[0]
            if user_mention.startswith("@"):  # Проверяем, что это упоминание
                intern_username = user_mention[1:]  # Убираем символ @
                # Проверяем, нет ли этого пользователя уже в списке
                if intern_username not in interns:
                    interns[intern_username] = user_mention
                    await update.message.reply_text(f"Стажер {user_mention} добавлен.")
                    await save_data()
                else:
                    await update.message.reply_text(f"{user_mention} уже в списке стажеров.")
            else:
                await update.message.reply_text("Укажите корректное упоминание пользователя через @.")
        else:
            await update.message.reply_text("Укажите имя пользователя через @.")
    else:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")

# Удаление стажеров вручную
async def remove_intern(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id in trusted_users:
        if context.args:
            user_mention = context.args[0]
            if user_mention.startswith("@"):
                # Ищем стажера по значению в словаре
                matching_key = None
                for key, value in interns.items():
                    if value == user_mention:
                        matching_key = key
                        break

                if matching_key:
                    del interns[matching_key]
                    await update.message.reply_text(f"Стажер {user_mention} удален.")
                    await save_data()
                else:
                    await update.message.reply_text(f"{user_mention} не найден в списке стажеров.")
            else:
                await update.message.reply_text("Укажите корректное упоминание пользователя через @.")
        else:
            await update.message.reply_text("Укажите имя пользователя через @.")
    else:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")


# Отслеживание новых участников
async def new_member(update: Update, context: CallbackContext) -> None:
    for member in update.message.new_chat_members:
        # Если у пользователя есть username, используем его, иначе берем full_name
        user_id = member.id
        username = f"@{member.username}" if member.username else member.full_name

        if user_id not in interns:
            interns[user_id] = username
            update.message.reply_text(f"Добро пожаловать, {username}! Вы добавлены в список стажеров.")
        else:
            update.message.reply_text(f"{username} уже в списке стажеров.")

# Обработка выхода участников
async def member_left(update: Update, context: CallbackContext) -> None:
    user_id = str(update.message.left_chat_member.id)
    if user_id in interns:
        del interns[user_id]
        await update.message.reply_text(f"{update.message.left_chat_member.full_name} удален из списка стажеров.")
        await save_data()

# Обработка команды "Список стажеров"
async def list_interns(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id in trusted_users:
        if interns:
            intern_list = "\n".join([f"{name}" for name in interns.values()])
            await update.message.reply_text(f"Список стажеров:\n{intern_list}")
        else:
            await update.message.reply_text("Список стажеров пуст.")
    else:
        await update.message.reply_text("У вас нет прав для просмотра списка стажеров.")

# Обработка начала записи на патруль
async def start_patrol(update: Update, context: CallbackContext) -> None:
    global patrol_active, patrol_list
    if update.message.from_user.id in trusted_users:
        patrol_active = True
        patrol_list = []
        await update.message.reply_text("Запись на патруль начата. Напишите 'Я готов патрулировать', чтобы записаться.")
    else:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")

# Добавление в список патруля
async def add_to_patrol_list(update: Update, context: CallbackContext) -> None:
    global patrol_list
    if patrol_active:
        user_name = str(update.message.from_user.name)
        if user_name not in patrol_list:
            patrol_list.append(user_name)
            user_name = update.message.from_user.username or update.message.from_user.full_name
            interns[user_name] = f"{user_name}"
            await update.message.reply_text(f"{user_name}, вы добавлены в список патруля.")
        else:
            await update.message.reply_text("Вы уже записаны на патруль.")

# Завершение патруля
async def end_patrol(update: Update, context: CallbackContext) -> None:
    global patrol_active, patrol_list
    if update.message.from_user.id in trusted_users:
        if patrol_active:
            # Завершаем патруль и отправляем сообщение
            patrol_active = False
            patrol_names = [interns.get(user_id, f"{user_id}") for user_id in patrol_list]
            patrol_list_str = "\n".join(patrol_names)
            bot_message = await update.message.reply_text(f"Патруль завершен. Участники:\n{patrol_list_str}\nВсе ли пришли?")

            # Сохраняем ID сообщения в chat_data для последующей проверки
            context.chat_data["patrol_message_id"] = bot_message.message_id
            print(f"Patrol message ID saved: {bot_message.message_id}")
        else:
            await update.message.reply_text("Патруль не начат.")
    else:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")



async def list_patrol(update: Update, context: CallbackContext) -> None:
    global patrol_active, patrol_list
    if update.message.from_user.id in trusted_users:
        if patrol_active:
            patrol_names = [interns.get(user_id, f"@{user_id}") for user_id in patrol_list]
            patrol_list_str = "\n".join(patrol_names)
            message = await update.message.reply_text(
                f"Запись на патруль. Заявки:\n{patrol_list_str}\n")
            context.chat_data["patrol_message_id"] = message.message_id
        else:
            await update.message.reply_text("Патруль не начат.")
    else:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")


# Обработка подтверждения присутствия
async def confirm_patrol(update: Update, context: CallbackContext) -> None:
    global patrol_list

    print('confirm_patrol called')

    # Проверяем, что сообщение является ответом на завершение патруля
    patrol_message_id = context.chat_data.get("patrol_message_id")
    if not patrol_message_id:
        return

    reply_to_message = update.message.reply_to_message
    if not reply_to_message or reply_to_message.message_id != patrol_message_id:
        print('Ignoring message: not a reply to patrol completion message')
        return  # Игнорируем сообщения, которые не являются ответом на сообщение завершения патруля

    # Разбор ответа
    text = update.message.text.strip().lower()
    if text == "да":
        arrived_users = patrol_list
        absent_users = []
    elif text.startswith("да кроме"):
        excluded = set(text.replace("да кроме", "").strip().split())
        arrived_users = [user for user in patrol_list if f"{user}" not in excluded]
        absent_users = [user for user in patrol_list if f"{user}" in excluded]
    elif text == "нет":
        arrived_users = []
        absent_users = patrol_list
    elif text.startswith("нет кроме"):
        included = set(text.replace("нет кроме", "").strip().split())
        arrived_users = [user for user in patrol_list if f"{user}" in included]
        absent_users = [user for user in patrol_list if f"{user}" not in included]
    else:
        await update.message.reply_text("Неправильный формат ответа. Используйте: 'да', 'да кроме @username', 'нет', 'нет кроме @username'.")
        return

    # Удаление пришедших из списка стажеров
    print(interns)
    print(arrived_users)
    for user in arrived_users:
        print('ok1', user)
        if user[1::] in interns:
            print('ok2')
            del interns[user[1::]]

    await save_data()

    print(interns)


    # Уведомление об итогах
    result_message = (
        f"Патруль завершен.\n"
        f"Пришли: {', '.join(arrived_users) if arrived_users else 'никто'}\n"
        f"Не пришли: {', '.join(absent_users) if absent_users else 'никто'}"
    )

    # Очистка списка патруля
    patrol_list.clear()
    context.chat_data["patrol_message_id"] = None  # Сброс ID сообщения1

    await update.message.reply_text(result_message)




# Создание и настройка приложения
application = Application.builder().token("8112479904:AAG-gQ5LhVt7REpzGGfVVnEToGOK8ffah88").build()

# Добавляем обработчики
application.add_handler(CommandHandler("add_intern", add_intern))
application.add_handler(CommandHandler("remove_intern", remove_intern))
application.add_handler(CommandHandler("set_phrase", set_command_phrase))
application.add_handler(CommandHandler("end_patrol", end_patrol)) # Подключаем обработчик для завершения патруля
application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))
application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, member_left))
application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, confirm_patrol))

application.add_handler(MessageHandler(filters.TEXT, handle_text))

# Запуск бота
print('бот запущен')
application.run_polling()


#8112479904:AAG-gQ5LhVt7REpzGGfVVnEToGOK8ffah88
