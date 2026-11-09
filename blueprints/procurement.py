from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from blueprints import role_required
from models.requisition_model import RequisitionModel
from models.purchase_order_model import PurchaseOrderModel
from models.supplier_model import SupplierModel
from models.material_model import MaterialModel
from models.audit_model import AuditModel

procurement_bp = Blueprint('procurement', __name__, url_prefix='/procurement')

@procurement_bp.route('/requests')
@role_required('procurement')
def requests_overview():
    status_filter = request.args.get('status')
    search = request.args.get('search')
    dept_filter = request.args.get('department')
    reqs = RequisitionModel.get_all(status=status_filter, search=search, department=dept_filter)
    return render_template('procurement/requests.html',
                           requisitions=reqs,
                           current_status=status_filter,
                           search=search,
                           dept_filter=dept_filter)

@procurement_bp.route('/receive/<int:req_id>', methods=['POST'])
@role_required('procurement')
def receive_request(req_id):
    # Step 2: Supply department receives the request
    user_id = session.get('user_id')
    user_name = session.get('full_name')
    user_role = session.get('role')

    req, _, _ = RequisitionModel.get_by_id(req_id)
    if not req:
        flash("Không tìm thấy yêu cầu!", "danger")
        return redirect(url_for('procurement.requests_overview'))

    RequisitionModel.update_status(
        req_id=req_id,
        new_status='received',
        actor_id=user_id,
        actor_name=user_name,
        actor_role=user_role,
        notes="Phòng Cung ứng đã tiếp nhận yêu cầu và bắt đầu xử lý.",
        procurement_note="Đã tiếp nhận hồ sơ yêu cầu."
    )
    AuditModel.log(user_id, user_name, 'Tiếp nhận yêu cầu', 'Requisition', req_id, f"Tiếp nhận {req['req_code']}")
    flash(f"Đã tiếp nhận yêu cầu {req['req_code']}.", "success")
    return redirect(url_for('employee.request_detail', req_id=req_id))

@procurement_bp.route('/review/<int:req_id>', methods=['POST'])
@role_required('procurement')
def submit_to_manager(req_id):
    # Step 3: Check stock feasibility & submit to management
    proc_note = request.form.get('procurement_note', '').strip()
    user_id = session.get('user_id')
    user_name = session.get('full_name')
    user_role = session.get('role')

    all_sufficient, shortages = RequisitionModel.check_stock_feasibility(req_id)
    if all_sufficient:
        note = f"Phòng Cung ứng đã thẩm định kho: ĐỦ HÀNG KHẢ DỤNG. Đề xuất lãnh đạo phê duyệt xuất cấp. {proc_note}"
    else:
        short_desc = ", ".join([f"{s['name']} (thiếu {s['shortage']} {s['unit']})" for s in shortages])
        note = f"Phòng Cung ứng đã thẩm định kho: THIẾU HÀNG [{short_desc}]. Đề xuất lãnh đạo phê duyệt phương án mua sắm bổ sung. {proc_note}"

    RequisitionModel.update_status(
        req_id=req_id,
        new_status='pending_approval',
        actor_id=user_id,
        actor_name=user_name,
        actor_role=user_role,
        notes=note,
        procurement_note=note
    )

    AuditModel.log(user_id, user_name, 'Trình lãnh đạo phê duyệt', 'Requisition', req_id, note)
    AuditModel.add_notification(
        title=f"Yêu cầu cần phê duyệt",
        message=f"Phòng Cung ứng đã thẩm định và trình duyệt yêu cầu {req_id}",
        role='manager',
        link=url_for('manager.approvals_list')
    )
    flash("Đã kiểm tra kho và trình hồ sơ lên Ban Lãnh Đạo xem xét phê duyệt!", "success")
    return redirect(url_for('employee.request_detail', req_id=req_id))

@procurement_bp.route('/orders')
@role_required('procurement')
def orders_list():
    status_filter = request.args.get('status')
    search = request.args.get('search')
    pos = PurchaseOrderModel.get_all(status=status_filter, search=search)
    return render_template('procurement/orders.html', purchase_orders=pos, current_status=status_filter, search=search)

@procurement_bp.route('/create-po', methods=['GET', 'POST'])
@role_required('procurement')
def create_po():
    if request.method == 'POST':
        supplier_id = request.form.get('supplier_id')
        requisition_id = request.form.get('requisition_id')
        expected_date = request.form.get('expected_delivery_date')
        notes = request.form.get('notes', '').strip()
        user_id = session.get('user_id')
        user_name = session.get('full_name')

        material_ids = request.form.getlist('material_id[]')
        quantities = request.form.getlist('order_qty[]')
        prices = request.form.getlist('unit_price[]')

        items = []
        for m_id, qty, pr in zip(material_ids, quantities, prices):
            if m_id and qty and float(qty) > 0:
                items.append({
                    'material_id': int(m_id),
                    'order_qty': float(qty),
                    'unit_price': float(pr) if pr else 0
                })

        if not supplier_id or not items:
            flash("Vui lòng chọn nhà cung cấp và ít nhất một mặt hàng đặt mua!", "warning")
            return redirect(url_for('procurement.create_po', req_id=requisition_id))

        success, po_id, code_or_err = PurchaseOrderModel.create(
            requisition_id=int(requisition_id) if requisition_id else None,
            supplier_id=int(supplier_id),
            created_by=user_id,
            expected_date=expected_date,
            notes=notes,
            items=items
        )

        if success:
            AuditModel.log(user_id, user_name, 'Lập đơn đặt hàng (PO)', 'PurchaseOrder', po_id, f"Mã PO: {code_or_err} ({len(items)} mặt hàng)")
            flash(f"Đã lập Đơn đặt hàng {code_or_err} thành công!", "success")
            return redirect(url_for('procurement.po_detail', po_id=po_id))
        else:
            flash(f"Lỗi: {code_or_err}", "danger")

    req_id = request.args.get('req_id')
    prefill_req = None
    prefill_items = []
    if req_id:
        prefill_req, prefill_items, _ = RequisitionModel.get_by_id(int(req_id))

    suppliers = SupplierModel.get_all(status='active')
    materials = MaterialModel.get_all()
    return render_template('procurement/create_po.html',
                           suppliers=suppliers,
                           materials=materials,
                           prefill_req=prefill_req,
                           prefill_items=prefill_items)

@procurement_bp.route('/po/<int:po_id>')
@role_required('procurement')
def po_detail(po_id):
    po, items = PurchaseOrderModel.get_by_id(po_id)
    if not po:
        flash("Không tìm thấy đơn đặt hàng!", "danger")
        return redirect(url_for('procurement.orders_list'))
    return render_template('procurement/po_detail.html', po=po, items=items)

@procurement_bp.route('/po/<int:po_id>/update-status', methods=['POST'])
@role_required('procurement')
def update_po_status(po_id):
    new_status = request.form.get('status')
    user_id = session.get('user_id')
    user_name = session.get('full_name')

    success, msg = PurchaseOrderModel.update_status(po_id, new_status, user_id=user_id, user_name=user_name)
    if success:
        AuditModel.log(user_id, user_name, 'Cập nhật tiến độ PO', 'PurchaseOrder', po_id, f"Trạng thái mới: {new_status}")
        flash("Đã cập nhật trạng thái đơn hàng thành công!", "success")
    else:
        flash(f"Lỗi: {msg}", "danger")

    return redirect(url_for('procurement.po_detail', po_id=po_id))
