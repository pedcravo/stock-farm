from app import app, db
from app.models import User, Role, Farmacia, Farmaceutico, Fornecedor, Vendedor, Medicamento, Estoque, Pedido, ItensPedido

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Role': Role,
        'Farmacia': Farmacia,
        'Farmaceutico': Farmaceutico,
        'Fornecedor': Fornecedor,
        'Vendedor': Vendedor,
        'Medicamento': Medicamento,
        'Estoque': Estoque,
        'Pedido': Pedido,
        'ItensPedido': ItensPedido
    }