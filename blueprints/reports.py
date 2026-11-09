from flask import Blueprint, render_template, request
from blueprints import login_required
from database import get_db

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/')
@login_required
def index():
    conn = get_db()

    dept_filter = request.args.get('department')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # 1. Inventory Summary by Category
    inv_summary = conn.execute('''
        SELECT category,
               COUNT(*) as total_items,
               SUM(current_stock) as total_on_hand,
               SUM(reserved_qty) as total_reserved,
               SUM(current_stock - reserved_qty) as total_available,
               SUM(current_stock * unit_price) as total_value,
               SUM(CASE WHEN current_stock <= min_stock THEN 1 ELSE 0 END) as low_stock_count
        FROM materials
        GROUP BY category
    ''').fetchall()

    total_inv_value = sum(row['total_value'] or 0 for row in inv_summary)
    total_on_hand_all = sum(row['total_on_hand'] or 0 for row in inv_summary)
    total_reserved_all = sum(row['total_reserved'] or 0 for row in inv_summary)
    total_available_all = sum(row['total_available'] or 0 for row in inv_summary)

    # 2. Requisition Statistics by Department
    dept_query = '''
        SELECT department,
               COUNT(*) as total_reqs,
               SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_reqs,
               SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected_reqs,
               SUM(CASE WHEN status IN ('submitted', 'received', 'under_review', 'pending_approval', 'purchasing', 'awaiting_issue', 'dispatched') THEN 1 ELSE 0 END) as active_reqs
        FROM requisitions
        WHERE 1=1
    '''
    dept_params = []
    if dept_filter:
        dept_query += " AND department = ?"
        dept_params.append(dept_filter)
    if start_date:
        dept_query += " AND created_at >= ?"
        dept_params.append(f"{start_date} 00:00:00")
    if end_date:
        dept_query += " AND created_at <= ?"
        dept_params.append(f"{end_date} 23:59:59")

    dept_query += " GROUP BY department"
    dept_stats = conn.execute(dept_query, dept_params).fetchall()

    # 3. Goods Receipts summary
    recent_receipts = conn.execute('''
        SELECT gr.*, m.name as mat_name, m.code as mat_code
        FROM goods_receipts gr
        JOIN materials m ON gr.material_id = m.id
        ORDER BY gr.receipt_date DESC LIMIT 10
    ''').fetchall()

    # 4. Goods Issues summary
    recent_issues = conn.execute('''
        SELECT gi.*, m.name as mat_name, m.code as mat_code, r.req_code as requisition_code
        FROM goods_issues gi
        JOIN materials m ON gi.material_id = m.id
        LEFT JOIN requisitions r ON gi.requisition_id = r.id
        ORDER BY gi.issue_date DESC LIMIT 10
    ''').fetchall()

    # 5. Low-stock critical items report
    low_stock_report = conn.execute('''
        SELECT m.*, (m.current_stock - m.reserved_qty) as available_qty
        FROM materials m
        WHERE m.current_stock <= m.min_stock
        ORDER BY m.current_stock ASC
    ''').fetchall()

    # 6. Procurement expenditure by supplier
    po_stats = conn.execute('''
        SELECT s.name as supplier_name, s.code as supplier_code,
               COUNT(po.id) as total_orders,
               SUM(po.total_amount) as total_spend,
               po.status
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        GROUP BY s.id, po.status
    ''').fetchall()

    # 7. Department list for filtering
    departments = conn.execute("SELECT DISTINCT department FROM users ORDER BY department").fetchall()

    conn.close()

    return render_template('reports/index.html',
                           inv_summary=inv_summary,
                           total_inv_value=total_inv_value,
                           total_on_hand_all=total_on_hand_all,
                           total_reserved_all=total_reserved_all,
                           total_available_all=total_available_all,
                           dept_stats=dept_stats,
                           recent_receipts=recent_receipts,
                           recent_issues=recent_issues,
                           low_stock_report=low_stock_report,
                           po_stats=po_stats,
                           departments=[d['department'] for d in departments],
                           selected_dept=dept_filter,
                           start_date=start_date,
                           end_date=end_date)
