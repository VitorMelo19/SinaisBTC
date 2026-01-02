import pandas as pd
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import joblib
import os
import json
import numpy as np
from datetime import datetime

def treinar_modelo_com_dados_salvos(df=None, salvar_modelo=True, nome_modelo=None):
    """
    Treina um modelo XGBoost usando dados da pasta data/ e salva o modelo também em data/.
    
    Args:
        df: DataFrame opcional com dados (se None, carrega da pasta data/)
        salvar_modelo: Se True, salva o modelo treinado
        nome_modelo: Nome personalizado para o modelo (opcional)
    
    Returns:
        modelo, X_teste, y_teste, metricas
    """
    
    # 1. Carregar dados se não foram fornecidos
    if df is None:
        try:
            from preparar_dados import carregar_dados_preparados
            print("📂 Carregando dados preparados da pasta data/...")
            df = carregar_dados_preparados()
            
            if df is None:
                raise ValueError("Não foi possível carregar dados da pasta data/")
                
        except ImportError as e:
            print(f"⚠️ Erro ao importar módulo: {e}")
            print("⚠️ Criando dados de exemplo...")
            df = criar_dados_exemplo()
    
    # 2. Define quais colunas são features (X) e qual é o alvo (y)
    colunas_features = ['retorno', 'amplitude', 'pos_fechamento', 'volume_relativo', 'diff_medias']
    
    # Verifica se todas as features estão presentes
    colunas_faltantes = [col for col in colunas_features if col not in df.columns]
    if colunas_faltantes:
        print(f"⚠️ Colunas faltantes: {colunas_faltantes}")
        print("⚠️ Tentando calcular features faltantes...")
        df = calcular_features_faltantes(df, colunas_faltantes)
    
    # 3. Prepara X e y
    X = df[colunas_features]
    y = df['alvo']
    
    # 4. Divide os dados: 80% para TREINO, 20% para TESTE
    # Usa shuffle=False para séries temporais
    X_treino, X_teste, y_treino, y_teste = train_test_split(
        X, y, test_size=0.2, shuffle=False, random_state=42
    )
    
    print(f"📊 Dimensões dos dados:")
    print(f"   • X_treino: {X_treino.shape}")
    print(f"   • X_teste: {X_teste.shape}")
    print(f"   • Distribuição do alvo (treino): {y_treino.value_counts().to_dict()}")
    
    # 5. Cria e treina o modelo XGBoost
    print("\n🤖 Treinando modelo XGBoost...")
    modelo = XGBClassifier(
        n_estimators=150,
        max_depth=5,
        learning_rate=0.1,
        random_state=42,
        eval_metric='logloss'
    )
    
    modelo.fit(
        X_treino, 
        y_treino,
        eval_set=[(X_teste, y_teste)],
        verbose=False
    )
    
    # 6. Avalia o modelo
    previsoes = modelo.predict(X_teste)
    previsoes_proba = modelo.predict_proba(X_teste)[:, 1]
    
    # Métricas
    acuracia = accuracy_score(y_teste, previsoes)
    report = classification_report(y_teste, previsoes, output_dict=True)
    matriz_confusao = confusion_matrix(y_teste, previsoes).tolist()
    
    print(f"\n✅ Acurácia nos dados de teste: {acuracia:.2%}")
    print("\n📊 Relatório de Classificação:")
    print(classification_report(y_teste, previsoes, target_names=['VENDER/ESPERAR', 'COMPRAR']))
    
    # 7. Salva o modelo treinado na pasta data/
    metricas = None
    if salvar_modelo:
        metricas = salvar_modelo_e_metricas(
            modelo, 
            acuracia, 
            report, 
            matriz_confusao,
            X_teste.shape[0],
            nome_modelo=nome_modelo
        )
    
    return modelo, X_teste, y_teste, metricas


def calcular_features_faltantes(df, colunas_faltantes):
    """Calcula features que estão faltando no DataFrame"""
    df = df.copy()
    
    if 'retorno' in colunas_faltantes:
        df['retorno'] = (df['fechamento'] - df['abertura']) / df['abertura']
    
    if 'amplitude' in colunas_faltantes:
        df['amplitude'] = (df['alta'] - df['baixa']) / df['abertura']
    
    if 'pos_fechamento' in colunas_faltantes:
        df['pos_fechamento'] = (df['fechamento'] - df['baixa']) / (df['alta'] - df['baixa'] + 1e-10)
    
    if 'volume_relativo' in colunas_faltantes:
        if 'volume' in df.columns:
            df['media_volume_20'] = df['volume'].rolling(window=20).mean()
            df['volume_relativo'] = df['volume'] / df['media_volume_20']
    
    if 'diff_medias' in colunas_faltantes:
        df['media_curta'] = df['fechamento'].rolling(window=10).mean()
        df['media_longa'] = df['fechamento'].rolling(window=30).mean()
        df['diff_medias'] = (df['media_curta'] - df['media_longa']) / df['media_longa']
    
    # Remove NaN que possam ter sido criados
    df = df.dropna()
    
    return df


