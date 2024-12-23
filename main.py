import sqlite3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import API_TOKEN, ADMIN_ID

bot = telebot.TeleBot(API_TOKEN)

def init_db():
    conn = sqlite3.connect("store.db")
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS products")
    cursor.execute("DROP TABLE IF EXISTS orders")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            price INTEGER NOT NULL,
            description TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            UNIQUE(user_id, product_id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    """)
    conn.commit()
    conn.close()

def add_test_products():
    conn = sqlite3.connect("store.db")
    cursor = conn.cursor()

    test_products = [
        ("Шоколад \"Рошен\"", 50, "Смачний молочний шоколад від Рошен."),
        ("Торт \"Київський\"", 300, "Класичний торт із горіхами та безе.")
    ]

    for product in test_products:
        cursor.execute("""
            INSERT OR IGNORE INTO products (name, price, description)
            VALUES (?, ?, ?)
        """, product)

    conn.commit()
    conn.close()

@bot.message_handler(commands=['catalog'])
def send_catalog(message):
    conn = sqlite3.connect("store.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price FROM products")
    products = cursor.fetchall()
    conn.close()

    if not products:
        bot.reply_to(message, "Каталог порожній. Адміністратор має додати товари.")
        return

    markup = InlineKeyboardMarkup()
    for product in products:
        button_text = f"{product[1]} - {product[2]} грн"
        callback_data = f"product_{product[0]}"
        markup.add(InlineKeyboardButton(button_text, callback_data=callback_data))

    bot.reply_to(message, "📋 Наші товари: "
                          " Щоб дізнатись більше, натисніть на товар."
                          " Щоб замовити товар введіть його номер", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("product_"))
def product_details(call):
    product_id = int(call.data.split("_")[1])
    conn = sqlite3.connect("store.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, price, description FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()

    if product:
        bot.send_message(call.message.chat.id, f"📄 Деталі товару:\n\n"
                                               f"Назва: {product[0]}\n"
                                               f"Ціна: {product[1]} грн\n"
                                               f"Опис: {product[2]}")
    else:
        bot.send_message(call.message.chat.id, "❌ Товар не знайдено.")

    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("product_"))
def product_details(call):
    product_id = int(call.data.split("_")[1])
    conn = sqlite3.connect("store.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, price, description FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()

    if product:
        bot.send_message(call.message.chat.id, f"📄 Деталі товару:\n"
                                             f"Назва: {product[0]}\n"
                                             f"Ціна: {product[1]} грн\n"
                                             f"Опис: {product[2]}\n")
    else:
        bot.send_message(call.message.chat.id, "❌ Товар не знайдено.")

    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: message.text.isdigit())
def handle_order(message):
    product_id = int(message.text)
    conn = sqlite3.connect("store.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()

    if product:
        user_id = message.from_user.id

        try:
            cursor.execute("INSERT INTO orders (user_id, product_id, status) VALUES (?, ?, 'pending')",
                           (user_id, product_id))
            conn.commit()

            order_id = cursor.lastrowid

            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✅ Підтвердити", callback_data=f"confirm_{order_id}"))
            markup.add(InlineKeyboardButton("❌ Скасувати", callback_data=f"cancel_{order_id}"))

            bot.reply_to(message,
                         f"📦 Ви обрали: {product[1]}\n💰 Ціна: {product[2]} грн\n"
                         f"🧾 Номер рахунку: {order_id}\n",
                         reply_markup=markup)
        except sqlite3.IntegrityError:
            bot.reply_to(message, "❌ Ви вже замовили цей товар.")
    else:
        bot.reply_to(message, "❌ Неправильний номер товару. Спробуйте ще раз.")
    conn.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_") or call.data.startswith("cancel_"))
def handle_payment_buttons(call):
    try:
        order_id = int(call.data.split("_")[1])
        action = call.data.split("_")[0]

        conn = sqlite3.connect("store.db")
        cursor = conn.cursor()

        if action == "confirm":
            cursor.execute("UPDATE orders SET status = 'paid' WHERE id = ?", (order_id,))
            conn.commit()
            bot.send_message(call.message.chat.id, f"✅ Оплата за рахунком {order_id} підтверджена!")
        elif action == "cancel":
            cursor.execute("UPDATE orders SET status = 'canceled' WHERE id = ?", (order_id,))
            conn.commit()
            bot.send_message(call.message.chat.id, f"❌ Оплата за рахунком {order_id} скасована.")

        conn.close()
        bot.answer_callback_query(call.id, "Дія виконана.")  # Обов'язкова відповідь
    except Exception as e:
        print(f"Error in handle_payment_buttons: {e}")
        bot.answer_callback_query(call.id, "Сталася помилка.")


@bot.message_handler(commands=['help'])
def send_help(message):
        bot.reply_to(message, "Доступні команди:\n"
            "/start - Почати роботу\n"
            "/catalog - Переглянути каталог товарів\n"
            "/add_item - Додати новий товар (тільки для адміністратора)\n"
            "/remove_item - Видалити товар (тільки для адміністратора)\n"
            "/orders - Переглянути список замовлень (тільки для адміністратора)\n"
            "/help - Список команд\n"
            "/info - Інформація про бот\n")

@bot.message_handler(commands=['info'])
def send_info(message):
    bot.reply_to(message, "Цей бот створений для демонстрації магазину Рошен. Ви можете переглядати каталог, робити замовлення та залишати відгуки!")

@bot.message_handler(commands=['add_item'])
def add_item(message):
    if message.chat.id == ADMIN_ID:
        bot.reply_to(message, "У вас немає доступу до цієї команди.")
        return

    msg = bot.reply_to(message, "Введіть новий товар у форматі: Назва, Ціна, Опис")
    bot.register_next_step_handler(msg, process_add_item)

def process_add_item(message):
    try:
        name, price, description = map(str.strip, message.text.split(",", 2))
        conn = sqlite3.connect("store.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO products (name, price, description) VALUES (?, ?, ?)", (name, int(price), description))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"Товар '{name}' додано успішно!")
    except Exception as e:
        bot.reply_to(message, "❌ Помилка при додаванні товару. Перевірте формат введення.")

@bot.message_handler(commands=['remove_item'])
def remove_item(message):
    if message.chat.id == ADMIN_ID:
        bot.reply_to(message, "У вас немає доступу до цієї команди.")
        return

    msg = bot.reply_to(message, "Введіть ID товару, який потрібно видалити:")
    bot.register_next_step_handler(msg, process_remove_item)

def process_remove_item(message):
    try:
        product_id = int(message.text)
        conn = sqlite3.connect("store.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        if cursor.rowcount == 0:
            bot.reply_to(message, "❌ Товар із таким ID не знайдено.")
        else:
            bot.reply_to(message, "✅ Товар успішно видалено.")
        conn.commit()
        conn.close()
    except ValueError:
        bot.reply_to(message, "❌ ID товару має бути числом.")
    except Exception as e:
        bot.reply_to(message, "❌ Сталася помилка при видаленні товару.")

@bot.message_handler(commands=['orders'])
def view_orders(message):
    if message.chat.id == ADMIN_ID:
        bot.reply_to(message, "У вас немає доступу до цієї команди.")
        return

    conn = sqlite3.connect("store.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT orders.id, products.name, orders.status, orders.user_id
        FROM orders
        JOIN products ON orders.product_id = products.id
    """)
    orders = cursor.fetchall()
    conn.close()

    if not orders:
        bot.reply_to(message, "Список замовлень порожній.")
        return

    orders_text = "\n".join([f"Замовлення ID {o[0]}: {o[1]} (Статус: {o[2]}, User ID: {o[3]})" for o in orders])
    bot.reply_to(message, f"📋 Список замовлень:\n{orders_text}")

@bot.message_handler(commands=['feedback'])
def feedback_start(message):
    msg = bot.reply_to(message, "Напишіть ваш відгук, і ми його отримаємо.")
    bot.register_next_step_handler(msg, handle_feedback)

def handle_feedback(message):
    feedback = message.text
    bot.send_message(ADMIN_ID, f"Новий відгук від {message.chat.username}: {feedback}")
    bot.reply_to(message, "Дякуємо за ваш відгук!")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('/catalog'), KeyboardButton('/help'))
    keyboard.add(KeyboardButton('/info'), KeyboardButton('/feedback'))
    bot.reply_to(message, " Ласкаво просимо до магазину Рошен! 🍬\n"
                          "Використовуйте меню для навігації:", reply_markup=keyboard)

init_db()
add_test_products()
bot.infinity_polling()
