# Gera o nos.json para N nos e sobe N processos, um por no (cada um abre a sua janela).
# Uso (a partir da raiz do projeto): python src/iniciar.py --n 3   (ou 8, ou 15)

import argparse
import json
import os
import subprocess
import sys

from configuracao import GRUPO_MULTICAST, PORTA_GRUPO

PASTA_SRC = os.path.dirname(os.path.abspath(__file__))  # onde este arquivo e o no.py estao


def gerar_config(quantidade_de_nos, caminho):
    dados = {
        "grupo_multicast": GRUPO_MULTICAST,
        "porta_grupo": PORTA_GRUPO,
        "nos": [
            {"id": id_no, "host": "127.0.0.1", "porta": 5000 + id_no}
            for id_no in range(1, quantidade_de_nos + 1)
        ],
    }
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, indent=2)


def principal():
    analisador = argparse.ArgumentParser(description="Sobe varios nos do chat distribuido")
    analisador.add_argument("--n", type=int, default=3, help="quantidade de nos")
    analisador.add_argument("--config", default="nos.json")
    analisador.add_argument("--nomes", nargs="*", default=[],
                            help="nomes dos nos, na ordem dos ids (opcional)")
    argumentos = analisador.parse_args()

    gerar_config(argumentos.n, argumentos.config)
    print(f"nos.json gerado para {argumentos.n} nos.")

    processos = []
    for id_no in range(1, argumentos.n + 1):
        comando = [sys.executable, os.path.join(PASTA_SRC, "no.py"),
                   "--id", str(id_no), "--config", argumentos.config]
        if id_no <= len(argumentos.nomes):
            comando += ["--nome", argumentos.nomes[id_no - 1]]
        processo = subprocess.Popen(comando)
        processos.append(processo)
    print(f"{argumentos.n} nos iniciados. Feche as janelas para encerrar.")

    for processo in processos:
        processo.wait()


if __name__ == "__main__":
    principal()
