import asyncio
from aiogram.types import InputFile
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import logging
import sqlite3

BOT_TOKEN = "7707802349:AAFIQNJ3ZXZbmCOTjlEhBU79NXK1G9uiyWU"  # O'zgartiring!
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

conn = sqlite3.connect('orders.db')
cursor = conn.cursor()

cursor.execute('DROP TABLE IF EXISTS orders')
cursor.execute('''
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    full_name TEXT,
    username TEXT,
    order_details TEXT,
    phone TEXT,
    status TEXT
)
''')
conn.commit()

# Kategoriyalar va mahsulotlar tuzilmasi
categories = {
    "clothing": "Kiyim-kechak",
    "footwear": "Oyoq kiyim",
    "accessories": "Aksessuarlar",
}

products = {
    "clothing": [
        {  # index 0
            "key": "sweater1",
            "name": "Blaknot",
            "price": 50000,
            "image": "https://drive.google.com/uc?export=view&id=1m2y1jlc7akTXzQx16VziJSPiEBuJqP8q"
        },
        {  # index 1
            "key": "sweater2",
            "name": "Blaknot_2",
            "price": 100000,
            "image": "https://drive.google.com/uc?export=view&id=1m2y1jlc7akTXzQx16VziJSPiEBuJqP8q"


        }
    ],
    "footwear": [
        {
            "key": "shoes1",
            "name": "Shoes",
            "price": 70000,
            "image": "https://cdn.pixabay.com/photo/2016/03/27/22/16/shoes-1284005_960_720.jpg"
        },
        {
            "key": "shoes2",
            "name": "Boots",
            "price": 90000,
            "image": "https://cdn.pixabay.com/photo/2016/11/18/15/11/boots-1837645_960_720.jpg"
        }
    ],
    "accessories": [
        {
            "key": "hat1",
            "name": "Hat",
            "price": 20000,
            "image": "https://cdn.pixabay.com/photo/2017/09/25/13/12/hat-2787789_960_720.jpg"
        },
        {
            "key": "hat2",
            "name": "Scarf",
            "price": 15000,
            "image": "https://cdn.pixabay.com/photo/2018/12/19/20/27/scarf-3881621_960_720.jpg"
        }
    ]
}

user_carts = {}  # user_id: { 'category_key_product_key': quantity }
user_views = {}  # user_id: {'category': str, 'product_index': int, 'quantity': int}

ADMIN_ID = 8081986794

class OrderStates(StatesGroup):
    waiting_for_phone = State()

# Asosiy menyu klaviaturasi
def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="🛍 Kategoriyalar", callback_data="show_categories")
    kb.button(text="📦 Zakazlar", callback_data="show_orders")
    kb.adjust(1)
    return kb.as_markup()

# Kategoriya ro'yxati
def categories_list():
    kb = InlineKeyboardBuilder()
    for key, name in categories.items():
        kb.button(text=name, callback_data=f"category_{key}")
    kb.button(text="⬅️ Ortga", callback_data="back_to_main")
    kb.adjust(1)
    return kb.as_markup()

# Mahsulotlar orasida oldinga-orqaga o'tish tugmalari bilan klaviatura
def product_detail_keyboard(category_key: str, product_index: int, quantity: int):
    kb = InlineKeyboardBuilder()

    # Oldingi va keyingi tugmalar
    products_list = products.get(category_key, [])
    prev_index = product_index - 1 if product_index > 0 else None
    next_index = product_index + 1 if product_index < len(products_list) - 1 else None

    if prev_index is not None:
        kb.button(text="⬅️ Oldingi", callback_data=f"navigate_{category_key}_{prev_index}")
    else:
        kb.button(text=" ", callback_data="noop")  # Bo'sh tugma (bosilmaydi)

    kb.button(text=f"Soni: {quantity}", callback_data="quantity")

    if next_index is not None:
        kb.button(text="Keyingi ➡️", callback_data=f"navigate_{category_key}_{next_index}")
    else:
        kb.button(text=" ", callback_data="noop")

    # Miqdorni kamaytirish/ko'paytirish tugmalari
    kb.button(text="➖", callback_data=f"decrease_{category_key}_{product_index}")
    kb.button(text="➕", callback_data=f"increase_{category_key}_{product_index}")

    # Savatga qo'shish
    kb.button(text="✅ Savatga qo'shish", callback_data=f"addtocart_{category_key}_{product_index}")

    # Ortga tugmasi (kategoriya ro'yxatiga)
    kb.button(text="⬅️ Orqaga", callback_data=f"category_{category_key}")

    kb.adjust(3)
    return kb.as_markup()

