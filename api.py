import sys
import os

# === CORREÇÃO DO PATH ===
# Obtém o diretório atual deste arquivo (api.py)
current_dir = os.path.dirname(os.path.abspath(__file__))

# Sobe um nível para a raiz do projeto (onde está a pasta models)
project_root = os.path.dirname(current_dir)

# Adiciona a raiz ao sys.path
sys.path.insert(0, project_root)

print(f"📍 Diretório atual: {current_dir}")
print(f"📍 Raiz do projeto: {project_root}")
print(f"📍 sys.path: {sys.path}")

# === AGORA TENTA IMPORTAR ===
try:
    from models.gerar_sinal import gerar_sinal_ao_vivo
    print("✅ Módulo 'models.gerar_sinal' importado com sucesso!")
    
except ImportError as e:
    print(f"⚠️ Erro ao importar módulo: {e}")
    print("⚠️ Usando função simulada...")
    
    # Função de fallback
    def gerar_sinal_ao_vivo():
        from datetime import datetime
        return {
            "id_sinal": f"SINAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "ativo": "BTC/USDT",
            "timeframe": "5m",
            "status": "COMPRAR",
            "probabilidade": "85%",
            "forca_sinal": "FORTE",
            "risco": "ALTO",
            "horario_analise": datetime.now().strftime("%H:%M"),
            "estado": "ATIVO",
            "mensagem": "Modo de fallback - Módulo não encontrado"
        }

import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Importa o gerador de sinais
from app import gerador

# ==================== CONFIGURAÇÃO ====================
IS_RENDER = os.environ.get('RENDER', False)
PORT = int(os.environ.get('PORT', 8000))

# ==================== MODELOS PYDANTIC ====================
class Sinal(BaseModel):
    id_sinal: str
    ativo: str
    timeframe: str
    status: str
    tipo_operacao: str
    probabilidade: str
    forca_sinal: str
    risco: str
    horario_analise: str
    estado: str
    horario_entrada_sugerido: Optional[str] = None
    horario_saida_estimado: Optional[str] = None
    volatilidade_atual: Optional[str] = None
    info_previsao: Optional[str] = None
    mensagem: Optional[str] = None

class Configuracao(BaseModel):
    limiar_compra: float = 0.65
    limiar_venda: float = 0.35
    ativo_principal: str = "BTC/USDT"

# ==================== BANCO DE DADOS ====================
def init_db():
    """Inicializa o banco de dados SQLite"""
    conn = sqlite3.connect('sinais.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Tabela de sinais
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sinais (
            id TEXT PRIMARY KEY,
            dados TEXT,
            estado TEXT,
            criado_em TIMESTAMP,
            atualizado_em TIMESTAMP
        )
    ''')
    
    # Tabela de histórico
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id TEXT PRIMARY KEY,
            dados TEXT,
            resultado TEXT,
            criado_em TIMESTAMP
        )
    ''')
    
    conn.commit()
    return conn

# ==================== LIFECYCLE ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação"""
    print("🚀 Iniciando API Sinais BTC...")
    
    # Inicializa banco de dados
    global db_conn
    db_conn = init_db()
    print("✅ Banco de dados inicializado")
    
    if IS_RENDER:
        print("🌐 Ambiente: Render.com")
    else:
        print("💻 Ambiente: Local")
    
    print(f"📡 API rodando na porta: {PORT}")
    print("=" * 50)
    
    yield
    
    # Cleanup
    if db_conn:
        db_conn.close()
        print("🔴 API encerrada")

