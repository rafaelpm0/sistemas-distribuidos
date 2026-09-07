# Camada de rede: um socket para enviar e outro para receber no grupo multicast.
# Toda a comunicacao entre nos passa por aqui - nao ha unicast nem estado compartilhado.

import socket
import struct
import threading

from mensagem import serializar, desserializar


class Rede:

    def __init__(self, grupo_multicast, porta_grupo, ttl, ao_receber):
        self.grupo_multicast = grupo_multicast
        self.porta_grupo = porta_grupo
        self.ao_receber = ao_receber   # callback(mensagem_dict), chamado pela thread receptora
        self._ativo = True

        # Socket de envio.
        self.socket_envio = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.socket_envio.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)

        # Socket de recepcao. Varios nos na mesma maquina => reaproveitar endereco/porta.
        self.socket_recepcao = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.socket_recepcao.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                self.socket_recepcao.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        self.socket_recepcao.bind(("", porta_grupo))
        pedido_associacao = struct.pack("4sl", socket.inet_aton(grupo_multicast), socket.INADDR_ANY)
        self.socket_recepcao.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, pedido_associacao)

        self.thread_recepcao = threading.Thread(target=self._laco_recepcao, daemon=True)

    def iniciar(self):
        self.thread_recepcao.start()

    def enviar(self, mensagem):
        # Difunde uma mensagem para todos os nos do grupo.
        self.socket_envio.sendto(serializar(mensagem), (self.grupo_multicast, self.porta_grupo))

    def _laco_recepcao(self):
        # Recebe datagramas e entrega o dicionario ja decodificado ao callback.
        while self._ativo:
            try:
                dados, _ = self.socket_recepcao.recvfrom(65536)
            except OSError:
                break
            try:
                mensagem = desserializar(dados)
            except ValueError:
                continue  # datagrama corrompido: ignora
            self.ao_receber(mensagem)

    def fechar(self):
        self._ativo = False
        for socket_do_no in (self.socket_recepcao, self.socket_envio):
            try:
                socket_do_no.close()
            except OSError:
                pass
