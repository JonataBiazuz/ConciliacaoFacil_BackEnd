from flask import Blueprint, request, jsonify
from src.models.conciliacao import db, ContaReceber
from datetime import datetime
from decimal import Decimal

conta_receber_bp = Blueprint('conta_receber', __name__)

@conta_receber_bp.route('/criar', methods=['POST'])
def criar_conta_receber():
    """Cria uma nova conta a receber"""
    try:
        dados = request.get_json()
        
        if not dados:
            return jsonify({'erro': 'Dados não fornecidos'}), 400
        
        # Validações obrigatórias
        if not dados.get('cliente_nome'):
            return jsonify({'erro': 'Nome do cliente é obrigatório'}), 400
        
        if not dados.get('valor_esperado'):
            return jsonify({'erro': 'Valor esperado é obrigatório'}), 400
        
        # Converte valor
        try:
            valor_esperado = Decimal(str(dados['valor_esperado']))
        except:
            return jsonify({'erro': 'Valor esperado inválido'}), 400
        
        # Converte data de vencimento se fornecida
        data_vencimento = None
        if dados.get('data_vencimento'):
            try:
                data_vencimento = datetime.strptime(dados['data_vencimento'], '%Y-%m-%d').date()
            except:
                return jsonify({'erro': 'Data de vencimento inválida. Use formato YYYY-MM-DD'}), 400
        
        # Cria conta a receber
        conta = ContaReceber(
            numero_pedido=dados.get('numero_pedido'),
            cliente_nome=dados['cliente_nome'],
            cliente_cpf_cnpj=dados.get('cliente_cpf_cnpj'),
            valor_esperado=valor_esperado,
            data_vencimento=data_vencimento,
            observacoes=dados.get('observacoes')
        )
        
        db.session.add(conta)
        db.session.commit()
        
        return jsonify({
            'sucesso': True,
            'conta': conta.to_dict(),
            'mensagem': 'Conta a receber criada com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': f'Erro ao criar conta a receber: {str(e)}'}), 500

@conta_receber_bp.route('/listar', methods=['GET'])
def listar_contas_receber():
    """Lista todas as contas a receber"""
    try:
        # Parâmetros de filtro
        status = request.args.get('status')
        cliente = request.args.get('cliente')
        
        query = ContaReceber.query
        
        if status:
            query = query.filter(ContaReceber.status == status)
        
        if cliente:
            query = query.filter(ContaReceber.cliente_nome.ilike(f'%{cliente}%'))
        
        contas = query.order_by(ContaReceber.data_criacao.desc()).all()
        
        return jsonify({
            'contas': [conta.to_dict() for conta in contas]
        })
        
    except Exception as e:
        return jsonify({'erro': f'Erro ao listar contas a receber: {str(e)}'}), 500

@conta_receber_bp.route('/<int:conta_id>', methods=['GET'])
def obter_conta_receber(conta_id):
    """Obtém uma conta a receber específica"""
    try:
        conta = ContaReceber.query.get_or_404(conta_id)
        return jsonify({
            'conta': conta.to_dict()
        })
    except Exception as e:
        return jsonify({'erro': f'Erro ao obter conta a receber: {str(e)}'}), 500

@conta_receber_bp.route('/<int:conta_id>', methods=['PUT'])
def atualizar_conta_receber(conta_id):
    """Atualiza uma conta a receber"""
    try:
        conta = ContaReceber.query.get_or_404(conta_id)
        dados = request.get_json()
        
        if not dados:
            return jsonify({'erro': 'Dados não fornecidos'}), 400
        
        # Atualiza campos se fornecidos
        if 'numero_pedido' in dados:
            conta.numero_pedido = dados['numero_pedido']
        
        if 'cliente_nome' in dados:
            conta.cliente_nome = dados['cliente_nome']
        
        if 'cliente_cpf_cnpj' in dados:
            conta.cliente_cpf_cnpj = dados['cliente_cpf_cnpj']
        
        if 'valor_esperado' in dados:
            try:
                conta.valor_esperado = Decimal(str(dados['valor_esperado']))
            except:
                return jsonify({'erro': 'Valor esperado inválido'}), 400
        
        if 'data_vencimento' in dados:
            if dados['data_vencimento']:
                try:
                    conta.data_vencimento = datetime.strptime(dados['data_vencimento'], '%Y-%m-%d').date()
                except:
                    return jsonify({'erro': 'Data de vencimento inválida. Use formato YYYY-MM-DD'}), 400
            else:
                conta.data_vencimento = None
        
        if 'status' in dados:
            conta.status = dados['status']
        
        if 'observacoes' in dados:
            conta.observacoes = dados['observacoes']
        
        db.session.commit()
        
        return jsonify({
            'sucesso': True,
            'conta': conta.to_dict(),
            'mensagem': 'Conta a receber atualizada com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': f'Erro ao atualizar conta a receber: {str(e)}'}), 500

@conta_receber_bp.route('/<int:conta_id>', methods=['DELETE'])
def deletar_conta_receber(conta_id):
    """Deleta uma conta a receber"""
    try:
        conta = ContaReceber.query.get_or_404(conta_id)
        db.session.delete(conta)
        db.session.commit()
        
        return jsonify({
            'sucesso': True,
            'mensagem': 'Conta a receber deletada com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': f'Erro ao deletar conta a receber: {str(e)}'}), 500

@conta_receber_bp.route('/pendentes', methods=['GET'])
def listar_contas_pendentes():
    """Lista apenas contas a receber pendentes"""
    try:
        contas = ContaReceber.query.filter_by(status='pendente').order_by(ContaReceber.data_vencimento).all()
        
        return jsonify({
            'contas': [conta.to_dict() for conta in contas],
            'total': len(contas)
        })
        
    except Exception as e:
        return jsonify({'erro': f'Erro ao listar contas pendentes: {str(e)}'}), 500

