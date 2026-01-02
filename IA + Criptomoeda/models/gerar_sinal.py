import os
import pandas as pd
import numpy as np
import joblib
import json
from datetime import datetime, timedelta
import sys

# Adiciona o diretório atual ao path para importar módulos locais
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

def gerar_sinal_ao_vivo():
    """
    Usa o modelo treinado da pasta data/ para analisar o candle atual e gerar um sinal.
    Agora com força do sinal e horários de entrada/saída futuros.
    """
    agora = datetime.now()
    sinal_base = {
        "id_sinal": f"SINAL_{agora.strftime('%Y%m%d_%H%M%S')}",
        "ativo": "BTC/USDT",
        "timeframe": "5m",
        "horario_analise": agora.strftime("%H:%M"),
        "estado": "INATIVO",
        "mensagem": "Processando análise..."
    }
    
    try:
        # 1. Tenta carregar o modelo treinado da pasta data/models/
        modelo, metricas_modelo = carregar_modelo_mais_recente()
        
        if modelo is None:
            raise FileNotFoundError("Modelo de IA não encontrado na pasta data/models/")
        
        print(f"✅ Modelo carregado: {metricas_modelo.get('nome', 'Desconhecido')}")
        print(f"   Acurácia do modelo: {metricas_modelo.get('acuracia', 'N/A'):.2%}")
        
        # 2. Busca dados recentes
        print("📈 Buscando dados de mercado...")
        dados_brutos = buscar_dados_recentes(limite=100)
        
        if dados_brutos is None or len(dados_brutos) < 30:
            raise ValueError("Dados insuficientes para análise")
        
        # 3. Prepara os dados
        dados_preparados = preparar_dados_para_modelo(dados_brutos)
        
        if dados_preparados is None or len(dados_preparados) == 0:
            raise ValueError("Falha ao preparar dados para análise")
        
        # 4. Pega o último candle para previsão
        ultimo_candle = dados_preparados.iloc[-1]
        colunas_features = ['retorno', 'amplitude', 'pos_fechamento', 'volume_relativo', 'diff_medias']
        
        # Verifica se todas as features estão presentes
        features_disponiveis = [col for col in colunas_features if col in ultimo_candle.index]
        
        if len(features_disponiveis) < 3:
            raise ValueError(f"Features insuficientes. Disponíveis: {features_disponiveis}")
        
        features_atuais = ultimo_candle[features_disponiveis].values.reshape(1, -1)
        
        # 5. Faz a previsão de probabilidade
        probabilidade = modelo.predict_proba(features_atuais)[0]
        prob_compra = probabilidade[1] if len(probabilidade) > 1 else probabilidade[0]
        
        # 6. Toma a decisão baseada nos limiares
        LIMIAR_COMPRA = 0.65
        LIMIAR_VENDA = 0.35
        
        if prob_compra > LIMIAR_COMPRA:
            status = "COMPRAR"
            tipo_operacao = "COMPRA"
            emoji = "🟢"
        elif prob_compra < LIMIAR_VENDA:
            status = "VENDER"
            tipo_operacao = "VENDA"
            emoji = "🔴"
        else:
            status = "AGUARDAR"
            tipo_operacao = "NEUTRO"
            emoji = "⚪"
        
        # 7. Define a força do sinal baseada na probabilidade e volatilidade
        volatilidade = dados_preparados['amplitude'].tail(10).mean() if 'amplitude' in dados_preparados.columns else 0.02
        
        forca_sinal, risco = calcular_forca_e_risco(
            tipo_operacao, 
            prob_compra, 
            volatilidade,
            LIMIAR_COMPRA if tipo_operacao == "COMPRA" else LIMIAR_VENDA
        )
        
        # 8. Monta o sinal base
        sinal = {
            **sinal_base,
            "status": f"{emoji} {status}",
            "tipo_operacao": tipo_operacao,
            "probabilidade": f"{prob_compra:.0%}",
            "forca_sinal": forca_sinal,
            "risco": risco,
            "volatilidade_atual": f"{volatilidade:.4f}",
            "mensagem": gerar_mensagem_sinal(status, forca_sinal, prob_compra, volatilidade),
            "estado": "ATIVO" if tipo_operacao != "NEUTRO" and forca_sinal in ["MÉDIO", "FORTE"] else "INATIVO",
            "info_tecnica": {
                "probabilidade_numerica": float(prob_compra),
                "volatilidade": float(volatilidade),
                "features_utilizadas": features_disponiveis,
                "timestamp_modelo": metricas_modelo.get('timestamp_treinamento', 'N/A')
            }
        }
        
        # 9. Adiciona horários de entrada/saída se for um sinal operável
        if sinal["estado"] == "ATIVO":
            horarios = calcular_horarios_operacao(agora, forca_sinal)
            sinal.update(horarios)
            sinal["mensagem"] = f"{emoji} {status} - {forca_sinal} ({prob_compra:.0%} confiança)"
        
        # 10. Salva o sinal gerado para histórico
        salvar_sinal_para_historico(sinal)
        
        print(f"✅ Sinal gerado: {status} ({forca_sinal}, {prob_compra:.0%})")
        
    except FileNotFoundError as e:
        print(f"⚠️ {e}")
        sinal = gerar_sinal_simulado(agora)
        sinal["mensagem"] = f"⚠️ {e} - Usando modo simulado"
        
    except Exception as e:
        print(f"❌ Erro ao gerar sinal: {e}")
        sinal = gerar_sinal_simulado(agora)
        sinal["mensagem"] = f"❌ Erro: {str(e)[:50]}... - Usando modo simulado"
    
    return sinal


