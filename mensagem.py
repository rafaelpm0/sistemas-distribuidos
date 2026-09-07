# Tipos de mensagem e serializacao JSON dos datagramas multicast.

import json

# Mensagens de chat / ordem total
CHAT_PEDIDO = "CHAT_PEDIDO"    # autor -> lider: sequencie esta mensagem
CHAT_ENTREGA = "CHAT_ENTREGA"  # lider -> todos: mensagem ja com num_seq global

# Controle
HEARTBEAT = "HEARTBEAT"        # cada no -> todos: continuo vivo
ELEICAO = "ELEICAO"            # no -> proximo no ativo do anel
COORDENADOR = "COORDENADOR"    # novo lider -> todos: quem venceu a eleicao
RETRANSMITIR = "RETRANSMITIR"  # no -> lider ou origem: reenvie o que faltou

# Estado global (Chandy-Lamport)
MARCADOR = "MARCADOR"
RESULTADO_SNAPSHOT = "RESULTADO_SNAPSHOT"

TODOS = "todos"


def montar(tipo, origem, destino=TODOS, **campos):
    # Monta o dicionario base de uma mensagem; os campos extras entram direto.
    mensagem = {"tipo": tipo, "origem": origem, "destino": destino}
    mensagem.update(campos)
    return mensagem


def serializar(mensagem):
    return json.dumps(mensagem).encode("utf-8")


def desserializar(dados):
    return json.loads(dados.decode("utf-8"))
