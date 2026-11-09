import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from database import get_db

def reset_to_blank_slate():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Clear all operational transaction tables in correct FK order
    cursor.execute('DELETE FROM purchase_order_items')
    cursor.execute('DELETE FROM purchase_orders')
    cursor.execute('DELETE FROM requisition_items')
    cursor.execute('DELETE FROM requisitions')
    cursor.execute('DELETE FROM stock_transactions')
    cursor.execute('DELETE FROM notifications')
    cursor.execute('DELETE FROM audit_logs')

    # 2. Reset sqlite auto-increment sequences for operational tables
    tables = ('requisitions', 'requisition_items', 'purchase_orders', 'purchase_order_items', 'stock_transactions', 'notifications', 'audit_logs')
    for t in tables:
        cursor.execute("DELETE FROM sqlite_sequence WHERE name = ?", (t,))

    # 3. Keep only the official user accounts
    official_usernames = ('admin', 'lan_nv', 'tau_nv', 'cungung_nv', 'kho_nv', 'lanhdao')
    placeholders = ','.join(['?'] * len(official_usernames))
    cursor.execute(f"DELETE FROM users WHERE username NOT IN ({placeholders})", official_usernames)

    # 4. Restore official materials catalog (10 standard items)
    cursor.execute("DELETE FROM materials")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'materials'")

    materials = [
        ('VT-LAN-01', 'Ống thở khí cao áp lặn biển 50m', 'Thiết bị lặn', 'Cuộn', 4500000, 10, 25, 'Kệ A1-Kho Lặn', 'Dùng cho thợ lặn thi công giàn khoan'),
        ('VT-LAN-02', 'Van giảm áp thở Kirb-Morgan', 'Thiết bị lặn', 'Bộ', 12500000, 5, 8, 'Kệ A2-Kho Lặn', 'Bộ van chuyên dụng thợ lặn sâu'),
        ('VT-LAN-03', 'Que hàn dưới nước Broco UW-1', 'Thiết bị lặn', 'Thùng', 3200000, 15, 30, 'Kệ A3-Kho Lặn', 'Que hàn cắt ngầm đáy biển'),
        ('VT-TAU-01', 'Dầu nhờn hàng hải Shell Melina S30', 'Nhiên liệu - Dầu mỡ', 'Phuy', 18500000, 10, 12, 'Kho Dầu B1', 'Dầu bôi trơn động cơ chính tàu kéo'),
        ('VT-TAU-02', 'Dây buộc tàu cao áp Polypropylene 60mm', 'Vật tư boong', 'Cuộn', 28000000, 4, 3, 'Bãi C1-Vật tư Boong', 'Dây chằng neo tàu công trình VSP-01'),
        ('VT-TAU-03', 'Sơn chống hà đáy tàu Jotun SeaForce', 'Hóa chất - Sơn', 'Thùng', 4800000, 20, 15, 'Kho Sơn C2', 'Sơn bảo dưỡng vỏ tàu bảo vệ đáy'),
        ('VT-BHO-01', 'Bộ áo quần phao cứu sinh hàng hải SOLAS', 'Bảo hộ lao động', 'Bộ', 1800000, 20, 45, 'Kệ D1-Bảo hộ', 'Tiêu chuẩn an toàn ngoài khơi'),
        ('VT-BHO-02', 'Bình dưỡng khí Oxy tinh khiết 40L', 'Bảo hộ lao động', 'Bình', 2200000, 10, 4, 'Kho Khí nén D2', 'Cần tái nạp/mua thêm gấp'),
        ('VT-CKI-01', 'Bộ gioăng mặt bích cao su chịu dầu DN100', 'Cơ khí - Đường ống', 'Bộ', 450000, 30, 85, 'Kệ E1-Cơ khí', 'Phụ tùng thay thế định kỳ van tàu'),
        ('VT-CKI-02', 'Bơm thủy lực áp cao Yuken A37', 'Cơ khí - Thủy lực', 'Cái', 35000000, 2, 1, 'Kho Máy E3', 'Phụ tùng tời cẩu trên tàu')
    ]
    cursor.executemany('''
        INSERT INTO materials (code, name, category, unit, unit_price, min_stock, current_stock, location, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', materials)

    # Restore official 4 suppliers
    cursor.execute("DELETE FROM suppliers")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'suppliers'")
    suppliers = [
        ('NCC-001', 'Công ty CP Kỹ thuật Thiết bị Biển Vũng Tàu', 'Nguyễn Anh Tuấn', '0254.3838999', 'marinetech@vt.vnn.vn', 'Số 45 Lê Lợi, TP. Vũng Tàu', '3500123456', 5),
        ('NCC-002', 'Tổng Công ty Dầu nhờn Petrolimex (PLC)', 'Lê Hữu Phúc', '028.38290001', 'plc_sales@petrolimex.com.vn', 'Số 1 Pasteur, Q.1, TP.HCM', '0100107890', 5),
        ('NCC-003', 'Tập đoàn Thiết bị Lặn & Cứu hộ Hải Dương', 'Đặng Quốc Huy', '0225.3789123', 'haiduong_diving@gmail.com', 'Khu Công Nghiệp Đình Vũ, Hải Phòng', '0200876543', 4),
        ('NCC-004', 'Công ty TNHH Vật tư Hàng hải Hoàng Gia', 'Võ Thị Mai Lan', '0254.3855678', 'hoanggia_marine@vungtau.vn', 'Đường 30/4, P.11, TP. Vũng Tàu', '3500987123', 4)
    ]
    cursor.executemany('''
        INSERT INTO suppliers (code, name, contact_person, phone, email, address, tax_id, rating)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', suppliers)

    conn.commit()

    # Verify counts
    req_cnt = conn.execute('SELECT COUNT(*) FROM requisitions').fetchone()[0]
    po_cnt = conn.execute('SELECT COUNT(*) FROM purchase_orders').fetchone()[0]
    tx_cnt = conn.execute('SELECT COUNT(*) FROM stock_transactions').fetchone()[0]
    notif_cnt = conn.execute('SELECT COUNT(*) FROM notifications').fetchone()[0]
    log_cnt = conn.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0]
    u_cnt = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    mat_cnt = conn.execute('SELECT COUNT(*) FROM materials').fetchone()[0]

    conn.close()

    print("=== DATABASE RESET RESULT ===")
    print(f"Requisitions: {req_cnt}")
    print(f"Purchase Orders: {po_cnt}")
    print(f"Stock Transactions: {tx_cnt}")
    print(f"Notifications: {notif_cnt}")
    print(f"Audit Logs: {log_cnt}")
    print(f"Users kept: {u_cnt}")
    print(f"Materials kept for request dropdown: {mat_cnt}")
    print("SUCCESS: Site is now a blank slate!")

if __name__ == '__main__':
    reset_to_blank_slate()