def carregar_modelo_mais_recente():
    """Carrega o modelo mais recente da pasta data/models/"""
    models_dir = os.path.join(project_root, 'data', 'models')
    
    if not os.path.exists(models_dir):
        print(f"⚠️ Pasta de modelos não encontrada: {models_dir}")
        return None, {"nome": "Nenhum", "acuracia": 0, "timestamp_treinamento": "N/A"}
    
    # Procura pelo modelo atual
    modelo_atual_path = os.path.join(models_dir, 'modelo_atual.pkl')
    metricas_atual_path = os.path.join(models_dir, 'metricas_atual.json')
    
    if os.path.exists(modelo_atual_path) and os.path.exists(metricas_atual_path):
        try:
            modelo = joblib.load(modelo_atual_path)
            with open(metricas_atual_path, 'r') as f:
                metricas = json.load(f)
            metricas['nome'] = 'modelo_atual'
            return modelo, metricas
        except Exception as e:
            print(f"⚠️ Erro ao carregar modelo atual: {e}")
    
    # Se não encontrar, procura por qualquer modelo
    modelos = [f for f in os.listdir(models_dir) if f.endswith('.pkl') and f != 'modelo_atual.pkl']
    if modelos:
        modelos.sort(reverse=True)
        modelo_path = os.path.join(models_dir, modelos[0])
        nome_base = modelos[0].replace('.pkl', '')
        metricas_path = os.path.join(models_dir, f'{nome_base}_metricas.json')
        
        try:
            modelo = joblib.load(modelo_path)
            metricas = {}
            if os.path.exists(metricas_path):
                with open(metricas_path, 'r') as f:
                    metricas = json.load(f)
            metricas['nome'] = nome_base
            return modelo, metricas
        except Exception as e:
            print(f"⚠️ Erro ao carregar modelo {modelos[0]}: {e}")
    
    return None, {"nome": "Nenhum", "acuracia": 0, "timestamp_treinamento": "N/A"}


