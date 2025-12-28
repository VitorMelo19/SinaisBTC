import pandas as pd
import numpy as np

def preparar_features_e_target(df):
    """
    Cria características (features) e o alvo (target) para o modelo.
    O alvo será: 1 se o próximo fechamento for MAIOR que o atual (sinal de COMPRA), 0 caso contrário.
    """
    df = df.copy()

    # --- ENGENHARIA DE FEATURES (Criando 'insights' a partir dos preços brutos) ---
    # 1. Retorno percentual do candle atual
    df['retorno'] = (df['fechamento'] - df['abertura']) / df['abertura']

    # 2. Amplitude normalizada do candle (alta - baixa) / abertura
    df['amplitude'] = (df['alta'] - df['baixa']) / df['abertura']

    # 3. Posição do fechamento no range do candle (0 = na mínima, 1 = na máxima)
    df['pos_fechamento'] = (df['fechamento'] - df['baixa']) / (df['alta'] - df['baixa'] + 1e-10) # +1e-10 evita divisão por zero

    # 4. Volume relativo (volume / média móvel de volume dos últimos 20 períodos)
    df['media_volume_20'] = df['volume'].rolling(window=20).mean()
    df['volume_relativo'] = df['volume'] / df['media_volume_20']

    # 5. Diferença entre Médias Móveis (tendência de curto vs. longo prazo)
    df['media_curta'] = df['fechamento'].rolling(window=10).mean()
    df['media_longa'] = df['fechamento'].rolling(window=30).mean()
    df['diff_medias'] = (df['media_curta'] - df['media_longa']) / df['media_longa']

    # --- DEFINIÇÃO DO ALVO (TARGET) ---
    # Queremos prever o movimento do PRÓXIMO candle.
    # Se o próximo fechamento for maior que o fechamento atual -> 1 (comprar), senão -> 0 (vender/esperar).
    #Prever 2 candles à frente (10 min)
    candles_a_frente = 2
    df['alvo'] = (df['fechamento'].shift(-candles_a_frente) > df['fechamento']).astype(int)

    # Remove as linhas que ficaram com NaN devido ao cálculo das médias móveis
    df = df.dropna()

    return df

# Testa a função
if __name__ == "__main__":
    from buscar_dados import buscar_dados_btc
    dados_brutos = buscar_dados_btc()
    dados_preparados = preparar_features_e_target(dados_brutos)

    print("Dados preparados (últimas 5 linhas):")
    print(dados_preparados[['fechamento', 'retorno', 'amplitude', 'volume_relativo', 'alvo']].tail())