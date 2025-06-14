from flask import Blueprint, request, jsonify
from src.models.conciliacao import db, Transacao, ContaReceber, Conciliacao
from datetime import datetime, timedelta
from decimal import Decimal
import re

conciliacao_bp = Blueprint('conciliacao', __name__)

def calcular_similaridade_texto(texto1, texto2):
    """Calcula similaridade básica entre dois textos"""
    if not texto1 or not texto2:
        return 0.0
    
    texto1 = texto1.lower().strip()
    texto2 = texto2.lower().strip()
    
    # Similaridade exata
    if texto1 == texto2:
        return 1.0
    
    # Verifica se um texto contém o outro
    if texto1 in texto2 or texto2 in texto1:
        return 0.8
    
    # Conta palavras em comum
    palavras1 = set(re.findall(r'\w+', texto1))
    palavras2 = set(re.findall(r'\w+', texto2))
    
    if not palavras1 or not palavras2:
        return 0.0
    
    intersecao = len(palavras1.intersection(palavras2))
    uniao = len(palavras1.union(palavras2))
    
    return intersecao / uniao if uniao > 0 else 0.0

def calcular_similaridade_valor(valor1, valor2, tolerancia_percentual=0.05):
    """Calcula similaridade entre valores com tolerância"""
    if valor1 == valor2:
        return 1.0
    
    diferenca = abs(valor1 - valor2)
    maior_valor = max(valor1, valor2)
    
    if maior_valor == 0:
        return 0.0
    
    percentual_diferenca = diferenca / maior_valor
    
    if percentual_diferenca <= tolerancia_percentual:
        return 1.0 - percentual_diferenca
    
    return 0.0

def calcular_similaridade_data(data1, data2, tolerancia_dias=7):
    """Calcula similaridade entre datas com tolerância"""
    if data1 == data2:
        return 1.0
    
    diferenca_dias = abs((data1 - data2).days)
    
    if diferenca_dias <= tolerancia_dias:
        return 1.0 - (diferenca_dias / tolerancia_dias)
    
    return 0.0

def encontrar_correspondencias_automaticas(transacao):
    """Encontra possíveis correspondências para uma transação"""
    correspondencias = []
    
    # Busca contas a receber pendentes
    contas_pendentes = ContaReceber.query.filter_by(status='pendente').all()
    
    for conta in contas_pendentes:
        confianca_total = 0.0
        fatores = []
        
        # Similaridade de valor (peso 40%)
        sim_valor = calcular_similaridade_valor(float(transacao.valor), float(conta.valor_esperado))
        confianca_total += sim_valor * 0.4
        fatores.append(f"Valor: {sim_valor:.2f}")
        
        # Similaridade de nome/CPF (peso 30%)
        sim_nome = 0.0
        if transacao.nome_pagador and conta.cliente_nome:
            sim_nome = calcular_similaridade_texto(transacao.nome_pagador, conta.cliente_nome)
        
        sim_cpf = 0.0
        if transacao.cpf_cnpj_pagador and conta.cliente_cpf_cnpj:
            sim_cpf = 1.0 if transacao.cpf_cnpj_pagador == conta.cliente_cpf_cnpj else 0.0
        
        sim_identificacao = max(sim_nome, sim_cpf)
        confianca_total += sim_identificacao * 0.3
        fatores.append(f"Identificação: {sim_identificacao:.2f}")
        
        # Similaridade de data (peso 20%)
        sim_data = 0.0
        if conta.data_vencimento:
            sim_data = calcular_similaridade_data(transacao.data_transacao, conta.data_vencimento)
        else:
            # Se não há data de vencimento, considera proximidade com data de criação
            sim_data = calcular_similaridade_data(transacao.data_transacao, conta.data_criacao.date(), tolerancia_dias=30)
        
        confianca_total += sim_data * 0.2
        fatores.append(f"Data: {sim_data:.2f}")
        
        # Busca por número do pedido na descrição (peso 10%)
        sim_pedido = 0.0
        if conta.numero_pedido and transacao.descricao:
            if conta.numero_pedido in transacao.descricao:
                sim_pedido = 1.0
        
        confianca_total += sim_pedido * 0.1
        fatores.append(f"Pedido: {sim_pedido:.2f}")
        
        # Adiciona à lista se confiança mínima
        if confianca_total >= 0.3:  # 30% de confiança mínima
            correspondencias.append({
                'conta': conta,
                'confianca': confianca_total,
                'fatores': fatores
            })
    
    # Ordena por confiança decrescente
    correspondencias.sort(key=lambda x: x['confianca'], reverse=True)
    
    return correspondencias

