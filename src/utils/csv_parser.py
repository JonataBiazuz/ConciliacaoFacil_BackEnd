import csv
from typing import List, Dict
from datetime import datetime

# Função para ler e validar um arquivo CSV de contas a receber
# Considera todos os campos da classe ContaReceber

def parse_contas_receber_csv(file_stream) -> List[Dict]:
    contas = []
    reader = csv.DictReader(file_stream.decode('utf-8').splitlines())
    for row in reader:
        # Validação básica dos campos obrigatórios
        if not row.get('cliente_nome') or not row.get('valor_esperado'):
            continue  # Pula linhas inválidas
        contas.append({
            'numero_pedido': row.get('numero_pedido'),
            'cliente_nome': row.get('cliente_nome'),
            'cliente_cpf_cnpj': row.get('cliente_cpf_cnpj'),
            'valor_esperado': row.get('valor_esperado'),
            'data_vencimento': row.get('data_vencimento'),
            'status': row.get('status', 'pendente'),
            'observacoes': row.get('observacoes'),
        })
    return contas