# ==================== APP FASTAPI ====================
app = FastAPI(
    title="API Sinais BTC - IA Trading",
    description="API para fornecer sinais de trading gerados por IA",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== ENDPOINTS ====================
@app.get("/")
async def root():
    """Endpoint raiz"""
    return {
        "api": "Sinais BTC - IA Trading",
        "versao": "1.0.0",
        "status": "online",
        "ambiente": "render" if IS_RENDER else "local",
        "documentacao": "/docs",
        "hora_servidor": datetime.now().strftime("%H:%M:%S")
    }

@app.get("/status")
async def status():
    """Status do sistema"""
    cursor = db_conn.cursor()
    
    # Conta sinais ativos
    cursor.execute("SELECT COUNT(*) FROM sinais WHERE estado = 'ATIVO'")
    ativos = cursor.fetchone()[0]
    
    # Conta sinais hoje
    hoje = datetime.now().date()
    cursor.execute("SELECT COUNT(*) FROM sinais WHERE DATE(criado_em) = ?", (hoje,))
    hoje_total = cursor.fetchone()[0]
    
    return {
        "sistema": "operacional",
        "sinais_ativos": ativos,
        "sinais_hoje": hoje_total,
        "ultima_atualizacao": datetime.now().strftime("%H:%M:%S"),
        "proxima_analise": (datetime.now() + timedelta(minutes=1)).strftime("%H:%M")
    }

@app.get("/sinal/atual", response_model=Sinal)
async def sinal_atual(background_tasks: BackgroundTasks):
    """Gera um novo sinal"""
    try:
        # Gera sinal
        sinal_data = gerador.gerar_sinal()
        
        # Salva no banco se for ATIVO
        if sinal_data["estado"] == "ATIVO":
            cursor = db_conn.cursor()
            
            # Remove sinal antigo do mesmo ID se existir
            cursor.execute("DELETE FROM sinais WHERE id = ?", (sinal_data["id_sinal"],))
            
            # Insere novo
            cursor.execute(
                "INSERT INTO sinais (id, dados, estado, criado_em, atualizado_em) VALUES (?, ?, ?, ?, ?)",
                (
                    sinal_data["id_sinal"],
                    json.dumps(sinal_data, ensure_ascii=False),
                    sinal_data["estado"],
                    datetime.now(),
                    datetime.now()
                )
            )
            db_conn.commit()
        
        return sinal_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar sinal: {str(e)}")

@app.get("/sinal/{id_sinal}", response_model=Sinal)
async def obter_sinal(id_sinal: str):
    """Busca sinal por ID"""
    cursor = db_conn.cursor()
    cursor.execute("SELECT dados FROM sinais WHERE id = ?", (id_sinal,))
    resultado = cursor.fetchone()
    
    if not resultado:
        raise HTTPException(status_code=404, detail="Sinal não encontrado")
    
    return json.loads(resultado[0])

@app.get("/sinais/ativos", response_model=List[Sinal])
async def sinais_ativos(limite: int = 10):
    """Lista sinais ativos"""
    cursor = db_conn.cursor()
    cursor.execute("""
        SELECT dados FROM sinais 
        WHERE estado = 'ATIVO' 
        ORDER BY criado_em DESC 
        LIMIT ?
    """, (limite,))
    
    resultados = cursor.fetchall()
    return [json.loads(r[0]) for r in resultados]

@app.get("/sinais/hoje", response_model=List[Sinal])
async def sinais_hoje():
    """Lista todos os sinais de hoje"""
    hoje = datetime.now().date()
    cursor = db_conn.cursor()
    cursor.execute("""
        SELECT dados FROM sinais 
        WHERE DATE(criado_em) = ?
        ORDER BY criado_em DESC
    """, (hoje,))
    
    resultados = cursor.fetchall()
    return [json.loads(r[0]) for r in resultados]

@app.post("/sinal/{id_sinal}/finalizar")
async def finalizar_sinal(id_sinal: str, resultado: str = "CONCLUÍDO"):
    """Marca um sinal como finalizado"""
    cursor = db_conn.cursor()
    
    # Busca sinal
    cursor.execute("SELECT dados FROM sinais WHERE id = ?", (id_sinal,))
    sinal = cursor.fetchone()
    
    if not sinal:
        raise HTTPException(status_code=404, detail="Sinal não encontrado")
    
    sinal_data = json.loads(sinal[0])
    sinal_data["estado"] = resultado
    sinal_data["finalizado_em"] = datetime.now().strftime("%H:%M")
    
    # Move para histórico
    cursor.execute("""
        INSERT INTO historico (id, dados, resultado, criado_em)
        VALUES (?, ?, ?, ?)
    """, (id_sinal, json.dumps(sinal_data), resultado, datetime.now()))
    
    # Remove dos ativos
    cursor.execute("DELETE FROM sinais WHERE id = ?", (id_sinal,))
    
    db_conn.commit()
    
    return {"mensagem": f"Sinal {id_sinal} finalizado como {resultado}"}

@app.get("/historico", response_model=List[Sinal])
async def historico(dias: int = 7):
    """Busca histórico de sinais"""
    data_limite = datetime.now() - timedelta(days=dias)
    
    cursor = db_conn.cursor()
    cursor.execute("""
        SELECT dados FROM historico 
        WHERE criado_em >= ?
        ORDER BY criado_em DESC
    """, (data_limite,))
    
    resultados = cursor.fetchall()
    return [json.loads(r[0]) for r in resultados]

@app.post("/configurar")
async def configurar(config: Configuracao):
    """Salva configurações"""
    # Aqui você poderia salvar em um arquivo ou banco
    config_data = config.dict()
    
    # Simples: salva em um arquivo JSON
    with open('config.json', 'w') as f:
        json.dump(config_data, f, indent=2)
    
    return {
        "mensagem": "Configurações salvas",
        "config": config_data
    }

# ==================== ENDPOINTS PARA APP ANDROID ====================
@app.get("/app/sinais")
async def app_sinais():
    """Endpoint otimizado para o app Android"""
    try:
        # Gera sinal atual
        sinal_atual_data = gerador.gerar_sinal()
        
        # Busca sinais ativos
        cursor = db_conn.cursor()
        cursor.execute("SELECT dados FROM sinais WHERE estado = 'ATIVO' ORDER BY criado_em DESC LIMIT 5")
        ativos = [json.loads(r[0]) for r in cursor.fetchall()]
        
        return {
            "sinal_atual": sinal_atual_data,
            "sinais_ativos": ativos,
            "timestamp": datetime.now().isoformat(),
            "status": "success"
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "sinal_atual": gerador.gerar_sinal(),  # Fallback
                "sinais_ativos": []
            }
        )

# ==================== WEBHOOK TESTE ====================
@app.post("/webhook/teste")
async def webhook_teste(payload: dict):
    """Teste de webhook"""
    print(f"📨 Webhook recebido: {payload}")
    
    # Você pode processar o payload aqui
    # Exemplo: notificar quando um sinal forte for gerado
    
    return {
        "status": "recebido",
        "timestamp": datetime.now().isoformat(),
        "data": payload
    }

# ==================== INICIAR SERVIDOR ====================
if __name__ == "__main__":
    import uvicorn
    print(f"🌍 Iniciando servidor na porta {PORT}")
    print(f"📚 Documentação: http://localhost:{PORT}/docs")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )