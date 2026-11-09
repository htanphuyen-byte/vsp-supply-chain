import sqlite3
import os
from werkzeug.security import generate_password_hash
from config import Config

def get_db():
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        employee_id TEXT UNIQUE NOT NULL,
        department TEXT NOT NULL,
        position TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        role TEXT NOT NULL CHECK(role IN ('employee', 'procurement', 'warehouse', 'manager', 'admin')),
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        unit TEXT NOT NULL,
        unit_price REAL DEFAULT 0,
        min_stock INTEGER DEFAULT 5,
        current_stock INTEGER DEFAULT 0,
        reserved_qty INTEGER DEFAULT 0,
        location TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        contact_person TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        tax_id TEXT,
        supplied_categories TEXT,
        cooperation_status TEXT DEFAULT 'active' CHECK(cooperation_status IN ('active', 'inactive')),
        rating INTEGER DEFAULT 5,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS requisitions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        req_code TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        department TEXT NOT NULL,
        title TEXT NOT NULL,
        reason TEXT,
        required_date DATE,
        priority TEXT DEFAULT 'normal' CHECK(priority IN ('normal', 'high', 'urgent')),
        status TEXT DEFAULT 'draft' CHECK(status IN ('draft', 'submitted', 'received', 'under_review', 'pending_approval', 'approved', 'rejected', 'purchasing', 'goods_received', 'awaiting_issue', 'dispatched', 'handed_over', 'completed', 'cancelled')),
        manager_note TEXT,
        procurement_note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS requisition_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        requisition_id INTEGER NOT NULL,
        material_id INTEGER NOT NULL,
        requested_qty INTEGER NOT NULL,
        approved_qty INTEGER DEFAULT 0,
        dispatched_qty INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (requisition_id) REFERENCES requisitions(id) ON DELETE CASCADE,
        FOREIGN KEY (material_id) REFERENCES materials(id)
    );

    CREATE TABLE IF NOT EXISTS request_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        requisition_id INTEGER NOT NULL,
        status TEXT NOT NULL,
        actor_id INTEGER,
        actor_name TEXT,
        actor_role TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (requisition_id) REFERENCES requisitions(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS purchase_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_code TEXT UNIQUE NOT NULL,
        requisition_id INTEGER,
        supplier_id INTEGER NOT NULL,
        created_by INTEGER NOT NULL,
        total_amount REAL DEFAULT 0,
        order_date DATE DEFAULT CURRENT_DATE,
        expected_delivery_date DATE,
        actual_delivery_date DATE,
        status TEXT DEFAULT 'waiting_purchase' CHECK(status IN ('waiting_purchase', 'po_created', 'sent_supplier', 'in_transit', 'partially_received', 'fully_received', 'completed', 'cancelled')),
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (requisition_id) REFERENCES requisitions(id),
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
        FOREIGN KEY (created_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS purchase_order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_id INTEGER NOT NULL,
        material_id INTEGER NOT NULL,
        order_qty INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        received_qty INTEGER DEFAULT 0,
        FOREIGN KEY (po_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
        FOREIGN KEY (material_id) REFERENCES materials(id)
    );

    CREATE TABLE IF NOT EXISTS goods_receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_code TEXT UNIQUE NOT NULL,
        po_id INTEGER,
        material_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        unit TEXT NOT NULL,
        supplier_id INTEGER,
        supplier_name TEXT,
        receipt_date DATE DEFAULT CURRENT_DATE,
        warehouse_staff_id INTEGER,
        warehouse_staff_name TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (po_id) REFERENCES purchase_orders(id),
        FOREIGN KEY (material_id) REFERENCES materials(id),
        FOREIGN KEY (warehouse_staff_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS goods_issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        issue_code TEXT UNIQUE NOT NULL,
        requisition_id INTEGER,
        material_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        unit TEXT NOT NULL,
        recipient_name TEXT NOT NULL,
        department TEXT NOT NULL,
        issue_date DATE DEFAULT CURRENT_DATE,
        warehouse_staff_id INTEGER,
        warehouse_staff_name TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (requisition_id) REFERENCES requisitions(id),
        FOREIGN KEY (material_id) REFERENCES materials(id),
        FOREIGN KEY (warehouse_staff_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS stock_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trans_code TEXT UNIQUE NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('IN', 'OUT')),
        material_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        previous_stock INTEGER NOT NULL,
        new_stock INTEGER NOT NULL,
        reference_type TEXT,
        reference_id TEXT,
        user_id INTEGER,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (material_id) REFERENCES materials(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        user_name TEXT,
        action TEXT NOT NULL,
        target_type TEXT,
        target_id TEXT,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        role TEXT,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        link TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ''')

    # Seed baseline users if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        users = [
            ('admin', generate_password_hash('admin123'), 'Quản Trị Viên Hệ Thống', 'VSP-ADM-001', 'Phòng CNTT & Tự Động Hóa', 'Trưởng Ban CNTT', 'admin@vietsov.com.vn', '0912345678', 'admin'),
            ('lan_nv', generate_password_hash('123456'), 'Nguyễn Văn Hải', 'VSP-LAN-012', 'Đội Công Tác Lặn Biển Sâu', 'Thợ lặn kỹ thuật bậc 5', 'hai.nv@vietsov.com.vn', '0988112233', 'employee'),
            ('tau_nv', generate_password_hash('123456'), 'Trần Đình Trọng', 'VSP-TAU-034', 'Hải Đội Tàu Dịch Vụ Dầu Khí', 'Thuyền phó tàu VSP-01', 'trong.td@vietsov.com.vn', '0988445566', 'employee'),
            ('cungung_nv', generate_password_hash('123456'), 'Lê Thị Thu Hương', 'VSP-CU-008', 'Phòng Cung Ứng Vật Tư', 'Chuyên viên cung ứng cao cấp', 'huong.lt@vietsov.com.vn', '0977223344', 'procurement'),
            ('kho_nv', generate_password_hash('123456'), 'Phạm Quốc Bảo', 'VSP-KHO-005', 'Kho Tổng Cảng Dịch Vụ VSP', 'Thủ kho trưởng', 'bao.pq@vietsov.com.vn', '0966334455', 'warehouse'),
            ('lanhdao', generate_password_hash('123456'), 'Vũ Đức Thắng', 'VSP-BGD-002', 'Ban Giám Đốc Xí Nghiệp', 'Phó Giám đốc Kỹ thuật & Cung ứng', 'thang.vd@vietsov.com.vn', '0903112244', 'manager')
        ]
        cursor.executemany('''
            INSERT INTO users (username, password_hash, full_name, employee_id, department, position, email, phone, role)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', users)

    # Seed baseline materials if empty
    cursor.execute("SELECT COUNT(*) FROM materials")
    if cursor.fetchone()[0] == 0:
        materials = [
            ('VT-LAN-01', '[SAMPLE DATA] Ống thở khí cao áp lặn biển 50m', 'Thiết bị lặn', 'Cuộn', 4500000, 10, 25, 0, 'Kệ A1-Kho Lặn', 'Dùng cho thợ lặn thi công giàn khoan'),
            ('VT-LAN-02', '[SAMPLE DATA] Van giảm áp thở Kirb-Morgan', 'Thiết bị lặn', 'Bộ', 12500000, 5, 8, 0, 'Kệ A2-Kho Lặn', 'Bộ van chuyên dụng thợ lặn sâu'),
            ('VT-LAN-03', '[SAMPLE DATA] Que hàn dưới nước Broco UW-1', 'Thiết bị lặn', 'Thùng', 3200000, 15, 30, 0, 'Kệ A3-Kho Lặn', 'Que hàn cắt ngầm đáy biển'),
            ('VT-TAU-01', '[SAMPLE DATA] Dầu nhờn hàng hải Shell Melina S30', 'Nhiên liệu - Dầu mỡ', 'Phuy', 18500000, 10, 12, 0, 'Kho Dầu B1', 'Dầu bôi trơn động cơ chính tàu kéo'),
            ('VT-TAU-02', '[SAMPLE DATA] Dây buộc tàu cao áp Polypropylene 60mm', 'Vật tư boong', 'Cuộn', 28000000, 4, 3, 0, 'Bãi C1-Vật tư Boong', 'Dây chằng neo tàu công trình VSP-01'),
            ('VT-TAU-03', '[SAMPLE DATA] Sơn chống hà đáy tàu Jotun SeaForce', 'Hóa chất - Sơn', 'Thùng', 4800000, 20, 15, 0, 'Kho Sơn C2', 'Sơn bảo dưỡng vỏ tàu bảo vệ đáy'),
            ('VT-BHO-01', '[SAMPLE DATA] Bộ áo quần phao cứu sinh hàng hải SOLAS', 'Bảo hộ lao động', 'Bộ', 1800000, 20, 45, 0, 'Kệ D1-Bảo hộ', 'Tiêu chuẩn an toàn ngoài khơi'),
            ('VT-BHO-02', '[SAMPLE DATA] Bình dưỡng khí Oxy tinh khiết 40L', 'Bảo hộ lao động', 'Bình', 2200000, 10, 4, 0, 'Kho Khí nén D2', 'Cần tái nạp/mua thêm gấp'),
            ('VT-CKI-01', '[SAMPLE DATA] Bộ gioăng mặt bích cao su chịu dầu DN100', 'Cơ khí - Đường ống', 'Bộ', 450000, 30, 85, 0, 'Kệ E1-Cơ khí', 'Phụ tùng thay thế định kỳ van tàu'),
            ('VT-CKI-02', '[SAMPLE DATA] Bơm thủy lực áp cao Yuken A37', 'Cơ khí - Thủy lực', 'Cái', 35000000, 2, 1, 0, 'Kho Máy E3', 'Phụ tùng tời cẩu trên tàu')
        ]
        cursor.executemany('''
            INSERT INTO materials (code, name, category, unit, unit_price, min_stock, current_stock, reserved_qty, location, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', materials)

    # Seed baseline suppliers if empty
    cursor.execute("SELECT COUNT(*) FROM suppliers")
    if cursor.fetchone()[0] == 0:
        suppliers = [
            ('NCC-001', '[SAMPLE DATA] Công ty CP Kỹ thuật Thiết bị Biển Vũng Tàu', 'Nguyễn Anh Tuấn', '0254.3838999', 'marinetech@vt.vnn.vn', 'Số 45 Lê Lợi, TP. Vũng Tàu', '3500123456', 'Thiết bị lặn, Cơ khí - Thủy lực', 'active', 5, 'Nhà cung ứng thiết bị lặn chiến lược'),
            ('NCC-002', '[SAMPLE DATA] Tổng Công ty Dầu nhờn Petrolimex (PLC)', 'Lê Hữu Phúc', '028.38290001', 'plc_sales@petrolimex.com.vn', 'Số 1 Pasteur, Q.1, TP.HCM', '0100107890', 'Nhiên liệu - Dầu mỡ, Hóa chất', 'active', 5, 'Đối tác cung ứng dầu mỡ bôi trơn tàu biển'),
            ('NCC-003', '[SAMPLE DATA] Tập đoàn Thiết bị Lặn & Cứu hộ Hải Dương', 'Đặng Quốc Huy', '0225.3789123', 'haiduong_diving@gmail.com', 'KCN Đình Vũ, Hải Phòng', '0200876543', 'Thiết bị lặn, Bảo hộ lao động', 'active', 4, 'Cung ứng khí nén và đồ bảo hộ cứu sinh'),
            ('NCC-004', '[SAMPLE DATA] Công ty TNHH Vật tư Hàng hải Hoàng Gia', 'Võ Thị Mai Lan', '0254.3855678', 'hoanggia_marine@vungtau.vn', 'Đường 30/4, P.11, TP. Vũng Tàu', '3500987123', 'Vật tư boong, Cơ khí - Đường ống', 'active', 4, 'Chuyên dây buộc tàu và phụ kiện mặt bích')
        ]
        cursor.executemany('''
            INSERT INTO suppliers (code, name, contact_person, phone, email, address, tax_id, supplied_categories, cooperation_status, rating, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', suppliers)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database updated and initialized successfully!")
