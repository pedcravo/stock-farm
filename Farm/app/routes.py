from urllib.parse import urlsplit
from flask import render_template, flash, redirect, url_for, request, session
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from sqlalchemy.orm import joinedload
from app import app, db
from app.forms import LoginForm, RegistrationForm, ProdutoForm, FarmaciaManagementForm, FiltroProdutoForm, FiltroVendaForm, VendaForm
from app.models import User, Produto, Estoque, Farmacia, Fornecedor, Fabricante, ProdutoLog
from datetime import datetime

@app.route('/')
@app.route('/index')
@login_required
def index():
    if not current_user.farmacia:
        return redirect(url_for('manage_farmacia'))
    estoques = db.session().scalars(
        sa.select(Estoque).where(Estoque.farmacia_id == current_user.farmacia_id)
    ).all()
    produtos = [estoque.produto for estoque in estoques]
    farmacia_nome = current_user.farmacia.nome if current_user.farmacia else "Nenhuma farmácia associada"
    return render_template('index.html', title='Início - Stock Farm', produtos=produtos, can_manage=True, farmacia_nome=farmacia_nome)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session().scalar(sa.select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash('Usuário ou senha inválidos')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Entrar - Stock Farm', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Parabéns, você foi registrado com sucesso!')
        login_user(user, remember=False)
        return redirect(url_for('manage_farmacia'))
    return render_template('register.html', title='Registrar - Stock Farm', form=form)

@app.route('/manage_farmacia', methods=['GET', 'POST'])
@login_required
def manage_farmacia():
    form = FarmaciaManagementForm()

    if form.validate_on_submit():
        farmacia = db.session().scalar(sa.select(Farmacia).filter_by(nome=form.nome.data))
        if farmacia and not form.create_new.data:
            current_user.farmacia_id = farmacia.id
            db.session.commit()
            flash(f'Conectado à farmácia {farmacia.nome}!')
            return redirect(url_for('index'))
        elif form.create_new.data and (form.endereco.data or form.endereco.data == ""):
            farmacia = Farmacia(
                nome=form.nome.data,
                endereco=form.endereco.data or "",
                telefone=form.telefone.data,
                cep=form.cep.data,
                cnpj=form.cnpj.data
            )
            db.session.add(farmacia)
            db.session.commit()
            current_user.farmacia_id = farmacia.id
            db.session.commit()
            flash('Farmácia criada com sucesso!')
            return redirect(url_for('index'))
        else:
            flash('Erro: Preencha o endereço para criar uma nova farmácia.')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Erro no campo {field}: {error}')

    return render_template('manage_farmacia.html', title='Gerenciar Farmácia - Stock Farm', form=form)

@app.route('/stock', methods=['GET'])
@login_required
def stock():
    if not current_user.farmacia:
        return redirect(url_for('manage_farmacia'))
    
    form = FiltroProdutoForm(request.args)
    query = (
        sa.select(Estoque)
        .where(Estoque.farmacia_id == current_user.farmacia_id)
        .join(Produto, Produto.id == Estoque.produto_id)
        .options(joinedload(Estoque.produto))
    )

    if form.nome.data:
        query = query.where(Produto.nome.ilike(f'%{form.nome.data}%'))
    if form.genero.data:
        query = query.where(Produto.genero.ilike(f'%{form.genero.data}%'))
    if form.tipo.data:
        query = query.where(Produto.tipo == form.tipo.data)
    if form.fabricante_id.data:
        query = query.where(Produto.fabricante_id == form.fabricante_id.data)
    if form.codigo_barras.data:
        query = query.where(Produto.codigo_barras.ilike(f'%{form.codigo_barras.data}%'))

    estoques = db.session().scalars(query).all()
    if not estoques and (form.nome.data or form.genero.data or form.tipo.data or form.fabricante_id.data or form.codigo_barras.data):
        flash('Nenhum produto encontrado com essas especificações.', 'info')

    return render_template('stock.html', title='Estoque - Stock Farm', estoques=estoques, can_manage=True, form=form)

