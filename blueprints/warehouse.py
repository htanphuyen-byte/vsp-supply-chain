from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from blueprints import role_required
from models.material_model import MaterialModel
from models.requisition_model import RequisitionModel
from models.supplier_model import SupplierModel
from models.audit_model import AuditModel
from database import get_db

warehouse_bp = Blueprint('warehouse', __name__, url_prefix='/warehouse')

@warehouse_bp.route('/inventory')
@role_required('warehouse')
def inventory():
    search = request.args.get('search')
    category = request.args.get('category')
    stock_status = request.args.get('status') # 'low', 'out', 'sufficient', 'reserved'

    materials = MaterialModel.get_all(search=search, category=category, stock_status=stock_status)
    categories = MaterialModel.get_categories()
    low_stocks = MaterialModel.get_low_stock()

    return render_template('warehouse/inventory.html',
                           materials=materials,
                           categories=categories,
                           low_stocks=low_stocks,
                           selected_cat=category,
                           selected_status=stock_status,
                           search=search)

@warehouse_bp.route('/material/add', methods=['POST'])
@role_required('warehouse')
def add_material():
    code = request.form.get('code', '').strip()
    name = request.form.get('name', '').strip()
    category = request.form.get('category', '').strip()
    unit = request.form.get('unit', '').strip()
    unit_price = float(request.form.get('unit_price', 0))
    min_stock = int(request.form.get('min_stock', 5))
    initial_stock = int(request.form.get('initial_stock', 0))
    location = request.form.get('location', '').strip()
    description = request.form.get('description', '').strip()

    user_id = session.get('user_id')
    user_name = session.get('full_name')

    success, msg = MaterialModel.create(code, name, category, unit, unit_price, min_stock, initial_stock, location, description)
    if success:
        AuditModel.log(user_id, user_name, 'Thêm mã vật tư mới', 'Material', code, f"Vật tư: {name} (Mã: {code})")
        flash(f"Đã thêm vật tư '{name}' vào danh mục thành công!", "success")
    else:
        flash(f"Lỗi thêm vật tư: {msg}", "danger")

    return redirect(url_for('warehouse.inventory'))

@warehouse_bp.route('/material/edit/<int:mat_id>', methods=['POST'])
@role_required('warehouse')
def edit_material(mat_id):
    name = request.form.get('name', '').strip()
    category = request.form.get('category', '').strip()
    unit = request.form.get('unit', '').strip()
    unit_price = float(request.form.get('unit_price', 0))
    min_stock = int(request.form.get('min_stock', 5))
    location = request.form.get('location', '').strip()
    description = request.form.get('description', '').strip()

    user_id = session.get('user_id')
    user_name = session.get('full_name')

    success, msg = MaterialModel.update(mat_id, name, category, unit, unit_price, min_stock, location, description)
    if success:
        AuditModel.log(user_id, user_name, 'Cập nhật vật tư', 'Material', mat_id, f"Cập nhật thông tin vật tư {name}")
        flash("Cập nhật thông tin vật tư thành công!", "success")
    else:
        flash(f"Lỗi: {msg}", "danger")
    return redirect(url_for('warehouse.inventory'))

@warehouse_bp.route('/receipts', methods=['GET', 'POST'])
@role_required('warehouse')
def goods_receipts():
    # Section 8: Goods Receipt Management
    user_id = session.get('user_id')
    user_name = session.get('full_name')

    if request.method == 'POST':
        material_id = int(request.form.get('material_id'))
        quantity = int(request.form.get('quantity'))
        supplier_id = request.form.get('supplier_id')
        supplier_name = request.form.get('supplier_name', '').strip()
        notes = request.form.get('notes', '').strip()

        if supplier_id:
            sup = SupplierModel.get_by_id(int(supplier_id))
            if sup:
                supplier_name = sup['name']

        success, res_or_err = MaterialModel.record_goods_receipt(
            material_id=material_id,
            quantity=quantity,
            supplier_id=int(supplier_id) if supplier_id else None,
            supplier_name=supplier_name,
            staff_id=user_id,
            staff_name=user_name,
            notes=notes
        )

        if success:
            AuditModel.log(user_id, user_name, 'Nhập kho (Goods Receipt)', 'GoodsReceipt', res_or_err, f"Nhập kho {quantity} sản phẩm")
            flash(f"Đã lập phiếu nhập kho {res_or_err} thành công! Số lượng tồn kho đã được cộng dồn.", "success")
            return redirect(url_for('warehouse.goods_receipts'))
        else:
            flash(f"Lỗi nhập kho: {res_or_err}", "danger")

    receipts = MaterialModel.get_goods_receipts()
    materials = MaterialModel.get_all()
    suppliers = SupplierModel.get_all(status='active')
    return render_template('warehouse/goods_receipts.html', receipts=receipts, materials=materials, suppliers=suppliers)

