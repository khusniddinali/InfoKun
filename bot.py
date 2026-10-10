import asyncio
import logging
import os
import requests
import aiohttp
import feedparser
from typing import Dict
from datetime import datetime, timezone
from PIL import Image
import pytesseract
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, Message
)
from aiogram.client.default import DefaultBotProperties

# --- your secrets live in config.py ---
from config import BOT_TOKEN, ADMINS, OPENWEATHER_KEY, NEWSAPI_KEY, validate_config

# =====================
# BOT INIT (aiogram 3.7+)
# =====================
validate_config()
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD", "tesseract")

logging.basicConfig(level=logging.INFO)

# =====================
# SIMPLE IN-MEMORY STATE
# =====================
# Tracks which submenu a user is in: "main" | "weather" | "prayer"
USER_STATE: Dict[int, str] = {}

# =====================
# MANUAL DATA (admin-updated)
# =====================
EXCHANGE_TEXT = "📊 Joriy kurslar: Hozircha ma'lumot yo‘q. Admin yangilashi kerak."
FUEL_TEXT     = "⛽️ Yonilg‘i narxlari: Hozircha ma'lumot yo‘q. Admin yangilashi kerak."

# =====================
# CITY LISTS & MAPPING
# =====================
CITIES_SHOW = ["Toshkent", "Samarqand", "Buxoro", "Namangan", "Andijon", "Farg‘ona", "Jizzax",
               "Navoiy", "Qashqadaryo", "Sirdaryo", "Surxondaryo", "Xorazm", "Qoraqalpog‘iston"]
CITY_MAP = {
    "Toshkent": "Tashkent",
    "Andijon": "Andijan",
    "Buxoro": "Bukhara",
    CITIES_SHOW[5]: "Fergana",
    "Jizzax": "Jizzakh",
    "Namangan": "Namangan",
    "Navoiy": "Navoiy",
    "Qashqadaryo": "Qarshi",        # API city = Qarshi
    "Samarqand": "Samarkand",
    "Sirdaryo": "Gulistan",         # API city = Gulistan
    "Surxondaryo": "Termez",        # API city = Termez
    "Xorazm": "Urgench",            # API city = Urgench
    CITIES_SHOW[12]: "Nukus",  # API city = Nukus
}

pending_rates = {}

exchange_rates = {}

# =====================
# REPLY KEYBOARDS
# =====================
def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📈 Valyuta kurslari"), KeyboardButton(text="🌤 Ob-havo")],
            [KeyboardButton(text="🕌 Namoz vaqtlari"),  KeyboardButton(text="⛽️ Yonilg‘i narxlari")],
            [KeyboardButton(text="📰 Kun yangiliklari")],
        ],
        resize_keyboard=True
    )

