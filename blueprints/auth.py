from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models.user_model import UserModel
from models.audit_model import AuditModel

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip() or request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        remember = bool(request.form.get('remember'))

        user = UserModel.authenticate(identifier, password)
        if user:
            if not user['is_active']:
                flash("Tài khoản này đã bị khóa bởi Quản trị viên. Vui lòng liên hệ Admin!", "danger")
                return render_template('auth/login.html')

            session.permanent = remember
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['employee_id'] = user['employee_id']
            session['role'] = user['role']
            session['department'] = user['department']
            session['position'] = user['position']

            AuditModel.log(user['id'], user['full_name'], 'Đăng nhập', 'Auth', user['id'], f"Đăng nhập thành công ({user['employee_id']})")
            flash(f"Xin chào {user['full_name']} ({user['position']})! Đăng nhập thành công.", "success")
            return redirect(url_for('dashboard.index'))
        else:
            flash("Tên đăng nhập / Email hoặc mật khẩu không chính xác!", "danger")

    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        employee_id = request.form.get('employee_id', '').strip()
        department = request.form.get('department', '').strip()
        position = request.form.get('position', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        # Automatic account activation & default role: EMPLOYEE
        success, res = UserModel.register(
            full_name=full_name,
            employee_id=employee_id,
            department=department,
            position=position,
            email=email,
            phone=phone,
            username=username,
            password=password,
            confirm_password=confirm_password
        )

        if success:
            user_id = res
            AuditModel.log(user_id, full_name, 'Đăng ký tài khoản', 'Auth', user_id, f"Đăng ký tự động kích hoạt mã NV: {employee_id}")
            AuditModel.add_notification(
                title=f"Thành viên mới: {full_name}",
                message=f"Đồng chí {full_name} ({employee_id} - {department}) vừa đăng ký tài khoản.",
                role='admin',
                link=url_for('admin.user_list')
            )
            flash("Đăng ký tài khoản thành công! Tài khoản đã được kích hoạt tự động. Bạn có thể đăng nhập ngay.", "success")
            return redirect(url_for('auth.login'))
        else:
            flash(res, "danger")

    return render_template('auth/register.html')

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    identifier = request.form.get('identifier', '').strip()
    user = UserModel.get_by_username_or_email(identifier)
    if user:
        flash(f"Yêu cầu đặt lại mật khẩu cho tài khoản '{user['username']}' ({user['email']}) đã được ghi nhận. Vui lòng liên hệ Admin hệ thống hoặc kiểm tra hòm thư nội bộ Vietsovpetro.", "info")
        AuditModel.log(user['id'], user['full_name'], 'Yêu cầu khôi phục mật khẩu', 'Auth', user['id'], f"Yêu cầu cấp lại mật khẩu cho email {user['email']}")
    else:
        flash("Không tìm thấy tài khoản tương ứng với thông tin đã nhập!", "warning")
    return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
    user_name = session.get('full_name')
    if user_id:
        AuditModel.log(user_id, user_name, 'Đăng xuất', 'Auth', user_id, 'Người dùng đã đăng xuất khỏi hệ thống')
    session.clear()
    flash("Bạn đã đăng xuất khỏi hệ thống.", "info")
    return redirect(url_for('auth.login'))
