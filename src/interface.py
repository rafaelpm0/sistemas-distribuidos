# Tela de um no (requisito R5), em Tkinter.
# O Tkinter nao e thread-safe: o nucleo poe eventos numa fila e a janela
# le essa fila a cada 100 ms; os botoes so chamam metodos do nucleo.

import queue
import tkinter as tk
from tkinter import messagebox, simpledialog

from grupos import GERAL


class Janela:

    def __init__(self, nucleo):
        self.nucleo = nucleo
        self.janela = tk.Tk()
        self._atualizar_titulo()
        self.janela.geometry("760x620")

        self.grupo_escolhido = tk.StringVar(value=GERAL)
        self._montar_widgets()
        self._atualizar_paineis()
        self.janela.after(100, self._drenar_fila)
        self.janela.protocol("WM_DELETE_WINDOW", self._ao_fechar)

    # ------------------------------------------------------------------ layout

    def _atualizar_titulo(self):
        # Titulo da janela: "No 1" ou "No 1 - Alice" quando ha nome.
        titulo = f"No {self.nucleo.meu_id}"
        if self.nucleo.meu_nome:
            titulo += f" - {self.nucleo.meu_nome}"
        self.janela.title(titulo)

    def _montar_widgets(self):
        topo = tk.Frame(self.janela)
        topo.pack(fill="x", padx=8, pady=4)
        self.rotulo_cabecalho = tk.Label(topo, font=("TkDefaultFont", 10, "bold"))
        self.rotulo_cabecalho.pack(side="left")
        self.rotulo_estado = tk.Label(topo, fg="gray25")
        self.rotulo_estado.pack(side="right")

        identificacao = tk.Frame(self.janela)
        identificacao.pack(fill="x", padx=8, pady=2)
        tk.Label(identificacao, text="Nome deste no:").pack(side="left")
        self.campo_nome = tk.Entry(identificacao, width=22)
        if self.nucleo.meu_nome:
            self.campo_nome.insert(0, self.nucleo.meu_nome)
        self.campo_nome.pack(side="left", padx=4)
        self.campo_nome.bind("<Return>", lambda evento: self._definir_nome())
        tk.Button(identificacao, text="Definir nome", command=self._definir_nome).pack(side="left")

        envio = tk.Frame(self.janela)
        envio.pack(fill="x", padx=8, pady=4)
        tk.Label(envio, text="Conversa:").grid(row=0, column=0, sticky="w")
        self.seletor_conversa = tk.OptionMenu(envio, self.grupo_escolhido, GERAL)
        self.seletor_conversa.grid(row=0, column=1, sticky="w")
        self.campo_texto = tk.Entry(envio, width=60)
        self.campo_texto.grid(row=1, column=0, columnspan=2, sticky="we", pady=2)
        self.campo_texto.bind("<Return>", lambda evento: self._enviar())
        tk.Button(envio, text="Enviar", command=self._enviar).grid(row=1, column=2, padx=4)
        tk.Button(envio, text="Criar grupo", command=self._criar_grupo).grid(row=2, column=0, sticky="w", pady=2)
        tk.Button(envio, text="Nova conversa privada", command=self._nova_privada).grid(row=2, column=1, sticky="w")
        envio.columnconfigure(0, weight=1)

        painel = tk.Frame(self.janela)
        painel.pack(fill="both", expand=True, padx=8, pady=4)

        coluna_esquerda = tk.Frame(painel)
        coluna_esquerda.pack(side="left", fill="both", expand=True)
        tk.Label(coluna_esquerda, text="Ordem local (o que este no emitiu/entregou)").pack(anchor="w")
        self.texto_ordem_local = _area_texto(coluna_esquerda, altura=9)
        self.rotulo_mensagens = tk.Label(coluna_esquerda, anchor="w", justify="left")
        self.rotulo_mensagens.pack(anchor="w")
        self.texto_mensagens = _area_texto(coluna_esquerda, altura=11)

        coluna_direita = tk.Frame(painel, width=220)
        coluna_direita.pack(side="right", fill="y")
        coluna_direita.pack_propagate(False)
        tk.Label(coluna_direita, text="Relogio vetorial").pack(anchor="w")
        self.rotulo_relogio = tk.Label(coluna_direita, fg="navy", justify="left", wraplength=210)
        self.rotulo_relogio.pack(anchor="w")
        self.rotulo_buffer = tk.Label(coluna_direita, justify="left")
        self.rotulo_buffer.pack(anchor="w", pady=4)
        tk.Button(coluna_direita, text="Capturar estado global", command=self.nucleo.capturar_estado).pack(fill="x", pady=2)
        tk.Button(coluna_direita, text="Forcar eleicao", command=self.nucleo.forcar_eleicao).pack(fill="x", pady=2)
        tk.Button(coluna_direita, text="Simular queda", command=self._simular_queda).pack(fill="x", pady=2)

        tk.Label(self.janela, text="Log do sistema").pack(anchor="w", padx=8)
        self.texto_log = _area_texto(self.janela, altura=7)

    # ------------------------------------------------------------------ acoes

    def _enviar(self):
        texto = self.campo_texto.get().strip()
        if not texto:
            return
        self.nucleo.enviar_chat(self.grupo_escolhido.get(), texto)
        self.campo_texto.delete(0, tk.END)

    def _definir_nome(self):
        # Aplica o nome digitado no campo; campo vazio deixa o no "sem nome".
        novo_nome = self.campo_nome.get().strip()
        self.nucleo.definir_nome(novo_nome or None)
        self._atualizar_titulo()
        self._atualizar_paineis()

    def _criar_grupo(self):
        DialogoCriarGrupo(self.janela, self.nucleo)

    def _nova_privada(self):
        outros = [i for i in self.nucleo.config.ids if i != self.nucleo.meu_id]
        alvo = simpledialog.askinteger("Nova conversa privada",
                                       f"Id do outro no {outros}:", parent=self.janela)
        if alvo in outros:
            grupo_id = self.nucleo.abrir_privada(alvo)
            self._escolher_conversa(grupo_id)

    def _simular_queda(self):
        if messagebox.askyesno("Simular queda", "Encerrar este no agora?"):
            self.nucleo.simular_queda()
            self.janela.destroy()

    def _ao_fechar(self):
        self.nucleo.encerrar()
        self.janela.destroy()

    # ------------------------------------------------------------------ fila

    def _drenar_fila(self):
        precisa_repintar = False
        try:
            while True:
                tipo, dados = self.nucleo.fila_interface.get_nowait()
                if tipo == "log":
                    self._acrescentar_log(dados)
                elif tipo == "snapshot":
                    self._mostrar_snapshot(dados)
                else:
                    precisa_repintar = True
        except queue.Empty:
            pass
        if precisa_repintar:
            self._atualizar_paineis()
        if self.nucleo.ativo:
            self.janela.after(100, self._drenar_fila)

    # ------------------------------------------------------------------ paineis

    def _atualizar_paineis(self):
        conversa = self.grupo_escolhido.get()
        with self.nucleo.trava_estado:
            papel = "LIDER" if self.nucleo.eleicao.sou_lider else "comum"
            relogio = str(self.nucleo.relogio)
            esperado = self.nucleo.ordem.proximo_num_seq_esperado
            pendentes = len(self.nucleo.ordem.pendentes)
            conversas = self.nucleo.grupos.conversas_visiveis()
            linhas_local = [self._formatar_local(evento) for evento in self.nucleo.ordem_local]
            # So as mensagens da conversa selecionada, na ordem global (num_seq).
            linhas_mensagens = [self._formatar_mensagem(m) for m in self.nucleo.ordem_global
                                if m.get("grupo") == conversa]

        cabecalho = f"No {self.nucleo.meu_id}"
        if self.nucleo.meu_nome:
            cabecalho += f" - {self.nucleo.meu_nome}"
        self.rotulo_cabecalho.config(text=f"{cabecalho}   |   Papel: {papel}")
        self.rotulo_estado.config(text=f"nos: {self.nucleo.config.total_nos}")
        self.rotulo_relogio.config(text=relogio)
        self.rotulo_buffer.config(text=f"Proximo num_seq esperado: {esperado}\nBuffer pendentes: {pendentes}")

        nomes_conversa = {grupo_id: nome for grupo_id, nome in conversas}
        self.rotulo_mensagens.config(
            text=f"Mensagens do chat - {nomes_conversa.get(conversa, conversa)} (ordem global, por num_seq)")
        self._recarregar_seletor([grupo_id for grupo_id, _ in conversas], nomes_conversa)
        _preencher(self.texto_ordem_local, linhas_local)
        _preencher(self.texto_mensagens, linhas_mensagens)

    def _recarregar_seletor(self, ids_grupos, nomes):
        menu = self.seletor_conversa["menu"]
        menu.delete(0, "end")
        for grupo_id in ids_grupos:
            rotulo = nomes.get(grupo_id, grupo_id)
            menu.add_command(label=rotulo, command=lambda g=grupo_id: self._escolher_conversa(g))
        if self.grupo_escolhido.get() not in ids_grupos:
            self.grupo_escolhido.set(GERAL)

    def _escolher_conversa(self, grupo_id):
        # Troca a conversa ativa e repinta na hora (sem esperar o proximo evento).
        self.grupo_escolhido.set(grupo_id)
        self._atualizar_paineis()

    def _formatar_local(self, evento):
        acao, grupo, autor, texto, num_seq = evento
        nome = self.nucleo.grupos.nome_de(grupo)
        if acao == "envio":
            return f"envio     -> {nome:<12} \"{texto}\""
        return f"entrega   #{num_seq} de {autor}  {nome:<12} \"{texto}\""

    def _formatar_mensagem(self, mensagem):
        num_seq = mensagem.get("num_seq")
        origem = mensagem.get("origem")
        payload = mensagem.get("payload", {})
        if "acao" in payload:
            return f"#{num_seq:<3} -- conversa criada pelo no {origem} --"
        return f"#{num_seq:<3} No {origem}: {payload.get('texto', '')}"

    # ------------------------------------------------------------------ log / snapshot

    def _acrescentar_log(self, texto):
        self.texto_log.config(state="normal")
        self.texto_log.insert("end", texto + "\n")
        self.texto_log.see("end")
        self.texto_log.config(state="disabled")

    def _mostrar_snapshot(self, dados):
        janela_snap = tk.Toplevel(self.janela)
        janela_snap.title(f"Estado global {dados['id']}")
        area = _area_texto(janela_snap, altura=24)
        linhas = [f"Snapshot {dados['id']}", ""]
        for id_no, resultado in dados["resultados"].items():
            estado = resultado["estado_local"]
            linhas.append(f"No {id_no}: entregou ate num_seq {estado['num_seq_entregue']}  "
                          f"relogio {estado['relogio_vetorial']}  lider {estado['lider']}")
            for origem, mensagens in resultado["canais"].items():
                if mensagens:
                    linhas.append(f"    canal {origem}->{id_no}: {len(mensagens)} msg em transito")
        _preencher(area, linhas)

    # ------------------------------------------------------------------ loop

    def executar(self):
        self.janela.mainloop()