def salvar_modelo_e_metricas(modelo, acuracia, report, matriz_confusao, n_amostras, nome_modelo=None):
    """
    Salva o modelo e suas métricas na pasta data/
    """
    # Caminho para a pasta data
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    data_dir = os.path.join(project_root, 'data')
    
    # Cria a pasta data/ se não existir
    os.makedirs(data_dir, exist_ok=True)
    
    # Cria subpasta para modelos
    models_dir = os.path.join(data_dir, 'models')
    os.makedirs(models_dir, exist_ok=True)
    
    # Timestamp atual
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Define nome do modelo
    if nome_modelo is None:
        nome_modelo = f'modelo_xgboost_btc_{timestamp}'
    
    # Caminhos dos arquivos
    modelo_path = os.path.join(models_dir, f'{nome_modelo}.pkl')
    metricas_path = os.path.join(models_dir, f'{nome_modelo}_metricas.json')
    modelo_atual_path = os.path.join(models_dir, 'modelo_atual.pkl')
    metricas_atual_path = os.path.join(models_dir, 'metricas_atual.json')
    
    # Salva o modelo
    joblib.dump(modelo, modelo_path)
    
    # Prepara métricas para salvar
    metricas = {
        'timestamp_treinamento': timestamp,
        'acuracia': float(acuracia),
        'n_amostras_teste': int(n_amostras),
        'classification_report': report,
        'confusion_matrix': matriz_confusao,
        'modelo_info': {
            'nome': nome_modelo,
            'tipo': 'XGBClassifier',
            'n_estimators': 150,
            'max_depth': 5,
            'learning_rate': 0.1
        },
        'features_utilizadas': ['retorno', 'amplitude', 'pos_fechamento', 'volume_relativo', 'diff_medias']
    }
    
    # Salva métricas como JSON
    with open(metricas_path, 'w') as f:
        json.dump(metricas, f, indent=2, default=str)
    
    # Também salva como modelo atual (último)
    joblib.dump(modelo, modelo_atual_path)
    with open(metricas_atual_path, 'w') as f:
        json.dump(metricas, f, indent=2, default=str)
    
    print(f"\n💾 Modelo salvo em: {modelo_path}")
    print(f"📊 Métricas salvas em: {metricas_path}")
    print(f"🔄 Modelo atualizado em: {modelo_atual_path}")
    
    return metricas


def carregar_modelo_treinado(nome_modelo=None, usar_modelo_atual=True):
    """
    Carrega um modelo treinado da pasta data/models/
    
    Args:
        nome_modelo: Nome específico do modelo (sem extensão)
        usar_modelo_atual: Se True, carrega 'modelo_atual.pkl'
    
    Returns:
        modelo, metricas
    """
    # Caminho para a pasta data/models
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    models_dir = os.path.join(project_root, 'data', 'models')
    
    if not os.path.exists(models_dir):
        print(f"⚠️ Pasta de modelos não encontrada: {models_dir}")
        return None, None
    
    if usar_modelo_atual and nome_modelo is None:
        modelo_path = os.path.join(models_dir, 'modelo_atual.pkl')
        metricas_path = os.path.join(models_dir, 'metricas_atual.json')
    else:
        if nome_modelo is None:
            # Lista todos os modelos .pkl
            modelos = [f for f in os.listdir(models_dir) if f.endswith('.pkl') and f != 'modelo_atual.pkl']
            if not modelos:
                print("⚠️ Nenhum modelo encontrado!")
                return None, None
            # Pega o mais recente
            modelos.sort(reverse=True)
            nome_modelo = modelos[0].replace('.pkl', '')
        
        modelo_path = os.path.join(models_dir, f'{nome_modelo}.pkl')
        metricas_path = os.path.join(models_dir, f'{nome_modelo}_metricas.json')
    
    try:
        # Carrega modelo
        modelo = joblib.load(modelo_path)
        
        # Carrega métricas
        if os.path.exists(metricas_path):
            with open(metricas_path, 'r') as f:
                metricas = json.load(f)
        else:
            metricas = None
        
        print(f"✅ Modelo carregado: {os.path.basename(modelo_path)}")
        if metricas:
            print(f"   📊 Acurácia: {metricas.get('acuracia', 'N/A')}")
            print(f"   📅 Treinado em: {metricas.get('timestamp_treinamento', 'N/A')}")
        
        return modelo, metricas
        
    except Exception as e:
        print(f"❌ Erro ao carregar modelo: {e}")
        return None, None


