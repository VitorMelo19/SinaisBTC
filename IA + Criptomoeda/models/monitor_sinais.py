import json
import time
import sqlite3
from datetime import datetime, timedelta
from gerar_sinal import gerar_sinal_ao_vivo

class MonitorDeSinais:
    def __init__(self):
        self.conn = sqlite3.connect('sinais_ativos.db', check_same_thread=False)
        self.criar_tabela()
        
    def criar_tabela(self):
        query = '''
        CREATE TABLE IF NOT EXISTS sinais (
            id TEXT PRIMARY KEY,
            dados TEXT,
            estado TEXT,
            criado_em TIMESTAMP,
            atualizado_em TIMESTAMP
        )
        '''
        self.conn.execute(query)
        self.conn.commit()
    
    def salvar_sinal(self, sinal):
        query = '''
        INSERT INTO sinais (id, dados, estado, criado_em, atualizado_em)
        VALUES (?, ?, ?, ?, ?)
        '''
        dados_json = json.dumps(sinal, ensure_ascii=False)
        agora = datetime.now()
        
        self.conn.execute(query, (
            sinal['id_sinal'],
            dados_json,
            sinal['estado'],
            agora,
            agora
        ))
        self.conn.commit()
        print(f"✅ Sinal {sinal['id_sinal']} salvo.")
    
    def buscar_sinais_ativos(self):
        query = "SELECT id, dados FROM sinais WHERE estado = 'ATIVO'"
        cursor = self.conn.execute(query)
        return cursor.fetchall()
    
    def atualizar_sinal(self, id_sinal, novos_dados, novo_estado):
        query = '''
        UPDATE sinais 
        SET dados = ?, estado = ?, atualizado_em = ?
        WHERE id = ?
        '''
        dados_json = json.dumps(novos_dados, ensure_ascii=False)
        agora = datetime.now()
        
        self.conn.execute(query, (dados_json, novo_estado, agora, id_sinal))
        self.conn.commit()
        print(f"🔄 Sinal {id_sinal} atualizado: {novo_estado}")
    
    def monitorar_sinal(self, sinal_original):
        sinal_id = sinal_original['id_sinal']
        print(f"\n🔍 MONITORAMENTO INICIADO: {sinal_id}")
        print(f"   Entrada: {sinal_original.get('horario_entrada_sugerido', 'N/A')}")
        print(f"   Saída: {sinal_original.get('horario_saida_estimado', 'N/A')}")
        
        entrada_sugerida_str = sinal_original.get('horario_entrada_sugerido')
        saida_estimada_str = sinal_original.get('horario_saida_estimado')
        
        if not entrada_sugerida_str or not saida_estimada_str:
            print("   ⚠️ Sinal sem horários definidos.")
            self.atualizar_sinal(sinal_id, sinal_original, 'CANCELADO')
            return
        
        hoje = datetime.now().date()
        entrada_sugerida = datetime.strptime(f"{hoje} {entrada_sugerida_str}", "%Y-%m-%d %H:%M")
        saida_estimada = datetime.strptime(f"{hoje} {saida_estimada_str}", "%Y-%m-%d %H:%M")
        
        # JANELA DE CONFIRMAÇÃO (5 min antes da entrada)
        janela_confirmacao = 5
        horario_limite_confirmacao = entrada_sugerida - timedelta(minutes=janela_confirmacao)
        print(f"   ⏳ Janela de confirmação: até {horario_limite_confirmacao.strftime('%H:%M')}")
        
        confirmacoes_consecutivas = 0
        reavaliacoes_feitas = 0
        max_reavaliacoes = 8
        entrada_confirmada = False
        
        while reavaliacoes_feitas < max_reavaliacoes:
            agora = datetime.now()
            
            # FASE 1: ANTES DA ENTRADA - JANELA DE CONFIRMAÇÃO
            if not entrada_confirmada:
                if agora < horario_limite_confirmacao:
                    minutos_restantes = int((horario_limite_confirmacao - agora).total_seconds() / 60)
                    if minutos_restantes > 0:
                        print(f"   ⏳ Aguardando janela de confirmação: {minutos_restantes} min")
                elif agora >= horario_limite_confirmacao and agora < entrada_sugerida:
                    print(f"   🔍 JANELA DE CONFIRMAÇÃO ATIVA (até {entrada_sugerida.strftime('%H:%M')})")
                    
                    novo_sinal = gerar_sinal_ao_vivo()
                    mesmo_sentido = (novo_sinal['tipo_operacao'] == sinal_original['tipo_operacao'])
                    ainda_forte = novo_sinal['forca_sinal'] in ['MÉDIO', 'FORTE']
                    
                    if mesmo_sentido and ainda_forte:
                        print(f"   ✅ CONFIRMADO para entrada às {entrada_sugerida.strftime('%H:%M')}")
                        entrada_confirmada = True
                        sinal_original['estado'] = 'CONFIRMADO'
                        sinal_original['confirmado_em'] = agora.strftime("%H:%M")
                        self.atualizar_sinal(sinal_id, sinal_original, 'CONFIRMADO')
                        
                        tempo_espera = (entrada_sugerida - agora).total_seconds()
                        if tempo_espera > 0:
                            print(f"   ⏳ Aguardando entrada em {int(tempo_espera/60)} min...")
                            time.sleep(tempo_espera)
                        continue
                    else:
                        print(f"   🚫 CANCELADO ANTES DA ENTRADA: Sinal perdeu força")
                        sinal_original['estado'] = 'CANCELADO'
                        sinal_original['motivo_cancelamento'] = 'Enfraquecido na janela de confirmação'
                        sinal_original['cancelado_em'] = agora.strftime("%H:%M")
                        self.atualizar_sinal(sinal_id, sinal_original, 'CANCELADO')
                        return
            
            # FASE 2: APÓS A ENTRADA - MONITORAMENTO CONTÍNUO
            else:
                if agora > saida_estimada:
                    print(f"   ⏰ HORÁRIO DE SAÍDA ATINGIDO ({saida_estimada_str})")
                    sinal_original['estado'] = 'CONCLUÍDO'
                    sinal_original['conclusao'] = 'Período de operação encerrado'
                    self.atualizar_sinal(sinal_id, sinal_original, 'CONCLUÍDO')
                    break
                
                novo_sinal = gerar_sinal_ao_vivo()
                mesmo_sentido = (novo_sinal['tipo_operacao'] == sinal_original['tipo_operacao'])
                
                if not mesmo_sentido:
                    print(f"   🚨 ALERTA CRÍTICO: Sinal INVERTEU!")
                    print(f"   💡 RECOMENDAÇÃO: Considere SAIR ANTECIPADAMENTE")
                    sinal_original['alerta_critico'] = 'SINAL INVERTIDO - SAIA ANTECIPADO'
                    sinal_original['estado'] = 'ALERTA'
                    self.atualizar_sinal(sinal_id, sinal_original, 'ALERTA')
                elif novo_sinal['forca_sinal'] == 'BAIXO' and novo_sinal['risco'] == 'ALTO':
                    print(f"   ⚠️ Sinal enfraquecido. Risco alto.")
                    sinal_original.update({
                        'probabilidade': novo_sinal['probabilidade'],
                        'forca_sinal': novo_sinal['forca_sinal'],
                        'risco': novo_sinal['risco'],
                        'ultima_reavaliacao': agora.strftime("%H:%M")
                    })
                    self.atualizar_sinal(sinal_id, sinal_original, 'CONFIRMADO')
                else:
                    confirmacoes_consecutivas += 1
                    if confirmacoes_consecutivas >= 3:
                        print(f"   ✅ Sinal mantido forte ({confirmacoes_consecutivas} confirmações)")
            
            # Aguarda 5 minutos para próxima reavaliação
            reavaliacoes_feitas += 1
            if reavaliacoes_feitas < max_reavaliacoes and not (agora > saida_estimada):
                print(f"   🔄 Próxima reavaliação em 5 min... (#{reavaliacoes_feitas+1}/{max_reavaliacoes})")
                time.sleep(300)
        
        if sinal_original['estado'] == 'ATIVO':
            print("   ⏰ TEMPO MÁXIMO DE MONITORAMENTO ESGOTADO")
            sinal_original['estado'] = 'EXPIRADO'
            self.atualizar_sinal(sinal_id, sinal_original, 'EXPIRADO')
    
    def iniciar_monitoramento_contínuo(self):
        print("=" * 60)
        print("🤖 SISTEMA DE MONITORAMENTO DE SINAIS - INICIADO")
        print("=" * 60)
        
        try:
            while True:
                print("\n" + "=" * 50)
                print(f"📈 GERANDO NOVO SINAL - {datetime.now().strftime('%H:%M:%S')}")
                print("=" * 50)
                
                novo_sinal = gerar_sinal_ao_vivo()
                
                for chave, valor in novo_sinal.items():
                    if chave not in ['id_sinal', 'estado']:
                        print(f"{chave.upper()}: {valor}")
                
                if novo_sinal['estado'] == 'ATIVO' and novo_sinal['forca_sinal'] in ['MÉDIO', 'FORTE']:
                    self.salvar_sinal(novo_sinal)
                    self.monitorar_sinal(novo_sinal)
                
                sinais_ativos = self.buscar_sinais_ativos()
                if sinais_ativos:
                    print(f"\n👁️  SINAIS ATIVOS: {len(sinais_ativos)}")
                    for id_sinal, dados_json in sinais_ativos:
                        sinal = json.loads(dados_json)
                        atualizado_em_str = sinal.get('atualizado_em')
                        if atualizado_em_str:
                            atualizado_em = datetime.strptime(atualizado_em_str, '%Y-%m-%d %H:%M:%S')
                        else:
                            atualizado_em = datetime.now() - timedelta(minutes=15)
                        
                        if (datetime.now() - atualizado_em).total_seconds() > 600:
                            print(f"   🔄 Reavaliando sinal antigo: {id_sinal}")
                            self.monitorar_sinal(sinal)
                
                print(f"\n⏱️  PRÓXIMA ANÁLISE EM 5 MINUTOS...")
                print("=" * 60)
                time.sleep(300)
                
        except KeyboardInterrupt:
            print("\n\n👋 MONITORAMENTO INTERROMPIDO")
            self.conn.close()

if __name__ == "__main__":
    monitor = MonitorDeSinais()
    monitor.iniciar_monitoramento_contínuo()