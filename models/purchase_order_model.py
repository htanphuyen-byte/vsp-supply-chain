from database import get_db
from models.material_model import MaterialModel

class PurchaseOrderModel:
    STATUS_TRANSLATIONS = {
        'waiting_purchase': 'Chờ mua sắm',
        'po_created': 'Đã lập đơn PO',
        'sent_supplier': 'Đã gửi nhà cung cấp',
        'in_transit': 'Đang vận chuyển',
        'partially_received': 'Nhận một phần',
        'fully_received': 'Đã nhận đủ & nhập kho',
        'completed': 'Hoàn thành hợp đồng',
        'cancelled': 'Đã hủy'
    }

    @staticmethod
    def get_all(status=None, search=None):
        conn = get_db()
        query = '''
            SELECT po.*, s.name as supplier_name, s.code as supplier_code, s.phone as supplier_phone,
                   u.full_name as creator_name,
                   r.req_code as requisition_code
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            JOIN users u ON po.created_by = u.id
            LEFT JOIN requisitions r ON po.requisition_id = r.id
            WHERE 1=1
        '''
        params = []
        if status:
            query += " AND po.status = ?"
            params.append(status)
        if search:
            query += " AND (po.po_code LIKE ? OR s.name LIKE ? OR r.req_code LIKE ?)"
            s = f"%{search}%"
            params.extend([s, s, s])

        query += " ORDER BY po.created_at DESC"
        pos = conn.execute(query, params).fetchall()
        conn.close()
        return pos

    @staticmethod
    def get_by_id(po_id):
        conn = get_db()
        po = conn.execute('''
            SELECT po.*, s.name as supplier_name, s.code as supplier_code, s.phone as supplier_phone,
                   s.email as supplier_email, s.address as supplier_address, s.tax_id as supplier_tax_id,
                   u.full_name as creator_name,
                   r.req_code as requisition_code, r.title as requisition_title, r.department as requisition_dept
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            JOIN users u ON po.created_by = u.id
            LEFT JOIN requisitions r ON po.requisition_id = r.id
            WHERE po.id = ?
        ''', (po_id,)).fetchone()

        if not po:
            conn.close()
            return None, []

        items = conn.execute('''
            SELECT poi.*, m.code as mat_code, m.name as mat_name, m.unit as mat_unit
            FROM purchase_order_items poi
            JOIN materials m ON poi.material_id = m.id
            WHERE poi.po_id = ?
        ''', (po_id,)).fetchall()
        conn.close()
        return po, items

    @staticmethod
    def create(requisition_id, supplier_id, created_by, expected_date, notes, items):
        conn = get_db()
        try:
            count = conn.execute("SELECT COALESCE(MAX(id), 0) FROM purchase_orders").fetchone()[0] + 1
            po_code = f"PO-2026-{count:04d}"

            total_amount = sum(float(it['order_qty']) * float(it['unit_price']) for it in items)

            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO purchase_orders (po_code, requisition_id, supplier_id, created_by, total_amount, expected_delivery_date, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, 'po_created', ?)
            ''', (po_code, requisition_id if requisition_id else None, supplier_id, created_by, total_amount, expected_date, notes))

            po_id = cursor.lastrowid

            for it in items:
                cursor.execute('''
                    INSERT INTO purchase_order_items (po_id, material_id, order_qty, unit_price, received_qty)
                    VALUES (?, ?, ?, ?, 0)
                ''', (po_id, it['material_id'], it['order_qty'], it['unit_price']))

            # If linked to a requisition, update status to purchasing
            if requisition_id:
                cursor.execute("UPDATE requisitions SET status = 'purchasing' WHERE id = ?", (requisition_id,))

            conn.commit()
            return True, po_id, po_code
        except Exception as e:
            conn.rollback()
            return False, None, str(e)
        finally:
            conn.close()

    @staticmethod
    def update_status(po_id, new_status, user_id=None, user_name="", notes=""):
        conn = get_db()
        try:
            po = conn.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,)).fetchone()
            if not po:
                return False, "Không tìm thấy đơn hàng"

            # Prevent duplicate inventory increases if already received!
            if po['status'] in ('fully_received', 'completed') and new_status in ('fully_received', 'completed'):
                return False, "Đơn hàng này đã được nhập kho trước đó. Không được nhập trùng lặp!"

            cursor = conn.cursor()

            if new_status == 'fully_received':
                # Update PO status and set actual delivery date
                cursor.execute('''
                    UPDATE purchase_orders
                    SET status = ?, actual_delivery_date = CURRENT_DATE
                    WHERE id = ?
                ''', (new_status, po_id))

                # Process Goods Receipt for each item
                items = cursor.execute("SELECT * FROM purchase_order_items WHERE po_id = ?", (po_id,)).fetchall()
                sup = cursor.execute("SELECT name FROM suppliers WHERE id = ?", (po['supplier_id'],)).fetchone()
                sup_name = sup['name'] if sup else "Nhà cung cấp"

                for it in items:
                    # Update received_qty in po_items
                    cursor.execute("UPDATE purchase_order_items SET received_qty = order_qty WHERE id = ?", (it['id'],))

                    # Update stock via MaterialModel logic
                    mat = cursor.execute("SELECT current_stock, unit FROM materials WHERE id = ?", (it['material_id'],)).fetchone()
                    prev = mat['current_stock']
                    new_val = prev + it['order_qty']
                    cursor.execute("UPDATE materials SET current_stock = ? WHERE id = ?", (new_val, it['material_id']))

                    # Record goods_receipts
                    gr_count = cursor.execute("SELECT COALESCE(MAX(id), 0) FROM goods_receipts").fetchone()[0] + 1
                    gr_code = f"GR-2026-{gr_count:04d}"
                    cursor.execute('''
                        INSERT INTO goods_receipts (receipt_code, po_id, material_id, quantity, unit, supplier_id, supplier_name, warehouse_staff_id, warehouse_staff_name, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (gr_code, po_id, it['material_id'], it['order_qty'], mat['unit'], po['supplier_id'], sup_name, user_id, user_name, f"Nhập kho từ Đơn mua hàng {po['po_code']}"))

                    # Record stock transaction
                    trans_code = f"GD-IN-{cursor.execute('SELECT COALESCE(MAX(id), 0) FROM stock_transactions').fetchone()[0] + 1:05d}"
                    cursor.execute('''
                        INSERT INTO stock_transactions (trans_code, type, material_id, quantity, previous_stock, new_stock, reference_type, reference_id, user_id, notes)
                        VALUES (?, 'IN', ?, ?, ?, ?, 'PURCHASE_ORDER', ?, ?, ?)
                    ''', (trans_code, it['material_id'], it['order_qty'], prev, new_val, po['po_code'], user_id, f"Nhập kho từ PO {po['po_code']}"))

                # If tied to a requisition, update requisition to awaiting_issue
                if po['requisition_id']:
                    cursor.execute("UPDATE requisitions SET status = 'awaiting_issue' WHERE id = ?", (po['requisition_id'],))
                    cursor.execute('''
                        INSERT INTO request_history (requisition_id, status, actor_id, actor_name, actor_role, notes)
                        VALUES (?, 'awaiting_issue', ?, ?, 'warehouse', ?)
                    ''', (po['requisition_id'], user_id, user_name, f"Hàng từ đơn mua {po['po_code']} đã nhập kho, sẵn sàng xuất cấp"))

            else:
                cursor.execute("UPDATE purchase_orders SET status = ? WHERE id = ?", (new_status, po_id))

            conn.commit()
            return True, "Cập nhật trạng thái đơn hàng thành công"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()
