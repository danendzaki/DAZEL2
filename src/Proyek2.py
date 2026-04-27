from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from db_proyek2 import init_db, tambah_produk, get_produk, kurangi_stok
from service_proyek2 import simpan_pesanan, ambil_pesanan, hapus_pesanan

# 🔥 IMPORT AI + ENV
from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

# 🔥 CLIENT GROQ
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

OWNER_ID = 8660243218

# INIT DB
init_db()
tambah_produk()

# MENU
def menu():
    return ReplyKeyboardMarkup([
        ["📦 Paket", "📊 Stok"]
    ], resize_keyboard=True)

# ===================== AI =====================

def tanya_ai(user_input):
    try:
        data = get_produk()

        produk_text = ""
        for d in data:
            produk_text += f"{d[0]} - Rp{d[1]} (stok: {d[2]})\n"

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Kamu adalah customer service UMKM sembako.\n\n"
                        "DATA PRODUK RESMI:\n"
                        f"{produk_text}\n\n"
                        "ATURAN WAJIB:\n"
                        "1. HANYA jawab berdasarkan data di atas.\n"
                        "2. DILARANG menambah produk baru.\n"
                        "3. Jika tidak ada dalam data, arahkan ke menu bot.\n"
                        "4. Jawaban singkat dan jelas.\n"
                    )
                },
                {
                    "role": "user",
                    "content": user_input
                }
            ]
        )

        return response.choices[0].message.content

    except:
        return "⚠️ AI error"

def validasi_jawaban(jawaban):
    data = get_produk()
    nama_produk = [d[0] for d in data]

    for nama in nama_produk:
        if nama.lower() in jawaban.lower():
            return jawaban

    return "Silakan pilih menu yang tersedia di bot."

# ===================== COMMAND =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selamat datang!", reply_markup=menu())

# ===================== FITUR =====================

async def paket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_produk()
    teks = "📦 DAFTAR PAKET:\n\n"
    keyboard = []

    for d in data:
        if d[0] == "Paket Hemat":
            isi = "Beras 2kg, Minyak 1L, Gula 1kg"
        elif d[0] == "Paket Keluarga":
            isi = "Beras 5kg, Minyak 2L, Gula 2kg, Mie Instan 10"
        else:
            isi = "-"

        teks += f"{d[0]} - Rp{d[1]}\nIsi: {isi}\n(Stok: {d[2]})\n\n"

        keyboard.append([
            InlineKeyboardButton(f"Beli {d[0]}", callback_data=f"beli_{d[0]}")
        ])

    await update.message.reply_text(teks, reply_markup=InlineKeyboardMarkup(keyboard))

async def stok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_produk()
    teks = "📊 STOK:\n"
    for d in data:
        teks += f"{d[0]}: {d[2]}\n"
    await update.message.reply_text(teks)

# ===================== BUTTON =====================

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
            "📱 DANA/OVO/GoPay: 08123456789\n\n"
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

# ===================== HANDLE CHAT =====================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    # MENU
    if text == "📦 paket":
        await paket(update, context)
        return

    elif text == "📊 stok":
        await stok(update, context)
        return

    # PRODUK CEPAT
    elif "harga" in text or "paket" in text:
        data = get_produk()
        teks = "📦 DAFTAR PAKET:\n\n"

        for d in data:
            teks += f"{d[0]} - Rp{d[1]} (stok: {d[2]})\n"

        await update.message.reply_text(teks)
        return

    # 🔥 INFO PEMBAYARAN
    elif "bayar" in text or "pembayaran" in text:
        await update.message.reply_text(
            "💳 Pembayaran bisa melalui:\n\n"
            "🏦 BCA: 123456789\n"
            "📱 DANA/OVO/GoPay: 08123456789"
        )
        return

    # 🔥 DETEKSI PEMBAYARAN USER → KIRIM KE ADMIN
    elif "gopay" in text or "dana" in text or "ovo" in text or "transfer" in text:

        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=(
                "💳 NOTIF PEMBAYARAN\n\n"
                f"User: {update.message.from_user.id}\n"
                f"Pesan: {update.message.text}"
            )
        )

        await update.message.reply_text(
            "✅ Pembayaran kamu sedang dicek admin ya 🙏"
        )
        return

    # 🔥 AI FALLBACK
    jawaban = tanya_ai(text)
    jawaban = validasi_jawaban(jawaban)

    await update.message.reply_text(jawaban)

# ===================== RUN =====================

app = ApplicationBuilder().token(os.getenv("TOKEN")).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT, handle))

app.run_polling()