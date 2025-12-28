import pandas as pd
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib # Para salvar o modelo treinado
import os

def treinar_e_salvar_modelo(df):
    """
    Treina um modelo XGBoost e salva em um arquivo.
    """
    # 1. Define quais colunas são features (X) e qual é o alvo (y)
    colunas_features = ['retorno', 'amplitude', 'pos_fechamento', 'volume_relativo', 'diff_medias']
    X = df[colunas_features]
    y = df['alvo']

    # 2. Divide os dados: 80% para TREINO, 20% para TESTE (validação)
    # O parâmetro 'shuffle=False' é importante para séries temporais.
    X_treino, X_teste, y_treino, y_teste = train_test_split(X, y, test_size=0.2, shuffle=False, random_state=42)

    # 3. Cria e treina o modelo XGBoost
    print("Treinando o modelo XGBoost...")
    modelo = XGBClassifier(
        n_estimators=150,      # Número de árvores
        max_depth=5,           # Profundidade máxima de cada árvore
        learning_rate=0.1,     # Taxa de aprendizado
        random_state=42,       # Semente para reproducibilidade
        eval_metric='logloss'  # Métrica de avaliação durante o treino
    )
    modelo.fit(X_treino, y_treino)

    # 4. Avalia o modelo nos dados de TESTE (que ele nunca viu)
    previsoes = modelo.predict(X_teste)
    print(f"\n✅ Acurácia nos dados de teste: {accuracy_score(y_teste, previsoes):.2%}")
    print("\n📊 Relatório de Classificação Detalhado:")
    print(classification_report(y_teste, previsoes, target_names=['VENDER/ESPERAR', 'COMPRAR']))

    # 5. Salva o modelo treinado em um arquivo .pkl
    nome_arquivo_modelo = 'modelo_xgboost_btc.pkl'
    # Garante que a pasta 'resultados' existe
    os.makedirs('resultados', exist_ok=True)
    caminho_modelo = os.path.join('resultados', 'modelo_xgboost_btc.pkl')
    joblib.dump(modelo, caminho_modelo)
    print(f"\n💾 Modelo salvo em: '{caminho_modelo}'")
    return modelo, X_teste, y_teste

if __name__ == "__main__":
    from buscar_dados import buscar_dados_btc
    from preparar_dados import preparar_features_e_target

    print("Carregando e preparando dados...")
    dados = buscar_dados_btc()
    dados_prontos = preparar_features_e_target(dados)
    modelo_treinado, X_teste, y_teste = treinar_e_salvar_modelo(dados_prontos)