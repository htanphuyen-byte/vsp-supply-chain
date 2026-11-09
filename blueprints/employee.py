from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from blueprints import login_required
from models.requisition_model import RequisitionModel
from models.material_model import MaterialModel
from models.audit_model import AuditModel

employee_bp = Blueprint('employee', __name__, url_prefix='/employee')

@employee_bp.route('/requests')
@login_required
def requests_list():
    user_id = session.get('user_id')
    role = session.get('role')

    search = request.args.get('search')
    status_filter = request.args.get('status')
    dept_filter = request.args.get('department')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # If employee, view own requests; supply/manager/warehouse/admin can view all
    reqs = RequisitionModel.get_all(
        user_id=user_id if role == 'employee' else None,
        role=role,
        status=status_filter,
        department=dept_filter,
        search=search,
        start_date=start_date,
        end_date=end_date
    )

    return render_template('employee/requests.html',
                           requisitions=reqs,
                           current_status=status_filter,
                           search=search,
                           dept_filter=dept_filter,
                           start_date=start_date,
                           end_date=end_date)

@employee_bp.route('/create-request', methods=['GET', 'POST'])
@login_required
def create_request():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        reason = request.form.get('reason', '').strip()
        required_date = request.form.get('required_date')
        priority = request.form.get('priority', 'normal')
        department = session.get('department', 'Bộ phận vận hành')
        user_id = session.get('user_id')
        user_name = session.get('full_name')
        user_role = session.get('role')
        action_type = request.form.get('action_type', 'submit') # 'draft' or 'submit'
        is_draft = (action_type == 'draft')

        material_ids = request.form.getlist('material_id[]')
        quantities = request.form.getlist('quantity[]')

        items = []
        for m_id, qty in zip(material_ids, quantities):
            if m_id and qty and int(qty) > 0:
                items.append({'material_id': int(m_id), 'quantity': int(qty)})

        if not title or not items:
            flash("Vui lòng nhập tiêu đề yêu cầu và chọn ít nhất một mặt hàng vật tư!", "warning")
            return redirect(url_for('employee.create_request'))

        success, req_id, code_or_err = RequisitionModel.create(
            user_id=user_id,
            department=department,
            title=title,
            reason=reason,
            required_date=required_date,
            priority=priority,
            items=items,
            is_draft=is_draft,
            actor_name=user_name,
            actor_role=user_role
        )

        if success:
            log_action = "Tạo bản nháp yêu cầu" if is_draft else "Tạo và gửi yêu cầu vật tư"
            AuditModel.log(user_id, user_name, log_action, 'Requisition', req_id, f"Mã yêu cầu: {code_or_err} ({len(items)} mặt hàng)")

            if not is_draft:
                AuditModel.add_notification(
                    title=f"Yêu cầu vật tư mới: {code_or_err}",
                    message=f"Đồng chí {user_name} ({department}) vừa gửi yêu cầu cấp vật tư: {title}.",
                    role='procurement',
                    link=url_for('employee.request_detail', req_id=req_id)
                )
                flash(f"Đã gửi yêu cầu cấp phát vật tư {code_or_err} thành công đến Phòng Cung ứng!", "success")
            else:
                flash(f"Đã lưu bản nháp yêu cầu {code_or_err}. Bạn có thể chỉnh sửa và gửi sau.", "info")

            return redirect(url_for('employee.request_detail', req_id=req_id))
        else:
            flash(f"Lỗi: {code_or_err}", "danger")

    materials = MaterialModel.get_all()
    return render_template('employee/create_request.html', materials=materials)

@employee_bp.route('/request/<int:req_id>')
@login_required
def request_detail(req_id):
    req, items, history = RequisitionModel.get_by_id(req_id)
    if not req:
        flash("Không tìm thấy yêu cầu vật tư này!", "danger")
        return redirect(url_for('employee.requests_list'))

    all_sufficient, shortages = RequisitionModel.check_stock_feasibility(req_id)
    return render_template('employee/request_detail.html',
                           req=req,
                           items=items,
                           history=history,
                           all_sufficient=all_sufficient,
                           shortages=shortages)

