# backend/models.py
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Usuario(UserMixin, db.Model):
    """Modelo de usuário com controle de acesso"""
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    perfil = db.Column(db.String(25), nullable=False, default='Operador')
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    ultimo_acesso = db.Column(db.DateTime)
    
    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)
    
    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)
    
    def tem_permissao(self, permissao):
        if self.perfil == 'Supervisor':
            return True
        
        permissoes = {
            'Operador': ['apontar_producao', 'apontar_refugo', 'ver_apontamentos'],
            'Líder de Produção': ['ver_dashboard', 'ver_relatorios', 'ver_usuarios', 'gerenciar_usuarios'],
            'Analista': [
                'apontar_producao', 'apontar_refugo', 'ver_apontamentos', 'criar_op', 'editar_op',
                'ver_ordens', 'ver_produtos', 'ver_estoque', 'ver_relatorios', 'ver_dashboard',
                'ver_estrutura', 'ver_cadastros', 'ver_usuarios', 'gerenciar_usuarios'
            ]
        }
        return permissao in permissoes.get(self.perfil, [])
    
    def __repr__(self):
        return f"<Usuario {self.nome} ({self.perfil})>"


class Maquina(db.Model):
    __tablename__ = 'maquinas'
    
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    status = db.Column(db.String(20), default='Ativo')
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Maquina {self.codigo} - {self.nome}>"


class Produto(db.Model):
    __tablename__ = 'produtos'
    
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    descricao = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # MP, SA, PA
    unidade = db.Column(db.String(20), nullable=False)
    estoque_atual = db.Column(db.Float, default=0.0)
    estoque_minimo = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='Ativo')
    observacao = db.Column(db.Text)
    maquina_id = db.Column(db.Integer, db.ForeignKey('maquinas.id'), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    maquina = db.relationship('Maquina', backref='produtos', foreign_keys=[maquina_id])
    
    def __repr__(self):
        return f"<Produto {self.codigo} - {self.descricao}>"


class Estrutura(db.Model):
    __tablename__ = 'estrutura_produto'
    
    id = db.Column(db.Integer, primary_key=True)
    produto_pai_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    componente_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    quantidade = db.Column(db.Float, nullable=False)
    # Quantidade é armazenada na unidade de estoque do componente; esta coluna
    # preserva a unidade escolhida pelo usuário na BOM (ex.: 200 ML).
    unidade_consumo = db.Column(db.String(10), nullable=True)
    perda_percentual = db.Column(db.Float, default=0.0)
    observacao = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    produto_pai = db.relationship('Produto', foreign_keys=[produto_pai_id], backref='componentes')
    componente = db.relationship('Produto', foreign_keys=[componente_id], backref='produtos_pai')
    
    __table_args__ = (
        db.UniqueConstraint('produto_pai_id', 'componente_id', name='uq_estrutura_produto_componente'),
    )
    
    def __repr__(self):
        return f"<Estrutura {self.produto_pai.codigo} <- {self.componente.codigo} x{self.quantidade}>"


class Operador(db.Model):
    __tablename__ = 'operadores'
    
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    setor = db.Column(db.String(100))
    status = db.Column(db.String(20), default='Ativo')
    # Mantido para rastreabilidade dos apontamentos e vinculado à conta de acesso.
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), unique=True, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Operador {self.codigo} - {self.nome}>"


class OrdemProducao(db.Model):
    __tablename__ = 'ordens_producao'
    
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(50), unique=True, nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    quantidade_planejada = db.Column(db.Float, nullable=False)
    quantidade_produzida = db.Column(db.Float, default=0.0)
    data = db.Column(db.Date, nullable=False)
    prioridade = db.Column(db.String(20), default='Normal')
    observacao = db.Column(db.Text)
    status = db.Column(db.String(30), default='Planejada')
    criada_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    produto = db.relationship('Produto', backref='ordens_producao')
    
    def __repr__(self):
        return f"<OrdemProducao {self.numero} - {self.produto.codigo}>"


class Apontamento(db.Model):
    __tablename__ = 'apontamentos'
    
    id = db.Column(db.Integer, primary_key=True)
    op_id = db.Column(db.Integer, db.ForeignKey('ordens_producao.id'), nullable=False)
    operador_id = db.Column(db.Integer, db.ForeignKey('operadores.id'), nullable=True)
    quantidade_produzida = db.Column(db.Float, nullable=False)
    quantidade_boa = db.Column(db.Float, nullable=False)
    quantidade_refugada = db.Column(db.Float, nullable=False, default=0.0)
    motivo_refugo = db.Column(db.String(200))
    observacao = db.Column(db.Text)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    
    op = db.relationship('OrdemProducao', backref='apontamentos')
    operador = db.relationship('Operador', backref='apontamentos')
    
    def __repr__(self):
        return f"<Apontamento OP {self.op.numero} - {self.quantidade_produzida}>"


class Movimentacao(db.Model):
    __tablename__ = 'movimentacoes'
    
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    quantidade = db.Column(db.Float, nullable=False)
    tipo = db.Column(db.String(30), nullable=False)
    op_id = db.Column(db.Integer, db.ForeignKey('ordens_producao.id'), nullable=True)
    apontamento_id = db.Column(db.Integer, db.ForeignKey('apontamentos.id'), nullable=True)
    usuario = db.Column(db.String(100), default='Sistema')
    observacao = db.Column(db.Text)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    
    produto = db.relationship('Produto', backref='movimentacoes')
    op = db.relationship('OrdemProducao', backref='movimentacoes')
    apontamento = db.relationship('Apontamento', backref='movimentacoes')
    
    def __repr__(self):
        return f"<Movimentacao {self.tipo} - {self.produto.codigo} x{self.quantidade}>"


class Historico(db.Model):
    __tablename__ = 'historicos'
    
    id = db.Column(db.Integer, primary_key=True)
    op_id = db.Column(db.Integer, db.ForeignKey('ordens_producao.id'), nullable=True)
    descricao = db.Column(db.String(300), nullable=False)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    
    op = db.relationship('OrdemProducao', backref='historicos')
    
    def __repr__(self):
        return f"<Historico OP {self.op_id} - {self.descricao[:50]}>"


class Configuracao(db.Model):
    __tablename__ = 'configuracoes'
    
    id = db.Column(db.Integer, primary_key=True)
    permitir_estoque_negativo = db.Column(db.Boolean, default=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Configuracao estoque_negativo={self.permitir_estoque_negativo}>"
