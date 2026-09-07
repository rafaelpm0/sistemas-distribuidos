# Nucleo de um no: junta os modulos, roda o laco de despacho de mensagens e as
# tarefas periodicas, protege o estado com uma trava e oferece a API que a
# interface (ou o modo de teste) usa.

import queue
import threading
import time

from configuracao import ATRASO_ENVIO, TAMANHO_HISTORICO, TTL_MULTICAST
from eleicao import Eleicao
from grupos import RegistroGrupos
from mensagem import (CHAT_ENTREGA, CHAT_PEDIDO, COORDENADOR, ELEICAO, HEARTBEAT,
                      MARCADOR, RESULTADO_SNAPSHOT, RETRANSMITIR, montar)
from ordem_total import OrdemTotal
from rede import Rede
from relogio import RelogioVetorial
from snapshot import Snapshot


class Nucleo:

    def __init__(self, meu_id, config, nome=None):
        self.meu_id = meu_id
        self.meu_nome = nome  # nome amigavel opcional; so serve para identificar o no na tela
        self.config = config
        self.trava_estado = threading.Lock()
        self.fila_recebidas = queue.Queue()
        self.fila_interface = queue.Queue()
        self.ativo = True

        self.relogio = RelogioVetorial(meu_id, config.ids)
        self.grupos = RegistroGrupos(meu_id, config.ids)
        self.eleicao = Eleicao(self)
        self.ordem = OrdemTotal(self)
        self.snapshot = Snapshot(self)

        self.seq_origem_atual = 0
        self.enviadas_recentes = {}       # id_msg -> CHAT_PEDIDO (retransmissao por origem)
        self.ultimo_seq_por_origem = {}   # origem -> maior seq_origem visto
        self.ordem_global = []            # CHAT_ENTREGA entregues, na ordem de num_seq
        self.ordem_local = []             # eventos locais: (acao, grupo, autor, texto, num_seq)
        self.ultimo_snapshot = None       # ultima fotografia global montada por este no

        self.rede = Rede(config.grupo_multicast, config.porta_grupo, TTL_MULTICAST,
                         self.fila_recebidas.put)
        self.thread_nucleo = threading.Thread(target=self._laco, daemon=True)

    # --------------------------------------------------------------- ciclo de vida

    def iniciar(self):
        self.rede.iniciar()
        self.thread_nucleo.start()

    def encerrar(self):
        self.ativo = False
        self.rede.fechar()

    # ------------------------------------------------------------------- laco

    def _laco(self):
        while self.ativo:
            try:
                mensagem = self.fila_recebidas.get(timeout=0.2)
            except queue.Empty:
                mensagem = None
            with self.trava_estado:
                if mensagem is not None:
                    self._tratar(mensagem)
                self.eleicao.tarefas_periodicas()
                self.ordem.verificar_timeouts()

    def _tratar(self, mensagem):
        tipo = mensagem.get("tipo")
        if tipo == CHAT_PEDIDO:
            self.ordem.ao_receber_pedido(mensagem)
        elif tipo == CHAT_ENTREGA:
            self._detectar_lacuna_por_origem(mensagem)
            self.snapshot.ao_receber_mensagem_app(mensagem)
            self.ordem.ao_receber_entrega(mensagem)
        elif tipo == HEARTBEAT:
            self.eleicao.ao_receber_heartbeat(mensagem)
        elif tipo == ELEICAO:
            self.eleicao.ao_receber_eleicao(mensagem)
        elif tipo == COORDENADOR:
            self.eleicao.ao_receber_coordenador(mensagem)
        elif tipo == RETRANSMITIR:
            self._tratar_retransmitir(mensagem)
        elif tipo == MARCADOR:
            self.snapshot.ao_receber_marcador(mensagem)
        elif tipo == RESULTADO_SNAPSHOT:
            self.snapshot.ao_receber_resultado(mensagem)

    def _tratar_retransmitir(self, mensagem):
        if int(mensagem["destino"]) != self.meu_id:
            return
        payload = mensagem.get("payload", {})
        if "num_seq" in payload:
            self.ordem.responder_retransmissao(mensagem)          # sou o lider
        elif "seq_origem" in payload:
            id_msg = f"{self.meu_id}:{payload['seq_origem']}"      # sou a origem
            pedido = self.enviadas_recentes.get(id_msg)
            if pedido is not None:
                self.enviar_rede(pedido)

    def _detectar_lacuna_por_origem(self, mensagem):
        # Se percebemos um buraco no seq_origem de um no, pedimos a ele o que faltou.
        origem = int(mensagem["origem"])
        seq = mensagem.get("seq_origem")
        if seq is None or origem == self.meu_id:
            return
        ultimo = self.ultimo_seq_por_origem.get(origem, 0)
        if seq > ultimo + 1:
            self.enviar_rede(montar(RETRANSMITIR, origem=self.meu_id, destino=origem,
                                    payload={"seq_origem": ultimo + 1}))
        if seq > ultimo:
            self.ultimo_seq_por_origem[origem] = seq

    # ----------------------------------------------------------------- entrega

    def entregar_mensagem(self, mensagem):
        # Chamado pela OrdemTotal quando um num_seq sai do buffer, ja em ordem.
        origem = int(mensagem["origem"])
        if origem != self.meu_id:
            self.relogio.ao_entregar(mensagem["relogio_vetorial"])
        self.ordem_global.append(mensagem)

        payload = mensagem.get("payload", {})
        if "acao" in payload:
            self._aplicar_acao_grupo(mensagem)
        elif self.grupos.sou_membro(mensagem["grupo"]):
            self.ordem_local.append(
                ("entrega", mensagem["grupo"], origem, payload.get("texto", ""), mensagem["num_seq"])
            )
        self.evento_interface("entrega", {})

    def _aplicar_acao_grupo(self, mensagem):
        payload = mensagem["payload"]
        if payload["acao"] == "criar_grupo":
            membros = sorted(int(m) for m in payload["membros"])
            self.grupos.criar(mensagem["grupo"], payload["nome"], membros)
            self.registrar_log(
                f"grupo '{payload['nome']}' ({mensagem['grupo']}) criado pelo no "
                f"{mensagem['origem']} - membros {membros}"
            )

    # ----------------------------------------------------------- API da interface

    def enviar_chat(self, grupo_id, texto):
        with self.trava_estado:
            self._novo_pedido(grupo_id, {"texto": texto})
            self.ordem_local.append(("envio", grupo_id, self.meu_id, texto, None))
        self.evento_interface("ordem_local", {})

    def criar_grupo(self, nome, membros):
        with self.trava_estado:
            membros = sorted(set(int(m) for m in membros) | {self.meu_id})
            self._novo_pedido(None, {"acao": "criar_grupo", "nome": nome, "membros": membros})

    def definir_nome(self, nome):
        # Nome amigavel do no, definido em tempo de execucao pela tela.
        with self.trava_estado:
            self.meu_nome = nome

    def abrir_privada(self, outro_id):
        with self.trava_estado:
            grupo_id = self.grupos.abrir_privado(int(outro_id))
        self.evento_interface("estado", {})
        return grupo_id

    def capturar_estado(self):
        with self.trava_estado:
            self.snapshot.iniciar()

    def forcar_eleicao(self):
        with self.trava_estado:
            self.eleicao.iniciar_eleicao()

    def simular_queda(self):
        self.registrar_log("simulando queda deste no")
        self.encerrar()

    # ----------------------------------------------------------------- utilidades

    def _novo_pedido(self, grupo_id, payload):
        # Monta e difunde um CHAT_PEDIDO (mensagem de chat ou acao de grupo).
        self.seq_origem_atual += 1
        vetor = self.relogio.evento_envio()
        id_msg = f"{self.meu_id}:{self.seq_origem_atual}"
        if grupo_id is None:
            grupo_id = f"g-{self.meu_id}-{self.seq_origem_atual}"  # id do novo grupo

        pedido = montar(CHAT_PEDIDO, origem=self.meu_id, destino=self.eleicao.lider_atual,
                        grupo=grupo_id, id_msg=id_msg, seq_origem=self.seq_origem_atual,
                        relogio_vetorial=vetor, payload=payload)

        self.enviadas_recentes[id_msg] = pedido
        if len(self.enviadas_recentes) > TAMANHO_HISTORICO:
            self.enviadas_recentes.pop(next(iter(self.enviadas_recentes)))
        self.ordem.aguardar_carimbo(id_msg, pedido)
        self.enviar_rede(pedido)

    def enviar_rede(self, mensagem):
        if ATRASO_ENVIO > 0:
            time.sleep(ATRASO_ENVIO)
        self.rede.enviar(mensagem)

    def registrar_log(self, texto):
        self.fila_interface.put(("log", texto))

    def evento_interface(self, tipo, dados):
        if tipo == "snapshot":
            self.ultimo_snapshot = dados
        self.fila_interface.put((tipo, dados))