def buscar_dados_recentes(limite=100):
    """Busca dados recentes do mercado"""
    try:
        from models.buscar_dados import buscar_dados_btc
        dados = buscar_dados_btc(limite=limite, salvar_csv=False)
        return dados
    except ImportError as e:
        print(f"⚠️ Erro ao importar buscar_dados: {e}")
        # Cria dados de exemplo para emergência
        return criar_dados_exemplo(limite)


def preparar_dados_para_modelo(dados_brutos):
    """Prepara dados para o modelo"""
    try:
        from models.preparar_dados import preparar_features_e_target
        dados_preparados = preparar_features_e_target(dados_brutos, salvar_preparado=False)
        return dados_preparados
    except ImportError as e:
        print(f"⚠️ Erro ao importar preparar_dados: {e}")
        # Prepara manualmente
        return preparar_dados_manualmente(dados_brutos)


def preparar_dados_manualmente(df):
    """Prepara dados manualmente se o módulo não estiver disponível"""
    df = df.copy()
    
    # Calcula features básicas
    if 'abertura' in df.columns and 'fechamento' in df.columns:
        df['retorno'] = (df['fechamento'] - df['abertura']) / df['abertura']
    
    if 'alta' in df.columns and 'baixa' in df.columns and 'abertura' in df.columns:
        df['amplitude'] = (df['alta'] - df['baixa']) / df['abertura']
    
    if 'fechamento' in df.columns and 'baixa' in df.columns and 'alta' in df.columns:
        df['pos_fechamento'] = (df['fechamento'] - df['baixa']) / (df['alta'] - df['baixa'] + 1e-10)
    
    if 'volume' in df.columns:
        df['media_volume_20'] = df['volume'].rolling(window=20).mean()
        df['volume_relativo'] = df['volume'] / df['media_volume_20']
    
    if 'fechamento' in df.columns:
        df['media_curta'] = df['fechamento'].rolling(window=10).mean()
        df['media_longa'] = df['fechamento'].rolling(window=30).mean()
        df['diff_medias'] = (df['media_curta'] - df['media_longa']) / df['media_longa']
    
    # Cria alvo (próximo candle será maior?)
    if 'fechamento' in df.columns:
        df['alvo'] = (df['fechamento'].shift(-2) > df['fechamento']).astype(int)
    
    df = df.dropna()
    return df


def calcular_forca_e_risco(tipo_operacao, probabilidade, volatilidade, limiar):
    """Calcula a força e risco do sinal"""
    if tipo_operacao == "NEUTRO":
        return "NULO", "NEUTRO"
    
    # Distância do limiar de decisão
    distancia_limiar = abs(probabilidade - limiar)
    
    # Ajusta baseado na volatilidade (mais volatil = mais risco)
    fator_volatilidade = 1.0
    if volatilidade > 0.03:  # Alta volatilidade
        fator_volatilidade = 0.7
    elif volatilidade < 0.01:  # Baixa volatilidade
        fator_volatilidade = 1.3
    
    distancia_ajustada = distancia_limiar * fator_volatilidade
    
    if distancia_ajustada > 0.25:
        forca = "FORTE"
        risco = "BAIXO" if volatilidade < 0.015 else "MÉDIO"
    elif distancia_ajustada > 0.15:
        forca = "MÉDIO"
        risco = "MÉDIO" if volatilidade < 0.02 else "ALTO"
    else:
        forca = "BAIXO"
        risco = "ALTO"
    
    return forca, risco


