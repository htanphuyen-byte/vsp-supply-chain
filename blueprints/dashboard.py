from flask import Blueprint, render_template, session
from blueprints import login_required
from database import get_db

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    conn = get_db()

    # 1. Operational Statistics (Calculated dynamically from DB)
    total_requests = conn.execute("SELECT COUNT(*) FROM requisitions").fetchone()[0]
    pending_requests = conn.execute("SELECT COUNT(*) FROM requisitions WHERE status IN ('submitted', 'received', 'under_review', 'pending_approval')").fetchone()[0]
    awaiting_management = conn.execute("SELECT COUNT(*) FROM requisitions WHERE status = 'pending_approval'").fetchone()[0]
    approved_requests = conn.execute("SELECT COUNT(*) FROM requisitions WHERE status IN ('approved', 'purchasing', 'goods_received', 'awaiting_issue', 'dispatched', 'handed_over', 'completed')").fetchone()[0]
    rejected_requests = conn.execute("SELECT COUNT(*) FROM requisitions WHERE status = 'rejected'").fetchone()[0]
    completed_requests = conn.execute("SELECT COUNT(*) FROM requisitions WHERE status = 'completed'").fetchone()[0]

    total_materials = conn.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
    low_stock_count = conn.execute("SELECT COUNT(*) FROM materials WHERE current_stock <= min_stock").fetchone()[0]
    active_pos = conn.execute("SELECT COUNT(*) FROM purchase_orders WHERE status IN ('waiting_purchase', 'po_created', 'sent_supplier', 'in_transit')").fetchone()[0]
    total_suppliers = conn.execute("SELECT COUNT(*) FROM suppliers WHERE cooperation_status = 'active'").fetchone()[0]

    # 2. Latest & Recently updated material requests
    latest_requests = conn.execute('''
        SELECT r.*, u.full_name as requester_name
        FROM requisitions r
        JOIN users u ON r.user_id = u.id
        ORDER BY r.created_at DESC LIMIT 6
    ''').fetchall()

    # 3. Pending approvals for management
    pending_approvals_list = conn.execute('''
        SELECT r.*, u.full_name as requester_name
        FROM requisitions r
        JOIN users u ON r.user_id = u.id
        WHERE r.status = 'pending_approval'
        ORDER BY r.created_at DESC LIMIT 5
    ''').fetchall()

    # 4. Low stock materials alert
    low_stock_items = conn.execute('''
        SELECT m.*, (m.current_stock - m.reserved_qty) as available_qty
        FROM materials m
        WHERE m.current_stock <= m.min_stock
        ORDER BY m.current_stock ASC LIMIT 6
    ''').fetchall()

    # 5. Recent inventory transactions
    recent_transactions = conn.execute('''
        SELECT st.*, m.name as mat_name, m.code as mat_code, m.unit as mat_unit, u.full_name as actor_name
        FROM stock_transactions st
        JOIN materials m ON st.material_id = m.id
        LEFT JOIN users u ON st.user_id = u.id
        ORDER BY st.created_at DESC LIMIT 6
    ''').fetchall()

    # 6. Chart: Requests by Status
    status_counts = conn.execute('''
        SELECT status, COUNT(*) as count FROM requisitions GROUP BY status
    ''').fetchall()

    status_name_map = {
        'draft': 'Bản nháp',
        'submitted': 'Chờ cung ứng',
        'received': 'Cung ứng tiếp nhận',
        'under_review': 'Đang kiểm kho',
        'pending_approval': 'Chờ LĐ duyệt',
        'approved': 'LĐ đã duyệt',
        'rejected': 'Bị từ chối',
        'purchasing': 'Đang mua sắm (PO)',
        'goods_received': 'Hàng về kho',
        'awaiting_issue': 'Chờ xuất cấp',
        'dispatched': 'Kho đã xuất',
        'handed_over': 'Đã bàn giao',
        'completed': 'Hoàn thành'
    }

    req_status_labels = [status_name_map.get(row['status'], row['status']) for row in status_counts]
    req_status_counts = [row['count'] for row in status_counts]

    # 7. Chart: Material Stock Levels (Top 6 items On-hand vs Reserved vs Min)
    stock_levels = conn.execute('''
        SELECT name, current_stock, reserved_qty, min_stock FROM materials ORDER BY id ASC LIMIT 6
    ''').fetchall()

    stock_labels = [row['name'][:18] + '...' if len(row['name']) > 18 else row['name'] for row in stock_levels]
    stock_on_hand = [row['current_stock'] for row in stock_levels]
    stock_reserved = [row['reserved_qty'] for row in stock_levels]
    stock_min = [row['min_stock'] for row in stock_levels]

    # 8. Chart: Monthly Material Requests (last 6 months)
    monthly_reqs = conn.execute('''
        SELECT strftime('%m/%Y', created_at) as month, COUNT(*) as count
        FROM requisitions
        GROUP BY month
        ORDER BY created_at ASC LIMIT 6
    ''').fetchall()

    month_labels = [row['month'] for row in monthly_reqs]
    month_counts = [row['count'] for row in monthly_reqs]

    conn.close()

    return render_template('dashboard/index.html',
                           total_requests=total_requests,
                           pending_requests=pending_requests,
                           awaiting_management=awaiting_management,
                           approved_requests=approved_requests,
                           rejected_requests=rejected_requests,
                           completed_requests=completed_requests,
                           total_materials=total_materials,
                           low_stock_count=low_stock_count,
                           active_pos=active_pos,
                           total_suppliers=total_suppliers,
                           latest_requests=latest_requests,
                           pending_approvals_list=pending_approvals_list,
                           low_stock_items=low_stock_items,
                           recent_transactions=recent_transactions,
                           req_status_labels=req_status_labels,
                           req_status_counts=req_status_counts,
                           stock_labels=stock_labels,
                           stock_on_hand=stock_on_hand,
                           stock_reserved=stock_reserved,
                           stock_min=stock_min,
                           month_labels=month_labels,
                           month_counts=month_counts)
