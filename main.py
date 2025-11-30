import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters, Application
from typing import Dict, Any
import json
# ВАЖНО: Модуль datetime не используется, его можно удалить для чистоты, 
# но я оставил импорт, чтобы не ломать структуру, которую вы скопировали.

# --- КОНСТАНТЫ И НАЧАЛЬНЫЕ ДАННЫЕ ---
BUSINESS_NAME = "Frucino"
MENU: Dict[str, int] = {"Фраппе": 990, "Банановый смузи": 990, "Клубничный смузи": 1050}
# ВНИМАНИЕ: Замените это на ВАШ ID, если 8206672878 не Ваш
YOUR_ID = 8206672878 
ORDER_FILE = "orders.txt"

# ИЗМЕНЕННЫЕ СОСТОЯНИЯ:
CHOOSING_DRINK, CHOOSING_QTY, ADD_MORE_OR_CONTACT, GET_CONTACT, CONFIRM_ORDER = range(5)
users_orders: Dict[int, Dict[str, Any]] = {}

# --- ВАШ ТОКЕН ПРОПИСАН ЗДЕСЬ ---
HARDCODED_TOKEN = "7922104399:AAFFbWZ_naxiiSrAYvvPf91JZ5yuzdFwv7w"
# -----------------------------------

# --- АСИНХРОННЫЕ ФУНКЦИИ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало разговора, приветствие и показ меню."""
    if update.message:
        keyboard = [[InlineKeyboardButton(f"{name} — {price} ₸", callback_data=name)] for name, price in MENU.items()]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"👋 Добро пожаловать в {BUSINESS_NAME}!\nВыберите напиток:", reply_markup=reply_markup)
        
        users_orders[update.message.from_user.id] = {"items": []}
        return CHOOSING_DRINK