def weather_kb() -> ReplyKeyboardMarkup:
    # includes a special location-request button (works for both weather & prayer)
    rows = [
        [KeyboardButton(text=CITIES_SHOW[0]), KeyboardButton(text=CITIES_SHOW[1])],
        [KeyboardButton(text=CITIES_SHOW[2]), KeyboardButton(text=CITIES_SHOW[3])],
        [KeyboardButton(text=CITIES_SHOW[4]), KeyboardButton(text=CITIES_SHOW[5])],
        [KeyboardButton(text=CITIES_SHOW[6]), KeyboardButton(text=CITIES_SHOW[7])],
        [KeyboardButton(text=CITIES_SHOW[8]), KeyboardButton(text=CITIES_SHOW[9])],
        [KeyboardButton(text=CITIES_SHOW[10]), KeyboardButton(text=CITIES_SHOW[11])],
        [KeyboardButton(text=CITIES_SHOW[12]),],
        [KeyboardButton(text="📍 Joylashuvim", request_location=True)],
        [KeyboardButton(text="⬅️ Asosiy menyu")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def prayer_kb() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=CITIES_SHOW[0]), KeyboardButton(text=CITIES_SHOW[1])],
        [KeyboardButton(text=CITIES_SHOW[2]), KeyboardButton(text=CITIES_SHOW[3])],
        [KeyboardButton(text=CITIES_SHOW[4]), KeyboardButton(text=CITIES_SHOW[5])],
        [KeyboardButton(text=CITIES_SHOW[6]), KeyboardButton(text=CITIES_SHOW[7])],
        [KeyboardButton(text=CITIES_SHOW[8]), KeyboardButton(text=CITIES_SHOW[9])],
        [KeyboardButton(text=CITIES_SHOW[10]), KeyboardButton(text=CITIES_SHOW[11])],
        [KeyboardButton(text=CITIES_SHOW[12])],
        [KeyboardButton(text="📍 Joylashuvim", request_location=True)],
        [KeyboardButton(text="⬅️ Asosiy menyu")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

# =====================
# HELPERS
# =====================

def resolve_city(display_name: str) -> str:
    """Map Uzbek display city to English API city."""
    return CITY_MAP.get(display_name, display_name)

def weather_by_city(city_display: str) -> str:
    city_api = resolve_city(city_display)
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city_api}&appid={OPENWEATHER_KEY}&units=metric&lang=uz"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if str(data.get("cod")) != "200":
            return "❌ Ob-havo ma’lumoti topilmadi yoki vaqtincha mavjud emas."
        name = data.get("name", city_display)
        temp = data["main"]["temp"]
        feels = data["main"]["feels_like"]
        wind = data["wind"]["speed"]
        desc = data["weather"][0]["description"].capitalize()
        hum = data["main"]["humidity"]
        return (f"🌤 <b>{name}</b>\n"
                f"🌡 Harorat: <b>{temp}°C</b> (his: {feels}°C)\n"
                f"💨 Shamol: {wind} m/s\n"
                f"💧 Namlik: {hum}%\n"
                f"☁️ Holat: {desc}")
    except Exception:
        return "⚠️ Ob-havo xizmatiga ulanishda xatolik yuz berdi."

def weather_by_coords(lat: float, lon: float) -> str:
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_KEY}&units=metric&lang=uz"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if str(data.get("cod")) != "200":
            return "❌ Ob-havo ma’lumoti topilmadi."
        name = data.get("name", "Sizning joyingiz")
        temp = data["main"]["temp"]
        desc = data["weather"][0]["description"].capitalize()
        return f"🌤 <b>{name}</b>\n🌡 {temp}°C, {desc}"
    except Exception:
        return "⚠️ Ob-havo xizmatiga ulanishda xatolik yuz berdi."

async def prayer_by_city(city_display: str) -> str:
    try:
        city_api = resolve_city(city_display)
        logging.info(f"[PRAYER] Using prayer_by_city with city='{city_api}'")
        url = f"http://api.aladhan.com/v1/timingsByCity?city={city_api}&country=Uzbekistan&method=2&school=1"
        logging.info(f"[PRAYER] Requesting: {url}")

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.json()

        if data.get("code") != 200:
            logging.error(f"[PRAYER] API error response: {data}")
            return "⚠️ Namoz vaqtlari xizmatiga ulanishda xatolik"

        t = data["data"]["timings"]
        return (
            f"🕌 <b>{city_api} uchun namoz vaqtlari:</b>\n"
            f"🌅 Bomdod: {t['Fajr']}\n"
            f"🌞 Quyosh: {t['Sunrise']}\n"
            f"🌙 Peshin: {t['Dhuhr']}\n"
            f"🌆 Asr: {t['Asr']}\n"
            f"🌃 Shom: {t['Maghrib']}\n"
            f"🌌 Xufton: {t['Isha']}"
        )
    except Exception as e:
        logging.exception("[PRAYER] Exception in prayer_by_city")
        return "⚠️ Namoz vaqtlari xizmatiga ulanishda xatolik"


