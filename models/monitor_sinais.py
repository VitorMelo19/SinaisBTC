import json
import time
import sqlite3
import os
from datetime import datetime, timedelta
from gerar_sinal import gerar_sinal_ao_vivo

class MonitorDeSinais:
    def __init__(self, db_name='sinais_ativos.db'):
        """
        Inicializa o monitor de sinais.
        
        Args:
            db_name: Nome do arquivo de banco de dados SQLite
        """
        self.db_name = db_name
        self.db_path = self._get_db_path()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.criar_tabelas()
        self.estados_validos = ['ATIVO', 'CONFIRMADO', 'EM_MONITORAMENTO', 'CONCLUÍDO', 
                               'CANCELADO', 'EXPIRADO', 'ALERTA']
    
    def _get_db_path(self):
        """Retorna o caminho completo para o banco de dados na pasta data/"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        data_dir = os.path.join(project_root, 'data')
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, self.db_name)
    
    def criar_tabelas(self):
        """Cria as tabelas necessárias no banco de dados"""
        queries = [
            '''
            CREATE TABLE IF NOT EXISTS sinais (
                id TEXT PRIMARY KEY,
                dados TEXT,
                estado TEXT,
                tipo_operacao TEXT,
                forca_sinal TEXT,
                risco TEXT,
                probabilidade REAL,
                horario_entrada_sugerido TEXT,
                horario_saida_estimado TEXT,
                criado_em TIMESTAMP,
                atualizado_em TIMESTAMP,
                duracao_min INTEGER
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS historico_monitoramento (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sinal_id TEXT,
                estado TEXT,
                mensagem TEXT,
                timestamp TIMESTAMP,
                FOREIGN KEY (sinal_id) REFERENCES sinais (id)
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS metricas_sinais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data DATE,
                total_sinais INTEGER,
                sinais_ativos INTEGER,
                sinais_concluidos INTEGER,
                sinais_cancelados INTEGER,
                taxa_sucesso REAL,
                timestamp TIMESTAMP
            )
            '''
        ]
        
        for query in queries:
            self.conn.execute(query)
        self.conn.commit()
        print(f"✅ Banco de dados inicializado: {self.db_path}")
    
    def salvar_sinal(self, sinal):
        """
        Salva um novo sinal no banco de dados.
        
        Args:
            sinal: Dicionário com dados do sinal
        """
        query = '''
        INSERT INTO sinais (id, dados, estado, tipo_operacao, forca_sinal, risco, 
                           probabilidade, horario_entrada_sugerido, horario_saida_estimado,
                           criado_em, atualizado_em, duracao_min)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        
        dados_json = json.dumps(sinal, ensure_ascii=False, default=str)
        agora = datetime.now()
        
        # Calcula duração estimada
        duracao_min = 0
        entrada = sinal.get('horario_entrada_sugerido')
        saida = sinal.get('horario_saida_estimado')
        
        if entrada and saida:
            try:
                hoje = agora.date()
                entrada_dt = datetime.strptime(f"{hoje} {entrada}", "%Y-%m-%d %H:%M")
                saida_dt = datetime.strptime(f"{hoje} {saida}", "%Y-%m-%d %H:%M")
                
                # Se a saída for antes da entrada, assume-se que é no dia seguinte
                if saida_dt < entrada_dt:
                    saida_dt += timedelta(days=1)
                
                duracao_min = int((saida_dt - entrada_dt).total_seconds() / 60)
            except:
                pass
        
        # Extrai probabilidade numérica
        probabilidade_num = 0.0
        prob_str = sinal.get('probabilidade', '0%')
        if isinstance(prob_str, str) and '%' in prob_str:
            try:
                probabilidade_num = float(prob_str.replace('%', '')) / 100
            except:
                pass
        elif isinstance(prob_str, (int, float)):
            probabilidade_num = float(prob_str)
        
        params = (
            sinal['id_sinal'],
            dados_json,
            sinal.get('estado', 'ATIVO'),
            sinal.get('tipo_operacao', 'NEUTRO'),
            sinal.get('forca_sinal', 'NULO'),
            sinal.get('risco', 'NEUTRO'),
            probabilidade_num,
            entrada,
            saida,
            agora,
            agora,
            duracao_min
        )
        
        try:
            self.conn.execute(query, params)
            self.conn.commit()
            print(f"✅ Sinal {sinal['id_sinal']} salvo no banco de dados.")
            
            # Registra no histórico
            self._registrar_historico(
                sinal['id_sinal'], 
                'CRIADO', 
                f"Sinal criado - {sinal.get('tipo_operacao')} ({sinal.get('forca_sinal')})"
            )
            return True
        except Exception as e:
            print(f"❌ Erro ao salvar sinal: {e}")
            return False
    
    def _registrar_historico(self, sinal_id, estado, mensagem):
        """Registra uma entrada no histórico de monitoramento"""
        query = '''
        INSERT INTO historico_monitoramento (sinal_id, estado, mensagem, timestamp)
        VALUES (?, ?, ?, ?)
        '''
        self.conn.execute(query, (sinal_id, estado, mensagem, datetime.now()))
        self.conn.commit()
    
    def buscar_sinais_ativos(self):
        """Retorna todos os sinais ativos (ATIVO, CONFIRMADO, EM_MONITORAMENTO)"""
        query = """
        SELECT id, dados, estado, atualizado_em 
        FROM sinais 
        WHERE estado IN ('ATIVO', 'CONFIRMADO', 'EM_MONITORAMENTO', 'ALERTA')
        ORDER BY criado_em DESC
        """
        cursor = self.conn.execute(query)
        return cursor.fetchall()
    
    def buscar_sinal_por_id(self, sinal_id):
        """Busca um sinal específico pelo ID"""
        query = "SELECT id, dados FROM sinais WHERE id = ?"
        cursor = self.conn.execute(query, (sinal_id,))
        result = cursor.fetchone()
        if result:
            return json.loads(result[1])
        return None
    
    def atualizar_sinal(self, sinal_id, novos_dados=None, novo_estado=None, mensagem=None):
        """
        Atualiza um sinal existente.
        
        Args:
            sinal_id: ID do sinal a ser atualizado
            novos_dados: Novos dados do sinal (opcional)
            novo_estado: Novo estado do sinal
            mensagem: Mensagem para o histórico (opcional)
        """
        if novos_dados is None:
            # Carrega os dados atuais
            sinal_atual = self.buscar_sinal_por_id(sinal_id)
            if sinal_atual is None:
                print(f"⚠️ Sinal {sinal_id} não encontrado para atualização.")
                return False
            
            # Atualiza apenas o estado
            sinal_atual['estado'] = novo_estado
            novos_dados = sinal_atual
        
        dados_json = json.dumps(novos_dados, ensure_ascii=False, default=str)
        agora = datetime.now()
        
        query = '''
        UPDATE sinais 
        SET dados = ?, estado = ?, atualizado_em = ?
        WHERE id = ?
        '''
        
        try:
            self.conn.execute(query, (dados_json, novo_estado, agora, sinal_id))
            self.conn.commit()
            
            # Registra no histórico
            if mensagem:
                self._registrar_historico(sinal_id, novo_estado, mensagem)
            else:
                self._registrar_historico(sinal_id, novo_estado, f"Estado atualizado para {novo_estado}")
            
            print(f"🔄 Sinal {sinal_id} atualizado: {novo_estado}")
            return True
        except Exception as e:
            print(f"❌ Erro ao atualizar sinal {sinal_id}: {e}")
            return False
    
    def monitorar_sinal(self, sinal_original):
        """
        Monitora um sinal ativo, reavaliando periodicamente.
        
        Args:
            sinal_original: Dicionário com dados do sinal
        """
        sinal_id = sinal_original['id_sinal']
        
        print(f"\n🔍 MONITORAMENTO INICIADO: {sinal_id}")
        print(f"   Tipo: {sinal_original.get('tipo_operacao')}")
        print(f"   Força: {sinal_original.get('forca_sinal')}")
        print(f"   Entrada: {sinal_original.get('horario_entrada_sugerido', 'N/A')}")
        print(f"   Saída: {sinal_original.get('horario_saida_estimado', 'N/A')}")
        
        # Valida horários
        entrada_sugerida_str = sinal_original.get('horario_entrada_sugerido')
        saida_estimada_str = sinal_original.get('horario_saida_estimado')
        
        if not entrada_sugerida_str or not saida_estimada_str:
            print("   ⚠️ Sinal sem horários definidos.")
            self.atualizar_sinal(
                sinal_id, 
                novo_estado='CANCELADO',
                mensagem="Cancelado: Sem horários definidos"
            )
            return
        
        # Converte strings para datetime
        hoje = datetime.now().date()
        try:
            entrada_sugerida = datetime.strptime(f"{hoje} {entrada_sugerida_str}", "%Y-%m-%d %H:%M")
            saida_estimada = datetime.strptime(f"{hoje} {saida_estimada_str}", "%Y-%m-%d %H:%M")
            
            # Ajusta para o dia seguinte se necessário
            if entrada_sugerida < datetime.now():
                entrada_sugerida += timedelta(days=1)
                saida_estimada += timedelta(days=1)
            
            # Garante que a saída é depois da entrada
            if saida_estimada <= entrada_sugerida:
                saida_estimada = entrada_sugerida + timedelta(minutes=30)
                
        except Exception as e:
            print(f"   ⚠️ Erro ao processar horários: {e}")
            # Usa horários padrão
            entrada_sugerida = datetime.now() + timedelta(minutes=5)
            saida_estimada = entrada_sugerida + timedelta(minutes=30)
        
        print(f"   ⏳ Entrada programada: {entrada_sugerida.strftime('%H:%M')}")
        print(f"   ⏰ Saída estimada: {saida_estimada.strftime('%H:%M')}")
        
        # Janela de confirmação (5 min antes da entrada)
        janela_confirmacao = 5
        horario_limite_confirmacao = entrada_sugerida - timedelta(minutes=janela_confirmacao)
        print(f"   🔍 Janela de confirmação: até {horario_limite_confirmacao.strftime('%H:%M')}")
        
        # Parâmetros de monitoramento
        confirmacoes_consecutivas = 0
        reavaliacoes_feitas = 0
        max_reavaliacoes = 10
        entrada_confirmada = False
        sinal_original['estado'] = 'EM_MONITORAMENTO'
        self.atualizar_sinal(sinal_id, sinal_original, 'EM_MONITORAMENTO', "Iniciando monitoramento")
        
        # Loop principal de monitoramento
        while reavaliacoes_feitas < max_reavaliacoes:
            agora = datetime.now()
            
            # FASE 1: ANTES DA ENTRADA - JANELA DE CONFIRMAÇÃO
            if not entrada_confirmada:
                if agora < horario_limite_confirmacao:
                    # Aguarda início da janela de confirmação
                    minutos_restantes = int((horario_limite_confirmacao - agora).total_seconds() / 60)
                    if minutos_restantes > 0:
                        print(f"   ⏳ Aguardando janela de confirmação: {minutos_restantes} min")
                        time.sleep(min(300, minutos_restantes * 60))  # Espera 5 min ou menos
                        reavaliacoes_feitas += 1
                        continue
                
                # Janela de confirmação ativa
                print(f"   🔍 JANELA DE CONFIRMAÇÃO ATIVA (até {entrada_sugerida.strftime('%H:%M')})")
                
                # Gera novo sinal para confirmação
                novo_sinal = gerar_sinal_ao_vivo()
                
                # Verifica se o sinal ainda é válido
                mesmo_sentido = (novo_sinal['tipo_operacao'] == sinal_original['tipo_operacao'])
                ainda_forte = novo_sinal['forca_sinal'] in ['MÉDIO', 'FORTE']
                probabilidade_alta = float(novo_sinal.get('probabilidade', '0%').replace('%', '')) > 60
                
                if mesmo_sentido and ainda_forte and probabilidade_alta:
                    print(f"   ✅ CONFIRMADO para entrada às {entrada_sugerida.strftime('%H:%M')}")
                    entrada_confirmada = True
                    
                    # Atualiza sinal com novas informações
                    sinal_original.update({
                        'estado': 'CONFIRMADO',
                        'confirmado_em': agora.strftime("%H:%M"),
                        'forca_sinal_atual': novo_sinal['forca_sinal'],
                        'risco_atual': novo_sinal['risco'],
                        'probabilidade_atual': novo_sinal['probabilidade']
                    })
                    
                    self.atualizar_sinal(
                        sinal_id, 
                        sinal_original, 
                        'CONFIRMADO',
                        f"Confirmado para entrada às {entrada_sugerida.strftime('%H:%M')}"
                    )
                    
                    # Aguarda até o horário de entrada
                    tempo_espera = (entrada_sugerida - agora).total_seconds()
                    if tempo_espera > 0:
                        print(f"   ⏳ Aguardando entrada em {int(tempo_espera/60)} min...")
                        time.sleep(min(300, tempo_espera))  # Espera no máximo 5 min
                        reavaliacoes_feitas += 1
                        continue
                    
                else:
                    motivo = []
                    if not mesmo_sentido:
                        motivo.append("sentido invertido")
                    if not ainda_forte:
                        motivo.append("força insuficiente")
                    if not probabilidade_alta:
                        motivo.append("probabilidade baixa")
                    
                    print(f"   🚫 CANCELADO ANTES DA ENTRADA: {', '.join(motivo)}")
                    
                    sinal_original.update({
                        'estado': 'CANCELADO',
                        'motivo_cancelamento': f"Sinal enfraquecido: {', '.join(motivo)}",
                        'cancelado_em': agora.strftime("%H:%M")
                    })
                    
                    self.atualizar_sinal(
                        sinal_id,
                        sinal_original,
                        'CANCELADO',
                        f"Cancelado: {', '.join(motivo)}"
                    )
                    return
            
            # FASE 2: APÓS A ENTRADA - MONITORAMENTO CONTÍNUO
            else:
                # Verifica se atingiu o horário de saída
                if agora > saida_estimada:
                    print(f"   ⏰ HORÁRIO DE SAÍDA ATINGIDO ({saida_estimada.strftime('%H:%M')})")
                    sinal_original.update({
                        'estado': 'CONCLUÍDO',
                        'conclusao': 'Período de operação encerrado',
                        'concluido_em': agora.strftime("%H:%M")
                    })
                    
                    self.atualizar_sinal(
                        sinal_id,
                        sinal_original,
                        'CONCLUÍDO',
                        "Concluído: Período de operação encerrado"
                    )
                    break
                
                # Reavalia o sinal
                novo_sinal = gerar_sinal_ao_vivo()
                mesmo_sentido = (novo_sinal['tipo_operacao'] == sinal_original['tipo_operacao'])
                
                # Verifica condições de alerta
                if not mesmo_sentido:
                    print(f"   🚨 ALERTA CRÍTICO: Sinal INVERTEU!")
                    print(f"   💡 RECOMENDAÇÃO: Considere SAIR ANTECIPADAMENTE")
                    
                    sinal_original.update({
                        'alerta_critico': 'SINAL INVERTIDO - SAIA ANTECIPADO',
                        'estado': 'ALERTA',
                        'ultimo_alerta': agora.strftime("%H:%M")
                    })
                    
                    self.atualizar_sinal(
                        sinal_id,
                        sinal_original,
                        'ALERTA',
                        "Alerta crítico: Sinal inverteu!"
                    )
                    
                elif novo_sinal['forca_sinal'] == 'BAIXO' and novo_sinal['risco'] == 'ALTO':
                    print(f"   ⚠️ Sinal enfraquecido. Risco alto.")
                    
                    sinal_original.update({
                        'probabilidade_atual': novo_sinal['probabilidade'],
                        'forca_sinal_atual': novo_sinal['forca_sinal'],
                        'risco_atual': novo_sinal['risco'],
                        'ultima_reavaliacao': agora.strftime("%H:%M")
                    })
                    
                    self.atualizar_sinal(
                        sinal_id,
                        sinal_original,
                        'CONFIRMADO',  # Mantém como confirmado mas com alerta
                        f"Reavaliado: Força {novo_sinal['forca_sinal']}, Risco {novo_sinal['risco']}"
                    )
                    
                else:
                    confirmacoes_consecutivas += 1
                    if confirmacoes_consecutivas >= 3:
                        print(f"   ✅ Sinal mantido forte ({confirmacoes_consecutivas} confirmações)")
            
            # Aguarda 5 minutos para próxima reavaliação
            reavaliacoes_feitas += 1
            if reavaliacoes_feitas < max_reavaliacoes and not (agora > saida_estimada):
                print(f"   🔄 Próxima reavaliação em 5 min... (#{reavaliacoes_feitas+1}/{max_reavaliacoes})")
                time.sleep(300)
        
        # Se chegou aqui e não foi concluído, expira
        if sinal_original['estado'] not in ['CONCLUÍDO', 'CANCELADO']:
            print("   ⏰ TEMPO MÁXIMO DE MONITORAMENTO ESGOTADO")
            sinal_original['estado'] = 'EXPIRADO'
            self.atualizar_sinal(
                sinal_id,
                sinal_original,
                'EXPIRADO',
                "Expirado: Tempo máximo de monitoramento esgotado"
            )
    
    def limpar_sinais_antigos(self, dias=7):
        """
        Remove sinais antigos do banco de dados.
        
        Args:
            dias: Número de dias para manter no histórico
        """
        limite_data = datetime.now() - timedelta(days=dias)
        
        query = """
        DELETE FROM sinais 
        WHERE criado_em < ? AND estado IN ('CONCLUÍDO', 'CANCELADO', 'EXPIRADO')
        """
        
        cursor = self.conn.execute(query, (limite_data,))
        linhas_removidas = cursor.rowcount
        
        # Limpa histórico antigo também
        query_historico = """
        DELETE FROM historico_monitoramento 
        WHERE timestamp < ?
        """
        self.conn.execute(query_historico, (limite_data,))
        
        self.conn.commit()
        
        if linhas_removidas > 0:
            print(f"🧹 Removidos {linhas_removidas} sinais antigos (mais de {dias} dias).")
        
        return linhas_removidas
    
    def gerar_relatorio(self):
        """Gera um relatório com estatísticas dos sinais"""
        queries = {
            'total_sinais': "SELECT COUNT(*) FROM sinais",
            'sinais_ativos': "SELECT COUNT(*) FROM sinais WHERE estado IN ('ATIVO', 'CONFIRMADO', 'EM_MONITORAMENTO')",
            'sinais_concluidos': "SELECT COUNT(*) FROM sinais WHERE estado = 'CONCLUÍDO'",
            'sinais_cancelados': "SELECT COUNT(*) FROM sinais WHERE estado = 'CANCELADO'",
            'media_probabilidade': "SELECT AVG(probabilidade) FROM sinais WHERE probabilidade > 0",
            'sinais_por_tipo': "SELECT tipo_operacao, COUNT(*) FROM sinais GROUP BY tipo_operacao",
            'sinais_por_forca': "SELECT forca_sinal, COUNT(*) FROM sinais GROUP BY forca_sinal"
        }
        
        relatorio = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'estatisticas': {}
        }
        
        for nome, query in queries.items():
            cursor = self.conn.execute(query)
            resultado = cursor.fetchone()
            relatorio['estatisticas'][nome] = resultado[0] if resultado else 0
        
        # Calcula taxa de "sucesso" (sinais concluídos vs cancelados)
        total_concluidos = relatorio['estatisticas']['sinais_concluidos']
        total_cancelados = relatorio['estatisticas']['sinais_cancelados']
        total_finalizados = total_concluidos + total_cancelados
        
        if total_finalizados > 0:
            taxa_sucesso = total_concluidos / total_finalizados
        else:
            taxa_sucesso = 0
        
        relatorio['estatisticas']['taxa_sucesso'] = f"{taxa_sucesso:.1%}"
        
        # Salva relatório em arquivo
        data_dir = os.path.dirname(self.db_path)
        relatorio_path = os.path.join(data_dir, 'relatorio_sinais.json')
        
        with open(relatorio_path, 'w') as f:
            json.dump(relatorio, f, indent=2, default=str)
        
        print(f"📊 Relatório salvo em: {relatorio_path}")
        
        # Exibe resumo
        print(f"\n📈 RESUMO DE SINAIS:")
        print(f"   Total de sinais: {relatorio['estatisticas']['total_sinais']}")
        print(f"   Sinais ativos: {relatorio['estatisticas']['sinais_ativos']}")
        print(f"   Sinais concluídos: {relatorio['estatisticas']['sinais_concluidos']}")
        print(f"   Sinais cancelados: {relatorio['estatisticas']['sinais_cancelados']}")
        print(f"   Taxa de conclusão: {relatorio['estatisticas']['taxa_sucesso']}")
        
        return relatorio
    
    def iniciar_monitoramento_contínuo(self, intervalo_minutos=5):
        """
        Inicia o monitoramento contínuo de sinais.
        
        Args:
            intervalo_minutos: Intervalo entre análises (padrão: 5 minutos)
        """
        print("=" * 60)
        print("🤖 SISTEMA DE MONITORAMENTO DE SINAIS - INICIADO")
        print(f"📊 Banco de dados: {self.db_path}")
        print("=" * 60)
        
        # Limpa sinais antigos no início
        self.limpar_sinais_antigos()
        
        try:
            ciclo = 0
            while True:
                ciclo += 1
                print(f"\n{'=' * 50}")
                print(f"📈 CICLO {ciclo} - {datetime.now().strftime('%H:%M:%S')}")
                print(f"{'=' * 50}")
                
                # 1. Gera novo sinal
                print("🔍 Analisando mercado...")
                novo_sinal = gerar_sinal_ao_vivo()
                
                # Exibe informações principais
                print(f"\n📊 NOVO SINAL GERADO:")
                print(f"   Status: {novo_sinal.get('status')}")
                print(f"   Força: {novo_sinal.get('forca_sinal')}")
                print(f"   Risco: {novo_sinal.get('risco')}")
                print(f"   Probabilidade: {novo_sinal.get('probabilidade')}")
                
                # 2. Verifica se é um sinal válido para monitoramento
                if (novo_sinal['estado'] == 'ATIVO' and 
                    novo_sinal['forca_sinal'] in ['MÉDIO', 'FORTE'] and
                    novo_sinal.get('horario_entrada_sugerido')):
                    
                    print(f"\n🎯 SINAL VÁLIDO DETECTADO - Iniciando monitoramento...")
                    self.salvar_sinal(novo_sinal)
                    
                    # Inicia monitoramento em uma thread separada (simplificado)
                    # Na prática, você poderia usar threading aqui
                    self.monitorar_sinal(novo_sinal)
                else:
                    print(f"\n⏭️  Sinal não atendendo critérios para monitoramento.")
                
                # 3. Verifica sinais ativos existentes
                sinais_ativos = self.buscar_sinais_ativos()
                if sinais_ativos:
                    print(f"\n👁️  SINAIS EM MONITORAMENTO ATIVO: {len(sinais_ativos)}")
                    
                    for id_sinal, dados_json, estado, atualizado_em_str in sinais_ativos:
                        sinal = json.loads(dados_json)
                        
                        # Converte string para datetime
                        try:
                            if isinstance(atualizado_em_str, str):
                                atualizado_em = datetime.strptime(atualizado_em_str, '%Y-%m-%d %H:%M:%S')
                            else:
                                atualizado_em = datetime.now() - timedelta(minutes=15)
                        except:
                            atualizado_em = datetime.now() - timedelta(minutes=15)
                        
                        # Reavalia se não foi atualizado nos últimos 10 minutos
                        if (datetime.now() - atualizado_em).total_seconds() > 600:
                            print(f"   🔄 Reavaliando sinal: {id_sinal}")
                            self.monitorar_sinal(sinal)
                
                # 4. Gera relatório periódico a cada 10 ciclos
                if ciclo % 10 == 0:
                    self.gerar_relatorio()
                    self.limpar_sinais_antigos()
                
                # 5. Aguarda próximo ciclo
                print(f"\n⏱️  PRÓXIMA ANÁLISE EM {intervalo_minutos} MINUTOS...")
                print(f"{'=' * 60}")
                time.sleep(intervalo_minutos * 60)
                
        except KeyboardInterrupt:
            print("\n\n👋 MONITORAMENTO INTERROMPIDO PELO USUÁRIO")
        except Exception as e:
            print(f"\n❌ ERRO NO MONITORAMENTO: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.conn.close()
            print("🔒 Conexão com banco de dados fechada.")

    def fechar(self):
        """Fecha a conexão com o banco de dados"""
        self.conn.close()
        print("🔒 Conexão com banco de dados fechada.")


if __name__ == "__main__":
    # Testa o monitor
    monitor = MonitorDeSinais()
    
    try:
        # Gera um relatório inicial
        monitor.gerar_relatorio()
        
        # Inicia monitoramento contínuo
        monitor.iniciar_monitoramento_contínuo(intervalo_minutos=5)
    finally:
        monitor.fechar()