from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'  # Ajuste conforme seu banco
app.config.from_object(Config)

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login = LoginManager(app)
login.login_view = 'login'

# Importar rotas, modelos e erros somente após a inicialização do db
from app import routes, models, errors

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': models.User,
        'Farmacia': models.Farmacia,
        'Farmaceutico': models.Farmaceutico,
        'Fornecedor': models.Fornecedor,
        'Vendedor': models.Vendedor,
        'Medicamento': models.Medicamento,
        'Estoque': models.Estoque,
        'Pedido': models.Pedido,
        'ItensPedido': models.ItensPedido
    }