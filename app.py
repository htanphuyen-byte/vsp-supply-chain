import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from flask import Flask, session
from config import Config
from database import init_db
from models.audit_model import AuditModel

# Import Blueprints
from blueprints.auth import auth_bp
from blueprints.dashboard import dashboard_bp
from blueprints.employee import employee_bp
from blueprints.manager import manager_bp
from blueprints.procurement import procurement_bp
from blueprints.warehouse import warehouse_bp
from blueprints.supplier import supplier_bp
from blueprints.reports import reports_bp
from blueprints.admin import admin_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize Database
    with app.app_context():
        init_db()

    # Register Blueprints (Separation into distinct actors & modules)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(manager_bp)
    app.register_blueprint(procurement_bp)
    app.register_blueprint(warehouse_bp)
    app.register_blueprint(supplier_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_bp)

    @app.context_processor
    def inject_global_data():
        if 'user_id' in session:
            notifs = AuditModel.get_notifications(user_id=session.get('user_id'), role=session.get('role'))
            return {'notifications': notifs}
        return {'notifications': []}

    return app

app = create_app()

if __name__ == '__main__':
    print("==================================================================")
    print("  VIETSOVPETRO SUPPLY CHAIN MANAGEMENT (VSP SCM)")
    print("  Local:   http://127.0.0.1:5000 or http://localhost:5000")
    print("  Network: http://192.168.1.9:5000")
    print("==================================================================")
    app.run(host='0.0.0.0', port=5000, debug=False)