@app.route('/add_produto', methods=['GET', 'POST'])
@login_required
def add_produto():
    if not current_user.farmacia:
        return redirect(url_for('manage_farmacia'))
    form = ProdutoForm()
    if form.validate_on_submit():
        fabricante = db.session().scalar(sa.select(Fabricante).where(Fabricante.id == form.fabricante_id.data))
        if not fabricante:
            fabricante = Fabricante(id=form.fabricante_id.data)
            db.session.add(fabricante)
            db.session.commit()

        fornecedor = db.session().scalar(sa.select(Fornecedor).where(Fornecedor.id == form.fornecedor_id.data))
        if not fornecedor:
            fornecedor = Fornecedor(id=form.fornecedor_id.data)
            db.session.add(fornecedor)
            db.session.commit()

        produto = Produto(
            nome=form.nome.data,
            genero=form.genero.data,
            tipo=form.tipo.data,
            numeracao_original=form.numeracao_original.data,
            grupo=form.grupo.data,
            fabricante_id=form.fabricante_id.data,
            quantidade_embalagem=form.quantidade_embalagem.data,
            quantidade=form.quantidade.data,
            fornecedor_id=form.fornecedor_id.data,
            preco_compra=form.preco_compra.data,
            preco_venda=form.preco_venda.data,
            codigo_barras=form.codigo_barras.data
        )
        db.session.add(produto)
        db.session.commit()
        estoque = Estoque(farmacia_id=current_user.farmacia_id, produto_id=produto.id, quantidade=0)
        db.session.add(estoque)
        db.session.commit()
        flash('Produto adicionado com sucesso!')
        return redirect(url_for('stock'))
    return render_template('edit_produto.html', title='Adicionar Produto - Stock Farm', form=form)

