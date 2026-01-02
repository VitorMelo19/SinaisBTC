import pandas as pd
import numpy as np
import os
import joblib
from datetime import datetime

def preparar_features_e_target(df, salvar_preparado=True, nome_arquivo=None):
    """
    Cria características (features) e o alvo (target) para o modelo.
    Salva os dados preparados na pasta data/.
    
    Args:
        df: DataFrame com dados brutos
        salvar_preparado: Se True, salva os dados preparados em CSV
        nome_arquivo: Nome personalizado do arquivo (opcional)
    
    Returns:
        DataFrame com features e target
    """
    df = df.copy()

    # --- ENGENHARIA DE FEATURES (Criando 'insights' a partir dos preços brutos) ---
    # 1. Retorno percentual do candle atual
    df['retorno'] = (df['fechamento'] - df['abertura']) / df['abertura']

    # 2. Amplitude normalizada do candle (alta - baixa) / abertura
    df['amplitude'] = (df['alta'] - df['baixa']) / df['abertura']

    # 3. Posição do fechamento no range do candle (0 = na mínima, 1 = na máxima)
    df['pos_fechamento'] = (df['fechamento'] - df['baixa']) / (df['alta'] - df['baixa'] + 1e-10)  # +1e-10 evita divisão por zero

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
    # Prever 2 candles à frente (10 min)
    candles_a_frente = 2
    df['alvo'] = (df['fechamento'].shift(-candles_a_frente) > df['fechamento']).astype(int)

    # Remove as linhas que ficaram com NaN devido ao cálculo das médias móveis
    df = df.dropna()
    
    # --- SALVAR DADOS PREPARADOS ---
    if salvar_preparado:
        # Caminho para a pasta data
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)  # Sobe para raiz do projeto
        data_dir = os.path.join(project_root, 'data')
        
        # Cria a pasta data/ se não existir
        os.makedirs(data_dir, exist_ok=True)
        
        # Define nome do arquivo
        if nome_arquivo is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            nome_arquivo = f'dados_preparados_{timestamp}.csv'
        
        # Caminho completo
        filepath = os.path.join(data_dir, nome_arquivo)
        
        # Salva como CSV
        df.to_csv(filepath, index=False)
        print(f"✅ Dados preparados salvos em: {filepath}")
        print(f"   📊 Dimensões: {df.shape[0]} linhas × {df.shape[1]} colunas")
        
        # Também salva como pickle (mais rápido para carregar depois)
        pickle_path = os.path.join(data_dir, f'dados_preparados_{timestamp}.pkl')
        df.to_pickle(pickle_path)
        print(f"   💾 Versão pickle salva em: {pickle_path}")
        
        # Salva um arquivo "ultimos_preparados.csv" sempre atualizado
        ultimo_csv = os.path.join(data_dir, 'ultimos_dados_preparados.csv')
        df.to_csv(ultimo_csv, index=False)
        
        ultimo_pkl = os.path.join(data_dir, 'ultimos_dados_preparados.pkl')
        df.to_pickle(ultimo_pkl)
        
        print(f"   🔄 Últimos dados atualizados: {ultimo_csv}")
        
        # Salva estatísticas em um arquivo de metadados
        salvar_estatisticas(df, data_dir, timestamp)

    return df


def salvar_estatisticas(df, data_dir, timestamp):
    """Salva estatísticas descritivas dos dados preparados"""
    stats = {
        'timestamp_geracao': timestamp,
        'total_linhas': int(df.shape[0]),
        'total_colunas': int(df.shape[1]),
        'periodo_inicio': str(df['timestamp'].min()) if 'timestamp' in df.columns else 'N/A',
        'periodo_fim': str(df['timestamp'].max()) if 'timestamp' in df.columns else 'N/A',
        'colunas': list(df.columns),
        'estatisticas_alvo': {
            'total_1': int(df['alvo'].sum()),
            'total_0': int(len(df) - df['alvo'].sum()),
            'percentual_1': float(df['alvo'].mean()),
            'percentual_0': float(1 - df['alvo'].mean())
        },
        'estatisticas_numericas': df.describe().to_dict()
    }
    
    # Salva estatísticas como JSON
    import json
    stats_path = os.path.join(data_dir, f'stats_dados_preparados_{timestamp}.json')
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2, default=str)
    
    print(f"   📊 Estatísticas salvas em: {stats_path}")