# Kategoriya mahsulotlari ro'yxati tugmalari
def product_list(category_key: str):
    kb = InlineKeyboardBuilder()
    for idx, product in enumerate(products.get(category_key, [])):
        kb.button(text=f"{product['name']} - {product['price']} so'm", callback_data=f"product_{category_key}_{idx}")
    kb.button(text="⬅️ Orqaga", callback_data="show_categories")
    kb.adjust(1)
    return kb.as_markup()

def cart_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Ortga", callback_data="back_to_main")
    kb.button(text="📝 Zakaz berish", callback_data="place_order")
    kb.button(text="🗑 Tozalash", callback_data="clear_cart")  # Tozalash tugmasi qo‘shildi
    kb.adjust(3)
    return kb.as_markup()

@dp.callback_query(lambda c: c.data == "clear_cart")
async def clear_cart_handler(call: types.CallbackQuery):
    user_id = call.from_user.id
    user_carts[user_id] = {}  # Savatni bo'shatish

    await call.message.edit_text("Sizning savatingiz tozalandi.", reply_markup=main_menu())
    await call.answer("Savat tozalandi.")


@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user_carts[message.from_user.id] = {}
    user_views[message.from_user.id] = {}
    await message.answer("Assalomu alaykum! Do'kon botiga xush kelibsiz!", reply_markup=main_menu())

@dp.callback_query(lambda c: c.data == "show_categories")
async def show_categories(call: types.CallbackQuery):
    await call.message.edit_text("📂 Kategoriyalar ro'yxati:", reply_markup=categories_list())
    await call.answer()

@dp.callback_query(lambda c: c.data.startswith("category_"))
async def show_category_products(call: types.CallbackQuery):
    category_key = call.data.split("_")[1]
    await call.message.edit_text(f"🛒 {categories[category_key]} mahsulotlari:", reply_markup=product_list(category_key))
    await call.answer()

@dp.callback_query(lambda c: c.data.startswith("product_"))
async def show_product_detail(call: types.CallbackQuery):
    _, category_key, product_index_str = call.data.split("_")
    product_index = int(product_index_str)
    product = products.get(category_key, [])[product_index]

    user_id = call.from_user.id
    if user_id not in user_views:
        user_views[user_id] = {}
    if user_id not in user_carts:
        user_carts[user_id] = {}

    # Hozir ko'rinayotgan mahsulot va miqdorni saqlaymiz
    user_views[user_id] = {
        "category": category_key,
        "product_index": product_index,
        "quantity": user_views[user_id].get("quantity", 1)
    }

    quantity = user_views[user_id]["quantity"]

    media = types.InputMediaPhoto(media=product['image'],
                                  caption=f"📌 {product['name']}\n💰 {product['price']} so'm\n\nSoni: {quantity}",
                                  parse_mode="HTML")

    try:
        await call.message.edit_media(media=media, reply_markup=product_detail_keyboard(category_key, product_index, quantity))
    except Exception:
        await call.message.edit_text(
            f"📌 {product['name']}\n💰 {product['price']} so'm\n\nSoni: {quantity}",
            reply_markup=product_detail_keyboard(category_key, product_index, quantity)
        )
    await call.answer()

@dp.callback_query(lambda c: c.data.startswith("navigate_"))
async def navigate_products(call: types.CallbackQuery):
    _, category_key, product_index_str = call.data.split("_")
    product_index = int(product_index_str)
    user_id = call.from_user.id

    user_views[user_id]["category"] = category_key
    user_views[user_id]["product_index"] = product_index
    user_views[user_id]["quantity"] = 1  # Yangi mahsulotga o'tganda miqdorni 1 ga o'rnatamiz

    product = products.get(category_key, [])[product_index]

    media = types.InputMediaPhoto(media=product['image'],
                                  caption=f"📌 {product['name']}\n💰 {product['price']} so'm\n\nSoni: 1",
                                  parse_mode="HTML")

    try:
        await call.message.edit_media(media=media, reply_markup=product_detail_keyboard(category_key, product_index, 1))
    except Exception:
        await call.message.edit_text(
            f"📌 {product['name']}\n💰 {product['price']} so'm\n\nSoni: 1",
            reply_markup=product_detail_keyboard(category_key, product_index, 1)
        )
    await call.answer()

@dp.callback_query(lambda c: c.data.startswith("decrease_"))
async def decrease_quantity(call: types.CallbackQuery):
    _, category_key, product_index_str = call.data.split("_")
    product_index = int(product_index_str)
    user_id = call.from_user.id

    if user_id not in user_views:
        user_views[user_id] = {}

    quantity = user_views[user_id].get("quantity", 1)
    if quantity > 1:
        user_views[user_id]["quantity"] = quantity - 1
    else:
        user_views[user_id]["quantity"] = 1

    await show_product_detail(call)

