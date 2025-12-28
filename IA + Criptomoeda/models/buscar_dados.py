from binance.client import Client
import pandas as pd

# 1. Conecta à API pública da Binance (sem chaves são necessárias para dados)
client = Client()

# 2. Função para buscar os últimos candles (velas) de 5 minutos
def buscar_dados_btc(par='BTCUSDT', intervalo='5m', limite=500):
    """
    Busca dados históricos da Binance.
    Args:
        par: O par de negociação (ex: 'BTCUSDT')
        intervalo: O timeframe ('1m', '5m', '1h', etc.)
        limite: Quantidade de candles para trazer (máx. 1000)
    Returns:
        Um DataFrame do Pandas com os dados.
    """
    # Pega os candles
    candles = client.get_klines(symbol=par, interval=intervalo, limit=limite)

    # Converte para um DataFrame organizado
    colunas = ['abertura', 'alta', 'baixa', 'fechamento', 'volume']
    # Pega apenas as colunas de interesse (abertura, alta, baixa, fechamento, volume)
    dados = [[float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])] for c in candles]
    df = pd.DataFrame(dados, columns=colunas)

    return df

# 3. Testa a função
if __name__ == "__main__":
    df_btc = buscar_dados_btc()
    print("Primeiras 5 linhas dos dados:")
    print(df_btc.head())
    print(f"\nTotal de candles: {len(df_btc)}")