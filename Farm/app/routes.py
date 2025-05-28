from urllib.parse import urlsplit
from flask import render_template, flash, redirect, url_for, request, session
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from sqlalchemy.orm import joinedload
from app import app, db
from app.forms import LoginForm, RegistrationForm, ProdutoForm, FarmaciaManagementForm, FiltroProdutoForm, FiltroVendaForm, VendaForm, AddQuantidadeForm
from app.models import User, Produto, Estoque, Farmacia, Fornecedor, Fabricante, ProdutoLog, Validade
from datetime import datetime, timedelta
import statistics
from dateutil import parser

@app.route('/')
@app.route('/index')
@login_required
def index():
    if not current_user.farmacia:
        return redirect(url_for('manage_farmacia'))
    estoques = db.session().scalars(
        sa.select(Estoque).where(Estoque.farmacia_id == current_user.farmacia_id)
    ).all()
    produtos = [estoque.produto for estoque in estoques if estoque.produto is not None]
    farmacia_nome = current_user.farmacia.nome if current_user.farmacia else "Nenhuma farmácia associada"

    # Verificar produtos com estoque zerado, próximos da validade e estoque excedente
    now = datetime.now() - timedelta(hours=3)
    data_limite_validade = now + timedelta(days=7)  # 1 semana para vencer
    for produto in produtos:
        if produto is not None:
            # Estoque zerado
            total_quantidade = db.session().scalar(
                sa.select(sa.func.sum(Validade.quantidade))
                .where(Validade.produto_id == produto.id)
            ) or 0
            if total_quantidade == 0:
                flash(f'O produto {produto.nome} está com estoque zerado. Considere reabastecer.', 'warning')

            # Produtos próximos da validade
            validades = db.session().scalars(
                sa.select(Validade)
                .where(Validade.produto_id == produto.id)
                .where(Validade.quantidade > 0)
                .where(Validade.data_validade <= data_limite_validade)
            ).all()
            for validade in validades:
                dias_restantes = (validade.data_validade - now).days
                if 0 < dias_restantes <= 7:
                    flash(f'O produto {produto.nome} tem {validade.quantidade} unidades vencendo em {dias_restantes} dias (em {validade.data_validade.strftime("%d-%m-%Y")}).', 'warning')

            # Calcular estoque excedente (estoque atual > quantidade máxima)
            # Usar um período padrão (ex.: última semana) para calcular a demanda
            data_inicio = now - timedelta(days=7)
            data_fim = now
            data_inicio = data_inicio.replace(hour=0, minute=0, second=0, microsecond=0)
            data_fim = data_fim.replace(hour=23, minute=59, second=59, microsecond=999999)

            logs_produto = db.session().scalars(
                sa.select(ProdutoLog)
                .where(ProdutoLog.produto_id == produto.id)
                .where(ProdutoLog.timestamp >= data_inicio)
                .where(ProdutoLog.timestamp <= data_fim)
                .order_by(ProdutoLog.timestamp.asc())
            ).all()

            entradas = []
            saidas = []
            for log in logs_produto:
                log_timestamp = log.timestamp - timedelta(hours=3)
                if log.operacao == 'adicionado':
                    entradas.append({'data': log_timestamp, 'quantidade': log.quantidade})
                elif log.operacao == 'removido':
                    saidas.append({'data': log_timestamp, 'quantidade': log.quantidade})

            if saidas:  # Só calcular se houver saídas
                datas_saidas = [saida['data'] for saida in saidas]
                data_inicio_saidas = min(datas_saidas)
                data_fim_saidas = max(datas_saidas)
                periodo_dias = (data_fim_saidas - data_inicio_saidas).days + 1

                demanda_total = sum(saida['quantidade'] for saida in saidas)
                demanda_media_diaria = demanda_total / periodo_dias if periodo_dias > 0 else 0

                validades_produto = db.session().scalars(
                    sa.select(Validade)
                    .where(Validade.produto_id == produto.id)
                    .where(Validade.quantidade > 0)
                ).all()
                if validades_produto:
                    dias_validade = []
                    for validade in validades_produto:
                        dias_restantes = (validade.data_validade - now).days
                        if dias_restantes > 0:
                            dias_validade.append(dias_restantes)
                    validade_media = sum(dias_validade) / len(dias_validade) if dias_validade else 15
                else:
                    validade_media = 15

                quantidade_maxima = round(demanda_media_diaria * validade_media)
                entradas_total = sum(entrada['quantidade'] for entrada in entradas)
                saidas_total = sum(saida['quantidade'] for saida in saidas)
                estoque_atual = entradas_total - saidas_total

                if estoque_atual > quantidade_maxima:
                    flash(f'O produto {produto.nome} tem estoque excedente ({estoque_atual} unidades) acima da quantidade máxima ({quantidade_maxima} unidades). Considere reduzir o estoque para evitar perdas por validade.', 'warning')

    return render_template('index.html', title='Início - Stock Farm', farmacia_nome=farmacia_nome)

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

    # Calcular a validade mais próxima e quantidade total para cada produto
    for estoque in estoques:
        total_quantidade = db.session().scalar(
            sa.select(sa.func.sum(Validade.quantidade))
            .where(Validade.produto_id == estoque.produto_id)
        ) or 0
        estoque.produto.quantidade_total = total_quantidade
        # Buscar a validade mais próxima
        validade_proxima = db.session().scalar(
            sa.select(Validade.data_validade)
            .where(Validade.produto_id == estoque.produto_id)
            .where(Validade.quantidade > 0)
            .order_by(Validade.data_validade.asc())
            .limit(1)
        )
        # Ajustar o formato para DD-MM-YYYY
        estoque.produto.validade_proxima = validade_proxima.strftime('%d-%m-%Y') if validade_proxima else 'N/A'

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
            fornecedor_id=form.fornecedor_id.data,
            preco_compra=form.preco_compra.data,
            preco_venda=form.preco_venda.data,
            codigo_barras=form.codigo_barras.data
        )
        db.session.add(produto)
        db.session.commit()

        # Adicionar entrada na tabela Validade (não mais necessária aqui, mas mantida para consistência com add_quantidade)
        validade = Validade(
            produto_id=produto.id,
            data_validade=datetime.now(),  # Valor padrão, será ajustado via add_quantidade
            quantidade=0  # Valor padrão, será ajustado via add_quantidade
        )
        db.session.add(validade)

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
        produto.nome = form.nome.data
        produto.genero = form.genero.data
        produto.tipo = form.tipo.data
        produto.numeracao_original = form.numeracao_original.data
        produto.grupo = form.grupo.data
        produto.fabricante_id = form.fabricante_id.data
        produto.quantidade_embalagem = form.quantidade_embalagem.data
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
        db.session.commit()
        # Registrar log de edição
        log = ProdutoLog(produto_id=produto.id, quantidade=produto.quantidade, operacao='editado')
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
        form.fornecedor_id.data = produto.fornecedor_id
        form.preco_compra.data = produto.preco_compra
        form.preco_venda.data = produto.preco_venda
        form.codigo_barras.data = produto.codigo_barras
    return render_template('edit_produto.html', title='Editar Produto - Stock Farm', form=form)

