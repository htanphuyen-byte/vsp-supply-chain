import re
from database import get_db
from werkzeug.security import check_password_hash, generate_password_hash

class UserModel:
    @staticmethod
    def get_by_id(user_id):
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        return user

    @staticmethod
    def get_by_username_or_email(identifier):
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ? OR email = ?", (identifier, identifier)).fetchone()
        conn.close()
        return user

    @staticmethod
    def authenticate(identifier, password):
        user = UserModel.get_by_username_or_email(identifier)
        if user and user['is_active'] and check_password_hash(user['password_hash'], password):
            return user
        return None

    @staticmethod
    def get_all(search=None):
        conn = get_db()
        query = "SELECT * FROM users WHERE 1=1"
        params = []
        if search:
            query += " AND (username LIKE ? OR full_name LIKE ? OR employee_id LIKE ? OR email LIKE ? OR department LIKE ?)"
            s = f"%{search}%"
            params.extend([s, s, s, s, s])
        query += " ORDER BY created_at DESC"
        users = conn.execute(query, params).fetchall()
        conn.close()
        return users

    @staticmethod
    def register(full_name, employee_id, department, position, email, phone, username, password, confirm_password):
        # 1. Validation checks
        if not full_name or not employee_id or not department or not position or not email or not username or not password:
            return False, "Vui lòng điền đầy đủ các thông tin bắt buộc!"

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return False, "Định dạng email công ty không hợp lệ!"

        if password != confirm_password:
            return False, "Mật khẩu xác nhận không khớp!"

        if len(password) < 6:
            return False, "Mật khẩu phải có độ dài tối thiểu từ 6 ký tự!"

        conn = get_db()
        try:
            # Check unique username
            if conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone():
                return False, f"Tên đăng nhập '{username}' đã tồn tại trong hệ thống!"

            # Check unique email
            if conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
                return False, f"Email '{email}' đã được đăng ký!"

            # Check unique employee_id
            if conn.execute("SELECT id FROM users WHERE employee_id = ?", (employee_id,)).fetchone():
                return False, f"Mã nhân viên '{employee_id}' đã tồn tại trong hệ thống!"

            # Automatic account activation & default role: EMPLOYEE
            # Users CANNOT choose their own role on registration
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (username, password_hash, full_name, employee_id, department, position, email, phone, role, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'employee', 1)
            ''', (username, generate_password_hash(password), full_name, employee_id, department, position, email, phone))
            
            user_id = cursor.lastrowid
            conn.commit()
            return True, user_id
        except Exception as e:
            conn.rollback()
            return False, f"Lỗi hệ thống: {str(e)}"
        finally:
            conn.close()

    @staticmethod
    def update_user_by_admin(user_id, role, is_active, full_name=None, department=None, position=None, phone=None, email=None):
        conn = get_db()
        try:
            query = "UPDATE users SET role = ?, is_active = ?"
            params = [role, is_active]
            if full_name:
                query += ", full_name = ?"
                params.append(full_name)
            if department:
                query += ", department = ?"
                params.append(department)
            if position:
                query += ", position = ?"
                params.append(position)
            if phone:
                query += ", phone = ?"
                params.append(phone)
            if email:
                query += ", email = ?"
                params.append(email)
            query += " WHERE id = ?"
            params.append(user_id)
            
            conn.execute(query, params)
            conn.commit()
            return True, "Cập nhật tài khoản thành công"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def reset_password(user_id, new_password):
        conn = get_db()
        try:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new_password), user_id))
            conn.commit()
            return True, "Đặt lại mật khẩu thành công"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()
