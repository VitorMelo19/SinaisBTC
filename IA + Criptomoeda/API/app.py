import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class SinalGenerator:
    """Gerador de sinais (versão simplificada para Render)"""
    
    def __init__(self):
        self.ativos = ["BTC/USDT", "ETH/USDT", "ADA/USDT", "SOL/USDT", "XRP/USDT"]
        self.timeframes = ["5m", "15m", "1h", "4h"]
        self.status_options = ["COMPRAR", "VENDER", "AGUARDAR"]
        self.forca_options = ["FORTE", "MÉDIO", "BAIXO"]
        self.risco_options = ["ALTO", "MÉDIO", "BAIXO"]
        
    def gerar_sinal(self) -> Dict:
        """Gera um sinal simulado"""
        agora = datetime.now()
        ativo = random.choice(self.ativos)
        
        # Lógica básica de mercado (simulada)
        hora = agora.hour
        if 9 <= hora <= 17:  # Horário de mercado ativo
            status = "COMPRAR" if random.random() > 0.4 else "VENDER"
            forca = "FORTE" if random.random() > 0.3 else "MÉDIO"
            prob = random.randint(70, 95)
        else:  # Horário menos ativo
            status = "AGUARDAR" if random.random() > 0.5 else random.choice(["COMPRAR", "VENDER"])
            forca = "BAIXO" if status == "AGUARDAR" else random.choice(["MÉDIO", "BAIXO"])
            prob = random.randint(50, 75)
        
        # Risco baseado na força
        risco = "ALTO" if forca == "BAIXO" else "MÉDIO" if forca == "MÉDIO" else "BAIXO"
        
        # Horários
        entrada = agora + timedelta(minutes=random.randint(2, 10))
        saida = entrada + timedelta(minutes=random.randint(15, 60))
        
        return {
            "id_sinal": f"SINAL_{agora.strftime('%Y%m%d_%H%M%S')}",
            "ativo": ativo,
            "timeframe": random.choice(self.timeframes),
            "status": status,
            "tipo_operacao": "COMPRA" if status == "COMPRAR" else "VENDA" if status == "VENDER" else "NEUTRO",
            "probabilidade": f"{prob}%",
            "forca_sinal": forca,
            "risco": risco,
            "horario_analise": agora.strftime("%H:%M"),
            "estado": "ATIVO" if status != "AGUARDAR" else "INATIVO",
            "horario_entrada_sugerido": entrada.strftime("%H:%M"),
            "horario_saida_estimado": saida.strftime("%H:%M"),
            "volatilidade_atual": f"{random.uniform(0.5, 3.0):.1f}%",
            "info_previsao": "IA analisando em tempo real",
            "mensagem": self._get_mensagem(status, forca, prob)
        }
    
    def _get_mensagem(self, status: str, forca: str, prob: int) -> str:
        """Gera mensagem descritiva"""
        if status == "COMPRAR":
            if forca == "FORTE":
                return f"📈 Forte oportunidade de compra ({prob}% confiança). Tendência de alta confirmada."
            elif forca == "MÉDIO":
                return f"📈 Boa oportunidade de compra ({prob}% confiança). Análise técnica favorável."
            else:
                return f"⚠️ Possibilidade de compra ({prob}% confiança). Aguarde confirmação."
        
        elif status == "VENDER":
            if forca == "FORTE":
                return f"📉 Forte oportunidade de venda ({prob}% confiança). Tendência de baixa confirmada."
            elif forca == "MÉDIO":
                return f"📉 Boa oportunidade de venda ({prob}% confiança). Análise técnica favorável."
            else:
                return f"⚠️ Possibilidade de venda ({prob}% confiança). Aguarde confirmação."
        
        else:
            return "⚪ Mercado lateral. Aguarde melhor oportunidade."

# Instância global
gerador = SinalGenerator()