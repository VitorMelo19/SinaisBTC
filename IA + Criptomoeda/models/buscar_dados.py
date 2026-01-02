from binance.client import Client
import pandas as pd
import os

# 1. Conecta à API pública da Binance
client = Client()

def buscar_dados_btc(par='BTCUSDT', intervalo='5m', limite=500, salvar_csv=True):
    """
    Busca dados históricos da Binance e salva na pasta data/.
    
    Args:
        par: O par de negociação (ex: 'BTCUSDT')
        intervalo: O timeframe ('1m', '5m', '1h', etc.)
        limite: Quantidade de candles para trazer (máx. 1000)
        salvar_csv: Se True, salva os dados em um arquivo CSV
        
    Returns:
        Um DataFrame do Pandas com os dados.
    """
    # Pega os candles
    candles = client.get_klines(symbol=par, interval=intervalo, limit=limite)

    # Converte para um DataFrame organizado
    colunas = ['abertura', 'alta', 'baixa', 'fechamento', 'volume']
    dados = [[float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])] for c in candles]
    df = pd.DataFrame(dados, columns=colunas)
    
    # Adiciona timestamp dos candles (opcional)
    timestamps = [c[0] for c in candles]
    df['timestamp'] = timestamps
    df['data_hora'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Reorganiza as colunas
    df = df[['timestamp', 'data_hora', 'abertura', 'alta', 'baixa', 'fechamento', 'volume']]
    
    # Salva na pasta data/ se solicitado
    if salvar_csv:
        # Caminho para a pasta data (subindo um nível de models/)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)  # Sobe para raiz do projeto
        data_dir = os.path.join(project_root, 'data')
        
        # Cria a pasta data/ se não existir
        os.makedirs(data_dir, exist_ok=True)
        
        # Gera nome do arquivo com timestamp atual
        from datetime import datetime
        timestamp_agora = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'dados_btc_{par}_{intervalo}_{limite}_{timestamp_agora}.csv'
        filepath = os.path.join(data_dir, filename)
        
        # Salva como CSV
        df.to_csv(filepath, index=False)
        print(f"✅ Dados salvos em: {filepath}")
        
        # Também salva um arquivo "últimos_dados.csv" sempre atualizado
        ultimo_file = os.path.join(data_dir, 'ultimos_dados.csv')
        df.to_csv(ultimo_file, index=False)
        print(f"📊 Últimos dados atualizados: {ultimo_file}")
    
    return df

# 2. Função para carregar dados salvos
def carregar_dados_salvos(pasta='data', arquivo=None):
    """
    Carrega dados salvos anteriormente da pasta data/.
    
    Args:
        pasta: Nome da pasta (padrão 'data')
        arquivo: Nome específico do arquivo (None para carregar o último)
    
    Returns:
        DataFrame com os dados ou None se não encontrar.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    data_dir = os.path.join(project_root, pasta)
    
    if not os.path.exists(data_dir):
        print(f"⚠️ Pasta {data_dir} não existe!")
        return None
    
    if arquivo:
        filepath = os.path.join(data_dir, arquivo)
    else:
        # Tenta carregar o arquivo mais recente
        arquivos = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
        if not arquivos:
            print("⚠️ Nenhum arquivo CSV encontrado!")
            return None
        
        # Encontra o arquivo mais recente
        arquivos.sort(reverse=True)
        filepath = os.path.join(data_dir, arquivos[0])
    
    try:
        df = pd.read_csv(filepath)
        print(f"📂 Dados carregados: {os.path.basename(filepath)}")
        print(f"   📊 Linhas: {len(df)}, Colunas: {len(df.columns)}")
        return df
    except Exception as e:
        print(f"❌ Erro ao carregar {filepath}: {e}")
        return None

# 3. Testa a função
if __name__ == "__main__":
    print("📈 Buscando dados da Binance...")
    
    # Busca e salva dados
    df_btc = buscar_dados_btc(
        par='BTCUSDT', 
        intervalo='5m', 
        limite=100,  # Reduzido para teste
        salvar_csv=True
    )
    
    print("\n📋 Primeiras 5 linhas dos dados:")
    print(df_btc.head())
    print(f"\n📊 Total de candles: {len(df_btc)}")
    print(f"📅 Período: {df_btc['data_hora'].min()} até {df_btc['data_hora'].max()}")
    
    # Testa carregar dados
    print("\n" + "="*50)
    print("🔄 Testando carregamento de dados salvos...")
    dados_carregados = carregar_dados_salvos()
    
    if dados_carregados is not None:
        print("\n✅ Dados carregados com sucesso!")
        print(f"📊 Amostra dos dados carregados:")
        print(dados_carregados[['data_hora', 'fechamento', 'volume']].head())