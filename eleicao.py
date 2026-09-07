# Eleicao de lider pelo algoritmo do anel, mais os heartbeats que sustentam
# a deteccao de falha e a nocao de "proximo no ativo" no anel.

import time

from configuracao import INTERVALO_HEARTBEAT, T_FALHA
from mensagem import COORDENADOR, ELEICAO, HEARTBEAT, TODOS, montar


class Eleicao:

    def __init__(self, nucleo):
        self.nucleo = nucleo
        ids = nucleo.config.ids

        # No boot, cada no assume que o maior id e o lider ate um heartbeat confirmar.
        self.lider_atual = max(ids)
        self.sou_lider = (nucleo.meu_id == self.lider_atual)

        agora = time.monotonic()
        self.ultimo_heartbeat = {id_no: agora for id_no in ids}
        self.instante_ultimo_heartbeat_enviado = 0.0
        self.eleicao_em_andamento = False

    # ------------------------------------------------------------- periodico

    def tarefas_periodicas(self):
        agora = time.monotonic()

        if agora - self.instante_ultimo_heartbeat_enviado > INTERVALO_HEARTBEAT:
            self.instante_ultimo_heartbeat_enviado = agora
            self.nucleo.enviar_rede(montar(
                HEARTBEAT, origem=self.nucleo.meu_id, destino=TODOS,
                payload={"lider_conhecido": self.lider_atual,
                         "num_seq_visto": self.nucleo.ordem.proximo_num_seq_esperado - 1},
            ))

        # So quem nao e lider vigia a queda do lider.
        if not self.sou_lider:
            silencio = agora - self.ultimo_heartbeat.get(self.lider_atual, 0.0)
            if silencio > T_FALHA:
                self.iniciar_eleicao()

    # ---------------------------------------------------------------- anel

    def nos_vivos(self):
        agora = time.monotonic()
        vivos = [id_no for id_no, instante in self.ultimo_heartbeat.items()
                 if agora - instante <= T_FALHA]
        if self.nucleo.meu_id not in vivos:
            vivos.append(self.nucleo.meu_id)
        return sorted(vivos)

    def proximo_ativo(self, id_no):
        # Proximo no vivo em ordem crescente de id, dando a volta no anel.
        vivos = self.nos_vivos()
        maiores = [i for i in vivos if i > id_no]
        return maiores[0] if maiores else vivos[0]

    def iniciar_eleicao(self):
        if self.eleicao_em_andamento:
            return
        self.eleicao_em_andamento = True
        self.nucleo.registrar_log(f"eleicao iniciada pelo no {self.nucleo.meu_id}")
        self.nucleo.enviar_rede(montar(
            ELEICAO, origem=self.nucleo.meu_id, destino=self.proximo_ativo(self.nucleo.meu_id),
            payload={"ids_vistos": [self.nucleo.meu_id]},
        ))

    def ao_receber_eleicao(self, mensagem):
        if int(mensagem["destino"]) != self.nucleo.meu_id:
            return
        ids_vistos = list(mensagem["payload"]["ids_vistos"])

        if self.nucleo.meu_id in ids_vistos:
            # A mensagem deu a volta: o maior id visto vence.
            novo_lider = max(ids_vistos)
            base = self.nucleo.ordem.proximo_num_seq_esperado
            self.nucleo.registrar_log(f"anel completo {ids_vistos} -> lider {novo_lider}")
            self.nucleo.enviar_rede(montar(
                COORDENADOR, origem=self.nucleo.meu_id, destino=TODOS,
                payload={"lider": novo_lider, "proximo_num_seq": base},
            ))
        else:
            ids_vistos.append(self.nucleo.meu_id)
            self.nucleo.enviar_rede(montar(
                ELEICAO, origem=self.nucleo.meu_id,
                destino=self.proximo_ativo(self.nucleo.meu_id),
                payload={"ids_vistos": ids_vistos},
            ))

    def ao_receber_coordenador(self, mensagem):
        novo_lider = int(mensagem["payload"]["lider"])
        era_lider = self.sou_lider

        self.lider_atual = novo_lider
        self.sou_lider = (self.nucleo.meu_id == novo_lider)
        self.eleicao_em_andamento = False
        self.ultimo_heartbeat[novo_lider] = time.monotonic()
        self.nucleo.registrar_log(f"COORDENADOR: lider = {novo_lider}")

        if self.sou_lider and not era_lider:
            base = int(mensagem["payload"].get("proximo_num_seq", 1))
            self.nucleo.ordem.ao_virar_lider(base)
        self.nucleo.evento_interface("estado", {})

    def ao_receber_heartbeat(self, mensagem):
        origem = int(mensagem["origem"])
        self.ultimo_heartbeat[origem] = time.monotonic()
        # Se um no vivo conhece um lider de id maior que o nosso e esse lider esta
        # vivo, aceitamos - evita disputa desnecessaria logo apos o boot.
        lider_conhecido = mensagem.get("payload", {}).get("lider_conhecido")
        if (lider_conhecido is not None and lider_conhecido > self.lider_atual
                and not self.eleicao_em_andamento):
            agora = time.monotonic()
            if agora - self.ultimo_heartbeat.get(lider_conhecido, 0.0) <= T_FALHA:
                self.lider_atual = int(lider_conhecido)
                self.sou_lider = (self.nucleo.meu_id == self.lider_atual)