@employee_bp.route('/request/<int:req_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_draft(req_id):
    user_id = session.get('user_id')
    user_name = session.get('full_name')
    user_role = session.get('role')

    req, items, _ = RequisitionModel.get_by_id(req_id)
    if not req or (req['user_id'] != user_id and user_role != 'admin'):
        flash("Bạn không có quyền chỉnh sửa yêu cầu này!", "danger")
        return redirect(url_for('employee.requests_list'))

    if req['status'] != 'draft':
        flash("Chỉ có thể chỉnh sửa yêu cầu khi ở trạng thái Bản nháp (Draft)!", "warning")
        return redirect(url_for('employee.request_detail', req_id=req_id))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        reason = request.form.get('reason', '').strip()
        required_date = request.form.get('required_date')
        priority = request.form.get('priority', 'normal')
        action_type = request.form.get('action_type', 'draft')
        submit_now = (action_type == 'submit')

        material_ids = request.form.getlist('material_id[]')
        quantities = request.form.getlist('quantity[]')

        new_items = []
        for m_id, qty in zip(material_ids, quantities):
            if m_id and qty and int(qty) > 0:
                new_items.append({'material_id': int(m_id), 'quantity': int(qty)})

        success, msg = RequisitionModel.update_draft(
            req_id=req_id,
            user_id=user_id,
            title=title,
            reason=reason,
            required_date=required_date,
            priority=priority,
            items=new_items,
            submit=submit_now,
            actor_name=user_name,
            actor_role=user_role
        )

        if success:
            if submit_now:
                AuditModel.add_notification(
                    title=f"Yêu cầu vật tư đã gửi: {req['req_code']}",
                    message=f"Đồng chí {user_name} vừa gửi chính thức yêu cầu {req['req_code']}.",
                    role='procurement',
                    link=url_for('employee.request_detail', req_id=req_id)
                )
                flash(f"Đã cập nhật và chính thức gửi yêu cầu {req['req_code']}!", "success")
            else:
                flash(f"Đã cập nhật bản nháp {req['req_code']} thành công!", "info")
            return redirect(url_for('employee.request_detail', req_id=req_id))
        else:
            flash(f"Lỗi: {msg}", "danger")

    materials = MaterialModel.get_all()
    return render_template('employee/edit_draft.html', req=req, items=items, materials=materials)

@employee_bp.route('/request/<int:req_id>/confirm-receipt', methods=['POST'])
@login_required
def confirm_receipt(req_id):
    # Step 9: Handover confirmed -> completed
    user_id = session.get('user_id')
    user_name = session.get('full_name')
    user_role = session.get('role')
    req, _, _ = RequisitionModel.get_by_id(req_id)

    if req['status'] != 'dispatched':
        flash("Yêu cầu chưa được kho xuất cấp nên chưa thể xác nhận bàn giao!", "warning")
        return redirect(url_for('employee.request_detail', req_id=req_id))

    RequisitionModel.update_status(
        req_id=req_id,
        new_status='completed',
        actor_id=user_id,
        actor_name=user_name,
        actor_role=user_role,
        notes="Người yêu cầu đã nhận đủ vật tư tại hiện trường và ký xác nhận bàn giao hoàn tất.",
        procurement_note="Biên bản giao nhận đã ký đầy đủ."
    )
    AuditModel.log(user_id, user_name, 'Xác nhận bàn giao', 'Requisition', req_id, f"Hoàn tất bàn giao yêu cầu {req['req_code']}")
    flash("Đã xác nhận nhận đủ vật tư và hoàn tất toàn bộ quy trình cung ứng!", "success")
    return redirect(url_for('employee.request_detail', req_id=req_id))