@dp.callback_query(lambda c: c.data.startswith("increase_"))
async def increase_quantity(call: types.CallbackQuery):
    _, category_key, product_index_str = call.data.split("_")
    product_index = int(product_index_str)
    user_id = call.from_user.id

    if user_id not in user_views:
        user_views[user_id] = {}

    quantity = user_views[user_id].get("quantity", 1)
    user_views[user_id]["quantity"] = quantity + 1

    await show_product_detail(call)

@dp.callback_query(lambda c: c.data.startswith("addtocart_"))
async def add_to_cart(call: types.CallbackQuery):
    _, category_key, product_index_str = call.data.split("_")
    product_index = int(product_index_str)
    user_id = call.from_user.id

    if user_id not in user_carts:
        user_carts[user_id] = {}

    if user_id not in user_views:
        user_views[user_id] = {"quantity": 1}

    quantity = user_views[user_id].get("quantity", 1)
    if quantity < 1:
        await call.answer("Iltimos, kamida 1 ta mahsulot tanlang.", show_alert=True)
        return

    product = products.get(category_key, [])[product_index]
    cart_key = f"{category_key}_{product['key']}"

    current_qty = user_carts[user_id].get(cart_key, 0)
    user_carts[user_id][cart_key] = current_qty + quantity

    await call.answer(f"{product['name']} savatga qo'shildi. Jami: {user_carts[user_id][cart_key]} ta.")

@dp.callback_query(lambda c: c.data == "show_orders")
async def show_orders(call: types.CallbackQuery):
    user_id = call.from_user.id
    cart = user_carts.get(user_id, {})

    if not cart:
        await call.message.edit_text("Sizning savatingiz bo'sh.", reply_markup=main_menu())
        await call.answer()
        return

    text = "📦 Sizning zakazlaringiz:\n\n"
    total_price = 0
    for cart_key, qty in cart.items():
        category_key, product_key = cart_key.split("_", 1)
        product = next((p for p in products.get(category_key, []) if p["key"] == product_key), None)
        if product:
            price = product['price'] * qty
            total_price += price
            text += f"{product['name']} — {qty} ta — {price} so'm\n"
    text += f"\nUmumiy summa: {total_price} so'm"

    await call.message.edit_text(text, reply_markup=cart_keyboard())
    await call.answer()

@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(call: types.CallbackQuery):
    await call.message.edit_text("🏠 Asosiy menyu:", reply_markup=main_menu())
    await call.answer()

def add_order_to_db(user_id, full_name, username, order_details, phone):
    cursor.execute('''
    INSERT INTO orders (user_id, full_name, username, order_details, phone, status)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, full_name, username, order_details, phone, 'yaratildi'))
    conn.commit()

@dp.callback_query(lambda c: c.data == "place_order")
async def place_order(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    cart = user_carts.get(user_id, {})

    if not cart:
        await call.answer("Sizning savatingiz bo'sh!", show_alert=True)
        return

    await call.message.answer("Iltimos, telefon raqamingizni yuboring.")
    await state.set_state(OrderStates.waiting_for_phone)
    await call.answer()

@dp.message(OrderStates.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()

    if not (phone.startswith('+') or phone[0].isdigit()) or len(phone) < 9:
        await message.answer("Iltimos, telefon raqamingizni to'g'ri kiriting.")
        return

    user_id = message.from_user.id
    cart = user_carts.get(user_id, {})
    if not cart:
        await message.answer("Sizning savatingiz bo'sh.")
        await state.clear()
        return

    order_details = ""
    for cart_key, qty in cart.items():
        category_key, product_key = cart_key.split("_", 1)
        product = next((p for p in products.get(category_key, []) if p["key"] == product_key), None)
        if product:
            order_details += f"{product['name']} - {qty} ta, {product['price'] * qty} so'm\n"

    full_name = message.from_user.full_name or "Noma'lum"
    username = message.from_user.username or "Noma'lum"

    add_order_to_db(user_id, full_name, username, order_details, phone)

    user_carts[user_id] = {}  # Savatni bo'shatish
    user_views[user_id] = {}

    await message.answer("Zakazingiz qabul qilindi. Tez orada siz bilan bog'lanamiz.", reply_markup=main_menu())
    await state.clear()

    # Adminga xabar yuborish
    await bot.send_message(
        ADMIN_ID,
        f"Yangi zakaz:\nFIO: {full_name}\nUsername: @{username}\nTelefon: {phone}\nBuyurtma:\n{order_details}"
    )

@dp.callback_query(lambda c: c.data == "noop")
async def noop_handler(call: types.CallbackQuery):
    await call.answer()

if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
