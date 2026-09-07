# Estado global pelo algoritmo de Chandy-Lamport, sobre o multicast.
#
# Canal logico j -> i = as mensagens de chat que o no i recebe do no j
# (identificadas pelo campo "origem"). A ordem FIFO do canal e reconstruida
# pelo seq_origem.

import time

from mensagem import MARCADOR, RESULTADO_SNAPSHOT, TODOS, montar


class Snapshot:

    def __init__(self, nucleo):
        self.nucleo = nucleo
        self.id_snapshot_atual = None
        self.concluido = False
        self.estado_local = None
        self.gravando = {}    # origem_id -> lista de mensagens (canal ainda aberto)
        self.canais = {}      # origem_id -> lista de mensagens (canal ja fechado)
        self.resultados = {}  # id_no -> {"estado_local":..., "canais":...}

    # ---------------------------------------------------------------- iniciador

    def iniciar(self):
        # Registra o proprio estado e difunde um MARCADOR por todos os canais de saida.
        id_snapshot = f"{self.nucleo.meu_id}-{int(time.time())}"
        self._registrar_estado(id_snapshot, canal_de_entrada=None)
        self.nucleo.registrar_log(f"snapshot {id_snapshot} iniciado por mim")
        self.nucleo.enviar_rede(montar(
            MARCADOR, origem=self.nucleo.meu_id, destino=TODOS,
            payload={"id_snapshot": id_snapshot, "iniciador": self.nucleo.meu_id},
        ))

    # ----------------------------------------------------------------- marcador

    def ao_receber_marcador(self, mensagem):
        origem = int(mensagem["origem"])
        if origem == self.nucleo.meu_id:
            return
        id_snapshot = mensagem["payload"]["id_snapshot"]

        if id_snapshot != self.id_snapshot_atual:
            # Primeiro marcador deste snapshot: registra estado e propaga o marcador.
            self._registrar_estado(id_snapshot, canal_de_entrada=origem)
            self.nucleo.registrar_log(f"snapshot {id_snapshot}: registrei meu estado")
            self.nucleo.enviar_rede(montar(
                MARCADOR, origem=self.nucleo.meu_id, destino=TODOS,
                payload=mensagem["payload"],
            ))
        else:
            # Marcador seguinte: fecha o canal por onde ele chegou.
            if origem in self.gravando:
                self.canais[origem] = self.gravando.pop(origem)
            else:
                self.canais.setdefault(origem, [])

        self._talvez_concluir()

    def ao_receber_mensagem_app(self, mensagem):
        # Toda CHAT_ENTREGA recebida enquanto um canal esta aberto entra no estado do canal.
        if self.id_snapshot_atual is None or self.concluido:
            return
        origem = int(mensagem["origem"])
        if origem in self.gravando:
            self.gravando[origem].append(_resumo(mensagem))

    # ----------------------------------------------------------------- resultado

    def ao_receber_resultado(self, mensagem):
        if mensagem["payload"]["id_snapshot"] != self.id_snapshot_atual:
            return
        self.resultados[int(mensagem["origem"])] = mensagem["payload"]["resultado"]
        self._talvez_montar_fotografia()

    # ------------------------------------------------------------------ interno

    def _registrar_estado(self, id_snapshot, canal_de_entrada):
        self.id_snapshot_atual = id_snapshot
        self.concluido = False
        self.estado_local = {
            "num_seq_entregue": self.nucleo.ordem.proximo_num_seq_esperado - 1,
            "relogio_vetorial": self.nucleo.relogio.copia(),
            "lider": self.nucleo.eleicao.lider_atual,
            "pendentes": sorted(self.nucleo.ordem.pendentes),
            "ultimas_entregas": [_resumo(m) for m in self.nucleo.ordem_global[-5:]],
        }
        self.gravando = {}
        self.canais = {}
        self.resultados = {}
        for id_no in self.nucleo.config.ids:
            if id_no == self.nucleo.meu_id:
                continue
            if id_no == canal_de_entrada:
                self.canais[id_no] = []          # canal do marcador entra vazio
            else:
                self.gravando[id_no] = []        # demais canais comecam a gravar

    def _talvez_concluir(self):
        precisa = {i for i in self.nucleo.config.ids if i != self.nucleo.meu_id}
        if self.concluido or not set(self.canais) >= precisa:
            return
        self.concluido = True
        meu_resultado = {
            "estado_local": self.estado_local,
            "canais": {str(origem): mensagens for origem, mensagens in self.canais.items()},
        }
        self.resultados[self.nucleo.meu_id] = meu_resultado
        self.nucleo.registrar_log(f"snapshot {self.id_snapshot_atual}: meu estado local ficou completo")
        self.nucleo.enviar_rede(montar(
            RESULTADO_SNAPSHOT, origem=self.nucleo.meu_id, destino=TODOS,
            payload={"id_snapshot": self.id_snapshot_atual, "resultado": meu_resultado},
        ))
        self._talvez_montar_fotografia()

    def _talvez_montar_fotografia(self):
        # Coleta simples por multicast: quem receber os N resultados monta a
        # fotografia. O iniciador e quem mais provavelmente junta todos (comeca antes).
        if len(self.resultados) >= self.nucleo.config.total_nos:
            self.nucleo.registrar_log(f"snapshot {self.id_snapshot_atual}: fotografia global montada")
            self.nucleo.evento_interface("snapshot", {
                "id": self.id_snapshot_atual,
                "resultados": {str(k): v for k, v in sorted(self.resultados.items())},
            })


def _resumo(mensagem):
    # Descricao curta de uma mensagem entregue, para caber no estado do snapshot.
    payload = mensagem.get("payload", {})
    conteudo = payload.get("texto") if "texto" in payload else f"[{payload.get('acao', '?')}]"
    return {
        "num_seq": mensagem.get("num_seq"),
        "origem": mensagem.get("origem"),
        "grupo": mensagem.get("grupo"),
        "conteudo": conteudo,
    }
