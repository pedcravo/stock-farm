from datetime import datetime, timezone
from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login

class User(UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    farmacia_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey('farmacia.id'), index=True)

    farmacia: so.Mapped[Optional['Farmacia']] = so.relationship(back_populates='users')

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Farmacia(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    nome: so.Mapped[str] = so.mapped_column(sa.String(100), unique=True)
    endereco: so.Mapped[str] = so.mapped_column(sa.String(200))
    telefone: so.Mapped[Optional[str]] = so.mapped_column(sa.String(20))
    cep: so.Mapped[str] = so.mapped_column(sa.String(9), nullable=False)
    cnpj: so.Mapped[str] = so.mapped_column(sa.String(14), nullable=False)
    farmaceuticos: so.WriteOnlyMapped['Farmaceutico'] = so.relationship(
        back_populates='farmacia',
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    estoques: so.Mapped['Estoque'] = so.relationship(back_populates='farmacia')
    users: so.WriteOnlyMapped['User'] = so.relationship(
        back_populates='farmacia',
        cascade="all, delete-orphan",
        passive_deletes=True
    )

class Farmaceutico(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    nome: so.Mapped[str] = so.mapped_column(sa.String(100))
    licenca: so.Mapped[str] = so.mapped_column(sa.String(50), unique=True)
    farmacia_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('farmacia.id'))
    farmacia: so.Mapped['Farmacia'] = so.relationship(back_populates='farmaceuticos')

class Fornecedor(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    vendedores: so.WriteOnlyMapped['Vendedor'] = so.relationship(
        back_populates='fornecedor',
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    produtos: so.WriteOnlyMapped['Produto'] = so.relationship(
        back_populates='fornecedor',
        cascade="all, delete-orphan",
        passive_deletes=True
    )

class Fabricante(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    produtos: so.WriteOnlyMapped['Produto'] = so.relationship(
        back_populates='fabricante',
        cascade="all, delete-orphan",
        passive_deletes=True
    )

class Vendedor(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    nome: so.Mapped[str] = so.mapped_column(sa.String(100))
    fornecedor_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('fornecedor.id'))
    fornecedor: so.Mapped['Fornecedor'] = so.relationship(back_populates='vendedores')

class Produto(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    nome: so.Mapped[str] = so.mapped_column(sa.String(100))
    genero: so.Mapped[str] = so.mapped_column(sa.String(100), nullable=False)
    tipo: so.Mapped[str] = so.mapped_column(sa.String(20), nullable=False)
    numeracao_original: so.Mapped[Optional[int]] = so.mapped_column()
    grupo: so.Mapped[str] = so.mapped_column(sa.String(50), nullable=False)
    fabricante_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('fabricante.id'), nullable=False)
    quantidade_embalagem: so.Mapped[int] = so.mapped_column(nullable=False)
    quantidade: so.Mapped[int] = so.mapped_column(nullable=False)
    fornecedor_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('fornecedor.id'), nullable=False)
    preco_compra: so.Mapped[float] = so.mapped_column(nullable=False)
    preco_venda: so.Mapped[float] = so.mapped_column(nullable=False)
    codigo_barras: so.Mapped[str] = so.mapped_column(sa.String(13), nullable=False)
    fornecedor: so.Mapped['Fornecedor'] = so.relationship(back_populates='produtos')
    fabricante: so.Mapped['Fabricante'] = so.relationship(back_populates='produtos')
    estoques: so.WriteOnlyMapped['Estoque'] = so.relationship(
        back_populates='produto',
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    logs: so.WriteOnlyMapped['ProdutoLog'] = so.relationship(
        back_populates='produto',
        cascade="all, delete-orphan",
        passive_deletes=True
    )

class Estoque(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    farmacia_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('farmacia.id'))
    produto_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('produto.id'))
    quantidade: so.Mapped[int] = so.mapped_column(default=0)
    farmacia: so.Mapped['Farmacia'] = so.relationship(back_populates='estoques')
    produto: so.Mapped['Produto'] = so.relationship(back_populates='estoques')

class ProdutoLog(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    produto_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('produto.id'), nullable=False)
    quantidade: so.Mapped[int] = so.mapped_column(nullable=False)
    timestamp: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))
    produto: so.Mapped['Produto'] = so.relationship(back_populates='logs')

@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))