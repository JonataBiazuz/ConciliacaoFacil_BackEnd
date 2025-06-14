from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
import csv
import io
from datetime import datetime
from decimal import Decimal
from src.models.conciliacao import db, Extrato, Transacao
import re

extrato_bp = Blueprint('extrato', __name__)

ALLOWED_EXTENSIONS = {'csv', 'txt', 'ofx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extrair_cpf_cnpj(texto):
    """Extrai CPF ou CNPJ de um texto"""
    if not texto:
        return None
    
    # Remove caracteres especiais
    texto_limpo = re.sub(r'[^\d]', '', texto)
    
    # Verifica se é CPF (11 dígitos)
    if len(texto_limpo) == 11:
        return f"{texto_limpo[:3]}.{texto_limpo[3:6]}.{texto_limpo[6:9]}-{texto_limpo[9:]}"
    
    # Verifica se é CNPJ (14 dígitos)
    elif len(texto_limpo) == 14:
        return f"{texto_limpo[:2]}.{texto_limpo[2:5]}.{texto_limpo[5:8]}/{texto_limpo[8:12]}-{texto_limpo[12:]}"
    
    return None

def extrair_nome_pagador(descricao):
    """Extrai o nome do pagador da descrição da transação"""
    if not descricao:
        return None
    
    # Padrões comuns para extrair nomes
    padroes = [
        r'TED\s+(.+?)(?:\s+CPF|$)',
        r'DOC\s+(.+?)(?:\s+CPF|$)',
        r'PIX\s+(.+?)(?:\s+CPF|$)',
        r'DEPOSITO\s+(.+?)(?:\s+CPF|$)',
        r'TRANSFERENCIA\s+(.+?)(?:\s+CPF|$)',
    ]
    
    for padrao in padroes:
        match = re.search(padrao, descricao.upper())
        if match:
            nome = match.group(1).strip()
            # Remove números e caracteres especiais do final
            nome = re.sub(r'[\d\-\.\s]+$', '', nome).strip()
            if len(nome) > 3:  # Nome deve ter pelo menos 3 caracteres
                return nome
    
    return None

def processar_csv_extrato(arquivo_conteudo, nome_arquivo):
    """Processa um arquivo CSV de extrato bancário"""
    try:
        # Detecta o encoding
        try:
            conteudo = arquivo_conteudo.decode('utf-8')
        except UnicodeDecodeError:
            conteudo = arquivo_conteudo.decode('latin-1')
        
        # Cria o extrato
        extrato = Extrato(
            nome_arquivo=nome_arquivo,
            status='processando'
        )
        db.session.add(extrato)
        db.session.flush()  # Para obter o ID
        
        # Processa o CSV
        reader = csv.DictReader(io.StringIO(conteudo))
        transacoes_processadas = 0
        
        for linha in reader:
            try:
                # Mapeia campos comuns (adaptar conforme formato do banco)
                data_str = linha.get('Data', linha.get('data', ''))
                valor_str = linha.get('Valor', linha.get('valor', '0'))
                descricao = linha.get('Descrição', linha.get('descricao', linha.get('Histórico', '')))
                documento = linha.get('Documento', linha.get('documento', ''))
                
                # Converte data
                try:
                    if '/' in data_str:
                        data_transacao = datetime.strptime(data_str, '%d/%m/%Y').date()
                    else:
                        data_transacao = datetime.strptime(data_str, '%Y-%m-%d').date()
                except:
                    continue  # Pula linha com data inválida
                
                # Converte valor
                try:
                    valor_str = valor_str.replace(',', '.').replace('R$', '').strip()
                    valor = Decimal(valor_str)
                except:
                    continue  # Pula linha com valor inválido
                
                # Determina tipo (crédito/débito)
                tipo = 'credito' if valor > 0 else 'debito'
                valor = abs(valor)
                
                # Extrai informações adicionais
                nome_pagador = extrair_nome_pagador(descricao)
                cpf_cnpj = extrair_cpf_cnpj(descricao)
                
                # Cria transação
                transacao = Transacao(
                    extrato_id=extrato.id,
                    data_transacao=data_transacao,
                    valor=valor,
                    tipo=tipo,
                    descricao=descricao,
                    documento=documento,
                    nome_pagador=nome_pagador,
                    cpf_cnpj_pagador=cpf_cnpj
                )
                
                db.session.add(transacao)
                transacoes_processadas += 1
                
            except Exception as e:
                print(f"Erro ao processar linha: {e}")
                continue
        
        # Atualiza extrato
        extrato.total_transacoes = transacoes_processadas
        extrato.status = 'concluido'
        
        # Define período do extrato
        if transacoes_processadas > 0:
            primeira_transacao = db.session.query(Transacao).filter_by(extrato_id=extrato.id).order_by(Transacao.data_transacao).first()
            ultima_transacao = db.session.query(Transacao).filter_by(extrato_id=extrato.id).order_by(Transacao.data_transacao.desc()).first()
            
            if primeira_transacao and ultima_transacao:
                extrato.periodo_inicio = primeira_transacao.data_transacao
                extrato.periodo_fim = ultima_transacao.data_transacao
        
        db.session.commit()
        return extrato
        
    except Exception as e:
        db.session.rollback()
        raise e

@extrato_bp.route('/upload', methods=['POST'])
def upload_extrato():
    """Endpoint para upload de extrato bancário"""
    try:
        if 'arquivo' not in request.files:
            return jsonify({'erro': 'Nenhum arquivo enviado'}), 400
        
        arquivo = request.files['arquivo']
        if arquivo.filename == '':
            return jsonify({'erro': 'Nenhum arquivo selecionado'}), 400
        
        if arquivo and allowed_file(arquivo.filename):
            filename = secure_filename(arquivo.filename)
            
            # Lê o conteúdo do arquivo
            arquivo_conteudo = arquivo.read()
            
            # Processa baseado na extensão
            if filename.lower().endswith('.csv'):
                extrato = processar_csv_extrato(arquivo_conteudo, filename)
            else:
                return jsonify({'erro': 'Formato de arquivo não suportado ainda'}), 400
            
            return jsonify({
                'sucesso': True,
                'extrato': extrato.to_dict(),
                'mensagem': f'Extrato processado com sucesso. {extrato.total_transacoes} transações importadas.'
            })
        
        return jsonify({'erro': 'Tipo de arquivo não permitido'}), 400
        
    except Exception as e:
        return jsonify({'erro': f'Erro ao processar arquivo: {str(e)}'}), 500

@extrato_bp.route('/listar', methods=['GET'])
def listar_extratos():
    """Lista todos os extratos importados"""
    try:
        extratos = Extrato.query.order_by(Extrato.data_upload.desc()).all()
        return jsonify({
            'extratos': [extrato.to_dict() for extrato in extratos]
        })
    except Exception as e:
        return jsonify({'erro': f'Erro ao listar extratos: {str(e)}'}), 500

@extrato_bp.route('/<int:extrato_id>/transacoes', methods=['GET'])
def listar_transacoes(extrato_id):
    """Lista transações de um extrato específico"""
    try:
        extrato = Extrato.query.get_or_404(extrato_id)
        transacoes = Transacao.query.filter_by(extrato_id=extrato_id).order_by(Transacao.data_transacao.desc()).all()
        
        return jsonify({
            'extrato': extrato.to_dict(),
            'transacoes': [transacao.to_dict() for transacao in transacoes]
        })
    except Exception as e:
        return jsonify({'erro': f'Erro ao listar transações: {str(e)}'}), 500

@extrato_bp.route('/<int:extrato_id>', methods=['DELETE'])
def deletar_extrato(extrato_id):
    """Deleta um extrato e suas transações"""
    try:
        extrato = Extrato.query.get_or_404(extrato_id)
        db.session.delete(extrato)
        db.session.commit()
        
        return jsonify({
            'sucesso': True,
            'mensagem': 'Extrato deletado com sucesso'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': f'Erro ao deletar extrato: {str(e)}'}), 500

