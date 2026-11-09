from database import get_db

class RequisitionModel:
    STATUS_TRANSLATIONS = {
        'draft': 'Bản nháp',
        'submitted': 'Đã gửi (Chờ cung ứng)',
        'received': 'Cung ứng đã tiếp nhận',
        'under_review': 'Đang kiểm tra kho',
        'pending_approval': 'Chờ Lãnh đạo duyệt',
        'approved': 'Lãnh đạo đã phê duyệt',
        'rejected': 'Bị từ chối',
        'purchasing': 'Đang mua sắm (PO)',
        'goods_received': 'Hàng mua đã về kho',
        'awaiting_issue': 'Sẵn sàng xuất kho',
        'dispatched': 'Kho đã xuất cấp',
        'handed_over': 'Đã bàn giao vật tư',
        'completed': 'Hoàn thành toàn bộ',
        'cancelled': 'Đã hủy'
    }

    @staticmethod
    def get_all(user_id=None, role=None, status=None, department=None, search=None, start_date=None, end_date=None):
        conn = get_db()
        query = '''
            SELECT r.*, u.full_name as requester_name, u.department as requester_dept, u.employee_id as requester_emp_id,
                   (SELECT COUNT(*) FROM requisition_items WHERE requisition_id = r.id) as item_count,
                   (SELECT GROUP_CONCAT(m.name, ', ') FROM requisition_items ri JOIN materials m ON ri.material_id = m.id WHERE ri.requisition_id = r.id) as materials_summary
            FROM requisitions r
            JOIN users u ON r.user_id = u.id
            WHERE 1=1
        '''
        params = []
        if role == 'employee' and user_id:
            query += " AND r.user_id = ?"
            params.append(user_id)
        if status:
            query += " AND r.status = ?"
            params.append(status)
        if department:
            query += " AND r.department = ?"
            params.append(department)
        if search:
            query += " AND (r.req_code LIKE ? OR r.title LIKE ? OR r.reason LIKE ? OR u.full_name LIKE ?)"
            s = f"%{search}%"
            params.extend([s, s, s, s])
        if start_date:
            query += " AND r.created_at >= ?"
            params.append(f"{start_date} 00:00:00")
        if end_date:
            query += " AND r.created_at <= ?"
            params.append(f"{end_date} 23:59:59")

        query += " ORDER BY r.created_at DESC"
        reqs = conn.execute(query, params).fetchall()
        conn.close()
        return reqs

    @staticmethod
    def get_by_id(req_id):
        conn = get_db()
        req = conn.execute('''
            SELECT r.*, u.full_name as requester_name, u.department as requester_dept,
                   u.employee_id as requester_emp_id, u.email as requester_email, u.phone as requester_phone
            FROM requisitions r
            JOIN users u ON r.user_id = u.id
            WHERE r.id = ?
        ''', (req_id,)).fetchone()

        if not req:
            conn.close()
            return None, [], []

        items = conn.execute('''
            SELECT ri.*, m.code as mat_code, m.name as mat_name, m.unit as mat_unit,
                   m.category as mat_category, m.current_stock as current_stock,
                   m.reserved_qty as reserved_qty,
                   (m.current_stock - m.reserved_qty) as available_qty,
                   m.min_stock as min_stock, m.unit_price as unit_price
            FROM requisition_items ri
            JOIN materials m ON ri.material_id = m.id
            WHERE ri.requisition_id = ?
        ''', (req_id,)).fetchall()

        history = conn.execute('''
            SELECT * FROM request_history
            WHERE requisition_id = ?
            ORDER BY created_at ASC
        ''', (req_id,)).fetchall()

        conn.close()
        return req, items, history

    @staticmethod
    def create(user_id, department, title, reason, required_date, priority, items, is_draft=False, actor_name="", actor_role="employee"):
        conn = get_db()
        try:
            count = conn.execute("SELECT COALESCE(MAX(id), 0) FROM requisitions").fetchone()[0] + 1
            req_code = f"YCVT-2026-{count:04d}"
            status = 'draft' if is_draft else 'submitted'

            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO requisitions (req_code, user_id, department, title, reason, required_date, priority, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (req_code, user_id, department, title, reason, required_date, priority, status))

            req_id = cursor.lastrowid

            for item in items:
                cursor.execute('''
                    INSERT INTO requisition_items (requisition_id, material_id, requested_qty, approved_qty, status)
                    VALUES (?, ?, ?, ?, 'pending')
                ''', (req_id, item['material_id'], item['quantity'], item['quantity']))

            # Record in request_history
            action_desc = "Tạo bản nháp yêu cầu" if is_draft else "Tạo và gửi yêu cầu cấp phát vật tư"
            cursor.execute('''
                INSERT INTO request_history (requisition_id, status, actor_id, actor_name, actor_role, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (req_id, status, user_id, actor_name, actor_role, action_desc))

            conn.commit()
            return True, req_id, req_code
        except Exception as e:
            conn.rollback()
            return False, None, str(e)
        finally:
            conn.close()

    @staticmethod
    def update_draft(req_id, user_id, title, reason, required_date, priority, items, submit=False, actor_name="", actor_role="employee"):
        conn = get_db()
        try:
            req = conn.execute("SELECT * FROM requisitions WHERE id = ? AND user_id = ?", (req_id, user_id)).fetchone()
            if not req:
                return False, "Không tìm thấy yêu cầu hoặc bạn không có quyền sửa!"
            if req['status'] != 'draft':
                return False, "Chỉ có thể chỉnh sửa yêu cầu khi ở trạng thái Bản nháp (Draft)!"

            new_status = 'submitted' if submit else 'draft'

            cursor = conn.cursor()
            cursor.execute('''
                UPDATE requisitions
                SET title = ?, reason = ?, required_date = ?, priority = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (title, reason, required_date, priority, new_status, req_id))

            # Replace items
            cursor.execute("DELETE FROM requisition_items WHERE requisition_id = ?", (req_id,))
            for item in items:
                cursor.execute('''
                    INSERT INTO requisition_items (requisition_id, material_id, requested_qty, approved_qty, status)
                    VALUES (?, ?, ?, ?, 'pending')
                ''', (req_id, item['material_id'], item['quantity'], item['quantity']))

            note = "Cập nhật và chính thức gửi yêu cầu" if submit else "Cập nhật bản nháp"
            cursor.execute('''
                INSERT INTO request_history (requisition_id, status, actor_id, actor_name, actor_role, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (req_id, new_status, user_id, actor_name, actor_role, note))

            conn.commit()
            return True, req['req_code']
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def update_status(req_id, new_status, actor_id=None, actor_name="", actor_role="", notes="", manager_note=None, procurement_note=None):
        conn = get_db()
        try:
            query = "UPDATE requisitions SET status = ?, updated_at = CURRENT_TIMESTAMP"
            params = [new_status]
            if manager_note is not None:
                query += ", manager_note = ?"
                params.append(manager_note)
            if procurement_note is not None:
                query += ", procurement_note = ?"
                params.append(procurement_note)
            query += " WHERE id = ?"
            params.append(req_id)

            cursor = conn.cursor()
            cursor.execute(query, params)

            # Record in request_history for audit
            cursor.execute('''
                INSERT INTO request_history (requisition_id, status, actor_id, actor_name, actor_role, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (req_id, new_status, actor_id, actor_name, actor_role, notes))

            conn.commit()
            return True, "Cập nhật trạng thái thành công"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def check_stock_feasibility(req_id):
        conn = get_db()
        items = conn.execute('''
            SELECT ri.requested_qty, m.current_stock, m.reserved_qty,
                   (m.current_stock - m.reserved_qty) as available_qty, m.name, m.unit
            FROM requisition_items ri
            JOIN materials m ON ri.material_id = m.id
            WHERE ri.requisition_id = ?
        ''', (req_id,)).fetchall()
        conn.close()

        all_sufficient = True
        shortages = []
        for it in items:
            avail = it['available_qty']
            if avail < it['requested_qty']:
                all_sufficient = False
                shortages.append({
                    'name': it['name'],
                    'unit': it['unit'],
                    'need': it['requested_qty'],
                    'have': it['current_stock'],
                    'available': avail,
                    'shortage': it['requested_qty'] - max(0, avail)
                })
        return all_sufficient, shortages