async def prayer_by_coords(lat: float, lon: float) -> str:
    try:
        logging.info(f"[PRAYER] Using prayer_by_coords with lat={lat}, lon={lon}")
        url = f"http://api.aladhan.com/v1/timings?latitude={lat}&longitude={lon}&method=2&school=1"
        logging.info(f"[PRAYER] Requesting: {url}")

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.json()

        if data.get("code") != 200:
            logging.error(f"[PRAYER] API error response: {data}")
            return "⚠️ Namoz vaqtlari xizmatiga ulanishda xatolik"

        t = data["data"]["timings"]
        return (
            f"🕌 <b>Joylashuvingiz uchun namoz vaqtlari:</b>\n"
            f"🌅 Bomdod: {t['Fajr']}\n"
            f"🌞 Quyosh: {t['Sunrise']}\n"
            f"🌙 Peshin: {t['Dhuhr']}\n"
            f"🌆 Asr: {t['Asr']}\n"
            f"🌃 Shom: {t['Maghrib']}\n"
            f"🌌 Xufton: {t['Isha']}"
        )
    except Exception as e:
        logging.exception("[PRAYER] Exception in prayer_by_coords")
        return "⚠️ Namoz vaqtlari xizmatiga ulanishda xatolik"

def get_local_news(limit=3):
    feeds = [
        "https://kun.uz/news/rss",
        "https://www.gazeta.uz/uz/rss/"
    ]
    articles = []
    for url in feeds:
        feed = feedparser.parse(url)
        for entry in feed.entries[:limit]:
            articles.append(f"🇺🇿 {entry.title}\n🔗 {entry.link}")
    return articles

def get_global_news(limit=3):
    url = f"https://newsapi.org/v2/top-headlines?language=en&apiKey={NEWSAPI_KEY}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    payload = response.json()
    articles = []
    for article in payload.get("articles", [])[:limit]:
        title, link = article.get("title"), article.get("url")
        if title and link:
            articles.append(f"{title}\n{link}")
    return articles

def get_mixed_news():
    local = get_local_news(limit=3)
    global_ = get_global_news(limit=3)
    news = local + global_
    return "\n\n".join(news)

# =====================
# /start and /help
# =====================
@dp.message(Command("start"))
async def cmd_start(m: Message):
    USER_STATE[m.from_user.id] = "main"
    await m.answer(
        "👋 Assalomu alaykum! Men <b>InfoKun</b> botman.\n"
        "Quyidagilardan birini tanlang:",
        reply_markup=main_kb()
    )

@dp.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer(
        "ℹ️ Buyruqlar:\n"
        "/start — asosiy menyu\n"
        "/setrates <matn> — valyuta kurslarini yangilash (admin)\n"
        "/setfuel <matn> — yonilg‘i narxlarini yangilash (admin)"
    )

# =====================
# ADMIN COMMANDS
# =====================

