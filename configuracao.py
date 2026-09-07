# Constantes de rede e de tempo, e leitura do catalogo estatico de nos (nos.json).

import json

# Grupo multicast unico, usado para chat e para controle.
# Faixa multicast IPv4: 224.0.0.0 a 239.255.255.255.
GRUPO_MULTICAST = "224.1.1.1"
PORTA_GRUPO = 5007
TTL_MULTICAST = 1  # 1 = nao sai da maquina local

# Tempos, em segundos.
INTERVALO_HEARTBEAT = 2.0   # cada no anuncia que esta vivo neste intervalo
T_FALHA = 6.0               # sem heartbeat por mais que isso => no considerado caido
T_RETRANSMISSAO = 1.0       # espera antes de pedir retransmissao de algo que faltou
ATRASO_ENVIO = 0.0          # atraso artificial no envio; > 0 ajuda a ver canal nao-vazio no snapshot

TAMANHO_HISTORICO = 300     # quantas mensagens cada no guarda para poder retransmitir


class Config:
    # Catalogo lido uma vez na inicializacao. Nao e canal de coordenacao.

    def __init__(self, caminho):
        with open(caminho, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        self.grupo_multicast = dados.get("grupo_multicast", GRUPO_MULTICAST)
        self.porta_grupo = dados.get("porta_grupo", PORTA_GRUPO)
        self.ids = sorted(no["id"] for no in dados["nos"])
        self.total_nos = len(self.ids)