async def choose_drink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор напитка из меню."""
    query = update.callback_query
    if query:
        await query.answer()
        drink = query.data
        user_id = query.from_user.id
        
        if user_id not in users_orders:
            users_orders[user_id] = {"items": []}
            
        users_orders[user_id]["items"].append({"drink": drink, "qty": 1})
        context.user_data["current_drink_index"] = len(users_orders[user_id]["items"]) - 1
        
        await query.edit_message_text(f"Вы выбрали **{drink}**. Сколько штук? (Введите число):", parse_mode='Markdown')
        return CHOOSING_QTY

async def choose_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод количества напитка и переходит к выбору 'Добавить еще' / 'Продолжить'."""
    if not update.message: return CHOOSING_QTY
    
    user_id = update.message.from_user.id
    qty_text = update.message.text
    
    if not qty_text or not qty_text.isdigit() or int(qty_text) < 1:
        await update.message.reply_text("❌ Введите корректное количество (целое число > 0).")
        return CHOOSING_QTY
        
    qty = int(qty_text)
    index = context.user_data.get("current_drink_index")
    
    if user_id not in users_orders or index is None:
        await update.message.reply_text("Произошла ошибка с заказом. Начните снова с /start.")
        return ConversationHandler.END

    users_orders[user_id]["items"][index]["qty"] = qty
    
    # Кнопки 'Добавить еще' или 'Продолжить'
    keyboard = [
        [InlineKeyboardButton("Добавить ещё напиток 🍹", callback_data="add_more")],
        [InlineKeyboardButton("Продолжить оформление ✅", callback_data="proceed_to_contact")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    order_summary = "\n".join([
        f"• {item['drink']} x{item['qty']} — {MENU.get(item['drink'], 0) * item['qty']} ₸" 
        for item in users_orders[user_id]["items"]
    ])
    
    await update.message.reply_text(
        f"🛒 **Текущий заказ:**\n{order_summary}\n\nЧто дальше?", 
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return ADD_MORE_OR_CONTACT

async def add_more_or_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор 'Добавить ещё' или переход к сбору контакта."""
    query = update.callback_query
    if not query: return ADD_MORE_OR_CONTACT
    
    await query.answer()
    
    if query.data == "add_more":
        # Вернуться к меню напитков
        keyboard = [[InlineKeyboardButton(f"{name} — {price} ₸", callback_data=name)] for name, price in MENU.items()]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите ещё напиток:", reply_markup=reply_markup)
        return CHOOSING_DRINK
        
    elif query.data == "proceed_to_contact":
        # --- ИСПРАВЛЕННЫЙ БЛОК: ПЕРЕХОД К СБОРУ КОНТАКТОВ ---
        user_id = query.from_user.id
        order = users_orders.get(user_id)
        
        total = sum(MENU.get(item["drink"], 0) * item["qty"] for item in order["items"])

        # 1. Удаляем inline-кнопки из предыдущего сообщения, чтобы они не мешали
        await query.message.edit_reply_markup(reply_markup=None)

        # 2. Создаем ReplyKeyboardMarkup для запроса номера
        keyboard = [
            [KeyboardButton("📲 Поделиться номером телефона", request_contact=True)],
            [KeyboardButton("📝 Ввести имя и адрес текстом")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

        # 3. Отправляем НОВОЕ сообщение с запросом и ReplyKeyboardMarkup
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Ваша корзина собрана.\n💰 **Итого:** {total} ₸\n\n**ОБЯЗАТЕЛЬНЫЙ ШАГ:** Для завершения заказа, пожалуйста, **поделитесь номером телефона** (нажав кнопку) или введите ваше имя и адрес доставки/самовывоза текстом:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        return GET_CONTACT # Переход к новому состоянию

async def get_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Собирает контактные данные (номер или текст) и переходит к выбору доставки."""
    user_id = update.effective_user.id
    order = users_orders.get(user_id)
    contact_info = ""
    
    if not update.message: return GET_CONTACT
    
    if not order:
        await update.message.reply_text("Произошла ошибка с заказом. Начните снова с /start.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    if update.message.contact:
        # 1. Пользователь поделился номером через кнопку
        contact_info = update.message.contact.phone_number
        await update.message.reply_text(f"📞 Номер **{contact_info}** сохранен. Спасибо!", reply_markup=ReplyKeyboardRemove(), parse_mode='Markdown')
        
    elif update.message.text:
        # 2. Пользователь ввел текст (имя, адрес)
        contact_info = update.message.text
        await update.message.reply_text(f"📝 Контактные данные сохранены: **{contact_info}**", reply_markup=ReplyKeyboardRemove(), parse_mode='Markdown')
        
    else:
        # Ошибка ввода
        await update.message.reply_text("❌ Пожалуйста, используйте кнопку 'Поделиться номером' или введите текст вручную.")
        return GET_CONTACT

    # Сохраняем полученные данные в заказ
    users_orders[user_id]["contact"] = contact_info
    
    # Переход к выбору Самовывоза/Доставки (финальное подтверждение)
    keyboard = [
        [InlineKeyboardButton("Самовывоз 🏃‍♂️", callback_data="pickup")],
        [InlineKeyboardButton("Доставка 🚚", callback_data="delivery")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("Выберите способ получения заказа:", reply_markup=reply_markup)
    return CONFIRM_ORDER

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение заказа, отправка уведомления и запись в файл."""
    query = update.callback_query
    if not query: return CONFIRM_ORDER
    
    await query.answer()
    user_id = query.from_user.id
    order = users_orders.get(user_id)
    
    if not order: 
        await query.edit_message_text("Заказ не найден. Начните снова: /start")
        return ConversationHandler.END

    if query.data in ["pickup", "delivery"]:
        # Шаг 1: Отображение сводки заказа с выбором доставки
        order["delivery"] = query.data
        total = sum(MENU.get(item["drink"], 0) * item["qty"] for item in order["items"])
        contact_info = order.get("contact", "Не предоставлен")
        
        order_summary = "\n".join([
            f"• {item['drink']} x{item['qty']} — {MENU.get(item['drink'], 0) * item['qty']} ₸" 
            for item in order["items"]
        ])
        
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить заказ", callback_data="confirm")],
            [InlineKeyboardButton("❌ Отменить заказ", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        delivery_method = 'Самовывоз' if order['delivery'] == 'pickup' else 'Доставка'
        
        await query.edit_message_text(
            f"📋 **Ваш заказ:**\n{order_summary}\n\nСпособ: {delivery_method}\n📞 Контакт: **{contact_info}**\n💰 **Итого:** {total} ₸\n\nПодтвердите заказ:", 
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return CONFIRM_ORDER
        
    if query.data == "confirm":
        # Шаг 2: Финальное подтверждение и отправка уведомления
        total = sum(MENU.get(item["drink"], 0) * item["qty"] for item in order["items"])
        username = query.from_user.username or query.from_user.first_name
        contact_info = order.get("contact", "Не предоставлен")
        
        # УВЕДОМЛЕНИЕ ДЛЯ ВЛАДЕЛЬЦА: Включаем гарантированный контакт!
        order_text = f"🚨 **НОВЫЙ ЗАКАЗ** от @{username} (ID: {user_id}):\n" + \
                     f"📞 **Контакт:** {contact_info}\n" + \
                     "\n".join([f"• {item['drink']} x{item['qty']} — {MENU.get(item['drink'], 0) * item['qty']} ₸" for item in order["items"]])
        order_text += f"\n\nСпособ: {'Самовывоз' if order['delivery']=='pickup' else 'Доставка'}\n💰 **Итого:** {total} ₸"
        
        await context.bot.send_message(chat_id=YOUR_ID, text=order_text, parse_mode='Markdown')
        
        with open(ORDER_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(order, ensure_ascii=False) + "\n")
            
        await query.edit_message_text("🎉 **Ваш заказ подтверждён!** Мы скоро свяжемся с вами для уточнения деталей. Спасибо за покупку!", parse_mode='Markdown')
        
    elif query.data == "cancel":
        await query.edit_message_text("❌ **Заказ отменён.**", parse_mode='Markdown')
        
    users_orders.pop(user_id, None)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выход из ConversationHandler через команду /cancel."""
    if update.message:
        user_id = update.message.from_user.id
        users_orders.pop(user_id, None)
        await update.message.reply_text("Вы отменили заказ. Начните снова с /start.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- БЛОК ЗАПУСКА ПРИЛОЖЕНИЯ ---
if __name__ == "__main__":
    
    TOKEN = os.environ.get("TELEGRAM_TOKEN") or HARDCODED_TOKEN
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
    PORT = int(os.environ.get("PORT", 8080)) 
    
    if not TOKEN:
        print("Ошибка: Токен не найден. Бот не запущен.")
        exit(1)

    app: Application = ApplicationBuilder().token(TOKEN).build()
    
    # ОБНОВЛЕННЫЙ ConversationHandler с 5 состояниями
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING_DRINK: [CallbackQueryHandler(choose_drink, pattern='|'.join(MENU.keys()))],
            CHOOSING_QTY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_qty)],
            ADD_MORE_OR_CONTACT: [CallbackQueryHandler(add_more_or_contact, pattern="^(add_more|proceed_to_contact)$")],
            GET_CONTACT:    [MessageHandler(filters.TEXT | filters.CONTACT, get_contact)],
            CONFIRM_ORDER:  [CallbackQueryHandler(confirm_order, pattern="^(pickup|delivery|confirm|cancel)$")]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    app.add_handler(conv_handler)
    
    # 4. Логика запуска: Webhook или Polling
    
    if WEBHOOK_URL:
        # Режим Webhook для хостингов
        print(f"Бот запущен в режиме Webhook на порту {PORT}...")
        app.run_webhook(
            listen="0.0.0.0", 
            port=PORT,
            url_path=TOKEN, 
            webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
        )
    else:
        # Режим Long Polling для локального запуска
        print("WEBHOOK_URL не установлен. Запуск в режиме Long Polling...")
        app.run_polling(poll_interval=3)