def carregar_dados_preparados(nome_arquivo=None, usar_pickle=True):
    """
    Carrega dados preparados da pasta data/.
    
    Args:
        nome_arquivo: Nome específico do arquivo (None para carregar o último)
        usar_pickle: Se True, tenta carregar a versão pickle (mais rápida)
    
    Returns:
        DataFrame com os dados preparados ou None se não encontrar.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    data_dir = os.path.join(project_root, 'data')
    
    if not os.path.exists(data_dir):
        print(f"⚠️ Pasta {data_dir} não existe!")
        return None
    
    if nome_arquivo:
        filepath = os.path.join(data_dir, nome_arquivo)
        if not os.path.exists(filepath):
            print(f"⚠️ Arquivo {filepath} não encontrado!")
            return None
    else:
        # Tenta carregar o arquivo mais recente
        if usar_pickle:
            # Procura por arquivos pickle
            arquivos = [f for f in os.listdir(data_dir) if f.endswith('.pkl') and 'preparados' in f]
            if not arquivos:
                print("⚠️ Nenhum arquivo pickle encontrado, tentando CSV...")
                usar_pickle = False
        
        if not usar_pickle:
            # Procura por arquivos CSV
            arquivos = [f for f in os.listdir(data_dir) if f.endswith('.csv') and 'preparados' in f]
            if not arquivos:
                print("⚠️ Nenhum arquivo CSV encontrado!")
                return None
        
        # Encontra o arquivo mais recente
        arquivos.sort(reverse=True)
        filepath = os.path.join(data_dir, arquivos[0])
    
    try:
        if usar_pickle and filepath.endswith('.pkl'):
            df = pd.read_pickle(filepath)
            print(f"📂 Dados preparados carregados (pickle): {os.path.basename(filepath)}")
        else:
            df = pd.read_csv(filepath)
            print(f"📂 Dados preparados carregados (CSV): {os.path.basename(filepath)}")
        
        print(f"   📊 Dimensões: {df.shape[0]} linhas × {df.shape[1]} colunas")
        if 'alvo' in df.columns:
            print(f"   🎯 Distribuição do alvo: {df['alvo'].sum()} (1) vs {len(df) - df['alvo'].sum()} (0)")
        
        return df
    except Exception as e:
        print(f"❌ Erro ao carregar {filepath}: {e}")
        return None


def verificar_dados_preparados():
    """Verifica e lista os dados preparados disponíveis na pasta data/"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    data_dir = os.path.join(project_root, 'data')
    
    if not os.path.exists(data_dir):
        print(f"📁 Pasta data/ não encontrada em: {data_dir}")
        return []
    
    print(f"\n📁 Conteúdo da pasta data/:")
    arquivos = os.listdir(data_dir)
    
    preparados_csv = [f for f in arquivos if f.endswith('.csv') and 'preparados' in f]
    preparados_pkl = [f for f in arquivos if f.endswith('.pkl') and 'preparados' in f]
    stats_json = [f for f in arquivos if f.endswith('.json') and 'stats' in f]
    
    if preparados_csv:
        print("\n📄 Arquivos CSV preparados:")
        for f in sorted(preparados_csv, reverse=True)[:5]:  # Mostra apenas os 5 mais recentes
            filepath = os.path.join(data_dir, f)
            size_kb = os.path.getsize(filepath) / 1024
            print(f"   • {f} ({size_kb:.1f} KB)")
    
    if preparados_pkl:
        print("\n💾 Arquivos Pickle preparados:")
        for f in sorted(preparados_pkl, reverse=True)[:3]:
            filepath = os.path.join(data_dir, f)
            size_kb = os.path.getsize(filepath) / 1024
            print(f"   • {f} ({size_kb:.1f} KB)")
    
    if stats_json:
        print("\n📊 Arquivos de estatísticas:")
        for f in sorted(stats_json, reverse=True)[:3]:
            filepath = os.path.join(data_dir, f)
            size_kb = os.path.getsize(filepath) / 1024
            print(f"   • {f} ({size_kb:.1f} KB)")
    
    outros = len(arquivos) - len(preparados_csv) - len(preparados_pkl) - len(stats_json)
    if outros > 0:
        print(f"\n📦 Outros arquivos: {outros} arquivo(s)")
    
    return preparados_csv + preparados_pkl


# Testa a função
if __name__ == "__main__":
    print("🧪 Testando preparação de dados...")
    
    # Importa a função buscar_dados com tratamento de erro
    try:
        from buscar_dados import buscar_dados_btc
        
        # Busca dados (pode desativar salvamento para não duplicar)
        print("📈 Buscando dados da Binance...")
        dados_brutos = buscar_dados_btc(limite=100, salvar_csv=False)
        
        # Prepara e salva dados
        print("🔧 Preparando features e target...")
        dados_preparados = preparar_features_e_target(
            dados_brutos, 
            salvar_preparado=True,
            nome_arquivo=None  # Deixa gerar automaticamente
        )
        
        print("\n✅ Dados preparados com sucesso!")
        print("\n📋 Últimas 5 linhas dos dados preparados:")
        print(dados_preparados[['fechamento', 'retorno', 'amplitude', 'volume_relativo', 'alvo']].tail())
        
        # Verifica dados salvos
        print("\n" + "="*50)
        verificar_dados_preparados()
        
        # Testa carregamento
        print("\n" + "="*50)
        print("🔄 Testando carregamento de dados preparados...")
        dados_carregados = carregar_dados_preparados()
        
        if dados_carregados is not None:
            print("\n✅ Dados carregados com sucesso!")
            print(f"📊 Amostra dos dados carregados:")
            print(dados_carregados.head(3))
        
    except ImportError as e:
        print(f"⚠️ Erro ao importar buscar_dados: {e}")
        print("⚠️ Criando dados de exemplo para teste...")
        
        # Cria dados de exemplo
        np.random.seed(42)
        n = 200
        dados_exemplo = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=n, freq='5min'),
            'abertura': np.random.normal(50000, 1000, n),
            'alta': np.random.normal(50500, 1000, n),
            'baixa': np.random.normal(49500, 1000, n),
            'fechamento': np.random.normal(50250, 1000, n),
            'volume': np.random.normal(1000, 200, n)
        })
        
        # Prepara e salva dados de exemplo
        dados_preparados = preparar_features_e_target(dados_exemplo, salvar_preparado=True)
        print("\n✅ Dados de exemplo preparados e salvos!")
        
        # Verifica
        verificar_dados_preparados()