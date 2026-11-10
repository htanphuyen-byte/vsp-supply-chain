import sys
import os
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app import create_app
from database import get_db

class TestVSPSupplyChainComplete(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.ts = int(time.time())

    def test_01_authentication_and_access_control(self):
        print("\n[TEST 1] Kiem tra Xac thuc, Dang ky tu kich hoat & Dang nhap bang Email/Username...")
        # 1. Invalid login
        res = self.client.post('/auth/login', data={'identifier': 'invalid_user', 'password': 'bad_password'}, follow_redirects=True)
        self.assertIn("không chính xác", res.text.lower())

        # 2. Login as employee with username
        res = self.client.post('/auth/login', data={'identifier': 'lan_nv', 'password': '123456'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Nguyễn Văn Hải", res.text)

        # 3. Login as employee with Email
        res = self.client.post('/auth/login', data={'identifier': 'hai.nv@vietsov.com.vn', 'password': '123456'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Nguyễn Văn Hải", res.text)

        # 4. Access control: Employee forbidden from Admin and Manager views
        res = self.client.get('/admin/users', follow_redirects=True)
        self.assertIn("Bạn không có quyền truy cập", res.text)
        res = self.client.get('/manager/approvals', follow_redirects=True)
        self.assertIn("Bạn không có quyền truy cập", res.text)

        # 5. Register new user with full required fields
        reg_user = f"nv_{self.ts}"
        reg_empid = f"NV-{self.ts % 100000}"
        res = self.client.post('/auth/register', data={
            'full_name': 'Kỹ Sư Công Trình Mới',
            'employee_id': reg_empid,
            'department': 'Đội Công Trình Biển',
            'position': 'Kỹ sư giàn',
            'email': f'{reg_user}@vietsov.com.vn',
            'phone': '0912345678',
            'username': reg_user,
            'password': 'Password123!',
            'confirm_password': 'Password123!'
        }, follow_redirects=True)
        self.assertIn("thành công", res.text.lower())

        # Verify DB auto-activation and default role
        conn = get_db()
        u = conn.execute("SELECT * FROM users WHERE username = ?", (reg_user,)).fetchone()
        conn.close()
        self.assertIsNotNone(u)
        self.assertEqual(u['employee_id'], reg_empid)
        self.assertEqual(u['role'], 'employee')
        self.assertEqual(u['is_active'], 1)
        print(" -> Dang ky tu kich hoat (role=employee) & Dang nhap Username/Email: DAT")

    def test_02_draft_creation_and_rejection_validation(self):
        print("\n[TEST 2] Kiem tra Luu nhap (Draft) & Bat buoc ly do khi Tu choi (Rejection)...")
        # Login as employee
        self.client.post('/auth/login', data={'identifier': 'lan_nv', 'password': '123456'}, follow_redirects=True)

        # 1. Save request as DRAFT
        res = self.client.post('/employee/create-request', data={
            'title': f'Bản nháp yêu cầu thiết bị {self.ts}',
            'reason': 'Cần lưu tạm trước khi gửi duyệt',
            'priority': 'normal',
            'action_type': 'draft',
            'material_id[]': [1],
            'quantity[]': [2]
        }, follow_redirects=True)
        self.assertIn("bản nháp", res.text.lower())

        conn = get_db()
        draft_req = conn.execute("SELECT * FROM requisitions WHERE status = 'draft' ORDER BY id DESC LIMIT 1").fetchone()
        self.assertIsNotNone(draft_req)
        draft_id = draft_req['id']

        # 2. Submit the draft
        res = self.client.post(f'/employee/request/{draft_id}/edit', data={
            'title': f'Yêu cầu chính thức từ bản nháp {self.ts}',
            'reason': 'Đã bổ sung đầy đủ thông tin để trình duyệt',
            'priority': 'urgent',
            'action_type': 'submit',
            'material_id[]': [1],
            'quantity[]': [3]
        }, follow_redirects=True)
        self.assertIn("chính thức gửi", res.text.lower())

        sub_req = conn.execute("SELECT * FROM requisitions WHERE id = ?", (draft_id,)).fetchone()
        self.assertEqual(sub_req['status'], 'submitted')

        # Supply receives and forwards to Manager
        self.client.post('/auth/login', data={'identifier': 'cungung_nv', 'password': '123456'}, follow_redirects=True)
        self.client.post(f'/procurement/receive/{draft_id}', follow_redirects=True)
        self.client.post(f'/procurement/review/{draft_id}', data={'procurement_note': 'Đã kiểm tra sơ bộ'}, follow_redirects=True)

        rev_req = conn.execute("SELECT * FROM requisitions WHERE id = ?", (draft_id,)).fetchone()
        self.assertEqual(rev_req['status'], 'pending_approval')

        # 3. Manager tries to REJECT WITHOUT REASON -> Must fail!
        self.client.post('/auth/login', data={'identifier': 'lanhdao', 'password': '123456'}, follow_redirects=True)
        res = self.client.post(f'/manager/approve/{draft_id}', data={
            'decision': 'reject',
            'manager_note': '   ' # whitespace only
        }, follow_redirects=True)
        self.assertIn("bắt buộc phải nhập lý do", res.text.lower())

        # Check status is still pending_approval
        sub_req2 = conn.execute("SELECT * FROM requisitions WHERE id = ?", (draft_id,)).fetchone()
        self.assertEqual(sub_req2['status'], 'pending_approval')

        # 4. Manager rejects WITH REASON
        res = self.client.post(f'/manager/approve/{draft_id}', data={
            'decision': 'reject',
            'manager_note': 'Không đủ ngân sách dự phòng trong quý 4'
        }, follow_redirects=True)
        self.assertIn("từ chối", res.text.lower())

        sub_req3 = conn.execute("SELECT * FROM requisitions WHERE id = ?", (draft_id,)).fetchone()
        self.assertEqual(sub_req3['status'], 'rejected')
        conn.close()
        print(" -> Luu nhap, gui chinh thuc & Bat buoc ly do tu choi: DAT")

    def test_03_supplier_and_po_integrity(self):
        print("\n[TEST 3] Kiem tra Quan ly Nha cung cap & An toan du lieu...")
        self.client.post('/auth/login', data={'identifier': 'cungung_nv', 'password': '123456'}, follow_redirects=True)

        sup_email = f'doitac_{self.ts}@supply.vn'
        res = self.client.post('/suppliers/add', data={
            'name': f'Nhà Cung Ứng Kỹ Thuật {self.ts}',
            'tax_id': '3500888999',
            'contact_person': 'Trần Văn Đối Tác',
            'phone': '0988776655',
            'email': sup_email,
            'address': 'Khu công nghiệp Đông Xuyên, Vũng Tàu',
            'rating': '5',
            'supplied_categories': 'Thiết bị lặn, Vật tư cơ khí',
            'cooperation_status': 'active'
        }, follow_redirects=True)
        self.assertIn("thành công", res.text.lower())

        conn = get_db()
        sup = conn.execute("SELECT * FROM suppliers WHERE email = ?", (sup_email,)).fetchone()
        self.assertIsNotNone(sup)
        sup_id = sup['id']

        # Edit supplier
        res = self.client.post(f'/suppliers/edit/{sup_id}', data={
            'name': f'Nhà Cung Ứng Kỹ Thuật Quốc Tế {self.ts}',
            'tax_id': '3500888999',
            'contact_person': 'Trần Văn Đối Tác Cấp Cao',
            'phone': '0988776655',
            'email': sup_email,
            'address': 'Khu công nghiệp Đông Xuyên, Vũng Tàu',
            'rating': '5',
            'supplied_categories': 'Thiết bị lặn, Vật tư cơ khí',
            'cooperation_status': 'active'
        }, follow_redirects=True)
        self.assertIn("thành công", res.text.lower())

        # Safe delete without PO: hard deletes
        res = self.client.post(f'/suppliers/delete/{sup_id}', follow_redirects=True)
        self.assertIn("thành công", res.text.lower())
        sup_check = conn.execute("SELECT * FROM suppliers WHERE id = ?", (sup_id,)).fetchone()
        self.assertIsNone(sup_check)
        conn.close()
        print(" -> Quan ly nha cung cap & An toan du lieu: DAT")

    def test_04_full_9_steps_inventory_and_goods_movement(self):
        print("\n[TEST 4] Kiem tra QUY TRINH 9 BUOC, Nhap kho (Goods Receipt) & Xuat kho (Goods Issue)...")
        conn = get_db()
        mat = conn.execute("SELECT * FROM materials WHERE id = 10").fetchone()
        self.assertIsNotNone(mat)
        initial_stock = mat['current_stock']
        # Request more than currently available (current_stock = 1) to trigger purchasing flow!
        req_quantity = 5

        # STEP 1: Employee creates formal request
        self.client.post('/auth/login', data={'identifier': 'tau_nv', 'password': '123456'}, follow_redirects=True)
        res = self.client.post('/employee/create-request', data={
            'title': f'Cấp phát vật tư cho tàu VSP-02 đợt {self.ts}',
            'reason': 'Bảo dưỡng định kỳ hệ thống thủy lực biển',
            'priority': 'urgent',
            'action_type': 'submit',
            'material_id[]': [10],
            'quantity[]': [req_quantity]
        }, follow_redirects=True)
        self.assertIn("thành công", res.text.lower())

        req = conn.execute("SELECT * FROM requisitions ORDER BY id DESC LIMIT 1").fetchone()
        req_id = req['id']
        self.assertEqual(req['status'], 'submitted')
        print(f" -> Buoc 1: Yeu cau {req['req_code']} khoi tao (submitted)")

        # STEP 2: Procurement receives
        self.client.post('/auth/login', data={'identifier': 'cungung_nv', 'password': '123456'}, follow_redirects=True)
        self.client.post(f'/procurement/receive/{req_id}', follow_redirects=True)
        req = conn.execute("SELECT * FROM requisitions WHERE id = ?", (req_id,)).fetchone()
        self.assertEqual(req['status'], 'received')
        print(f" -> Buoc 2: Cung ung tiep nhan (received)")

        # STEP 3: Procurement checks feasibility & submits to Manager
        res = self.client.post(f'/procurement/review/{req_id}', data={
            'procurement_note': 'Đã kiểm tra kho: Thiếu hàng, cần làm đơn PO mua sắm'
        }, follow_redirects=True)
        req = conn.execute("SELECT * FROM requisitions WHERE id = ?", (req_id,)).fetchone()
        self.assertEqual(req['status'], 'pending_approval')
        print(f" -> Buoc 3: Cung ung trinh lanh dao (pending_approval)")

        # STEP 4: Manager Approves (Stock is NOT reduced here!)
        self.client.post('/auth/login', data={'identifier': 'lanhdao', 'password': '123456'}, follow_redirects=True)
        res = self.client.post(f'/manager/approve/{req_id}', data={
            'decision': 'approve',
            'manager_note': 'Phê duyệt mua sắm bổ sung do thiếu hàng'
        }, follow_redirects=True)
        req = conn.execute("SELECT * FROM requisitions WHERE id = ?", (req_id,)).fetchone()
        self.assertEqual(req['status'], 'purchasing')

        # Verify stock did not drop immediately upon approval
        mat_after_appr = conn.execute("SELECT * FROM materials WHERE id = 10").fetchone()
        self.assertEqual(mat_after_appr['current_stock'], initial_stock)
        print(" -> Buoc 4: Lanh dao phe duyet mua sam (Ton kho THUC TE KHONG BI TRU O BUOC NAY)")

        # STEP 5 & 6: Procurement creates PO for the needed quantity
        self.client.post('/auth/login', data={'identifier': 'cungung_nv', 'password': '123456'}, follow_redirects=True)
        res = self.client.post('/procurement/create-po', data={
            'supplier_id': 1,
            'requisition_id': req_id,
            'expected_delivery_date': '2026-12-01',
            'notes': 'Hàng đặt chuẩn kỹ thuật dầu khí',
            'material_id[]': [10],
            'order_qty[]': [req_quantity],
            'unit_price[]': [35000000]
        }, follow_redirects=True)
        self.assertIn("thành công", res.text.lower())

        po = conn.execute("SELECT * FROM purchase_orders WHERE requisition_id = ? ORDER BY id DESC LIMIT 1", (req_id,)).fetchone()
        po_id = po['id']
        self.assertEqual(po['status'], 'po_created')
        print(f" -> Buoc 6: Don dat hang PO {po['po_code']} da lap (po_created)")

        # STEP 7: Delivering (in_transit)
        res = self.client.post(f'/procurement/po/{po_id}/update-status', data={'status': 'in_transit'}, follow_redirects=True)
        po = conn.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,)).fetchone()
        self.assertEqual(po['status'], 'in_transit')

        # STEP 8.1: PO Received -> Auto Goods Receipt created in goods_receipts
        res = self.client.post(f'/procurement/po/{po_id}/update-status', data={'status': 'fully_received'}, follow_redirects=True)
        gr = conn.execute("SELECT * FROM goods_receipts WHERE po_id = ?", (po_id,)).fetchone()
        self.assertIsNotNone(gr)

        # Stock increased by req_quantity
        mat_after_po = conn.execute("SELECT * FROM materials WHERE id = 10").fetchone()
        self.assertEqual(mat_after_po['current_stock'], initial_stock + req_quantity)

        # Requisition is now ready for issue
        req = conn.execute("SELECT * FROM requisitions WHERE id = ?", (req_id,)).fetchone()
        self.assertEqual(req['status'], 'awaiting_issue')
        print(f" -> Buoc 8.1: Nhap kho tu dong tao Phieu Nhap Kho {gr['receipt_code']} -> Yeu cau san sang xuat")

        # STEP 8.2: Warehouse dispatches goods to employee -> Auto Goods Issue created in goods_issues
        self.client.post('/auth/login', data={'identifier': 'kho_nv', 'password': '123456'}, follow_redirects=True)
        res = self.client.post(f'/warehouse/dispatch/{req_id}', follow_redirects=True)
        self.assertIn("thành công", res.text.lower())

        gi = conn.execute("SELECT * FROM goods_issues WHERE requisition_id = ?", (req_id,)).fetchone()
        self.assertIsNotNone(gi)

        # Stock decreased by req_quantity back to initial_stock
        mat_after_gi = conn.execute("SELECT * FROM materials WHERE id = 10").fetchone()
        self.assertEqual(mat_after_gi['current_stock'], initial_stock)

        req = conn.execute("SELECT * FROM requisitions WHERE id = ?", (req_id,)).fetchone()
        self.assertEqual(req['status'], 'dispatched')
        print(f" -> Buoc 8.2: Thu kho xuat cap tao Phieu Xuat Kho {gi['issue_code']} (dispatched)")

        # STEP 9: Employee confirms handover
        self.client.post('/auth/login', data={'identifier': 'tau_nv', 'password': '123456'}, follow_redirects=True)
        res = self.client.post(f'/employee/request/{req_id}/confirm-receipt', follow_redirects=True)
        self.assertIn("thành công", res.text.lower())

        req = conn.execute("SELECT * FROM requisitions WHERE id = ?", (req_id,)).fetchone()
        self.assertEqual(req['status'], 'completed')
        conn.close()
        print(" -> Buoc 9: Nguoi yeu cau xac nhan ban giao thanh cong (completed)")

    def test_05_goods_receipts_and_issues_pages(self):
        print("\n[TEST 5] Kiem tra Giao dien Danh sach Phieu Nhap / Xuat kho...")
        self.client.post('/auth/login', data={'identifier': 'kho_nv', 'password': '123456'}, follow_redirects=True)

        res_gr = self.client.get('/warehouse/receipts')
        self.assertEqual(res_gr.status_code, 200)
        self.assertIn("Phiếu Nhập Kho", res_gr.text)

        res_gi = self.client.get('/warehouse/issues')
        self.assertEqual(res_gi.status_code, 200)
        self.assertIn("Phiếu Xuất Kho", res_gi.text)
        print(" -> Giao dien Phieu Nhap Kho & Phieu Xuat Kho hoat dong hoan hao: DAT")

    def test_06_admin_logs_and_reports(self):
        print("\n[TEST 6] Kiem tra Dashboard, Bao cao & Admin Audit Logs...")
        # Kiem tra nhan vien khong co quyen truy cap bao cao & thong ke
        self.client.post('/auth/login', data={'identifier': 'lan_nv', 'password': '123456'}, follow_redirects=True)
        res_emp_dash = self.client.get('/')
        self.assertNotIn("Báo Cáo & Thống Kê", res_emp_dash.text)

        res_emp_rep = self.client.get('/reports/', follow_redirects=True)
        self.assertIn("Bạn không có quyền truy cập vào chức năng này.", res_emp_rep.text)

        # Dang nhap admin kiem tra quyen truy cap hop le
        self.client.post('/auth/login', data={'identifier': 'admin', 'password': 'admin123'}, follow_redirects=True)

        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn("Bảng Điều Khiển Tổng Quan", res.text)
        self.assertIn("Báo Cáo & Thống Kê", res.text)

        res_rep = self.client.get('/reports/')
        self.assertEqual(res_rep.status_code, 200)
        self.assertIn("Báo Cáo & Thống Kê Tổng Hợp", res_rep.text)

        res_logs = self.client.get('/admin/logs')
        self.assertEqual(res_logs.status_code, 200)
        self.assertIn("Nhật Ký Hoạt Động", res_logs.text)
        self.assertIn("Quay về Tổng quan", res_logs.text)
        print(" -> Dashboard, Bao cao & Audit Logs (phan quyen Nhan vien / Admin): DAT")

if __name__ == '__main__':
    unittest.main()
