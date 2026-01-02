# api.py (Versão COMPLETA para Android)
import os
import sys
import json
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import sqlite3

# Configurar path para funcionar no Render
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, 'models'))

print("📍 Configurando API para Android...")
print(f"📍 Diretório atual: {current_dir}")

app = FastAPI(title="API Sinais BTC", 
              description="API para sistema de IA de criptomoedas",
              version="1.0.0")

# Configurar CORS para permitir acesso do app Android
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especificar domínios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar banco de dados
def init_db():
    db_path = os.path.join(current_dir, 'data', 'sinais_ativos.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Criar tabela se não existir
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sinais (
        id TEXT PRIMARY KEY,
        dados TEXT,
        estado TEXT,
        tipo_operacao TEXT,
        forca_sinal TEXT,
        risco TEXT,
        probabilidade REAL,
        horario_analise TEXT,
        horario_entrada_sugerido TEXT,
        horario_saida_estimado TEXT,
        criado_em TIMESTAMP,
        atualizado_em TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()
    print(f"✅ Banco de dados inicializado: {db_path}")

# Inicializar banco de dados
init_db()

# Funções auxiliares
def get_db_connection():
    db_path = os.path.join(current_dir, 'data', 'sinais_ativos.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# Endpoints da API

@app.get("/")
async def root():
    return {
        "message": "API de Sinais BTC - IA para Criptomoedas",
        "status": "online",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "/api/sinal": "GET - Sinal atual",
            "/api/sinais": "GET - Listar sinais ativos",
            "/api/sinal/{id}": "GET - Detalhes de um sinal",
            "/api/estatisticas": "GET - Estatísticas do sistema",
            "/api/historico": "GET - Histórico de sinais",
            "/api/health": "GET - Health check"
        }
    }

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "sinais-btc-api",
        "environment": "render"
    }

@app.get("/api/sinal")
async def get_sinal_atual():
    """Retorna o sinal atual gerado pela IA"""
    try:
        from gerar_sinal import gerar_sinal_ao_vivo
        sinal = gerar_sinal_ao_vivo()
        
        # Salvar no banco de dados
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar se já existe
        cursor.execute("SELECT id FROM sinais WHERE id = ?", (sinal['id_sinal'],))
        exists = cursor.fetchone()
        
        if not exists:
            dados_json = json.dumps(sinal, ensure_ascii=False, default=str)
            cursor.execute('''
            INSERT INTO sinais (id, dados, estado, tipo_operacao, forca_sinal, risco, 
                              probabilidade, horario_analise, horario_entrada_sugerido, 
                              horario_saida_estimado, criado_em, atualizado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                sinal['id_sinal'],
                dados_json,
                sinal.get('estado', 'ATIVO'),
                sinal.get('tipo_operacao', 'NEUTRO'),
                sinal.get('forca_sinal', 'NULO'),
                sinal.get('risco', 'NEUTRO'),
                float(sinal.get('probabilidade', '0%').replace('%', '')) / 100,
                sinal.get('horario_analise'),
                sinal.get('horario_entrada_sugerido'),
                sinal.get('horario_saida_estimado'),
                datetime.now(),
                datetime.now()
            ))
            conn.commit()
        
        conn.close()
        return sinal
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Erro ao importar módulo: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar sinal: {str(e)}")

@app.get("/api/sinais")
async def get_sinais_ativos():
    """Retorna todos os sinais ativos"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, dados, estado, tipo_operacao, forca_sinal, risco, probabilidade,
               horario_analise, horario_entrada_sugerido, horario_saida_estimado,
               criado_em, atualizado_em
        FROM sinais 
        WHERE estado IN ('ATIVO', 'CONFIRMADO', 'EM_MONITORAMENTO', 'ALERTA')
        ORDER BY criado_em DESC
        ''')
        
        sinais = []
        for row in cursor.fetchall():
            try:
                dados = json.loads(row['dados'])
                sinais.append(dados)
            except:
                # Formato simplificado se não conseguir parsear JSON
                sinal = {
                    'id_sinal': row['id'],
                    'ativo': 'BTC/USDT',
                    'timeframe': '5m',
                    'status': f"{row['tipo_operacao']} ({row['forca_sinal']})",
                    'tipo_operacao': row['tipo_operacao'],
                    'probabilidade': f"{row['probabilidade']*100:.0f}%",
                    'forca_sinal': row['forca_sinal'],
                    'risco': row['risco'],
                    'horario_analise': row['horario_analise'],
                    'horario_entrada_sugerido': row['horario_entrada_sugerido'],
                    'horario_saida_estimado': row['horario_saida_estimado'],
                    'estado': row['estado'],
                    'mensagem': f"Sinal {row['tipo_operacao']} com força {row['forca_sinal']}",
                    'criado_em': row['criado_em'],
                    'atualizado_em': row['atualizado_em']
                }
                sinais.append(sinal)
        
        conn.close()
        return sinais
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar sinais: {str(e)}")

@app.get("/api/sinal/{id_sinal}")
async def get_sinal_por_id(id_sinal: str):
    """Retorna um sinal específico pelo ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT dados FROM sinais WHERE id = ?", (id_sinal,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return json.loads(row['dados'])
        else:
            raise HTTPException(status_code=404, detail="Sinal não encontrado")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar sinal: {str(e)}")

@app.get("/api/estatisticas")
async def get_estatisticas():
    """Retorna estatísticas do sistema"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total de sinais
        cursor.execute("SELECT COUNT(*) as total FROM sinais")
        total_sinais = cursor.fetchone()['total']
        
        # Sinais ativos
        cursor.execute('''
        SELECT COUNT(*) as ativos FROM sinais 
        WHERE estado IN ('ATIVO', 'CONFIRMADO', 'EM_MONITORAMENTO', 'ALERTA')
        ''')
        sinais_ativos = cursor.fetchone()['ativos']
        
        # Sinais concluídos
        cursor.execute("SELECT COUNT(*) as concluidos FROM sinais WHERE estado = 'CONCLUÍDO'")
        sinais_concluidos = cursor.fetchone()['concluidos']
        
        # Sinais cancelados
        cursor.execute("SELECT COUNT(*) as cancelados FROM sinais WHERE estado = 'CANCELADO'")
        sinais_cancelados = cursor.fetchone()['cancelados']
        
        # Taxa de sucesso
        total_finalizados = sinais_concluidos + sinais_cancelados
        taxa_sucesso = (sinais_concluidos / total_finalizados * 100) if total_finalizados > 0 else 0
        
        conn.close()
        
        return {
            "total_sinais": total_sinais,
            "sinais_ativos": sinais_ativos,
            "sinais_concluidos": sinais_concluidos,
            "sinais_cancelados": sinais_cancelados,
            "taxa_sucesso": f"{taxa_sucesso:.1f}%",
            "ultima_atualizacao": datetime.now().strftime("%H:%M"),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar estatísticas: {str(e)}")

@app.get("/api/historico")
async def get_historico(
    limit: int = Query(50, ge=1, le=100, description="Número máximo de sinais"),
    offset: int = Query(0, ge=0, description="Offset para paginação")
):
    """Retorna histórico de sinais"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, dados, estado, tipo_operacao, forca_sinal, risco, probabilidade,
               horario_analise, horario_entrada_sugerido, horario_saida_estimado,
               criado_em, atualizado_em
        FROM sinais 
        ORDER BY criado_em DESC
        LIMIT ? OFFSET ?
        ''', (limit, offset))
        
        historico = []
        for row in cursor.fetchall():
            try:
                dados = json.loads(row['dados'])
                historico.append(dados)
            except:
                # Formato simplificado
                sinal = {
                    'id_sinal': row['id'],
                    'ativo': 'BTC/USDT',
                    'timeframe': '5m',
                    'status': f"{row['tipo_operacao']} ({row['forca_sinal']})",
                    'tipo_operacao': row['tipo_operacao'],
                    'probabilidade': f"{row['probabilidade']*100:.0f}%",
                    'forca_sinal': row['forca_sinal'],
                    'risco': row['risco'],
                    'horario_analise': row['horario_analise'],
                    'horario_entrada_sugerido': row['horario_entrada_sugerido'],
                    'horario_saida_estimado': row['horario_saida_estimado'],
                    'estado': row['estado'],
                    'mensagem': f"Sinal {row['tipo_operacao']}",
                    'criado_em': row['criado_em'],
                    'atualizado_em': row['atualizado_em']
                }
                historico.append(sinal)
        
        conn.close()
        return historico
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar histórico: {str(e)}")

@app.get("/api/sinais/filtrar")
async def filtrar_sinais(
    estado: str = Query(None, description="Estado para filtrar (ATIVO, CONCLUÍDO, etc)")
):
    """Filtra sinais por estado"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if estado:
            cursor.execute('''
            SELECT id, dados, estado, tipo_operacao, forca_sinal, risco, probabilidade,
                   horario_analise, horario_entrada_sugerido, horario_saida_estimado,
                   criado_em, atualizado_em
            FROM sinais 
            WHERE estado = ?
            ORDER BY criado_em DESC
            ''', (estado,))
        else:
            cursor.execute('''
            SELECT id, dados, estado, tipo_operacao, forca_sinal, risco, probabilidade,
                   horario_analise, horario_entrada_sugerido, horario_saida_estimado,
                   criado_em, atualizado_em
            FROM sinais 
            ORDER BY criado_em DESC
            ''')
        
        sinais = []
        for row in cursor.fetchall():
            try:
                dados = json.loads(row['dados'])
                sinais.append(dados)
            except:
                sinal = {
                    'id_sinal': row['id'],
                    'ativo': 'BTC/USDT',
                    'timeframe': '5m',
                    'status': f"{row['tipo_operacao']}",
                    'tipo_operacao': row['tipo_operacao'],
                    'probabilidade': f"{row['probabilidade']*100:.0f}%",
                    'forca_sinal': row['forca_sinal'],
                    'risco': row['risco'],
                    'horario_analise': row['horario_analise'],
                    'horario_entrada_sugerido': row['horario_entrada_sugerido'],
                    'horario_saida_estimado': row['horario_saida_estimado'],
                    'estado': row['estado'],
                    'mensagem': f"Sinal {row['estado']}",
                    'criado_em': row['criado_em']
                }
                sinais.append(sinal)
        
        conn.close()
        return sinais
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao filtrar sinais: {str(e)}")

@app.post("/api/analisar")
async def forcar_analise():
    """Força uma nova análise da IA"""
    try:
        from gerar_sinal import gerar_sinal_ao_vivo
        sinal = gerar_sinal_ao_vivo()
        return sinal
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao forçar análise: {str(e)}")

# Executar servidor
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Iniciando API na porta {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)