@warehouse_bp.route('/issues', methods=['GET', 'POST'])
@role_required('warehouse')
def goods_issues():
    # Section 8: Goods Issue Management
    user_id = session.get('user_id')
    user_name = session.get('full_name')

    if request.method == 'POST':
        material_id = int(request.form.get('material_id'))
        quantity = int(request.form.get('quantity'))
        recipient_name = request.form.get('recipient_name', '').strip()
        department = request.form.get('department', '').strip()
        notes = request.form.get('notes', '').strip()

        success, res_or_err = MaterialModel.record_goods_issue(
            material_id=material_id,
            quantity=quantity,
            recipient_name=recipient_name,
            department=department,
            staff_id=user_id,
            staff_name=user_name,
            notes=notes
        )

        if success:
            AuditModel.log(user_id, user_name, 'Xuất kho (Goods Issue)', 'GoodsIssue', res_or_err, f"Xuất kho {quantity} cho {recipient_name}")
            flash(f"Đã lập phiếu xuất kho {res_or_err} thành công! Tồn kho đã được trừ tương ứng.", "success")
            return redirect(url_for('warehouse.goods_issues'))
        else:
            flash(f"Lỗi xuất kho: {res_or_err}", "danger")

    issues = MaterialModel.get_goods_issues()
    materials = MaterialModel.get_all()
    return render_template('warehouse/goods_issues.html', issues=issues, materials=materials)

@warehouse_bp.route('/dispatch/<int:req_id>', methods=['POST'])
@role_required('warehouse')
def dispatch_requisition(req_id):
    # Step 8: Warehouse executes stock out for an approved requisition
    user_id = session.get('user_id')
    user_name = session.get('full_name')
    user_role = session.get('role')

    req, items, _ = RequisitionModel.get_by_id(req_id)
    if not req:
        flash("Không tìm thấy yêu cầu!", "danger")
        return redirect(url_for('employee.requests_list'))

    # Security check: Prevent issuing more than on-hand stock
    all_ok, shortages = RequisitionModel.check_stock_feasibility(req_id)
    if not all_ok:
        short_names = ", ".join([f"{s['name']} (thiếu {s['shortage']} {s['unit']})" for s in shortages])
        flash(f"Không thể xuất kho! Kho thiếu hàng: {short_names}. Vui lòng chuyển Phòng Cung ứng để mua bổ sung.", "danger")
        return redirect(url_for('employee.request_detail', req_id=req_id))

    # Perform goods issue for each material in the requisition
    issue_codes = []
    for item in items:
        success, code_or_err = MaterialModel.record_goods_issue(
            material_id=item['material_id'],
            quantity=item['requested_qty'],
            requisition_id=req_id,
            recipient_name=req['requester_name'],
            department=req['department'],
            staff_id=user_id,
            staff_name=user_name,
            notes=f"Xuất cấp theo yêu cầu {req['req_code']} ({req['title']})"
        )
        if not success:
            flash(f"Lỗi xuất mặt hàng {item['mat_name']}: {code_or_err}", "danger")
            return redirect(url_for('employee.request_detail', req_id=req_id))
        issue_codes.append(code_or_err)

    # Update requisition status to 'dispatched'
    issues_summary = ", ".join(issue_codes)
    RequisitionModel.update_status(
        req_id=req_id,
        new_status='dispatched',
        actor_id=user_id,
        actor_name=user_name,
        actor_role=user_role,
        notes=f"Kho đã xuất cấp vật tư (Mã phiếu xuất: {issues_summary}). Đang chờ bàn giao tại hiện trường.",
        procurement_note="Kho đã hoàn thành xuất cấp vật tư."
    )

    AuditModel.log(user_id, user_name, 'Xuất kho cấp phát vật tư', 'Requisition', req_id, f"Xuất kho yêu cầu {req['req_code']} (Phiếu xuất: {issues_summary})")
    AuditModel.add_notification(
        title=f"Vật tư đã được xuất kho",
        message=f"Kho đã chuẩn bị xong vật tư cho yêu cầu {req['req_code']}. Vui lòng kiểm tra và xác nhận bàn giao.",
        user_id=req['user_id'],
        link=url_for('employee.request_detail', req_id=req_id)
    )
    flash(f"Đã xuất kho cấp phát vật tư thành công cho yêu cầu {req['req_code']}! Phiếu xuất: {issues_summary}", "success")
    return redirect(url_for('employee.request_detail', req_id=req_id))

@warehouse_bp.route('/transactions')
@role_required('warehouse')
def transactions():
    search = request.args.get('search')
    type_filter = request.args.get('type')

    conn = get_db()
    query = '''
        SELECT st.*, m.code as mat_code, m.name as mat_name, m.unit as mat_unit, u.full_name as actor_name
        FROM stock_transactions st
        JOIN materials m ON st.material_id = m.id
        LEFT JOIN users u ON st.user_id = u.id
        WHERE 1=1
    '''
    params = []
    if type_filter:
        query += " AND st.type = ?"
        params.append(type_filter)
    if search:
        query += " AND (st.trans_code LIKE ? OR m.code LIKE ? OR m.name LIKE ? OR st.reference_id LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s, s])

    query += " ORDER BY st.created_at DESC"
    txs = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('warehouse/transactions.html', transactions=txs, search=search, current_type=type_filter)
