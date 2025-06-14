from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Extrato(db.Model):
    """Modelo para armazenar extratos bancários importados"""
    id = db.Column(db.Integer, primary_key=True)
    nome_arquivo = db.Column(db.String(255), nullable=False)
    data_upload = db.Column(db.DateTime, default=datetime.utcnow)
    banco = db.Column(db.String(100))
    conta = db.Column(db.String(50))
    periodo_inicio = db.Column(db.Date)
    periodo_fim = db.Column(db.Date)
    total_transacoes = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default='processando')  # processando, concluido, erro
    
    # Relacionamento com transações
    transacoes = db.relationship('Transacao', backref='extrato', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Extrato {self.nome_arquivo}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome_arquivo': self.nome_arquivo,
            'data_upload': self.data_upload.isoformat() if self.data_upload else None,
            'banco': self.banco,
            'conta': self.conta,
            'periodo_inicio': self.periodo_inicio.isoformat() if self.periodo_inicio else None,
            'periodo_fim': self.periodo_fim.isoformat() if self.periodo_fim else None,
            'total_transacoes': self.total_transacoes,
            'status': self.status
        }

class Transacao(db.Model):
    """Modelo para armazenar transações individuais do extrato"""
    id = db.Column(db.Integer, primary_key=True)
    extrato_id = db.Column(db.Integer, db.ForeignKey('extrato.id'), nullable=False)
    
    # Dados da transação
    data_transacao = db.Column(db.Date, nullable=False)
    valor = db.Column(db.Numeric(15, 2), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # credito, debito
    descricao = db.Column(db.Text)
    documento = db.Column(db.String(100))
    
    # Dados extraídos/processados
    nome_pagador = db.Column(db.String(255))
    cpf_cnpj_pagador = db.Column(db.String(20))
    banco_origem = db.Column(db.String(100))
    
    # Status da conciliação
    status_conciliacao = db.Column(db.String(50), default='pendente')  # pendente, conciliado, divergente
    confianca_conciliacao = db.Column(db.Float)  # 0.0 a 1.0
    
    # Relacionamento com conciliação
    conciliacoes = db.relationship('Conciliacao', backref='transacao', lazy=True)
    
    def __repr__(self):
        return f'<Transacao {self.id} - {self.valor}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'extrato_id': self.extrato_id,
            'data_transacao': self.data_transacao.isoformat() if self.data_transacao else None,
            'valor': float(self.valor) if self.valor else 0,
            'tipo': self.tipo,
            'descricao': self.descricao,
            'documento': self.documento,
            'nome_pagador': self.nome_pagador,
            'cpf_cnpj_pagador': self.cpf_cnpj_pagador,
            'banco_origem': self.banco_origem,
            'status_conciliacao': self.status_conciliacao,
            'confianca_conciliacao': self.confianca_conciliacao
        }

class ContaReceber(db.Model):
    """Modelo para contas a receber da empresa"""
    id = db.Column(db.Integer, primary_key=True)
    numero_pedido = db.Column(db.String(100))
    cliente_nome = db.Column(db.String(255), nullable=False)
    cliente_cpf_cnpj = db.Column(db.String(20))
    valor_esperado = db.Column(db.Numeric(15, 2), nullable=False)
    data_vencimento = db.Column(db.Date)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='pendente')  # pendente, pago, vencido
    observacoes = db.Column(db.Text)
    
    # Relacionamento com conciliações
    conciliacoes = db.relationship('Conciliacao', backref='conta_receber', lazy=True)
    
    def __repr__(self):
        return f'<ContaReceber {self.numero_pedido} - {self.cliente_nome}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'numero_pedido': self.numero_pedido,
            'cliente_nome': self.cliente_nome,
            'cliente_cpf_cnpj': self.cliente_cpf_cnpj,
            'valor_esperado': float(self.valor_esperado) if self.valor_esperado else 0,
            'data_vencimento': self.data_vencimento.isoformat() if self.data_vencimento else None,
            'data_criacao': self.data_criacao.isoformat() if self.data_criacao else None,
            'status': self.status,
            'observacoes': self.observacoes
        }

class Conciliacao(db.Model):
    """Modelo para registrar conciliações entre transações e contas a receber"""
    id = db.Column(db.Integer, primary_key=True)
    transacao_id = db.Column(db.Integer, db.ForeignKey('transacao.id'), nullable=False)
    conta_receber_id = db.Column(db.Integer, db.ForeignKey('conta_receber.id'), nullable=False)
    
    data_conciliacao = db.Column(db.DateTime, default=datetime.utcnow)
    tipo_conciliacao = db.Column(db.String(50), nullable=False)  # automatica, manual
    confianca = db.Column(db.Float)  # 0.0 a 1.0
    observacoes = db.Column(db.Text)
    usuario_responsavel = db.Column(db.String(100))
    
    def __repr__(self):
        return f'<Conciliacao {self.id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'transacao_id': self.transacao_id,
            'conta_receber_id': self.conta_receber_id,
            'data_conciliacao': self.data_conciliacao.isoformat() if self.data_conciliacao else None,
            'tipo_conciliacao': self.tipo_conciliacao,
            'confianca': self.confianca,
            'observacoes': self.observacoes,
            'usuario_responsavel': self.usuario_responsavel
        }

class RegraConciliacao(db.Model):
    """Modelo para armazenar regras de conciliação personalizadas"""
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), nullable=False)
    descricao = db.Column(db.Text)
    ativa = db.Column(db.Boolean, default=True)
    prioridade = db.Column(db.Integer, default=1)
    
    # Critérios da regra (JSON)
    criterios_valor = db.Column(db.Text)  # JSON com critérios de valor
    criterios_data = db.Column(db.Text)   # JSON com critérios de data
    criterios_texto = db.Column(db.Text)  # JSON com critérios de texto/descrição
    
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<RegraConciliacao {self.nome}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'descricao': self.descricao,
            'ativa': self.ativa,
            'prioridade': self.prioridade,
            'criterios_valor': self.criterios_valor,
            'criterios_data': self.criterios_data,
            'criterios_texto': self.criterios_texto,
            'data_criacao': self.data_criacao.isoformat() if self.data_criacao else None,
            'data_atualizacao': self.data_atualizacao.isoformat() if self.data_atualizacao else None
        }

