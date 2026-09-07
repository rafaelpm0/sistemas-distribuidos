# Ponto de entrada de um no: le --id e --config, cria o nucleo e abre a janela.
# O modo --sem-interface executa um roteiro de comandos e grava o resultado;
# serve para os testes automatizados (ver teste.py).

import argparse
import json
import time

from configuracao import Config
from nucleo import Nucleo


def principal():
    analisador = argparse.ArgumentParser(description="No do chat distribuido")
    analisador.add_argument("--id", type=int, required=True)
    analisador.add_argument("--nome", default=None, help="nome amigavel do no, so para identificacao na tela")
    analisador.add_argument("--config", default="nos.json")
    analisador.add_argument("--sem-interface", action="store_true")
    analisador.add_argument("--script", default=None, help="arquivo de comandos (modo de teste)")
    analisador.add_argument("--saida", default=None, help="onde gravar o resultado (modo de teste)")
    argumentos = analisador.parse_args()

    config = Config(argumentos.config)
    nucleo = Nucleo(argumentos.id, config, argumentos.nome)
    nucleo.iniciar()

    if argumentos.sem_interface:
        executar_roteiro(nucleo, argumentos)
    else:
        from interface import Janela
        Janela(nucleo).executar()


def executar_roteiro(nucleo, argumentos):
    # Le o script linha a linha e executa cada comando; ao final grava a saida.
    comandos = []
    if argumentos.script:
        with open(argumentos.script, "r", encoding="utf-8") as arquivo:
            comandos = [linha.strip() for linha in arquivo if linha.strip() and not linha.startswith("#")]

    time.sleep(1.0)  # deixa todos os nos subirem e trocarem os primeiros heartbeats

    for comando in comandos:
        _executar_comando(nucleo, comando)

    time.sleep(3.0)  # deixa a rede estabilizar antes de fotografar o estado
    if argumentos.saida:
        _gravar_saida(nucleo, argumentos.saida)
    nucleo.encerrar()


def _executar_comando(nucleo, comando):
    partes = comando.split(maxsplit=1)
    verbo = partes[0]
    resto = partes[1] if len(partes) > 1 else ""

    if verbo == "esperar":
        time.sleep(float(resto))
    elif verbo == "enviar":
        grupo, texto = resto.split(maxsplit=1)
        nucleo.enviar_chat(grupo, texto)
    elif verbo == "grupo":
        nome, ids = resto.split(maxsplit=1)
        nucleo.criar_grupo(nome, [int(x) for x in ids.replace(",", " ").split()])
    elif verbo == "privada":
        nucleo.abrir_privada(int(resto))
    elif verbo == "snapshot":
        nucleo.capturar_estado()
    elif verbo == "eleicao":
        nucleo.forcar_eleicao()
    elif verbo == "cair":
        nucleo.encerrar()


def _gravar_saida(nucleo, caminho):
    with nucleo.trava_estado:
        ordem_global = [
            {
                "num_seq": m.get("num_seq"),
                "id_msg": m.get("id_msg"),
                "origem": m.get("origem"),
                "grupo": m.get("grupo"),
                "resumo": m.get("payload", {}).get("texto", "[" + m.get("payload", {}).get("acao", "?") + "]"),
            }
            for m in nucleo.ordem_global
        ]
        grupos = {
            grupo_id: {"nome": grupo["nome"], "membros": sorted(grupo["membros"])}
            for grupo_id, grupo in nucleo.grupos.grupos.items()
        }
        dados = {
            "id": nucleo.meu_id,
            "nome": nucleo.meu_nome,
            "lider": nucleo.eleicao.lider_atual,
            "relogio": nucleo.relogio.copia(),
            "ordem_global": ordem_global,
            "grupos": grupos,
            "snapshot": nucleo.ultimo_snapshot,
        }
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    principal()
