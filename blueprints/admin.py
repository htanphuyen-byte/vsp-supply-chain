from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from blueprints import role_required
from models.user_model import UserModel
from models.audit_model import AuditModel
from database import get_db

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/users')
@role_required('admin')
def user_list():
    search = request.args.get('search')
    users = UserModel.get_all(search=search)
    return render_template('admin/users.html', users=users, search=search)

@admin_bp.route('/user/create', methods=['POST'])
@role_required('admin')
def create_user():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    full_name = request.form.get('full_name', '').strip()
    employee_id = request.form.get('employee_id', '').strip()
    department = request.form.get('department', '').strip()
    position = request.form.get('position', '').strip()
    role = request.form.get('role', 'employee')
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()

    current_uid = session.get('user_id')
    current_name = session.get('full_name')

    conn = get_db()
    try:
        from werkzeug.security import generate_password_hash
        conn.execute('''
            INSERT INTO users (username, password_hash, full_name, employee_id, department, position, email, phone, role, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (username, generate_password_hash(password), full_name, employee_id, department, position, email, phone, role))
        conn.commit()
        AuditModel.log(current_uid, current_name, 'Tạo người dùng mới', 'User', username, f"Admin tạo tài khoản {username} ({role})")
        flash(f"Đã tạo tài khoản cán bộ '{full_name}' ({employee_id}) với vai trò {role} thành công!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Lỗi: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('admin.user_list'))

@admin_bp.route('/user/update/<int:target_id>', methods=['POST'])
@role_required('admin')
def update_user(target_id):
    role = request.form.get('role')
    is_active = 1 if request.form.get('is_active') == '1' else 0
    full_name = request.form.get('full_name')
    department = request.form.get('department')
    position = request.form.get('position')
    phone = request.form.get('phone')
    email = request.form.get('email')

    current_uid = session.get('user_id')
    current_name = session.get('full_name')

    # Security rule: Do not allow admin to lock their own account
    if target_id == current_uid and is_active == 0:
        flash("Bạn không thể tự khóa tài khoản Admin đang đăng nhập!", "warning")
        return redirect(url_for('admin.user_list'))

    success, msg = UserModel.update_user_by_admin(
        user_id=target_id,
        role=role,
        is_active=is_active,
        full_name=full_name,
        department=department,
        position=position,
        phone=phone,
        email=email
    )

    if success:
        AuditModel.log(current_uid, current_name, 'Cập nhật tài khoản/Phân quyền', 'User', target_id, f"Vai trò: {role}, Hoạt động: {is_active}")
        flash("Cập nhật thông tin và phân quyền người dùng thành công!", "success")
    else:
        flash(f"Lỗi: {msg}", "danger")

    return redirect(url_for('admin.user_list'))

@admin_bp.route('/user/reset-password/<int:target_id>', methods=['POST'])
@role_required('admin')
def reset_user_password(target_id):
    new_password = request.form.get('new_password', '123456').strip()
    current_uid = session.get('user_id')
    current_name = session.get('full_name')

    success, msg = UserModel.reset_password(target_id, new_password)
    if success:
        AuditModel.log(current_uid, current_name, 'Đặt lại mật khẩu người dùng', 'User', target_id, "Admin đã reset mật khẩu")
        flash("Đã đặt lại mật khẩu người dùng thành công!", "success")
    else:
        flash(f"Lỗi: {msg}", "danger")

    return redirect(url_for('admin.user_list'))

@admin_bp.route('/logs')
@role_required('admin')
def logs():
    search = request.args.get('search')
    action_filter = request.args.get('action')
    audit_logs = AuditModel.get_logs(limit=250, action_filter=action_filter, search=search)
    return render_template('admin/logs.html', logs=audit_logs, search=search, action_filter=action_filter)
