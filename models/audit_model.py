from database import get_db

class AuditModel:
    @staticmethod
    def log(user_id, user_name, action, target_type, target_id, details):
        conn = get_db()
        try:
            conn.execute('''
                INSERT INTO audit_logs (user_id, user_name, action, target_type, target_id, details)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, user_name, action, target_type, str(target_id), details))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_logs(limit=200, action_filter=None, search=None):
        conn = get_db()
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []
        if action_filter:
            query += " AND action = ?"
            params.append(action_filter)
        if search:
            query += " AND (user_name LIKE ? OR details LIKE ? OR target_id LIKE ?)"
            s = f"%{search}%"
            params.extend([s, s, s])
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        logs = conn.execute(query, params).fetchall()
        conn.close()
        return logs

    @staticmethod
    def add_notification(title, message, user_id=None, role=None, link='/'):
        conn = get_db()
        try:
            conn.execute('''
                INSERT INTO notifications (user_id, role, title, message, link)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, role, title, message, link))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_notifications(user_id=None, role=None, limit=20):
        conn = get_db()
        query = '''
            SELECT * FROM notifications
            WHERE (user_id = ? OR role = ? OR (user_id IS NULL AND role IS NULL))
            ORDER BY created_at DESC LIMIT ?
        '''
        notes = conn.execute(query, (user_id, role, limit)).fetchall()
        conn.close()
        return notes

    @staticmethod
    def mark_notification_read(notif_id):
        conn = get_db()
        try:
            conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
            conn.commit()
        finally:
            conn.close()
