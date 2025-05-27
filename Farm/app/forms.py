from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, FloatField, IntegerField, SelectField, HiddenField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length, NumberRange
from app.models import User, Produto, Farmacia, Fornecedor, Fabricante
from app import db
import sqlalchemy as sa
from flask import request
import re

class LoginForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])
    remember_me = BooleanField('Lembrar-me')
    submit = SubmitField('Entrar')

class RegistrationForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired()])
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    password = PasswordField('Senha', validators=[DataRequired()])
    password2 = PasswordField('Repetir Senha', validators=[DataRequired(), EqualTo('password', message='As senhas devem coincidir')])
    submit = SubmitField('Registrar')

    def validate_username(self, username):
        user = db.session().scalar(sa.select(User).where(User.username == username.data))
        if user is not None:
            raise ValidationError('Por favor, use um nome de usuário diferente.')

    def validate_email(self, email):
        user = db.session().scalar(sa.select(User).where(User.email == email.data))
        if user is not None:
            raise ValidationError('Por favor, use um e-mail diferente.')

class FarmaciaManagementForm(FlaskForm):
    nome = StringField('Nome da Farmácia', validators=[DataRequired(), Length(min=1, max=100)])
    endereco = StringField('Endereço', validators=[Length(min=0, max=200)])
    telefone = StringField('Telefone', validators=[Length(max=20)])
    cep = StringField('CEP', validators=[DataRequired(), Length(min=8, max=9)])
    cnpj = StringField('CNPJ', validators=[DataRequired(), Length(min=14, max=14)])
    create_new = BooleanField('Criar nova farmácia se não encontrada', default=False)
    submit = SubmitField('Gerenciar Farmácia')

    def validate_nome(self, nome):
        farmacia = db.session().scalar(sa.select(Farmacia).where(Farmacia.nome == nome.data))
        if farmacia is not None and not self.create_new.data:
            raise ValidationError('Uma farmácia com esse nome já existe.')

    def validate_cep(self, cep):
        if not re.match(r'^\d{5}-\d{3}$', cep.data):
            raise ValidationError('O CEP deve estar no formato XXXXX-XXX.')

    def validate_cnpj(self, cnpj):
        if not re.match(r'^\d{14}$', cnpj.data):
            raise ValidationError('O CNPJ deve conter exatamente 14 dígitos.')

class ProdutoForm(FlaskForm):
    nome = StringField('Nome do Produto', validators=[DataRequired(), Length(min=1, max=100)])
    genero = StringField('Gênero', validators=[DataRequired(), Length(min=1, max=100)])
    tipo = SelectField('Tipo', choices=[('Generico', 'Genérico'), ('Original', 'Original'), ('Outros', 'Outros')], validators=[DataRequired()])
    numeracao_original = IntegerField('Numeração do Original')
    grupo = StringField('Grupo', validators=[DataRequired(), Length(min=1, max=50)])
    fabricante_id = IntegerField('ID do Fabricante', validators=[DataRequired()])
    quantidade_embalagem = IntegerField('Quantidade por Embalagem', validators=[DataRequired()])
    quantidade = IntegerField('Quantidade no Estoque', validators=[DataRequired()])
    fornecedor_id = IntegerField('ID do Fornecedor', validators=[DataRequired()])
    preco_compra = FloatField('Preço de Compra', validators=[DataRequired()])
    preco_venda = FloatField('Preço de Venda', validators=[DataRequired()])
    codigo_barras = StringField('Código de Barras', validators=[DataRequired(), Length(min=12, max=13)])
    submit = SubmitField('Enviar')

    def __init__(self, original_nome=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_nome = original_nome

class FiltroProdutoForm(FlaskForm):
    nome = StringField('Nome do Produto')
    genero = StringField('Gênero')
    tipo = SelectField('Tipo', choices=[('', 'Todos'), ('Generico', 'Genérico'), ('Original', 'Original'), ('Outros', 'Outros')])
    fabricante_id = IntegerField('ID do Fabricante', default=None)
    codigo_barras = StringField('Código de Barras')
    submit = SubmitField('Filtrar')

class FiltroVendaForm(FlaskForm):
    nome = StringField('Nome do Produto')
    codigo_barras = StringField('Código de Barras')
    submit = SubmitField('Filtrar')

class VendaForm(FlaskForm):
    produto_id = HiddenField('Produto ID')
    quantidade_carrinho = IntegerField('Quantidade no Carrinho', validators=[DataRequired(), NumberRange(min=0, max=999)])
    submit = SubmitField('Adicionar ao Carrinho')
    finalizar_compra = SubmitField('Finalizar Compra')