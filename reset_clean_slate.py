import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'vsp_supply_chain.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Clean transaction tables
cursor.execute('DELETE FROM notifications')
cursor.execute('DELETE FROM audit_logs')
cursor.execute('DELETE FROM stock_transactions')
cursor.execute('DELETE FROM goods_issues')
cursor.execute('DELETE FROM goods_receipts')
cursor.execute('DELETE FROM purchase_order_items')
cursor.execute('DELETE FROM purchase_orders')
cursor.execute('DELETE FROM request_history')
cursor.execute('DELETE FROM requisition_items')
cursor.execute('DELETE FROM requisitions')

# Remove test suppliers that might have been added in tests
cursor.execute("DELETE FROM suppliers WHERE id > 4")

# Reset sequence
tables = ['requisitions', 'requisition_items', 'request_history', 'purchase_orders', 
          'purchase_order_items', 'goods_receipts', 'goods_issues', 'stock_transactions', 
          'audit_logs', 'notifications']
for t in tables:
    cursor.execute("DELETE FROM sqlite_sequence WHERE name = ?", (t,))

# Reset material stock to standard baseline
cursor.execute("UPDATE materials SET reserved_qty = 0")
baseline_stocks = {
    1: 25, 2: 8, 3: 30, 4: 12, 5: 3, 6: 15, 7: 45, 8: 4, 9: 85, 10: 1
}
for mat_id, stk in baseline_stocks.items():
    cursor.execute("UPDATE materials SET current_stock = ? WHERE id = ?", (stk, mat_id))

conn.commit()
print("Clean blank slate ready! Transaction tables: 0. Standard users & materials preserved.")
conn.close()
