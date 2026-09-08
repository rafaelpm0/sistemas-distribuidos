# Ordem total das mensagens de grupo: o lider funciona como sequenciador.
#
# Um mesmo objeto tem dois papeis:
#  - Sequenciador (so o lider): recebe CHAT_PEDIDO, atribui um num_seq global
#    crescente e redifunde a mensagem completa como CHAT_ENTREGA.
#  - Entrega ordenada (todo no): guarda os CHAT_ENTREGA num buffer e entrega
#    estritamente na ordem de num_seq, de modo que a fila global fique igual
#    em todos os nos.

import time

from configuracao import T_RETRANSMISSAO, TAMANHO_HISTORICO
from mensagem import CHAT_ENTREGA, RETRANSMITIR, TODOS, montar


class OrdemTotal:

    def __init__(self, nucleo):
        self.nucleo = nucleo

        # Papel de entrega ordenada (todo no).
        self.proximo_num_seq_esperado = 1
        self.pendentes = {}            # num_seq -> mensagem CHAT_ENTREGA aguardando
        self.entregues_id_msg = set()  # id_msg ja entregues, para descartar duplicatas

        # Papel de sequenciador (usado enquanto o no for lider).
        self.proximo_num_seq = 1
        self.historico_por_num_seq = {}   # num_seq -> CHAT_ENTREGA (para retransmitir)
        self.num_seq_por_id_msg = {}      # id_msg -> num_seq (para nao sequenciar duas vezes)

        # Autor esperando ver a propria mensagem voltar carimbada.
        self.aguardando_carimbo = {}      # id_msg -> [pedido, instante_do_ultimo_envio]
        self.instante_lacuna = None       # desde quando falta o proximo num_seq esperado

    # ------------------------------------------------------------------ autor

    def aguardar_carimbo(self, id_msg, pedido):
        self.aguardando_carimbo[id_msg] = [pedido, time.monotonic()]

    # -------------------------------------------------------------- sequenciador

    def ao_receber_pedido(self, mensagem):
        # So o lider sequencia. Os demais nos ignoram o CHAT_PEDIDO.
        if not self.nucleo.eleicao.sou_lider:
            return

        id_msg = mensagem["id_msg"]
        if id_msg in self.num_seq_por_id_msg:
            # Pedido repetido (retransmissao): reenvia o CHAT_ENTREGA ja existente.
            entrega = self.historico_por_num_seq.get(self.num_seq_por_id_msg[id_msg])
            if entrega is not None:
                self.nucleo.enviar_rede(entrega)
            return

        num_seq = self.proximo_num_seq
        self.proximo_num_seq += 1

        entrega = dict(mensagem)
        entrega["tipo"] = CHAT_ENTREGA
        entrega["destino"] = TODOS
        entrega["num_seq"] = num_seq
        entrega["carimbado_por"] = self.nucleo.meu_id

        self._guardar_no_historico(num_seq, id_msg, entrega)
        self.nucleo.enviar_rede(entrega)

    def responder_retransmissao(self, mensagem):
        # Lider reenvia um CHAT_ENTREGA pedido por um no que detectou lacuna.
        num_seq = mensagem.get("payload", {}).get("num_seq")
        entrega = self.historico_por_num_seq.get(num_seq)
        if entrega is not None:
            self.nucleo.enviar_rede(entrega)

    def ao_virar_lider(self, num_seq_base):
        # Reconstroi o historico a partir do que este no ja viu, para poder
        # sequenciar e retransmitir a partir de agora.
        conhecidas = list(self.nucleo.ordem_global) + list(self.pendentes.values())
        for entrega in conhecidas:
            if "num_seq" in entrega:
                self._guardar_no_historico(entrega["num_seq"], entrega["id_msg"], entrega)
        maior_conhecido = max([0] + list(self.historico_por_num_seq))
        self.proximo_num_seq = max(num_seq_base, maior_conhecido + 1)
        self.nucleo.registrar_log("assumi o papel de lider (sequenciador)")

    def _guardar_no_historico(self, num_seq, id_msg, entrega):
        self.historico_por_num_seq[num_seq] = entrega
        self.num_seq_por_id_msg[id_msg] = num_seq
        if len(self.historico_por_num_seq) > TAMANHO_HISTORICO:
            mais_antigo = min(self.historico_por_num_seq)
            id_antigo = self.historico_por_num_seq[mais_antigo]["id_msg"]
            del self.historico_por_num_seq[mais_antigo]
            self.num_seq_por_id_msg.pop(id_antigo, None)

    # ----------------------------------------------------------- entrega ordenada

    def ao_receber_entrega(self, mensagem):
        num_seq = mensagem["num_seq"]
        if num_seq < self.proximo_num_seq_esperado:
            return  # ja entregamos essa posicao

        self.pendentes[num_seq] = mensagem
        self.aguardando_carimbo.pop(mensagem["id_msg"], None)

        # Se um dia este no virar lider, o contador precisa estar a frente do que circulou.
        if self.proximo_num_seq <= num_seq:
            self.proximo_num_seq = num_seq + 1

        self._tentar_entregar()

    def _tentar_entregar(self):
        # Entrega tudo que estiver em sequencia a partir do proximo esperado.
        while self.proximo_num_seq_esperado in self.pendentes:
            mensagem = self.pendentes.pop(self.proximo_num_seq_esperado)
            self.proximo_num_seq_esperado += 1
            if mensagem["id_msg"] in self.entregues_id_msg:
                continue
            self.entregues_id_msg.add(mensagem["id_msg"])
            self.nucleo.entregar_mensagem(mensagem)

    # ------------------------------------------------------------------ timeouts

    def verificar_timeouts(self):
        agora = time.monotonic()

        # 1) O autor nao viu o carimbo da propria mensagem: reenvia o pedido ao lider.
        for id_msg, registro in list(self.aguardando_carimbo.items()):
            pedido, instante = registro
            if agora - instante > T_RETRANSMISSAO:
                pedido = dict(pedido)
                pedido["destino"] = self.nucleo.eleicao.lider_atual
                self.nucleo.enviar_rede(pedido)
                registro[1] = agora

        # 2) Ha pendentes futuros mas o proximo num_seq esperado nao chega: pede ao lider.
        falta_o_proximo = self.pendentes and self.proximo_num_seq_esperado not in self.pendentes
        if falta_o_proximo:
            if self.instante_lacuna is None:
                self.instante_lacuna = agora
            elif agora - self.instante_lacuna > T_RETRANSMISSAO:
                pedido = montar(RETRANSMITIR, origem=self.nucleo.meu_id,
                                destino=self.nucleo.eleicao.lider_atual,
                                payload={"num_seq": self.proximo_num_seq_esperado})
                self.nucleo.enviar_rede(pedido)
                self.instante_lacuna = agora
        else:
            self.instante_lacuna = None