def gerar_mensagem_sinal(status, forca, probabilidade, volatilidade):
    """Gera mensagem descritiva para o sinal"""
    if status == "COMPRAR":
        if forca == "FORTE":
            return f"Forte oportunidade de compra ({probabilidade:.0%} confiança). Tendência de alta confirmada."
        elif forca == "MÉDIO":
            return f"Boa oportunidade de compra ({probabilidade:.0%} confiança). Análise técnica favorável."
        else:
            return f"Possibilidade de compra ({probabilidade:.0%} confiança). Aguarde confirmação."
    
    elif status == "VENDER":
        if forca == "FORTE":
            return f"Forte oportunidade de venda ({probabilidade:.0%} confiança). Tendência de baixa confirmada."
        elif forca == "MÉDIO":
            return f"Boa oportunidade de venda ({probabilidade:.0%} confiança). Análise técnica favorável."
        else:
            return f"Possibilidade de venda ({probabilidade:.0%} confiança). Aguarde confirmação."
    
    else:
        return f"Mercado lateral ({probabilidade:.0%} probabilidade de compra). Aguarde melhor oportunidade."


def calcular_horarios_operacao(agora, forca_sinal):
    """Calcula horários de entrada e saída sugeridos"""
    if forca_sinal == "FORTE":
        minutos_entrada = 5
        minutos_previsao = 10
    elif forca_sinal == "MÉDIO":
        minutos_entrada = 10
        minutos_previsao = 15
    else:
        minutos_entrada = 15
        minutos_previsao = 20
    
    margem_seguranca = 5
    minutos_saida = minutos_previsao + margem_seguranca
    
    entrada = agora + timedelta(minutes=minutos_entrada)
    saida = entrada + timedelta(minutes=minutos_saida)
    
    return {
        "horario_entrada_sugerido": entrada.strftime("%H:%M"),
        "horario_saida_estimado": saida.strftime("%H:%M"),
        "info_previsao": f"IA prevê movimento em {minutos_previsao}min",
        "tempo_operacao_min": minutos_saida
    }


