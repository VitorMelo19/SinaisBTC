import os
import pandas as pd
import numpy as np
import joblib
from datetime import datetime, timedelta
from buscar_dados import buscar_dados_btc
from preparar_dados import preparar_features_e_target

def gerar_sinal_ao_vivo():
    """
    Usa o modelo treinado para analisar o candle atual e gerar um sinal PRIMÁRIO.
    Agora com força do sinal e horários de entrada/saída futuros.
    """
    # 1. Carrega o modelo que você treinou
    caminho_modelo = os.path.join('resultados', 'modelo_xgboost_btc.pkl')
    modelo = joblib.load(caminho_modelo)

    # 2. Busca dados recentes (últimos 100 candles para mais contexto)
    dados_brutos = buscar_dados_btc(limite=100)
    dados_atualizados = preparar_features_e_target(dados_brutos)

    # 3. Pega o ÚLTIMO candle (o mais recente) para fazer a previsão
    ultimo_candle = dados_atualizados.iloc[-1]
    colunas_features = ['retorno', 'amplitude', 'pos_fechamento', 'volume_relativo', 'diff_medias']
    features_atuais = ultimo_candle[colunas_features].values.reshape(1, -1)

    # 4. Faz a previsão de PROBABILIDADE
    probabilidade = modelo.predict_proba(features_atuais)[0]
    prob_compra = probabilidade[1]  # Probabilidade da classe "COMPRAR" (alvo=1)

    # 5. Toma a decisão PRIMÁRIA com base nos limiares
    LIMIAR_COMPRA = 0.65
    LIMIAR_VENDA = 0.35

    if prob_compra > LIMIAR_COMPRA:
        status = "🟢 COMPRAR"
        tipo_operacao = "COMPRA"
    elif prob_compra < LIMIAR_VENDA:
        status = "🔴 VENDER"
        tipo_operacao = "VENDA"
    else:
        status = "⚪ AGUARDAR"
        tipo_operacao = "NEUTRO"

    # 6. Define a FORÇA do sinal baseada na probabilidade e volatilidade
    # (Quanto mais perto de 100% ou 0%, mais forte. Quanto mais volatil, mais cautela)
    volatilidade = dados_atualizados['amplitude'].tail(10).mean()  # Média da amplitude dos últimos 10 candles

    if tipo_operacao != "NEUTRO":
        # Distância do limiar de decisão (ex: 0.85 está 0.20 acima do limiar 0.65)
        distancia_limiar = abs(prob_compra - (0.65 if tipo_operacao == "COMPRA" else 0.35))

        if distancia_limiar > 0.25 and volatilidade < 0.01:
            forca_sinal = "FORTE"
            risco = "BAIXO"
        elif distancia_limiar > 0.15:
            forca_sinal = "MÉDIO"
            risco = "MÉDIO"
        else:
            forca_sinal = "BAIXO"
            risco = "ALTO"
    else:
        forca_sinal = "NULO"
        risco = "NEUTRO"


    # 7. Calcula janela de tempo FUTURA para entrada e saída
    agora = datetime.now()

    # Sinal neutro ou fraco - NÃO recomenda operação (VALOR PADRÃO)
    sinal = {
        "id_sinal": f"SINAL_{agora.strftime('%Y%m%d_%H%M%S')}",
        "ativo": "BTC",
        "timeframe": "5m",
        "status": status,
        "tipo_operacao": tipo_operacao,
        "probabilidade": f"{prob_compra:.0%}",
        "forca_sinal": forca_sinal,
        "risco": risco,
        "horario_analise": agora.strftime("%H:%M"),
        "mensagem": "Mercado lateral ou sinal fraco. Aguardar oportunidade.",
        "estado": "INATIVO"
    }

    # Entrada: 5-10 minutos no futuro (tempo para o usuário se preparar)
    # APENAS se for um sinal operável, SOBRESCREVE o sinal padrão
    if tipo_operacao != "NEUTRO" and forca_sinal in ["MÉDIO", "FORTE"]:
        # Se o sinal é bom, sugere entrada em 5-10 minutos
        minutos_entrada = 5 if forca_sinal == "FORTE" else 10
        horario_entrada = (agora + timedelta(minutes=minutos_entrada)).strftime("%H:%M")

        # Saída: BASEADO NA PREVISÃO DA IA (10 minutos) + margem de segurança
        minutos_previsao_ia = 10  # AGORA A IA PREVÊ 10 MIN À FRENTE (2 candles)
        margem_seguranca = 5
        minutos_saida = minutos_previsao_ia + margem_seguranca
        horario_saida_estimada = (agora + timedelta(minutes=minutos_entrada + minutos_saida)).strftime("%H:%M")

        # Monta o SINAL COMPLETO para API (sobrescreve o dicionário padrão)
        sinal = {
            "id_sinal": f"SINAL_{agora.strftime('%Y%m%d_%H%M%S')}",
            "ativo": "BTC",
            "timeframe": "5m",
            "status": status,
            "tipo_operacao": tipo_operacao,
            "probabilidade": f"{prob_compra:.0%}",
            "forca_sinal": forca_sinal,
            "risco": risco,
            "horario_analise": agora.strftime("%H:%M"),
            "horario_entrada_sugerido": horario_entrada,
            "horario_saida_estimado": horario_saida_estimada,
            "volatilidade_atual": f"{volatilidade:.4f}",
            "estado": "ATIVO",
            "info_previsao": f"IA prevê movimento em {minutos_previsao_ia}min"
        }

    return sinal

# Função para testar
if __name__ == "__main__":
    print("🤖 ANALISANDO MERCADO AO VIVO...")
    print("=" * 50)
    sinal = gerar_sinal_ao_vivo()
    
    for chave, valor in sinal.items():
        print(f"{chave.upper()}: {valor}")