@app.route('/edit_produto/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_produto(id):
    if not current_user.farmacia:
        return redirect(url_for('manage_farmacia'))
    produto = db.session().get(Produto, id) or db.first_or_404(sa.select(Produto).where(Produto.id == id))
    estoque = db.session().scalar(
        sa.select(Estoque).where(
            Estoque.farmacia_id == current_user.farmacia_id,
            Estoque.produto_id == id
        )
    )
    if not estoque:
        flash('Você não tem permissão para editar este produto.')
        return redirect(url_for('stock'))
    form = ProdutoForm(original_nome=produto.nome)
    if form.validate_on_submit():
        quantidade_antiga = produto.quantidade
        produto.nome = form.nome.data
        produto.genero = form.genero.data
        produto.tipo = form.tipo.data
        produto.numeracao_original = form.numeracao_original.data
        produto.grupo = form.grupo.data
        produto.fabricante_id = form.fabricante_id.data
        produto.quantidade_embalagem = form.quantidade_embalagem.data
        produto.quantidade = form.quantidade.data
        produto.fornecedor_id = form.fornecedor_id.data
        produto.preco_compra = form.preco_compra.data
        produto.preco_venda = form.preco_venda.data
        produto.codigo_barras = form.codigo_barras.data
        fabricante = db.session().scalar(sa.select(Fabricante).where(Fabricante.id == form.fabricante_id.data))
        if not fabricante:
            fabricante = Fabricante(id=form.fabricante_id.data)
            db.session.add(fabricante)
            db.session.commit()
        fornecedor = db.session().scalar(sa.select(Fornecedor).where(Fornecedor.id == form.fornecedor_id.data))
        if not fornecedor:
            fornecedor = Fornecedor(id=form.fornecedor_id.data)
            db.session.add(fornecedor)
            db.session.commit()
        if quantidade_antiga != form.quantidade.data:
            log = ProdutoLog(produto_id=produto.id, quantidade=produto.quantidade)
            db.session.add(log)
        db.session.commit()
        flash('Produto atualizado com sucesso!')
        return redirect(url_for('stock'))
    elif request.method == 'GET':
        form.nome.data = produto.nome
        form.genero.data = produto.genero
        form.tipo.data = produto.tipo
        form.numeracao_original.data = produto.numeracao_original
        form.grupo.data = produto.grupo
        form.fabricante_id.data = produto.fabricante_id
        form.quantidade_embalagem.data = produto.quantidade_embalagem
        form.quantidade.data = produto.quantidade
        form.fornecedor_id.data = produto.fornecedor_id
        form.preco_compra.data = produto.preco_compra
        form.preco_venda.data = produto.preco_venda
        form.codigo_barras.data = produto.codigo_barras
    return render_template('edit_produto.html', title='Editar Produto - Stock Farm', form=form)

@app.route('/delete_produto/<int:id>')
@login_required
def delete_produto(id):
    if not current_user.farmacia:
        return redirect(url_for('manage_farmacia'))
    produto = db.session().get(Produto, id) or db.first_or_404(sa.select(Produto).where(Produto.id == id))
    estoque = db.session().scalar(
        sa.select(Estoque).where(
            Estoque.farmacia_id == current_user.farmacia_id,
            Estoque.produto_id == id
        )
    )
    if not estoque:
        flash('Você não tem permissão para excluir este produto.')
        return redirect(url_for('stock'))
    db.session.delete(produto)
    db.session.commit()
    flash('Produto excluído com sucesso!')
    return redirect(url_for('stock'))

@app.route('/view_produto/<int:id>')
@login_required
def view_produto(id):
    if not current_user.farmacia:
        return redirect(url_for('manage_farmacia'))
    produto = db.session().get(Produto, id) or db.first_or_404(sa.select(Produto).where(Produto.id == id))
    estoque = db.session().scalar(
        sa.select(Estoque).where(
            Estoque.farmacia_id == current_user.farmacia_id,
            Estoque.produto_id == id
        )
    )
    if not estoque:
        flash('Você não tem permissão para visualizar este produto.')
        return redirect(url_for('stock'))
    return render_template('view_produto.html', title='Detalhes do Produto - Stock Farm', produto=produto)

@app.route('/vendas', methods=['GET', 'POST'])
@login_required
def vendas():
    if not current_user.farmacia:
        return redirect(url_for('manage_farmacia'))

    filtro_form = FiltroVendaForm(request.args)
    venda_form = VendaForm()

    # Inicializar o carrinho na sessão se não existir
    if 'carrinho' not in session:
        session['carrinho'] = {}

    # Lógica para adicionar ao carrinho
    if request.method == 'POST' and 'quantidade_carrinho' in request.form:
        produto_id = request.form.get('produto_id')
        quantidade = request.form.get('quantidade_carrinho')
        if not produto_id or not quantidade:
            flash('Erro: Produto ou quantidade não informados.', 'error')
            return redirect(url_for('vendas'))
        try:
            produto_id = str(produto_id)
            quantidade = int(quantidade)
            produto = db.session().get(Produto, int(produto_id))
            if not produto:
                flash('Produto não encontrado.', 'error')
                return redirect(url_for('vendas'))
            if quantidade <= 0:
                flash('A quantidade deve ser maior que zero.', 'error')
                return redirect(url_for('vendas'))
            if quantidade > produto.quantidade:
                flash(f'Quantidade insuficiente em estoque. Disponível: {produto.quantidade}.', 'error')
                return redirect(url_for('vendas'))
            session['carrinho'][produto_id] = quantidade
            session.modified = True
            flash('Produto adicionado ao carrinho!', 'success')
            return redirect(url_for('vendas'))
        except ValueError:
            flash('Erro: Quantidade inválida.', 'error')
            return redirect(url_for('vendas'))

    # Lógica para remover do carrinho
    if request.method == 'POST' and 'remove_from_cart_action' in request.form:
        produto_id = request.form.get('produto_id')
        if not produto_id:
            flash('Erro: Produto não informado.', 'error')
            return redirect(url_for('vendas'))
        produto_id = str(produto_id)
        if produto_id in session['carrinho']:
            del session['carrinho'][produto_id]
            session.modified = True
            flash('Produto removido do carrinho!', 'success')
        else:
            flash('Produto não estava no carrinho.', 'info')
        return redirect(url_for('vendas'))

    # Lógica para registrar a compra
    if request.method == 'POST' and 'finalizar_compra_action' in request.form:
        if not session['carrinho']:
            flash('O carrinho está vazio.', 'error')
            return redirect(url_for('vendas'))
        for produto_id, quantidade in session['carrinho'].items():
            try:
                produto = db.session().get(Produto, int(produto_id))
                if produto:
                    quantidade_antiga = produto.quantidade
                    produto.quantidade -= quantidade
                    if produto.quantidade < 0:
                        flash(f'Erro: Estoque insuficiente para o produto {produto.nome}.', 'error')
                        return redirect(url_for('vendas'))
                    # Registrar log da alteração de quantidade
                    log = ProdutoLog(produto_id=produto.id, quantidade=produto.quantidade)
                    db.session.add(log)
            except Exception as e:
                flash(f'Erro ao processar o produto {produto_id}: {str(e)}', 'error')
                db.session.rollback()
                return redirect(url_for('vendas'))
        db.session.commit()
        session['carrinho'] = {}
        session.modified = True
        flash('Compra registrada com sucesso!', 'success')
        return redirect(url_for('vendas'))

    # Lógica de filtro
    query = (
        sa.select(Estoque)
        .where(Estoque.farmacia_id == current_user.farmacia_id)
        .join(Produto, Produto.id == Estoque.produto_id)
        .options(joinedload(Estoque.produto))
    )

    if filtro_form.nome.data:
        query = query.where(Produto.nome.ilike(f'%{filtro_form.nome.data}%'))
    if filtro_form.codigo_barras.data:
        query = query.where(Produto.codigo_barras.ilike(f'%{filtro_form.codigo_barras.data}%'))

    estoques = db.session().scalars(query).all()

    # Se o filtro estiver vazio, mostrar apenas os produtos no carrinho
    if not (filtro_form.nome.data or filtro_form.codigo_barras.data):
        if session['carrinho']:
            estoques = [
                estoque for estoque in estoques
                if str(estoque.produto_id) in session['carrinho']
            ]
        else:
            estoques = []

    # Mensagem se não houver resultados após filtragem
    if not estoques and (filtro_form.nome.data or filtro_form.codigo_barras.data):
        flash('Nenhum produto encontrado com essas especificações.', 'info')

    return render_template(
        'vendas.html',
        title='Vendas - Stock Farm',
        filtro_form=filtro_form,
        venda_form=venda_form,
        estoques=estoques,
        carrinho=session['carrinho']
    )

@app.route('/relatorio', methods=['GET'])
@login_required
def relatorio():
    if not current_user.farmacia:
        return redirect(url_for('manage_farmacia'))

    page = request.args.get('page', default=1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    query = (
        sa.select(ProdutoLog)
        .join(Produto, Produto.id == ProdutoLog.produto_id)
        .options(joinedload(ProdutoLog.produto))
        .order_by(ProdutoLog.timestamp.desc())
    )

    total_logs = db.session().scalar(sa.select(sa.func.count()).select_from(ProdutoLog))
    logs = db.session().scalars(query.offset(offset).limit(per_page)).all()

    # Preparar dados para exibição
    logs_data = []
    for log in logs:
        produto = log.produto
        data = log.timestamp.strftime('%Y-%m-%d %H:%M') if log.timestamp else 'Sem data'
        quantidade_retirada = log.quantidade if log.quantidade < 0 else None
        quantidade_adicionada = log.quantidade if log.quantidade > 0 else None
        logs_data.append({
            'data': data,
            'produto': produto.nome,
            'quantidade_retirada': abs(quantidade_retirada) if quantidade_retirada else None,
            'quantidade_adicionada': quantidade_adicionada if quantidade_adicionada else None,
            'codigo_barras': produto.codigo_barras
        })

    has_next = offset + per_page < total_logs
    has_prev = page > 1

    return render_template(
        'relatorio.html',
        title='Relatório - Stock Farm',
        logs=logs_data,
        page=page,
        has_next=has_next,
        has_prev=has_prev
    )