class DialogoCriarGrupo(tk.Toplevel):
    # Nome do grupo + selecao de membros (checkboxes com todos os ids).

    def __init__(self, pai, nucleo):
        super().__init__(pai)
        self.nucleo = nucleo
        self.title("Criar grupo")
        self.transient(pai)

        tk.Label(self, text="Nome do grupo:").pack(anchor="w", padx=8, pady=4)
        self.campo_nome = tk.Entry(self, width=32)
        self.campo_nome.pack(padx=8)

        tk.Label(self, text="Membros (voce entra automaticamente):").pack(anchor="w", padx=8, pady=4)
        self.marcados = {}
        for id_no in nucleo.config.ids:
            if id_no == nucleo.meu_id:
                continue
            variavel = tk.BooleanVar(value=False)
            tk.Checkbutton(self, text=f"No {id_no}", variable=variavel).pack(anchor="w", padx=16)
            self.marcados[id_no] = variavel

        tk.Button(self, text="Criar", command=self._confirmar).pack(pady=8)

    def _confirmar(self):
        nome = self.campo_nome.get().strip()
        membros = [id_no for id_no, marcado in self.marcados.items() if marcado.get()]
        if not nome or not membros:
            messagebox.showwarning("Criar grupo", "Informe o nome e ao menos um membro.")
            return
        self.nucleo.criar_grupo(nome, membros)
        self.destroy()


def _area_texto(pai, altura):
    texto = tk.Text(pai, height=altura, wrap="none", state="disabled", font=("TkFixedFont", 9))
    texto.pack(fill="both", expand=True, pady=2)
    return texto


def _preencher(area_texto, linhas):
    area_texto.config(state="normal")
    area_texto.delete("1.0", "end")
    area_texto.insert("1.0", "\n".join(linhas))
    area_texto.see("end")
    area_texto.config(state="disabled")
