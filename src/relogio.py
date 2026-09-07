# Relogio vetorial de um no.
# Nao decide a ordem de entrega (isso e o num_seq do lider): serve para
# causalidade, para a tela e para o exemplo numerico do relatorio.

class RelogioVetorial:

    def __init__(self, meu_id, ids):
        self.meu_id = meu_id
        # Um contador por no do sistema.
        self.vetor = {id_no: 0 for id_no in ids}

    def evento_envio(self):
        # O no vai enviar uma mensagem: conta o proprio evento e devolve uma copia.
        self.vetor[self.meu_id] += 1
        return dict(self.vetor)

    def ao_entregar(self, vetor_recebido):
        # Entrega de mensagem de OUTRO no: funde os componentes e conta o evento local.
        for id_no, valor in _com_chaves_inteiras(vetor_recebido).items():
            if id_no in self.vetor:
                self.vetor[id_no] = max(self.vetor[id_no], valor)
        self.vetor[self.meu_id] += 1

    def copia(self):
        return dict(self.vetor)

    def __str__(self):
        partes = [f"{id_no}:{valor}" for id_no, valor in sorted(self.vetor.items())]
        return "[" + ", ".join(partes) + "]"


def _com_chaves_inteiras(vetor):
    # As chaves de um dict vindo de JSON chegam como string; padroniza para int.
    return {int(chave): valor for chave, valor in vetor.items()}


def concorrentes(vetor_a, vetor_b):
    # Verdadeiro se nenhum evento "aconteceu antes" do outro (eventos concorrentes).
    a = _com_chaves_inteiras(vetor_a)
    b = _com_chaves_inteiras(vetor_b)
    ids = set(a) | set(b)
    a_menor_ou_igual = all(a.get(i, 0) <= b.get(i, 0) for i in ids)
    b_menor_ou_igual = all(b.get(i, 0) <= a.get(i, 0) for i in ids)
    return not a_menor_ou_igual and not b_menor_ou_igual
