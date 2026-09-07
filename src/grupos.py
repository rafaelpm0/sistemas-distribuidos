# Registro dos grupos de conversa conhecidos por um no.

GERAL = "geral"


def id_privado(id_a, id_b):
    # Id canonico de uma conversa privada entre dois nos (sempre o menor primeiro).
    menor, maior = sorted((int(id_a), int(id_b)))
    return f"priv-{menor}-{maior}"


class RegistroGrupos:

    def __init__(self, meu_id, ids):
        self.meu_id = meu_id
        # grupo_id -> {"nome": str, "tipo": str, "membros": set de ids}
        self.grupos = {
            GERAL: {"nome": "geral", "tipo": "publico", "membros": set(ids)},
        }

    def criar(self, grupo_id, nome, membros):
        # Registra um grupo nomeado ou privado. Idempotente (a entrega pode repetir).
        if grupo_id in self.grupos:
            return
        tipo = "privado" if grupo_id.startswith("priv-") else "nomeado"
        self.grupos[grupo_id] = {
            "nome": nome,
            "tipo": tipo,
            "membros": set(int(membro) for membro in membros),
        }

    def abrir_privado(self, outro_id):
        # Cria localmente a conversa privada; o registro definitivo chega na entrega.
        grupo_id = id_privado(self.meu_id, outro_id)
        self.criar(grupo_id, grupo_id, [self.meu_id, int(outro_id)])
        return grupo_id

    def garantir_privado(self, grupo_id):
        # Um grupo "priv-a-b" tem os dois membros codificados no proprio id. Se uma
        # mensagem chega para uma conversa privada que este no ainda nao abriu, mas
        # da qual ele participa, registra a conversa aqui. Devolve True se registrou.
        if grupo_id in self.grupos or not grupo_id.startswith("priv-"):
            return False
        partes = grupo_id.split("-")
        if len(partes) != 3:
            return False
        try:
            id_a, id_b = int(partes[1]), int(partes[2])
        except ValueError:
            return False
        if self.meu_id not in (id_a, id_b):
            return False
        self.criar(grupo_id, grupo_id, [id_a, id_b])
        return True

    def sou_membro(self, grupo_id):
        grupo = self.grupos.get(grupo_id)
        return grupo is not None and self.meu_id in grupo["membros"]

    def membros(self, grupo_id):
        grupo = self.grupos.get(grupo_id)
        return sorted(grupo["membros"]) if grupo else []

    def nome_de(self, grupo_id):
        grupo = self.grupos.get(grupo_id)
        return grupo["nome"] if grupo else grupo_id

    def conversas_visiveis(self):
        # (grupo_id, nome) de cada conversa de que este no participa.
        visiveis = []
        for grupo_id, grupo in self.grupos.items():
            if self.meu_id in grupo["membros"]:
                visiveis.append((grupo_id, grupo["nome"]))
        return visiveis
