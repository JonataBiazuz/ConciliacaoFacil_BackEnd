import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory
from flask_cors import CORS
from src.models.conciliacao import db
from src.routes.extrato import extrato_bp
from src.routes.conta_receber import conta_receber_bp
from src.routes.conciliacao import conciliacao_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT'

# Habilita CORS para todas as rotas
CORS(app)

# Registra blueprints
app.register_blueprint(extrato_bp, url_prefix='/api/extrato')
app.register_blueprint(conta_receber_bp, url_prefix='/api/conta-receber')
app.register_blueprint(conciliacao_bp, url_prefix='/api/conciliacao')

# Configuração do banco de dados
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'database', 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()

@app.route('/api/status', methods=['GET'])
def status():
    """Endpoint de status da API"""
    return {
        'status': 'online',
        'message': 'API de Conciliação Bancária funcionando',
        'version': '1.0.0'
    }

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
