from database import get_db

class MaterialModel:
    @staticmethod
    def get_all(search=None, category=None, stock_status=None):
        conn = get_db()
        query = '''
            SELECT m.*, (m.current_stock - m.reserved_qty) as available_qty
            FROM materials m
            WHERE 1=1
        '''
        params = []
        if search:
            query += " AND (m.code LIKE ? OR m.name LIKE ? OR m.description LIKE ? OR m.location LIKE ?)"
            s = f"%{search}%"
            params.extend([s, s, s, s])
        if category:
            query += " AND m.category = ?"
            params.append(category)
        if stock_status == 'low':
            query += " AND m.current_stock <= m.min_stock AND m.current_stock > 0"
        elif stock_status == 'out':
            query += " AND m.current_stock = 0"
        elif stock_status == 'sufficient':
            query += " AND m.current_stock > m.min_stock"
        elif stock_status == 'reserved':
            query += " AND m.reserved_qty > 0"

        query += " ORDER BY m.id ASC"
        materials = conn.execute(query, params).fetchall()
        conn.close()
        return materials

    @staticmethod
    def get_by_id(material_id):
        conn = get_db()
        mat = conn.execute('''
            SELECT m.*, (m.current_stock - m.reserved_qty) as available_qty
            FROM materials m WHERE m.id = ?
        ''', (material_id,)).fetchone()
        conn.close()
        return mat

    @staticmethod
    def get_low_stock():
        conn = get_db()
        mats = conn.execute('''
            SELECT m.*, (m.current_stock - m.reserved_qty) as available_qty
            FROM materials m
            WHERE m.current_stock <= m.min_stock
            ORDER BY m.current_stock ASC
        ''').fetchall()
        conn.close()
        return mats

    @staticmethod
    def get_categories():
        conn = get_db()
        cats = conn.execute("SELECT DISTINCT category FROM materials ORDER BY category").fetchall()
        conn.close()
        return [c['category'] for c in cats]

    @staticmethod
    def create(code, name, category, unit, unit_price, min_stock, initial_stock, location, description):
        conn = get_db()
        try:
            conn.execute('''
                INSERT INTO materials (code, name, category, unit, unit_price, min_stock, current_stock, reserved_qty, location, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            ''', (code, name, category, unit, unit_price, min_stock, initial_stock, location, description))
            conn.commit()
            return True, "Thêm vật tư thành công"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def update(material_id, name, category, unit, unit_price, min_stock, location, description):
        conn = get_db()
        try:
            conn.execute('''
                UPDATE materials
                SET name = ?, category = ?, unit = ?, unit_price = ?, min_stock = ?, location = ?, description = ?
                WHERE id = ?
            ''', (name, category, unit, unit_price, min_stock, location, description, material_id))
            conn.commit()
            return True, "Cập nhật vật tư thành công"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def record_goods_receipt(material_id, quantity, supplier_id=None, supplier_name=None, po_id=None, staff_id=None, staff_name=None, notes=""):
        """
        Section 8: Goods Receipt Management
        When confirmed, increases on-hand inventory (current_stock).
        Logs in goods_receipts and stock_transactions.
        """
        conn = get_db()
        try:
            mat = conn.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
            if not mat:
                return False, "Không tìm thấy vật tư"

            prev_stock = mat['current_stock']
            new_stock = prev_stock + quantity

            # Update on-hand inventory
            conn.execute("UPDATE materials SET current_stock = ? WHERE id = ?", (new_stock, material_id))

            # Generate Receipt Code (e.g. GR-2026-0001)
            count = conn.execute("SELECT COALESCE(MAX(id), 0) FROM goods_receipts").fetchone()[0] + 1
            receipt_code = f"GR-2026-{count:04d}"

            conn.execute('''
                INSERT INTO goods_receipts (receipt_code, po_id, material_id, quantity, unit, supplier_id, supplier_name, warehouse_staff_id, warehouse_staff_name, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (receipt_code, po_id, material_id, quantity, mat['unit'], supplier_id, supplier_name, staff_id, staff_name, notes))

            # Log stock transaction
            trans_code = f"GD-IN-{conn.execute('SELECT COALESCE(MAX(id), 0) FROM stock_transactions').fetchone()[0] + 1:05d}"
            conn.execute('''
                INSERT INTO stock_transactions (trans_code, type, material_id, quantity, previous_stock, new_stock, reference_type, reference_id, user_id, notes)
                VALUES (?, 'IN', ?, ?, ?, ?, 'GOODS_RECEIPT', ?, ?, ?)
            ''', (trans_code, material_id, quantity, prev_stock, new_stock, receipt_code, staff_id, notes))

            conn.commit()
            return True, receipt_code
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def record_goods_issue(material_id, quantity, requisition_id=None, recipient_name="N/A", department="N/A", staff_id=None, staff_name=None, notes=""):
        """
        Section 8: Goods Issue Management
        When confirmed, decreases on-hand inventory (current_stock).
        Prevents issuing more than available quantity!
        """
        conn = get_db()
        try:
            mat = conn.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
            if not mat:
                return False, "Không tìm thấy vật tư"

            prev_stock = mat['current_stock']
            reserved = mat['reserved_qty']
            available = prev_stock - reserved

            # Security requirement: Prevent issuing more than available quantity!
            # If issuing for a requisition that had reserved stock, reduce reserved_qty accordingly
            if quantity > prev_stock:
                return False, f"Không thể xuất kho! Số lượng yêu cầu xuất ({quantity} {mat['unit']}) vượt quá tồn kho thực tế ({prev_stock} {mat['unit']})."

            new_stock = prev_stock - quantity
            new_reserved = max(0, reserved - quantity) if requisition_id else reserved

            conn.execute("UPDATE materials SET current_stock = ?, reserved_qty = ? WHERE id = ?", (new_stock, new_reserved, material_id))

            # Generate Issue Code (e.g. GI-2026-0001)
            count = conn.execute("SELECT COALESCE(MAX(id), 0) FROM goods_issues").fetchone()[0] + 1
            issue_code = f"GI-2026-{count:04d}"

            conn.execute('''
                INSERT INTO goods_issues (issue_code, requisition_id, material_id, quantity, unit, recipient_name, department, warehouse_staff_id, warehouse_staff_name, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (issue_code, requisition_id, material_id, quantity, mat['unit'], recipient_name, department, staff_id, staff_name, notes))

            # Log stock transaction
            trans_code = f"GD-OUT-{conn.execute('SELECT COALESCE(MAX(id), 0) FROM stock_transactions').fetchone()[0] + 1:05d}"
            conn.execute('''
                INSERT INTO stock_transactions (trans_code, type, material_id, quantity, previous_stock, new_stock, reference_type, reference_id, user_id, notes)
                VALUES (?, 'OUT', ?, ?, ?, ?, 'GOODS_ISSUE', ?, ?, ?)
            ''', (trans_code, material_id, quantity, prev_stock, new_stock, issue_code, staff_id, notes))

            conn.commit()
            return True, issue_code
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def reserve_material(material_id, quantity):
        conn = get_db()
        try:
            mat = conn.execute("SELECT current_stock, reserved_qty FROM materials WHERE id = ?", (material_id,)).fetchone()
            if not mat:
                return False, "Không tìm thấy vật tư"
            available = mat['current_stock'] - mat['reserved_qty']
            if quantity > available:
                return False, "Không đủ số lượng khả dụng để đặt trước (reserve)"
            conn.execute("UPDATE materials SET reserved_qty = reserved_qty + ? WHERE id = ?", (quantity, material_id))
            conn.commit()
            return True, "Đặt trước thành công"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def get_goods_receipts():
        conn = get_db()
        records = conn.execute('''
            SELECT gr.*, m.code as mat_code, m.name as mat_name
            FROM goods_receipts gr
            JOIN materials m ON gr.material_id = m.id
            ORDER BY gr.created_at DESC
        ''').fetchall()
        conn.close()
        return records

    @staticmethod
    def get_goods_issues():
        conn = get_db()
        records = conn.execute('''
            SELECT gi.*, m.code as mat_code, m.name as mat_name, r.req_code as requisition_code
            FROM goods_issues gi
            JOIN materials m ON gi.material_id = m.id
            LEFT JOIN requisitions r ON gi.requisition_id = r.id
            ORDER BY gi.created_at DESC
        ''').fetchall()
        conn.close()
        return records
