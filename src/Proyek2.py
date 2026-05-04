from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from db_proyek2 import init_db, tambah_produk, get_produk, kurangi_stok
from service_proyek2 import simpan_pesanan, ambil_pesanan, hapus_pesanan

from groq import Groq
from dotenv import load_dotenv
import os
import logging

# LOAD ENV
load_dotenv()

TOKEN = os.getenv("TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

OWNER_ID = 8660243218

client = Groq(api_key=GROQ_API_KEY)

# LOGGING
logging.basicConfig(
    filename='error_log.txt',
    level=logging.ERROR,
    format='%(asctime)s | %(levelname)s | %(message)s'
)

# DATA TAMBAHAN
isi_paket = {
    "Paket Hemat": "Beras 2kg, Minyak 1L, Gula 1kg",
    "Paket Keluarga": "Beras 5kg, Minyak 2L, Gula 2kg, Mie Instan 10"
}

# INIT DB
init_db()
tambah_produk()

# MENU
def menu():
    return ReplyKeyboardMarkup([
        ["📦 Paket", "📊 Stok"]
    ], resize_keyboard=True)

# AI 
def tanya_ai(user_input):
    try:
        data = get_produk()

        produk_text = ""
        for d in data:
            nama = d[0]
            harga = d[1]
            stok = d[2]
            isi = isi_paket.get(nama, "-")

            produk_text += f"{nama} - Rp{harga}\nIsi: {isi}\n(Stok: {stok})\n\n"

        system_prompt = f"""
Kamu adalah Customer Service toko sembako.

DATA PRODUK:
{produk_text}

INFO PEMBAYARAN:
- Transfer BCA: 123456789
- DANA/OVO: 08123456789

ATURAN:
- Jangan mengarang produk
- Jangan ubah harga
- Jawab hanya dari data
- Jika ditanya isi paket → jawab isi paket
- Jika ditanya pembayaran → jawab metode pembayaran
- Jika user mau beli → arahkan klik tombol
- Jika di luar konteks → jawab: "Silakan pilih menu bot"
"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]
        )

        return response.choices[0].message.content

    except Exception as e:
        logging.error(f"AI ERROR: {e}")
        raise e  # biar ketangkep error handler

# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selamat datang!", reply_markup=menu())


# PAKET

async def paket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_produk()
    teks = "📦 DAFTAR PAKET:\n\n"
    keyboard = []

    for d in data:
        nama = d[0]
        harga = d[1]
        stok = d[2]
        isi = isi_paket.get(nama, "-")

        teks += f"{nama} - Rp{harga}\nIsi: {isi}\n(Stok: {stok})\n\n"

        keyboard.append([
            InlineKeyboardButton(f"Beli {nama}", callback_data=f"beli_{nama}")
        ])

    await update.message.reply_text(teks, reply_markup=InlineKeyboardMarkup(keyboard))

# BUTTON
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    if data.startswith("beli_"):
        nama = data.replace("beli_", "")
        simpan_pesanan(user_id, nama)

        keyboard = [[InlineKeyboardButton("💳 Bayar", callback_data="bayar")]]

        await query.edit_message_text(
            f"🛒 Kamu pilih {nama}\nKlik bayar untuk lanjut",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "bayar":
        keyboard = [[InlineKeyboardButton("✅ Konfirmasi", callback_data="konfirmasi")]]

        await query.edit_message_text(
            "💳 Silakan transfer:\n\n"
            "🏦 BCA: 123456789\n"
            "📱 DANA/OVO: 08123456789\n\n"
            "Klik konfirmasi setelah bayar",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "konfirmasi":
        nama = ambil_pesanan(user_id)

        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"🛒 KONFIRMASI\nUser: {user_id}\nProduk: {nama}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ACC", callback_data=f"acc_{user_id}")]
            ])
        )

        await query.edit_message_text("⏳ Menunggu admin...")

    elif data.startswith("acc_"):
        uid = int(data.split("_")[1])
        nama = ambil_pesanan(uid)

        kurangi_stok(nama)

        await context.bot.send_message(
            uid,
            f"✅ Pesanan {nama} berhasil!\nTerima kasih 🙏"
        )

        hapus_pesanan(uid)

        await query.edit_message_text("✔ Pesanan di-ACC")

# STOK
async def stok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_produk()
    teks = "📊 STOK:\n"
    for d in data:
        teks += f"{d[0]}: {d[2]}\n"
    await update.message.reply_text(teks)

# HANDLE CHAT
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    if text == "📦 paket":
        await paket(update, context)
        return

    elif text == "📊 stok":
        await stok(update, context)
        return

    elif "bayar" in text or "transfer" in text:
        await update.message.reply_text(
            "💳 Pembayaran:\nBCA: 123456789\nDANA/OVO: 08123456789"
        )
        return

    # SIMULASI ERROR 
    elif text == "error":
        raise Exception("Simulasi error manual")

    jawaban = tanya_ai(text)
    await update.message.reply_text(jawaban)

# ERROR HANDLER
async def error_handler(update, context):
    logging.error("ERROR TERJADI:", exc_info=context.error)

    try:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"⚠️ ERROR TERJADI:\n{context.error}"
        )
    except:
        pass

# RUN
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT, handle))

app.add_error_handler(error_handler)

app.run_polling()