@dp.message(Command(commands=["setratesimg"]))
async def set_rates_img(message: types.Message):
    """
    Handle the /setratesimg <currency> command from an admin.
    The bot will then wait for an image upload to set rates for that currency.
    """
    user_id = message.from_user.id
    # Check if user is an admin
    if user_id not in ADMINS:
        await message.reply("❌ You are not authorized to use this command.")
        return

    # Parse command arguments to get currency code
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Usage: /setratesimg <CURRENCY_CODE> (e.g., /setratesimg USD)")
        return
    currency = parts[1].strip().upper()
    if not currency.isalpha():
        await message.reply("Invalid currency code. Please provide a valid code (e.g., USD).")
        return

    # Set the state: waiting for an image for this currency from this admin
    pending_rates[user_id] = currency
    await message.reply(f"Please send an image with the exchange rates for {currency}.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    """
    Handle photo uploads. If an admin was waiting with /setratesimg,
    download the image, run OCR in background, and update exchange_rates.
    """
    user_id = message.from_user.id
    if user_id not in pending_rates:
        return  # Ignore if user is not in pending state

    currency = pending_rates.pop(user_id)

    # Download file
    photo = message.photo[-1]
    file_path = f"{user_id}_{currency}_rates.jpg"
    try:
        await bot.download(photo, destination=file_path)
    except Exception:
        return await message.reply("❌ Failed to download the image. Please try again.")

    # --- OCR in background thread ---
    def run_ocr(path: str) -> str:
        img = Image.open(path)
        return pytesseract.image_to_string(img)

    try:
        ocr_result = await asyncio.to_thread(run_ocr, file_path)
    except Exception as e:
        return await message.reply(f"❌ OCR error: {e}")

    # Parse OCR lines
    lines = ocr_result.splitlines()
    rates_data = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 3:
            continue

        buy_str, sell_str = parts[-2], parts[-1]
        try:
            buy = float(buy_str.replace(',', '.'))
            sell = float(sell_str.replace(',', '.'))
        except ValueError:
            continue

        bank_name = " ".join(parts[:-2])
        if bank_name:
            rates_data[bank_name] = {"buy": buy, "sell": sell}

    if not rates_data:
        return await message.reply("❌ OCR did not find any valid rates. Please try again with a clearer image.")

    # Update global
    exchange_rates[currency] = rates_data
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    exchange_rates["_last_update"] = {"currency": currency, "time": timestamp}

    # Build summary
    summary_lines = [f"✅ Updated exchange rates for {currency}:"]
    for bank, data in rates_data.items():
        summary_lines.append(f"{bank}: buy {data['buy']:.2f}, sell {data['sell']:.2f}")
    summary = "\n".join(summary_lines)

    await message.reply(summary)

#@dp.message()
#async def fallback_handler(message: types.Message):
    """
    If an admin is expected to send an image but sends something else,
    notify them. (Optional)
    """
 #   user_id = message.from_user.id
  #  if user_id in pending_rates:
   #     await message.reply("❗️ Please upload an image with the rates table or send /cancel to abort.")


@dp.message(Command("setrates"))
async def set_rates(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Sizda bu buyruqni ishlatish huquqi yo‘q.")
        return

    # Expected format:
    # USD,Ipoteka,12450,12510
    # USD,Asaka,12470,12490
    # EUR,Milliy,13500,13600
    lines = message.text.splitlines()[1:]  # Skip the command line
    parsed_rates = {}
    try:
        for line in lines:
            parts = [item.strip() for item in line.split(",")]
            if len(parts) != 4:
                raise ValueError
            currency, bank, buy_text, sell_text = parts
            if not currency.isalpha() or not bank:
                raise ValueError
            buy, sell = float(buy_text), float(sell_text)
            if buy < 0 or sell < 0:
                raise ValueError
            parsed_rates.setdefault(currency.upper(), {})[bank] = {"buy": buy, "sell": sell}
        if not parsed_rates:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer("Invalid format. Use one row per rate: USD,Bank,12450,12510")
        return
    global exchange_rates
    exchange_rates = parsed_rates
    await message.answer("Rates updated successfully.")

@dp.message(Command("setfuel"))
async def cmd_setfuel(m: Message):
    if m.from_user.id not in ADMINS:
        return await m.answer("⛔ Bu buyruq faqat administratorlar uchun.")
    text = m.text.removeprefix("/setfuel").strip()
    global FUEL_TEXT
    if not text:
        return await m.answer("Foydalanish: <code>/setfuel yonilg‘i narxlari matni</code>")
    FUEL_TEXT = text
    await m.answer("✅ Yonilg‘i narxlari yangilandi.")

# =====================
# MAIN MENU HANDLERS (Reply buttons)
# =====================
@dp.message(Command("rates"))
async def show_rates(message: Message):
    # Get whatever variable your /setrates handler is filling
    data = (
        globals().get("exchange_rates")
        or globals().get("currency_data")
        or globals().get("bank_rates")
        or globals().get("parsed_data")
        or {}
    )

    # If nothing set yet → friendly message
    if not isinstance(data, dict) or not data:
        await message.answer(EXCHANGE_TEXT)
        return

    def fmt(x):
        try:
            x = float(x)
            return f"{int(x):,}".replace(",", " ") if x.is_integer() else f"{x:,.2f}".replace(",", " ")
        except Exception:
            return str(x)

    lines = ["💱 <b>Valyuta kurslari</b>\n"]

    for currency, banks in data.items():
        # validate structure
        if not isinstance(banks, dict) or not banks:
            continue
        valid = {
            bank: r for bank, r in banks.items()
            if isinstance(r, dict) and "buy" in r and "sell" in r
        }
        if not valid:
            continue

        # best offers
        best_buy_bank,  best_buy_val  = max(valid.items(), key=lambda kv: float(kv[1]["buy"]))
        best_sell_bank, best_sell_val = min(valid.items(), key=lambda kv: float(kv[1]["sell"]))

        lines.append(f"🔹 <b>{currency}</b>")
        lines.append(f"🔼 Sotib olish (eng yuqori): <b>{best_buy_bank}</b> — {fmt(best_buy_val['buy'])}")
        lines.append(f"🔽 Sotish (eng past): <b>{best_sell_bank}</b> — {fmt(best_sell_val['sell'])}\n")

        # all banks (sorted)
        lines.append("📋 <u>Barcha banklar:</u>")
        for bank, r in sorted(valid.items(), key=lambda kv: kv[0].lower()):
            lines.append(f"  • {bank} — Sotib olish: {fmt(r['buy'])} / Sotish: {fmt(r['sell'])}")
        lines.append("")  # blank line after each currency

    await message.answer("\n".join(lines) if len(lines) > 1 else "📉 Hali ma'lumotlar admin tomonidan kiritilgani yo‘q.")

@dp.message(F.text == "📈 Valyuta kurslari")
async def rates_button(message: Message):
    await show_rates(message)

@dp.message(F.text == "⛽️ Yonilg‘i narxlari")
async def show_fuel(m: Message):
    USER_STATE[m.from_user.id] = "main"
    await m.answer(FUEL_TEXT, reply_markup=main_kb())

@dp.message(F.text == "📰 Kun yangiliklari")
async def news_menu(m: Message):
    try:
        news_text = get_mixed_news()
    except (requests.RequestException, ValueError, KeyError) as exc:
        logging.warning("Could not load news: %s", exc)
        news_text = "News is temporarily unavailable. Please try again later."
    await m.answer(news_text, disable_web_page_preview=True)

@dp.message(F.text == "🌤 Ob-havo")
async def weather_menu_open(m: Message):
    USER_STATE[m.from_user.id] = "weather"
    await m.answer("🌤 Shaharni tanlang yoki <b>📍 Joylashuvim</b> tugmasidan foydalaning:", reply_markup=weather_kb())

@dp.message(F.text == "🕌 Namoz vaqtlari")
async def prayer_menu_open(m: Message):
    USER_STATE[m.from_user.id] = "prayer"
    await m.answer("🕌 Shaharni tanlang yoki <b>📍 Joylashuvim</b> tugmasidan foydalaning:", reply_markup=prayer_kb())

@dp.message(F.text == "⬅️ Asosiy menyu")
async def back_to_main(m: Message):
    USER_STATE[m.from_user.id] = "main"
    await m.answer("Asosiy menyu:", reply_markup=main_kb())

# =====================
# CITY SELECTION (same buttons used in both submenus)
# =====================
@dp.message(F.text.in_(CITIES_SHOW))
async def city_selected(m: Message):
    state = USER_STATE.get(m.from_user.id, "main")
    city = m.text
    if state == "weather":
        await m.answer(weather_by_city(city), reply_markup=weather_kb())
    elif state == "prayer":
        result = await prayer_by_city(city)
        await m.answer(result, reply_markup=prayer_kb())
    else:
        await m.answer("Avval bo‘limni tanlang:", reply_markup=main_kb())

# =====================
# LOCATION HANDLER (shows BOTH: weather + prayer)
# =====================
@dp.message(F.location)
async def location_received(m: Message):
    lat = m.location.latitude
    lon = m.location.longitude

    # weather_by_coords is sync → no await
    w = weather_by_coords(lat, lon)

    # prayer_by_coords is async → must use await
    p = await prayer_by_coords(lat, lon)

    await m.answer(w)
    await m.answer(p)

    # keep user in the last submenu if exists
    state = USER_STATE.get(m.from_user.id, "main")
    kb = (
        weather_kb() if state == "weather"
        else prayer_kb() if state == "prayer"
        else main_kb()
    )
    await m.answer("Tanlovingiz:", reply_markup=kb)

# =====================
# ENTRY POINT
# =====================
async def main():
    print("✅ InfoKun running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