@app.route('/edit_validade/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_validade(id):
    if not current_user.farmacia:
        return redirect(url_for('manage_farmacia'))
    validade = db.session().get(Validade, id) or db.first_or_404(sa.select(Validade).where(Validade.id == id))
    produto = db.session().get(Produto, validade.produto_id)
    estoque = db.session().scalar(
        sa.select(Estoque).where(
            Estoque.farmacia_id == current_user.farmacia_id,
            Estoque.produto_id == validade.produto_id
        )
    )
    if not estoque:
        flash('Você não tem permissão para editar esta validade.')
        return redirect(url_for('stock'))
    form = AddQuantidadeForm()
    if form.validate_on_submit():
        quantidade_anterior = validade.quantidade
        validade.data_validade = datetime.combine(form.data_validade.data, datetime.min.time())
        validade.quantidade = form.quantidade.data
        db.session.commit()
        # Registrar log de edição de validade (se houve mudança)
        if quantidade_anterior != form.quantidade.data:
            log = ProdutoLog(produto_id=produto.id, quantidade=form.quantidade.data - quantidade_anterior, operacao='adicionado' if form.quantidade.data > quantidade_anterior else 'removido')
            db.session.add(log)
            db.session.commit()
        flash('Validade atualizada com sucesso!')
        return redirect(url_for('view_produto', id=produto.id))
    elif request.method == 'GET':
        form.quantidade.data = validade.quantidade
        form.data_validade.data = validade.data_validade.date()
    return render_template('edit_validade.html', title='Editar Validade - Stock Farm', form=form, produto=produto)

@app.route('/add_quantidade/<int:id>', methods=['GET', 'POST'])
@login_required
def add_quantidade(id):
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
        flash('Você não tem permissão para adicionar quantidade a este produto.')
        return redirect(url_for('stock'))
    form = AddQuantidadeForm()
    if form.validate_on_submit():
        validade = Validade(
            produto_id=produto.id,
            data_validade=datetime.combine(form.data_validade.data, datetime.min.time()),
            quantidade=form.quantidade.data
        )
        db.session.add(validade)
        # Registrar log de adição
        log = ProdutoLog(produto_id=produto.id, quantidade=form.quantidade.data, operacao='adicionado')
        db.session.add(log)
        # Remover entradas com quantidade 0
        db.session.execute(
            sa.delete(Validade)
            .where(Validade.produto_id == produto.id)
            .where(Validade.quantidade == 0)
        )
        db.session.commit()
        flash('Quantidade adicionada com sucesso!')
        return redirect(url_for('stock'))
    return render_template('add_quantidade.html', title='Adicionar Quantidade - Stock Farm', form=form, produto=produto)

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
    quantidade = produto.quantidade
    db.session.delete(produto)
    db.session.commit()
    # Registrar log de remoção
    log = ProdutoLog(produto_id=id, quantidade=quantidade, operacao='removido')
    db.session.add(log)
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
    
    # Buscar todas as validades do produto
    validades = db.session().scalars(
        sa.select(Validade)
        .where(Validade.produto_id == produto.id)
        .order_by(Validade.data_validade.asc())
    ).all()

    return render_template('view_produto.html', title='Detalhes do Produto - Stock Farm', produto=produto, validades=validades)

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
                    if produto.quantidade < quantidade:
                        flash(f'Erro: Estoque insuficiente para o produto {produto.nome}.', 'error')
                        return redirect(url_for('vendas'))
                    
                    # Consultar validades ordenadas por data de validade (mais próxima primeiro)
                    validades = db.session().scalars(
                        sa.select(Validade)
                        .where(Validade.produto_id == produto.id)
                        .where(Validade.quantidade > 0)
                        .order_by(Validade.data_validade.asc())
                    ).all()

                    quantidade_restante = quantidade
                    for validade in validades:
                        if quantidade_restante <= 0:
                            break
                        if validade.quantidade >= quantidade_restante:
                            validade.quantidade -= quantidade_restante
                            quantidade_restante = 0
                        else:
                            quantidade_restante -= validade.quantidade
                            validade.quantidade = 0
                        db.session.add(validade)

                    if quantidade_restante > 0:
                        flash(f'Erro: Estoque insuficiente para o produto {produto.nome} após alocação por validade.', 'error')
                        db.session.rollback()
                        return redirect(url_for('vendas'))

                    # Remover entradas com quantidade 0
                    db.session.execute(
                        sa.delete(Validade)
                        .where(Validade.produto_id == produto.id)
                        .where(Validade.quantidade == 0)
                    )

                    # Registrar log de remoção
                    log = ProdutoLog(produto_id=produto.id, quantidade=quantidade, operacao='removido')
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

    # Calcular a quantidade total para cada produto
    for estoque in estoques:
        total_quantidade = db.session().scalar(
            sa.select(sa.func.sum(Validade.quantidade))
            .where(Validade.produto_id == estoque.produto_id)
        ) or 0
        estoque.produto.quantidade_total = total_quantidade

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

@app.route('/relatorio', methods=['GET', 'POST'])
@login_required
def relatorio():
    if not current_user.farmacia:
        return redirect(url_for('manage_farmacia'))

    # Lógica para logs existentes
    page = request.args.get('page', default=1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    query = (
        sa.select(ProdutoLog)
        .join(Produto, Produto.id == ProdutoLog.produto_id, isouter=True)
        .options(joinedload(ProdutoLog.produto))
        .order_by(ProdutoLog.timestamp.desc())
    )

    total_logs = db.session().scalar(sa.select(sa.func.count()).select_from(ProdutoLog))
    logs = db.session().scalars(query.offset(offset).limit(per_page)).all()

    # Preparar dados para exibição dos logs
    logs_data = []
    for log in logs:
        produto_nome = log.produto.nome if log.produto else "Produto Excluído"
        produto_codigo = log.produto.codigo_barras if log.produto else "N/A"
        # Ajustar o timestamp para GMT -3 (subtrair 3 horas) e formatar como DD-MM-YYYY HH:MM
        if log.timestamp:
            adjusted_timestamp = log.timestamp - timedelta(hours=3)
            data = adjusted_timestamp.strftime('%d-%m-%Y %H:%M')
        else:
            data = 'Sem data'
        operacao = log.operacao
        quantidade = log.quantidade
        logs_data.append({
            'data': data,
            'produto': produto_nome,
            'operacao': operacao,
            'quantidade': quantidade,
            'codigo_barras': produto_codigo
        })

    has_next = offset + per_page < total_logs
    has_prev = page > 1

    # Lógica para cálculo de demanda
    # Determinar o período com base nos parâmetros
    periodo = request.args.get('periodo', 'semana')  # Padrão: última semana
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')

    # Data atual ajustada para GMT-3
    now = datetime.now() - timedelta(hours=3)

    if data_inicio_str and data_fim_str:
        try:
            data_inicio = parser.parse(data_inicio_str)
            data_fim = parser.parse(data_fim_str)
            if data_inicio > data_fim:
                flash('A data inicial deve ser anterior à data final.', 'error')
                data_inicio = now - timedelta(days=7)
                data_fim = now
        except ValueError:
            flash('Datas inválidas. Usando o período padrão (última semana).', 'error')
            data_inicio = now - timedelta(days=7)
            data_fim = now
    else:
        if periodo == 'semana':
            data_inicio = now - timedelta(days=7)
        elif periodo == 'mes':
            data_inicio = now - timedelta(days=30)
        elif periodo == 'ano':
            data_inicio = now - timedelta(days=365)
        else:
            data_inicio = now - timedelta(days=7)  # Padrão: última semana
        data_fim = now

    # Ajustar datas para remover a parte de horário (considerar apenas o dia)
    data_inicio = data_inicio.replace(hour=0, minute=0, second=0, microsecond=0)
    data_fim = data_fim.replace(hour=23, minute=59, second=59, microsecond=999999)

    # Buscar todos os produtos da farmácia
    estoques = db.session().scalars(
        sa.select(Estoque)
        .where(Estoque.farmacia_id == current_user.farmacia_id)
        .options(joinedload(Estoque.produto))
    ).all()

    # Calcular a validade média dos produtos (em dias) com base na validade mais próxima
    demandas = []
    nivel_servico_z = 1.65  # Para 95% de nível de serviço

    for estoque in estoques:
        if not estoque.produto:
            continue  # Pular produtos excluídos

        produto = estoque.produto

        # Buscar logs de entrada (adicionado) e saída (removido) no período
        logs_produto = db.session().scalars(
            sa.select(ProdutoLog)
            .where(ProdutoLog.produto_id == produto.id)
            .where(ProdutoLog.timestamp >= data_inicio)
            .where(ProdutoLog.timestamp <= data_fim)
            .order_by(ProdutoLog.timestamp.asc())
        ).all()

        entradas = []
        saidas = []
        for log in logs_produto:
            # Ajustar timestamp para GMT-3
            log_timestamp = log.timestamp - timedelta(hours=3)
            if log.operacao == 'adicionado':
                entradas.append({'data': log_timestamp, 'quantidade': log.quantidade})
            elif log.operacao == 'removido':
                saidas.append({'data': log_timestamp, 'quantidade': log.quantidade})

        # Se não houver saídas, pular o cálculo para este produto
        if not saidas:
            continue

        # Passo 1: Determinar o período total com base nas saídas
        datas_saidas = [saida['data'] for saida in saidas]
        data_inicio_saidas = min(datas_saidas)
        data_fim_saidas = max(datas_saidas)
        periodo_dias = (data_fim_saidas - data_inicio_saidas).days + 1

        # Passo 2: Calcular a demanda total e a demanda média diária
        demanda_total = sum(saida['quantidade'] for saida in saidas)
        demanda_media_diaria = demanda_total / periodo_dias if periodo_dias > 0 else 0

        # Passo 3: Calcular o desvio padrão da demanda diária
        # Agrupar saídas por dia
        saídas_por_dia = {}
        data_atual = data_inicio_saidas
        while data_atual <= data_fim_saidas:
            saídas_por_dia[data_atual.date()] = 0
            data_atual += timedelta(days=1)

        for saida in saidas:
            data_saida = saida['data'].date()
            saídas_por_dia[data_saida] += saida['quantidade']

        quantidades_diarias = list(saídas_por_dia.values())
        desvio_padrao = statistics.stdev(quantidades_diarias) if len(quantidades_diarias) > 1 else 0

        # Passo 4: Calcular o estoque de segurança
        estoque_seguranca = nivel_servico_z * desvio_padrao
        estoque_seguranca = round(estoque_seguranca)

        # Passo 5: Calcular o ponto de reposição (sem lead time, é igual ao estoque de segurança)
        ponto_reposicao = estoque_seguranca

        # Passo 6: Calcular a validade média do produto (em dias)
        validades = db.session().scalars(
            sa.select(Validade)
            .where(Validade.produto_id == produto.id)
            .where(Validade.quantidade > 0)
        ).all()

        if validades:
            dias_validade = []
            for validade in validades:
                dias_restantes = (validade.data_validade - now).days
                if dias_restantes > 0:
                    dias_validade.append(dias_restantes)
            validade_media = sum(dias_validade) / len(dias_validade) if dias_validade else 15  # Padrão: 15 dias
        else:
            validade_media = 15  # Padrão: 15 dias se não houver validades

        # Passo 7: Calcular a quantidade máxima permitida
        quantidade_maxima = demanda_media_diaria * validade_media
        quantidade_maxima = round(quantidade_maxima)

        # Passo 8: Calcular o estoque atual (entradas - saídas)
        entradas_total = sum(entrada['quantidade'] for entrada in entradas)
        saidas_total = sum(saida['quantidade'] for saida in saidas)
        estoque_atual = entradas_total - saidas_total

        # Passo 9: Calcular a quantidade a pedir
        if estoque_atual < ponto_reposicao:
            quantidade_a_pedir = min(quantidade_maxima - estoque_atual, ponto_reposicao - estoque_atual)
            quantidade_a_pedir = max(0, round(quantidade_a_pedir))
        else:
            quantidade_a_pedir = 0

        # Passo 10: Calcular o tempo de duração do estoque
        tempo_duracao = (estoque_atual / demanda_media_diaria) if demanda_media_diaria > 0 else 0
        tempo_duracao = round(tempo_duracao, 2)

        # Passo 11: Verificar se o estoque atual excede a quantidade máxima
        estoque_excedente = estoque_atual > quantidade_maxima

        # Adicionar resultados à lista de demandas
        demandas.append({
            'nome': produto.nome,
            'preco_venda': produto.preco_venda,
            'demanda_media_diaria': round(demanda_media_diaria, 2),
            'estoque_seguranca': estoque_seguranca,
            'ponto_reposicao': ponto_reposicao,
            'quantidade_maxima': quantidade_maxima,
            'estoque_atual': estoque_atual,
            'quantidade_a_pedir': quantidade_a_pedir,
            'tempo_duracao': tempo_duracao,
            'estoque_excedente': estoque_excedente
        })

    return render_template(
        'relatorio.html',
        title='Relatório - Stock Farm',
        logs=logs_data,
        page=page,
        has_next=has_next,
        has_prev=has_prev,
        demandas=demandas,
        periodo=periodo,
        data_inicio=data_inicio.strftime('%Y-%m-%d'),
        data_fim=data_fim.strftime('%Y-%m-%d')
    )