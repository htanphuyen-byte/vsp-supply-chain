from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from blueprints import role_required
from models.supplier_model import SupplierModel
from models.audit_model import AuditModel

supplier_bp = Blueprint('supplier', __name__, url_prefix='/suppliers')

@supplier_bp.route('/')
@role_required('procurement')
def list_suppliers():
    search = request.args.get('search')
    status_filter = request.args.get('status')
    category_filter = request.args.get('category')
    suppliers = SupplierModel.get_all(search=search, status=status_filter, category=category_filter)
    return render_template('supplier/list.html',
                           suppliers=suppliers,
                           search=search,
                           current_status=status_filter,
                           current_category=category_filter)

@supplier_bp.route('/add', methods=['POST'])
@role_required('procurement')
def add_supplier():
    name = request.form.get('name', '').strip()
    contact_person = request.form.get('contact_person', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    address = request.form.get('address', '').strip()
    tax_id = request.form.get('tax_id', '').strip()
    supplied_categories = request.form.get('supplied_categories', '').strip()
    cooperation_status = request.form.get('cooperation_status', 'active')
    rating = int(request.form.get('rating', 5))
    notes = request.form.get('notes', '').strip()

    user_id = session.get('user_id')
    user_name = session.get('full_name')

    success, res = SupplierModel.create(
        name=name,
        contact_person=contact_person,
        phone=phone,
        email=email,
        address=address,
        tax_id=tax_id,
        supplied_categories=supplied_categories,
        cooperation_status=cooperation_status,
        rating=rating,
        notes=notes
    )

    if success:
        AuditModel.log(user_id, user_name, 'Thêm nhà cung cấp mới', 'Supplier', res, f"Thêm đối tác: {name} (Mã: {res})")
        flash(f"Đã thêm nhà cung cấp '{name}' (Mã: {res}) thành công!", "success")
    else:
        flash(f"Lỗi: {res}", "danger")

    return redirect(url_for('supplier.list_suppliers'))

@supplier_bp.route('/edit/<int:sup_id>', methods=['POST'])
@role_required('procurement')
def edit_supplier(sup_id):
    name = request.form.get('name', '').strip()
    contact_person = request.form.get('contact_person', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    address = request.form.get('address', '').strip()
    tax_id = request.form.get('tax_id', '').strip()
    supplied_categories = request.form.get('supplied_categories', '').strip()
    cooperation_status = request.form.get('cooperation_status', 'active')
    rating = int(request.form.get('rating', 5))
    notes = request.form.get('notes', '').strip()

    user_id = session.get('user_id')
    user_name = session.get('full_name')

    success, msg = SupplierModel.update(
        supplier_id=sup_id,
        name=name,
        contact_person=contact_person,
        phone=phone,
        email=email,
        address=address,
        tax_id=tax_id,
        supplied_categories=supplied_categories,
        cooperation_status=cooperation_status,
        rating=rating,
        notes=notes
    )

    if success:
        AuditModel.log(user_id, user_name, 'Sửa nhà cung cấp', 'Supplier', sup_id, f"Cập nhật thông tin đối tác {name}")
        flash("Cập nhật thông tin nhà cung cấp thành công!", "success")
    else:
        flash(f"Lỗi: {msg}", "danger")

    return redirect(url_for('supplier.list_suppliers'))

@supplier_bp.route('/delete/<int:sup_id>', methods=['POST'])
@role_required('procurement')
def delete_supplier(sup_id):
    user_id = session.get('user_id')
    user_name = session.get('full_name')

    success, msg = SupplierModel.delete_or_deactivate(sup_id)
    AuditModel.log(user_id, user_name, 'Xử lý xóa/ngừng hợp tác NCC', 'Supplier', sup_id, msg)
    if success:
        flash(msg, "info")
    else:
        flash(f"Lỗi: {msg}", "danger")

    return redirect(url_for('supplier.list_suppliers'))
