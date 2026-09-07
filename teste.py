# Testes automatizados: sobem varios nos de verdade (processos separados, so rede),
# cada um executa um roteiro de comandos e grava a saida; depois comparamos.
#
# Uso: python teste.py

import json
import os
import subprocess
import sys
import tempfile

PASTA_TESTE = os.path.join(tempfile.gettempdir(), "chat_distribuido_teste")


def _preparar_pasta():
    os.makedirs(PASTA_TESTE, exist_ok=True)
    for nome in os.listdir(PASTA_TESTE):
        os.remove(os.path.join(PASTA_TESTE, nome))


def _gerar_config(quantidade):
    caminho = os.path.join(PASTA_TESTE, "nos.json")
    dados = {
        "grupo_multicast": "224.1.1.1",
        "porta_grupo": 5007,
        "nos": [{"id": i, "host": "127.0.0.1", "porta": 5000 + i} for i in range(1, quantidade + 1)],
    }
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo)
    return caminho


def _rodar(quantidade, roteiros):
    # roteiros: dict {id_no: [linhas de comando]}. Devolve dict {id_no: saida_json}.
    _preparar_pasta()
    caminho_config = _gerar_config(quantidade)
    raiz = os.path.dirname(os.path.abspath(__file__))

    processos = []
    for id_no in range(1, quantidade + 1):
        caminho_script = os.path.join(PASTA_TESTE, f"script_{id_no}.txt")
        with open(caminho_script, "w", encoding="utf-8") as arquivo:
            arquivo.write("\n".join(roteiros.get(id_no, [])))
        caminho_saida = os.path.join(PASTA_TESTE, f"saida_{id_no}.json")
        processos.append(subprocess.Popen([
            sys.executable, os.path.join(raiz, "no.py"),
            "--id", str(id_no), "--config", caminho_config,
            "--sem-interface", "--script", caminho_script, "--saida", caminho_saida,
        ]))

    for processo in processos:
        processo.wait(timeout=60)

    saidas = {}
    for id_no in range(1, quantidade + 1):
        caminho_saida = os.path.join(PASTA_TESTE, f"saida_{id_no}.json")
        if os.path.exists(caminho_saida):
            with open(caminho_saida, "r", encoding="utf-8") as arquivo:
                saidas[id_no] = json.load(arquivo)
    return saidas


def _chave_ordem(saida):
    return [(item["num_seq"], item["id_msg"]) for item in saida["ordem_global"]]


def _verificar(condicao, descricao, falhas):
    marca = "ok  " if condicao else "FALHA"
    print(f"  [{marca}] {descricao}")
    if not condicao:
        falhas.append(descricao)


# --------------------------------------------------------------------- teste 1

def teste_ordem_total_e_grupos():
    print("Teste 1: ordem total, criacao de grupo e conversa privada (5 nos)")
    falhas = []
    roteiros = {
        1: ["esperar 0.5", "enviar geral ola-de-1", "esperar 1.5", "enviar geral tchau-de-1"],
        2: ["esperar 0.7", "enviar geral ola-de-2", "esperar 0.8",
            "grupo Equipe 4", "esperar 1.0", "enviar g-2-2 oi-equipe"],
        3: ["esperar 0.9", "enviar geral ola-de-3"],
        4: ["esperar 2.6", "enviar geral tchau-de-4"],
        5: ["esperar 0.6", "privada 1", "esperar 0.4", "enviar priv-1-5 oi-privado",
            "esperar 1.6", "snapshot"],
    }
    saidas = _rodar(5, roteiros)

    _verificar(len(saidas) == 5, "os 5 nos gravaram saida", falhas)
    if len(saidas) == 5:
        ordens = {id_no: _chave_ordem(saida) for id_no, saida in saidas.items()}
        referencia = ordens[1]
        _verificar(all(ordem == referencia for ordem in ordens.values()),
                   "a ordem global (num_seq) e identica nos 5 nos", falhas)
        # 7 mensagens de chat + 1 criacao de grupo, todas com num_seq.
        _verificar(len(referencia) == 8, f"as 8 operacoes ordenadas foram entregues (entregues: {len(referencia)})", falhas)
        _verificar([n for n, _ in referencia] == list(range(1, len(referencia) + 1)),
                   "os num_seq sao 1..N sem buraco", falhas)
        _verificar(all(saida["lider"] == 5 for saida in saidas.values()),
                   "todos reconhecem o no 5 como lider", falhas)

        grupo_equipe = _achar_grupo(saidas[1], "Equipe")
        _verificar(grupo_equipe is not None, "o grupo 'Equipe' foi registrado em todos os nos", falhas)
        if grupo_equipe:
            membros_por_no = {id_no: _membros_do_grupo(saida, "Equipe") for id_no, saida in saidas.items()}
            _verificar(all(m == [2, 4] for m in membros_por_no.values()),
                       f"todos concordam que 'Equipe' tem membros [2, 4] ({membros_por_no})", falhas)
    return falhas


