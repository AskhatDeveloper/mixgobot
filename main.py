import os;
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters, Application
import json, datetime

# --- КОНСТАНТЫ (Без изменений) ---
BUSINESS_NAME = "Frucino"
users_orders = {}
MENU = {"Фраппе":990,"Банановый смузи":990,"Клубничный смузи":1050}
YOUR_ID = 8206672878 # Ваш ID
ORDER_FILE = "orders.txt"

CHOOSING_DRINK, CHOOSING_QTY, DELIVERY, CONFIRM_ORDER = range(4)
users_orders = {}

# --- АСИНХРОННЫЕ ФУНКЦИИ (Без изменений) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(f"{name} — {price} ₸", callback_data=name)] for name, price in MENU.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"👋 Добро пожаловать в {BUSINESS_NAME}!\nВыбери напиток:", reply_markup=reply_markup)
    users_orders[update.message.from_user.id] = {"items":[]}
    return CHOOSING_DRINK

async def choose_drink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    drink = query.data
    user_id = query.from_user.id
    users_orders[user_id]["items"].append({"drink":drink,"qty":1})
    context.user_data["current_drink_index"] = len(users_orders[user_id]["items"])-1
    await query.edit_message_text(f"Вы выбрали {drink}. Сколько штук?")
    return CHOOSING_QTY

async def choose_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    qty_text = update.message.text
    if not qty_text.isdigit() or int(qty_text)<1:
        await update.message.reply_text("❌ Введите корректное количество (число>0).")
        return CHOOSING_QTY
    qty=int(qty_text)
    index=context.user_data["current_drink_index"]
    users_orders[user_id]["items"][index]["qty"]=qty
    keyboard=[[InlineKeyboardButton("Добавить ещё напиток 🍹", callback_data="add_more")],
              [InlineKeyboardButton("Выбрать способ доставки 🚚", callback_data="delivery")]]
    reply_markup=InlineKeyboardMarkup(keyboard)
    order_summary="\n".join([f"{item['drink']} x{item['qty']} — {MENU[item['drink']]*item['qty']} ₸" for item in users_orders[user_id]["items"]])
    await update.message.reply_text(f"🛒 Текущий заказ:\n{order_summary}", reply_markup=reply_markup)
    return DELIVERY

async def delivery_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data=="add_more":
        keyboard=[[InlineKeyboardButton(f"{name} — {price} ₸", callback_data=name)] for name,price in MENU.items()]
        reply_markup=InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите ещё напиток:", reply_markup=reply_markup)
        return CHOOSING_DRINK
    keyboard=[[InlineKeyboardButton("Самовывоз 🏃‍♂️", callback_data="pickup")],
              [InlineKeyboardButton("Доставка 🚚", callback_data="delivery")]]
    reply_markup=InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите способ получения заказа:", reply_markup=reply_markup)
    return CONFIRM_ORDER

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id=query.from_user.id
    order=users_orders.get(user_id)
    if not order: return ConversationHandler.END
    if query.data in ["pickup","delivery"]:
        order["delivery"]=query.data
        total=sum(MENU[item["drink"]]*item["qty"] for item in order["items"])
        order_summary="\n".join([f"{item['drink']} x{item['qty']} — {MENU[item['drink']]*item['qty']} ₸" for item in order["items"]])
        keyboard=[[InlineKeyboardButton("✅ Подтвердить заказ", callback_data="confirm")],
                  [InlineKeyboardButton("❌ Отменить заказ", callback_data="cancel")]]
        reply_markup=InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"📋 Ваш заказ:\n{order_summary}\nСпособ: {'Самовывоз' if order['delivery']=='pickup' else 'Доставка'}\n💰 Итого: {total} ₸\nПодтвердите заказ:", reply_markup=reply_markup)
        return CONFIRM_ORDER
    if query.data=="confirm":
        username=query.from_user.username or query.from_user.first_name
        order_text=f"Новый заказ от @{username}:\n" + "\n".join([f"{item['drink']} x{item['qty']} — {MENU[item['drink']]*item['qty']} ₸" for item in order["items"]])
        order_text+=f"\nСпособ: {'Самовывоз' if order['delivery']=='pickup' else 'Доставка'}\n💰 Итого: {sum(MENU[item['drink']]*item['qty'] for item in order['items'])} ₸"
        await context.bot.send_message(chat_id=YOUR_ID, text=order_text)
        with open(ORDER_FILE,"a",encoding="utf-8") as f:
            f.write(json.dumps(order, ensure_ascii=False)+"\n")
        await query.edit_message_text("🎉 Ваш заказ подтверждён! Спасибо за покупку!")
    else:
        await query.edit_message_text("❌ Заказ отменён.")
    users_orders.pop(user_id,None)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Вы отменили заказ.")
    return ConversationHandler.END

# --- БЛОК ЗАПУСКА (ИЗМЕНЕН) ---
if __name__=="__main__":
    
    # Переменные окружения
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
    PORT = int(os.environ.get("PORT", 8080)) # PORT предоставляет Render
    
    # Проверка, что токен есть
    if not TOKEN:
        print("Ошибка: Переменная окружения TELEGRAM_TOKEN не найдена.")
        exit(1)

    # Инициализация приложения
    app: Application = ApplicationBuilder().token(TOKEN).build()
    
    # Добавление обработчиков (без изменений)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start',start)],
        states={
            CHOOSING_DRINK:[CallbackQueryHandler(choose_drink)],
            CHOOSING_QTY:[MessageHandler(filters.TEXT & ~filters.COMMAND,choose_qty)],
            DELIVERY:[CallbackQueryHandler(delivery_choice)],
            CONFIRM_ORDER:[CallbackQueryHandler(confirm_order)]
        },
        fallbacks=[CommandHandler('cancel',cancel)]
    )
    app.add_handler(conv_handler)
    
    # Логика запуска: Webhook для Render, Polling для локального запуска
    if WEBHOOK_URL:
        # Режим Webhook для Render
        print("Бот запущен в режиме Webhook...")
        app.run_webhook(
            listen="0.0.0.0", # Важно: слушать все внешние интерфейсы
            port=PORT, # Использовать порт, предоставленный Render
            url_path=TOKEN, # Путь Webhook (часто используют токен или случайную строку)
            webhook_url=f"{WEBHOOK_URL}/{TOKEN}" # Полный URL для установки Webhook
        )
    else:
        # Режим Long Polling для локального тестирования
        print("WEBHOOK_URL не установлен. Запуск в режиме Polling...")
        app.run_polling(poll_interval=3)