def salvar_sinal_para_historico(sinal):
    """Salva o sinal gerado para histórico na pasta data/"""
    try:
        data_dir = os.path.join(project_root, 'data')
        sinais_dir = os.path.join(data_dir, 'sinais_gerados')
        os.makedirs(sinais_dir, exist_ok=True)
        
        # Nome do arquivo baseado no ID do sinal
        filename = f"{sinal['id_sinal']}.json"
        filepath = os.path.join(sinais_dir, filename)
        
        # Adiciona timestamp de salvamento
        sinal_com_timestamp = {
            **sinal,
            "salvado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Salva como JSON
        with open(filepath, 'w') as f:
            json.dump(sinal_com_timestamp, f, indent=2, default=str)
        
        print(f"📝 Sinal salvo para histórico: {filename}")
        
        # Também mantém um arquivo com os últimos 50 sinais
        atualizar_ultimos_sinais(sinal_com_timestamp, sinais_dir)
        
    except Exception as e:
        print(f"⚠️ Erro ao salvar sinal no histórico: {e}")


def atualizar_ultimos_sinais(sinal, sinais_dir):
    """Atualiza arquivo com os últimos sinais gerados"""
    try:
        ultimos_file = os.path.join(sinais_dir, 'ultimos_sinais.json')
        
        sinais = []
        if os.path.exists(ultimos_file):
            with open(ultimos_file, 'r') as f:
                sinais = json.load(f)
        
        # Adiciona novo sinal no início
        sinais.insert(0, sinal)
        
        # Mantém apenas os últimos 50
        sinais = sinais[:50]
        
        # Salva
        with open(ultimos_file, 'w') as f:
            json.dump(sinais, f, indent=2, default=str)
            
    except Exception as e:
        print(f"⚠️ Erro ao atualizar últimos sinais: {e}")


def criar_dados_exemplo(n=100):
    """Cria dados de exemplo para emergência"""
    print(f"📊 Criando dados de exemplo ({n} candles)...")
    
    np.random.seed(int(datetime.now().timestamp()))
    
    # Preços base com tendência
    preco_base = 50000
    tendencia = np.cumsum(np.random.normal(0, 30, n))
    ruido = np.random.normal(0, 100, n)
    
    dados = pd.DataFrame({
        'timestamp': pd.date_range(end=datetime.now(), periods=n, freq='5min'),
        'abertura': preco_base + tendencia + ruido,
        'alta': preco_base + tendencia + ruido + np.random.normal(50, 20, n),
        'baixa': preco_base + tendencia + ruido - np.random.normal(50, 20, n),
        'fechamento': preco_base + tendencia + ruido + np.random.normal(10, 30, n),
        'volume': np.random.normal(1000, 200, n)
    })
    
    # Garante que alta > baixa
    dados['alta'] = dados[['abertura', 'fechamento', 'alta']].max(axis=1) + 25
    dados['baixa'] = dados[['abertura', 'fechamento', 'baixa']].min(axis=1) - 25
    
    return dados


def gerar_sinal_simulado(agora):
    """Gera um sinal simulado para fallback"""
    import random
    
    status_opcoes = ["COMPRAR", "VENDER", "AGUARDAR"]
    forca_opcoes = ["FORTE", "MÉDIO", "BAIXO", "NULO"]
    risco_opcoes = ["ALTO", "MÉDIO", "BAIXO", "NEUTRO"]
    
    status = random.choice(status_opcoes)
    emoji = "🟢" if status == "COMPRAR" else "🔴" if status == "VENDER" else "⚪"
    
    if status == "AGUARDAR":
        forca = "NULO"
        risco = "NEUTRO"
    else:
        forca = random.choice(["FORTE", "MÉDIO", "BAIXO"])
        risco = random.choice(["ALTO", "MÉDIO", "BAIXO"])
    
    probabilidade = random.randint(50, 95) if status != "AGUARDAR" else random.randint(40, 60)
    
    sinal = {
        "id_sinal": f"SINAL_SIM_{agora.strftime('%Y%m%d_%H%M%S')}",
        "ativo": "BTC/USDT",
        "timeframe": "5m",
        "status": f"{emoji} {status}",
        "tipo_operacao": "COMPRA" if status == "COMPRAR" else "VENDA" if status == "VENDER" else "NEUTRO",
        "probabilidade": f"{probabilidade}%",
        "forca_sinal": forca,
        "risco": risco,
        "horario_analise": agora.strftime("%H:%M"),
        "volatilidade_atual": f"{random.uniform(0.5, 2.5):.2f}%",
        "estado": "ATIVO" if status != "AGUARDAR" and forca in ["FORTE", "MÉDIO"] else "INATIVO",
        "mensagem": f"Sinal simulado - {status} ({forca.lower()})",
        "info_previsao": "Modo simulado - Treine o modelo para sinais reais",
        "info_tecnica": {
            "probabilidade_numerica": probabilidade / 100,
            "volatilidade": random.uniform(0.005, 0.025),
            "features_utilizadas": ["simuladas"],
            "timestamp_modelo": "N/A (simulado)"
        }
    }
    
    # Adiciona horários se for ativo
    if sinal["estado"] == "ATIVO":
        entrada = agora + timedelta(minutes=random.randint(5, 15))
        saida = entrada + timedelta(minutes=random.randint(20, 40))
        
        sinal.update({
            "horario_entrada_sugerido": entrada.strftime("%H:%M"),
            "horario_saida_estimado": saida.strftime("%H:%M"),
            "tempo_operacao_min": random.randint(25, 45)
        })
    
    return sinal


# Função para testar
if __name__ == "__main__":
    print("🤖 ANALISANDO MERCADO AO VIVO...")
    print("=" * 50)
    
    sinal = gerar_sinal_ao_vivo()
    
    print("\n📊 SINAL GERADO:")
    print("=" * 50)
    
    for chave, valor in sinal.items():
        if chave == "info_tecnica":
            print(f"\n🔧 INFO TÉCNICA:")
            for sub_chave, sub_valor in valor.items():
                print(f"   {sub_chave}: {sub_valor}")
        elif chave not in ["salvado_em"]:
            print(f"{chave.upper().replace('_', ' ')}: {valor}")
    
    print("=" * 50)