@conciliacao_bp.route('/automatica', methods=['POST'])
def conciliacao_automatica():
    """Executa conciliação automática para transações pendentes"""
    try:
        dados = request.get_json() or {}
        confianca_minima = dados.get('confianca_minima', 0.8)  # 80% de confiança mínima para conciliação automática
        
        # Busca transações pendentes de crédito
        transacoes_pendentes = Transacao.query.filter_by(
            status_conciliacao='pendente',
            tipo='credito'
        ).all()
        
        conciliacoes_realizadas = 0
        resultados = []
        
        for transacao in transacoes_pendentes:
            correspondencias = encontrar_correspondencias_automaticas(transacao)
            
            if correspondencias and correspondencias[0]['confianca'] >= confianca_minima:
                # Concilia automaticamente
                melhor_correspondencia = correspondencias[0]
                conta = melhor_correspondencia['conta']
                
                # Verifica se a conta já não foi conciliada
                conciliacao_existente = Conciliacao.query.filter_by(conta_receber_id=conta.id).first()
                if conciliacao_existente:
                    continue
                
                # Cria conciliação
                conciliacao = Conciliacao(
                    transacao_id=transacao.id,
                    conta_receber_id=conta.id,
                    tipo_conciliacao='automatica',
                    confianca=melhor_correspondencia['confianca'],
                    observacoes=f"Conciliação automática. Fatores: {', '.join(melhor_correspondencia['fatores'])}"
                )
                
                # Atualiza status
                transacao.status_conciliacao = 'conciliado'
                transacao.confianca_conciliacao = melhor_correspondencia['confianca']
                conta.status = 'pago'
                
                db.session.add(conciliacao)
                conciliacoes_realizadas += 1
                
                resultados.append({
                    'transacao_id': transacao.id,
                    'conta_id': conta.id,
                    'confianca': melhor_correspondencia['confianca'],
                    'fatores': melhor_correspondencia['fatores']
                })
        
        db.session.commit()
        
        return jsonify({
            'sucesso': True,
            'conciliacoes_realizadas': conciliacoes_realizadas,
            'resultados': resultados,
            'mensagem': f'{conciliacoes_realizadas} conciliações automáticas realizadas'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': f'Erro na conciliação automática: {str(e)}'}), 500

@conciliacao_bp.route('/sugestoes/<int:transacao_id>', methods=['GET'])
def obter_sugestoes(transacao_id):
    """Obtém sugestões de conciliação para uma transação específica"""
    try:
        transacao = Transacao.query.get_or_404(transacao_id)
        
        if transacao.tipo != 'credito':
            return jsonify({'erro': 'Apenas transações de crédito podem ser conciliadas'}), 400
        
        correspondencias = encontrar_correspondencias_automaticas(transacao)
        
        sugestoes = []
        for corresp in correspondencias[:5]:  # Máximo 5 sugestões
            sugestoes.append({
                'conta': corresp['conta'].to_dict(),
                'confianca': corresp['confianca'],
                'fatores': corresp['fatores']
            })
        
        return jsonify({
            'transacao': transacao.to_dict(),
            'sugestoes': sugestoes
        })
        
    except Exception as e:
        return jsonify({'erro': f'Erro ao obter sugestões: {str(e)}'}), 500

@conciliacao_bp.route('/manual', methods=['POST'])
def conciliacao_manual():
    """Realiza conciliação manual entre transação e conta a receber"""
    try:
        dados = request.get_json()
        
        if not dados:
            return jsonify({'erro': 'Dados não fornecidos'}), 400
        
        transacao_id = dados.get('transacao_id')
        conta_receber_id = dados.get('conta_receber_id')
        observacoes = dados.get('observacoes', '')
        
        if not transacao_id or not conta_receber_id:
            return jsonify({'erro': 'ID da transação e conta a receber são obrigatórios'}), 400
        
        transacao = Transacao.query.get_or_404(transacao_id)
        conta = ContaReceber.query.get_or_404(conta_receber_id)
        
        # Verifica se já existe conciliação
        conciliacao_existente = Conciliacao.query.filter_by(
            transacao_id=transacao_id,
            conta_receber_id=conta_receber_id
        ).first()
        
        if conciliacao_existente:
            return jsonify({'erro': 'Conciliação já existe entre esta transação e conta'}), 400
        
        # Calcula confiança da conciliação manual
        correspondencias = encontrar_correspondencias_automaticas(transacao)
        confianca = 0.5  # Confiança padrão para conciliação manual
        
        for corresp in correspondencias:
            if corresp['conta'].id == conta_receber_id:
                confianca = corresp['confianca']
                break
        
        # Cria conciliação
        conciliacao = Conciliacao(
            transacao_id=transacao_id,
            conta_receber_id=conta_receber_id,
            tipo_conciliacao='manual',
            confianca=confianca,
            observacoes=observacoes,
            usuario_responsavel=dados.get('usuario', 'Sistema')
        )
        
        # Atualiza status
        transacao.status_conciliacao = 'conciliado'
        transacao.confianca_conciliacao = confianca
        conta.status = 'pago'
        
        db.session.add(conciliacao)
        db.session.commit()
        
        return jsonify({
            'sucesso': True,
            'conciliacao': conciliacao.to_dict(),
            'mensagem': 'Conciliação manual realizada com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': f'Erro na conciliação manual: {str(e)}'}), 500

@conciliacao_bp.route('/listar', methods=['GET'])
def listar_conciliacoes():
    """Lista todas as conciliações realizadas"""
    try:
        conciliacoes = db.session.query(Conciliacao).join(Transacao).join(ContaReceber).order_by(Conciliacao.data_conciliacao.desc()).all()
        
        resultado = []
        for conciliacao in conciliacoes:
            item = conciliacao.to_dict()
            item['transacao'] = conciliacao.transacao.to_dict()
            item['conta_receber'] = conciliacao.conta_receber.to_dict()
            resultado.append(item)
        
        return jsonify({
            'conciliacoes': resultado
        })
        
    except Exception as e:
        return jsonify({'erro': f'Erro ao listar conciliações: {str(e)}'}), 500

@conciliacao_bp.route('/pendentes', methods=['GET'])
def listar_pendentes():
    """Lista transações e contas pendentes de conciliação"""
    try:
        transacoes_pendentes = Transacao.query.filter_by(
            status_conciliacao='pendente',
            tipo='credito'
        ).order_by(Transacao.data_transacao.desc()).all()
        
        contas_pendentes = ContaReceber.query.filter_by(status='pendente').order_by(ContaReceber.data_vencimento).all()
        
        return jsonify({
            'transacoes_pendentes': [t.to_dict() for t in transacoes_pendentes],
            'contas_pendentes': [c.to_dict() for c in contas_pendentes],
            'total_transacoes': len(transacoes_pendentes),
            'total_contas': len(contas_pendentes)
        })
        
    except Exception as e:
        return jsonify({'erro': f'Erro ao listar pendências: {str(e)}'}), 500

@conciliacao_bp.route('/<int:conciliacao_id>', methods=['DELETE'])
def desfazer_conciliacao(conciliacao_id):
    """Desfaz uma conciliação"""
    try:
        conciliacao = Conciliacao.query.get_or_404(conciliacao_id)
        
        # Reverte status
        conciliacao.transacao.status_conciliacao = 'pendente'
        conciliacao.transacao.confianca_conciliacao = None
        conciliacao.conta_receber.status = 'pendente'
        
        db.session.delete(conciliacao)
        db.session.commit()
        
        return jsonify({
            'sucesso': True,
            'mensagem': 'Conciliação desfeita com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': f'Erro ao desfazer conciliação: {str(e)}'}), 500