# --------------------------------------------------------------------- teste 2

def teste_queda_do_lider():
    print("Teste 2: queda do lider e reeleicao pelo anel (5 nos)")
    falhas = []
    roteiros = {
        1: ["esperar 0.5", "enviar geral antes-1", "esperar 6.0", "enviar geral depois-1"],
        2: ["esperar 0.7", "enviar geral antes-2", "esperar 6.5", "enviar geral depois-2"],
        3: ["esperar 0.9", "enviar geral antes-3", "esperar 7.0", "enviar geral depois-3"],
        4: ["esperar 1.1", "enviar geral antes-4", "esperar 7.5", "enviar geral depois-4"],
        5: ["esperar 1.5", "cair"],  # o lider (maior id) cai cedo
    }
    saidas = _rodar(5, roteiros)
    sobreviventes = {id_no: saida for id_no, saida in saidas.items() if id_no != 5}

    _verificar(len(sobreviventes) == 4, "os 4 nos sobreviventes gravaram saida", falhas)
    if len(sobreviventes) == 4:
        ordens = {id_no: _chave_ordem(saida) for id_no, saida in sobreviventes.items()}
        referencia = ordens[1]
        _verificar(all(ordem == referencia for ordem in ordens.values()),
                   "a ordem global e identica nos 4 sobreviventes", falhas)
        _verificar(all(saida["lider"] == 4 for saida in sobreviventes.values()),
                   "os sobreviventes elegeram o no 4 como novo lider", falhas)
        _verificar(len(referencia) >= 8,
                   f"mensagens de antes e depois da queda foram entregues (entregues: {len(referencia)})", falhas)
        _verificar([n for n, _ in referencia] == list(range(1, len(referencia) + 1)),
                   "os num_seq continuam 1..N sem buraco apos a reeleicao", falhas)
    return falhas


# --------------------------------------------------------------------- teste 3

def teste_quinze_nos_e_snapshot():
    print("Teste 3: 15 nos, ordem total e estado global (Chandy-Lamport)")
    falhas = []
    roteiros = {}
    for id_no in range(1, 16):
        roteiros[id_no] = [f"esperar {0.4 + id_no * 0.05:.2f}", f"enviar geral msg-de-{id_no}"]
    roteiros[15] += ["esperar 2.0", "snapshot"]

    saidas = _rodar(15, roteiros)

    _verificar(len(saidas) == 15, f"os 15 nos gravaram saida (gravaram: {len(saidas)})", falhas)
    if len(saidas) == 15:
        ordens = {id_no: _chave_ordem(saida) for id_no, saida in saidas.items()}
        referencia = ordens[1]
        _verificar(all(ordem == referencia for ordem in ordens.values()),
                   "a ordem global e identica nos 15 nos", falhas)
        _verificar(len(referencia) == 15, f"as 15 mensagens foram entregues (entregues: {len(referencia)})", falhas)
        _verificar(all(saida["lider"] == 15 for saida in saidas.values()),
                   "todos reconhecem o no 15 como lider", falhas)

        fotografias = [saida["snapshot"] for saida in saidas.values() if saida.get("snapshot")]
        _verificar(len(fotografias) >= 1, "ao menos um no montou a fotografia global", falhas)
        if fotografias:
            foto = fotografias[0]
            _verificar(len(foto["resultados"]) == 15,
                       f"a fotografia tem o estado dos 15 nos (tem: {len(foto['resultados'])})", falhas)
    return falhas


# --------------------------------------------------------------------- auxiliares

def _achar_grupo(saida, nome):
    for grupo_id, grupo in saida["grupos"].items():
        if grupo["nome"] == nome:
            return grupo_id
    return None


def _membros_do_grupo(saida, nome):
    for grupo in saida["grupos"].values():
        if grupo["nome"] == nome:
            return grupo["membros"]
    return None


def principal():
    todas_as_falhas = []
    todas_as_falhas += teste_ordem_total_e_grupos()
    print()
    todas_as_falhas += teste_queda_do_lider()
    print()
    todas_as_falhas += teste_quinze_nos_e_snapshot()
    print()
    if todas_as_falhas:
        print(f"RESULTADO: {len(todas_as_falhas)} verificacao(oes) falharam.")
        sys.exit(1)
    print("RESULTADO: todos os testes passaram.")


if __name__ == "__main__":
    principal()