def listar_modelos_treinados():
    """Lista todos os modelos treinados disponíveis"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    models_dir = os.path.join(project_root, 'data', 'models')
    
    if not os.path.exists(models_dir):
        print(f"📁 Pasta de modelos não encontrada: {models_dir}")
        return []
    
    print(f"\n🤖 Modelos treinados disponíveis em {models_dir}:")
    
    modelos_pkl = [f for f in os.listdir(models_dir) if f.endswith('.pkl')]
    modelos_metricas = [f for f in os.listdir(models_dir) if f.endswith('_metricas.json')]
    
    if not modelos_pkl:
        print("   ⚠️ Nenhum modelo encontrado")
        return []
    
    # Mostra modelo atual primeiro
    if 'modelo_atual.pkl' in modelos_pkl:
        modelo_path = os.path.join(models_dir, 'modelo_atual.pkl')
        size_mb = os.path.getsize(modelo_path) / (1024 * 1024)
        print(f"   ⭐ modelo_atual.pkl ({size_mb:.2f} MB) [ÚLTIMO]")
    
    # Lista outros modelos
    outros_modelos = [f for f in modelos_pkl if f != 'modelo_atual.pkl']
    for modelo in sorted(outros_modelos, reverse=True)[:10]:  # Mostra os 10 mais recentes
        modelo_path = os.path.join(models_dir, modelo)
        size_mb = os.path.getsize(modelo_path) / (1024 * 1024)
        
        # Tenta encontrar métricas correspondentes
        nome_base = modelo.replace('.pkl', '')
        metricas_path = os.path.join(models_dir, f'{nome_base}_metricas.json')
        
        if os.path.exists(metricas_path):
            try:
                with open(metricas_path, 'r') as f:
                    metricas = json.load(f)
                acuracia = metricas.get('acuracia', 'N/A')
                timestamp = metricas.get('timestamp_treinamento', 'N/A')
                print(f"   • {modelo} ({size_mb:.2f} MB) - Ac: {acuracia:.2%} - {timestamp}")
            except:
                print(f"   • {modelo} ({size_mb:.2f} MB)")
        else:
            print(f"   • {modelo} ({size_mb:.2f} MB)")
    
    if len(outros_modelos) > 10:
        print(f"   ... e mais {len(outros_modelos) - 10} modelos")
    
    return modelos_pkl


def criar_dados_exemplo():
    """Cria dados de exemplo para teste"""
    print("📊 Criando dados de exemplo...")
    
    np.random.seed(42)
    n = 500
    
    # Preços base
    preco_base = 50000
    tendencia = np.cumsum(np.random.normal(0, 50, n))
    
    dados = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=n, freq='5min'),
        'abertura': preco_base + tendencia + np.random.normal(0, 100, n),
        'alta': preco_base + tendencia + np.random.normal(100, 50, n),
        'baixa': preco_base + tendencia + np.random.normal(-100, 50, n),
        'fechamento': preco_base + tendencia + np.random.normal(0, 80, n),
        'volume': np.random.normal(1000, 200, n)
    })
    
    # Garante que alta > baixa
    dados['alta'] = dados[['abertura', 'fechamento', 'alta']].max(axis=1) + 50
    dados['baixa'] = dados[['abertura', 'fechamento', 'baixa']].min(axis=1) - 50
    
    # Prepara features
    dados = calcular_features_faltantes(dados, ['retorno', 'amplitude', 'pos_fechamento', 'volume_relativo', 'diff_medias'])
    
    # Cria alvo (próximo candle será maior?)
    dados['alvo'] = (dados['fechamento'].shift(-1) > dados['fechamento']).astype(int)
    dados = dados.dropna()
    
    return dados


# Testa a função
if __name__ == "__main__":
    print("🧠 Testando treinamento de modelo XGBoost...")
    
    # Opção 1: Treinar com dados carregados da pasta data/
    print("\n" + "="*60)
    print("1️⃣ Tentando treinar com dados da pasta data/...")
    try:
        modelo, X_teste, y_teste, metricas = treinar_modelo_com_dados_salvos(
            salvar_modelo=True,
            nome_modelo=None  # Gera nome automaticamente com timestamp
        )
        
        print("\n✅ Treinamento concluído com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro ao treinar com dados reais: {e}")
        print("\n" + "="*60)
        print("2️⃣ Treinando com dados de exemplo...")
        
        # Opção 2: Treinar com dados de exemplo
        dados_exemplo = criar_dados_exemplo()
        modelo, X_teste, y_teste, metricas = treinar_modelo_com_dados_salvos(
            df=dados_exemplo,
            salvar_modelo=True,
            nome_modelo='modelo_exemplo'
        )
    
    # Lista modelos disponíveis
    print("\n" + "="*60)
    listar_modelos_treinados()
    
    # Testa carregar modelo
    print("\n" + "="*60)
    print("🔄 Testando carregamento de modelo...")
    modelo_carregado, metricas_carregadas = carregar_modelo_treinado()
    
    if modelo_carregado is not None:
        print("\n✅ Modelo carregado com sucesso!")
        
        # Faz uma previsão de exemplo
        if X_teste is not None and len(X_teste) > 0:
            exemplo = X_teste.iloc[[0]]  # Primeira amostra de teste
            previsao = modelo_carregado.predict(exemplo)
            probabilidade = modelo_carregado.predict_proba(exemplo)
            
            print(f"\n🔮 Previsão de exemplo:")
            print(f"   Dados: {exemplo.values[0].round(4)}")
            print(f"   Previsão: {'COMPRAR' if previsao[0] == 1 else 'VENDER/ESPERAR'}")
            print(f"   Probabilidade: {probabilidade[0][1]:.2%}")