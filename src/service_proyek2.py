pending_orders = {}

def simpan_pesanan(user_id, nama):
    pending_orders[user_id] = nama

def ambil_pesanan(user_id):
    return pending_orders.get(user_id)

def hapus_pesanan(user_id):
    if user_id in pending_orders:
        del pending_orders[user_id]