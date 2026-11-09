from database import get_db

class SupplierModel:
    @staticmethod
    def get_all(search=None, status=None, category=None):
        conn = get_db()
        query = "SELECT * FROM suppliers WHERE 1=1"
        params = []
        if search:
            query += " AND (code LIKE ? OR name LIKE ? OR contact_person LIKE ? OR phone LIKE ? OR tax_id LIKE ?)"
            s = f"%{search}%"
            params.extend([s, s, s, s, s])
        if status:
            query += " AND cooperation_status = ?"
            params.append(status)
        if category:
            query += " AND supplied_categories LIKE ?"
            params.append(f"%{category}%")

        query += " ORDER BY id ASC"
        suppliers = conn.execute(query, params).fetchall()
        conn.close()
        return suppliers

    @staticmethod
    def get_by_id(supplier_id):
        conn = get_db()
        sup = conn.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
        conn.close()
        return sup

    @staticmethod
    def create(name, contact_person, phone, email, address, tax_id, supplied_categories, cooperation_status='active', rating=5, notes=""):
        conn = get_db()
        try:
            count = conn.execute("SELECT COALESCE(MAX(id), 0) FROM suppliers").fetchone()[0] + 1
            code = f"NCC-{count:04d}"

            conn.execute('''
                INSERT INTO suppliers (code, name, contact_person, phone, email, address, tax_id, supplied_categories, cooperation_status, rating, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (code, name, contact_person, phone, email, address, tax_id, supplied_categories, cooperation_status, rating, notes))
            conn.commit()
            return True, code
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def update(supplier_id, name, contact_person, phone, email, address, tax_id, supplied_categories, cooperation_status, rating, notes):
        conn = get_db()
        try:
            conn.execute('''
                UPDATE suppliers
                SET name = ?, contact_person = ?, phone = ?, email = ?, address = ?, tax_id = ?,
                    supplied_categories = ?, cooperation_status = ?, rating = ?, notes = ?
                WHERE id = ?
            ''', (name, contact_person, phone, email, address, tax_id, supplied_categories, cooperation_status, rating, notes, supplier_id))
            conn.commit()
            return True, "Cập nhật nhà cung cấp thành công"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def delete_or_deactivate(supplier_id):
        """
        Section 9: If a supplier is linked to existing purchase orders or transactions,
        do not permanently delete. Mark as inactive (No Longer Cooperating).
        """
        conn = get_db()
        try:
            # Check if linked to POs
            linked_po = conn.execute("SELECT COUNT(*) FROM purchase_orders WHERE supplier_id = ?", (supplier_id,)).fetchone()[0]
            linked_gr = conn.execute("SELECT COUNT(*) FROM goods_receipts WHERE supplier_id = ?", (supplier_id,)).fetchone()[0]

            if linked_po > 0 or linked_gr > 0:
                conn.execute("UPDATE suppliers SET cooperation_status = 'inactive' WHERE id = ?", (supplier_id,))
                conn.commit()
                return True, "Nhà cung cấp đã có giao dịch lịch sử nên được chuyển sang trạng thái 'Ngừng hợp tác' thay vì xóa hoàn toàn."
            else:
                conn.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
                conn.commit()
                return True, "Đã xóa nhà cung cấp thành công."
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()
