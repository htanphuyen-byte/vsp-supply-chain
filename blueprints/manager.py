from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from blueprints import role_required
from models.requisition_model import RequisitionModel
from models.material_model import MaterialModel
from models.audit_model import AuditModel

manager_bp = Blueprint('manager', __name__, url_prefix='/manager')

@manager_bp.route('/approvals')
@role_required('manager')
def approvals_list():
    status_filter = request.args.get('status', 'pending_approval')
    search = request.args.get('search')
    dept_filter = request.args.get('department')

    if status_filter == 'all':
        reqs = RequisitionModel.get_all(search=search, department=dept_filter)
    else:
        reqs = RequisitionModel.get_all(status=status_filter, search=search, department=dept_filter)

    return render_template('manager/approvals.html',
                           requisitions=reqs,
                           current_filter=status_filter,
                           search=search,
                           dept_filter=dept_filter)

@manager_bp.route('/approve/<int:req_id>', methods=['POST'])
@role_required('manager')
def approve_request(req_id):
    decision = request.form.get('decision') # 'approve' or 'reject'
    note = request.form.get('manager_note', '').strip()
    user_id = session.get('user_id')
    user_name = session.get('full_name')
    user_role = session.get('role')

    req, items, _ = RequisitionModel.get_by_id(req_id)
    if not req:
        flash("Không tìm thấy yêu cầu!", "danger")
        return redirect(url_for('manager.approvals_list'))

    # Security check from Section 7: "A rejection must require a reason."
    if decision == 'reject':
        if not note:
            flash("Bắt buộc phải nhập lý do từ chối phê duyệt yêu cầu!", "danger")
            return redirect(url_for('employee.request_detail', req_id=req_id))

        RequisitionModel.update_status(
            req_id=req_id,
            new_status='rejected',
            actor_id=user_id,
            actor_name=user_name,
            actor_role=user_role,
            notes=f"Lãnh đạo từ chối: {note}",
            manager_note=f"Từ chối phê duyệt. Lý do: {note}"
        )
        AuditModel.log(user_id, user_name, 'Từ chối yêu cầu', 'Requisition', req_id, f"Từ chối {req['req_code']}: {note}")
        AuditModel.add_notification(
            title=f"Yêu cầu {req['req_code']} bị từ chối",
            message=f"Ban Lãnh Đạo đã từ chối yêu cầu của bạn. Lý do: {note}",
            user_id=req['user_id'],
            link=url_for('employee.request_detail', req_id=req_id)
        )
        flash(f"Đã từ chối yêu cầu {req['req_code']} (Đã lưu lý do từ chối).", "info")

    elif decision == 'approve':
        all_sufficient, shortages = RequisitionModel.check_stock_feasibility(req_id)

        # Section 7 rule: Approving a request must NOT automatically reduce warehouse inventory!
        # It only changes status and marks stock reservation if sufficient, or directs to procurement if short.
        if all_sufficient:
            new_status = 'awaiting_issue'
            msg_note = f"Phê duyệt cấp phát (Kho sẵn sàng xuất cấp). {note}"
            # Reserve materials in catalog
            for it in items:
                MaterialModel.reserve_material(it['material_id'], it['requested_qty'])
        else:
            new_status = 'purchasing'
            short_desc = ", ".join([f"{s['name']} (thiếu {s['shortage']} {s['unit']})" for s in shortages])
            msg_note = f"Phê duyệt mua sắm bổ sung [{short_desc}]. {note}"

        RequisitionModel.update_status(
            req_id=req_id,
            new_status=new_status,
            actor_id=user_id,
            actor_name=user_name,
            actor_role=user_role,
            notes=msg_note,
            manager_note=msg_note
        )

        AuditModel.log(user_id, user_name, 'Phê duyệt yêu cầu', 'Requisition', req_id, f"Phê duyệt {req['req_code']} -> {new_status}")
        AuditModel.add_notification(
            title=f"Yêu cầu {req['req_code']} đã được phê duyệt",
            message=f"Ban Lãnh Đạo đã phê duyệt yêu cầu của bạn. Tiến trình tiếp theo: {new_status}",
            user_id=req['user_id'],
            link=url_for('employee.request_detail', req_id=req_id)
        )
        AuditModel.add_notification(
            title=f"Yêu cầu {req['req_code']} đã được duyệt",
            message=f"Chuyển xử lý tiếp theo: {new_status}",
            role='procurement',
            link=url_for('employee.request_detail', req_id=req_id)
        )
        flash(f"Đã phê duyệt yêu cầu {req['req_code']} thành công!", "success")

    return redirect(url_for('manager.approvals_list'))
