# Plano de Implementação — Trabalho 1: Chat Distribuído

Disciplina de Sistemas Distribuídos (UNIVALI, Prof. Ramicés) — Entrega 1 em 09/09/2026.

Este documento descreve **o que vamos construir e como**: as decisões, os
algoritmos passo a passo e a divisão em módulos. O código já foi implementado em
`src/` (ver `manual_de_uso.md` para executar). A base teórica e a preparação do
seminário estão em `manual_teorico.md`.

---

## 1. Visão geral e decisões de projeto

| Tema | Decisão | Justificativa curta (detalhe no `manual_de_uso.md`) |
|------|---------|------------------------------------------------------|
| Tema | Chat distribuído | Escolha da equipe entre os dois temas do roteiro. |
| Transporte | **Só multicast UDP**, um único grupo `224.1.1.1:5007` | Comunicação de grupo nativa; um envio chega a todos. É a cara de um app de mensagens. |
| Mensagens direcionadas | Também vão por multicast, com campo `destino` | Não usamos unicast em lugar nenhum; quem não é o alvo ignora. |
| Ordem total | **Abordagem B — sequenciador definido pelo líder** | Ordem total simples e eficiente; casa com eleição de líder e com estado global. |
| Relógio lógico | **Relógio vetorial** em cada nó, só para causalidade e exibição | A ordem total vem do `num_seq` do líder; o vetor mostra causal × concorrente na tela e no relatório. |
| Eleição | **Algoritmo do anel** | Mensagens direcionadas simples sobre multicast; passo a passo determinístico, fácil de demonstrar. |
| Estado global | **Chandy-Lamport** | Não para o sistema, não exige relógio sincronizado, é "só rede", produz corte consistente. |
| Grupos | `geral` (todos) + **grupos nomeados com membros escolhidos na criação** + conversas privadas `priv-a-b` (2 membros) | Criar grupo, dar nome e escolher quem entra é função central de um app de mensagens. Tudo no mesmo multicast e no mesmo sequenciador. |
| Privacidade | Lógica (o app não exibe mensagem de grupo em que o nó não é membro) | Sem criptografia — limitação registrada no relatório. |
| Interface | **Tkinter**, uma janela por processo-nó | Biblioteca padrão; deixa a tela do R5 visível ao vivo em cada nó. |
| Execução | Um processo do SO por nó; `nos.json` só como catálogo estático | Regra "somente mensagens de rede" do roteiro. |
| Linguagem | Python 3, **só biblioteca padrão** | `socket`, `struct`, `json`, `threading`, `queue`, `time`, `subprocess`, `argparse`, `tkinter`. |

---

## 2. Requisitos do roteiro → onde são atendidos

| # | Requisito | Onde é atendido |
|---|-----------|-----------------|
| R1 | Comunicação de grupo (multicast) | `rede.py` + grupo `224.1.1.1:5007`. Uma mensagem de grupo chega a todos os nós. |
| R2 | Tema (chat) | `nucleo.py` + `interface.py`: mensagem privada, mensagem de grupo e criação de grupos com membros escolhidos. |
| R3 | Nº de nós configurável, ≥ 15 | `src/iniciar.py --n 3 / 8 / 15` gera `nos.json` e sobe os processos sem tocar no código. |
| R4 | Ordem total | `ordem_total.py`: todos entregam na ordem do `num_seq` do líder → fila global idêntica. |
| R5 | Tela do nó | `interface.py`: enviar p/ nó, enviar p/ grupo, ordem local, ordem global, relógio vetorial, buffer. |
| R6 | Estado global | `snapshot.py`: comando de menu dispara Chandy-Lamport e exibe a fotografia. |
| R7 | Relatório | Documento à parte, usando as seções deste plano como base. |
| R8 | Eleição de líder | `eleicao.py`: algoritmo do anel + demonstração de reeleição ao matar o líder. |

---

## 3. Arquitetura

### 3.1 Processos e rede

```
   Processo nó 1            Processo nó 2            ...          Processo nó 15
 +--------------+         +--------------+                      +--------------+
 | Tkinter      |         | Tkinter      |                      | Tkinter      |
 | Núcleo       |         | Núcleo       |                      | Núcleo       |
 | Rede (UDP)   |         | Rede (UDP)   |                      | Rede (UDP)   |
 +------+-------+         +------+-------+                      +------+-------+
        |                        |                                    |
        +------------------------+------ grupo multicast --------------+
                          224.1.1.1 : 5007
```

- Cada nó é um **processo independente** com estado em memória privada.
- Todos entram no mesmo grupo multicast. **Todo datagrama chega a todos**; o campo
  `destino` (`"todos"` ou um id) diz quem deve processar.
- `nos.json` é lido só na inicialização: dá a lista de ids e o total `N`. Não é
  canal de coordenação.

### 3.2 Threads dentro de um nó

| Thread | Arquivo | Papel |
|--------|---------|-------|
| Receptora | `rede.py` | `recvfrom` no socket multicast, `json.loads`, põe o dict em `fila_recebidas` (`queue.Queue`). |
| Núcleo | `nucleo.py` | Consome `fila_recebidas`, despacha por `tipo`, roda tarefas periódicas (heartbeat, timeouts, lacunas). Toda alteração de estado sob `trava_estado` (`threading.Lock`). Empurra eventos para `fila_interface`. |
| Interface (principal) | `interface.py` | `janela.mainloop()`. `janela.after(100, drenar)` lê `fila_interface` e atualiza os painéis. Botões chamam métodos do núcleo (que pegam o lock rapidinho). |

Estruturas compartilhadas entre threads (receptora, núcleo, interface) são só as
duas filas e o estado protegido pelo `trava_estado` — **dentro** do processo, o que
é permitido; entre nós, só rede.

---

## 4. Formato de mensagem (JSON)

Um dict serializado com `json.dumps`. Campos:

| Campo | Quando aparece | Significado |
|-------|----------------|-------------|
| `tipo` | sempre | `CHAT_PEDIDO`, `CHAT_ENTREGA`, `HEARTBEAT`, `ELEICAO`, `COORDENADOR`, `RETRANSMITIR`, `MARCADOR`, `RESULTADO_SNAPSHOT`. |
| `origem` | sempre | Id do nó que **gerou** o conteúdo (no `CHAT_ENTREGA` continua sendo o autor, não o líder). |
| `destino` | sempre | Id do nó alvo ou `"todos"`. |
| `seq_origem` | mensagens de chat | Contador FIFO por origem, para detectar perda/lacuna sobre UDP. |
| `relogio_vetorial` | mensagens de chat | Cópia do vetor da origem no momento do envio (para causalidade/tela). |
| `grupo` | mensagens de chat | `"geral"`, `"priv-a-b"` (a < b), ou o id de um grupo nomeado `"g-<criador>-<seq>"`. |
| `id_msg` | mensagens de chat | `"{origem}:{seq_origem}"`. Identifica a mensagem para casar pedido/entrega e remover duplicatas. |
| `nome_origem` | mensagens de chat | Nome amigável do autor (ou `null`). Só para exibição na tela; não coordena nada. |
| `num_seq` | só `CHAT_ENTREGA` | Número de sequência **global** atribuído pelo líder. Define a ordem total. |
| `carimbado_por` | só `CHAT_ENTREGA` | Id do líder que sequenciou (para o log/relatório). |
| `payload` | sempre | Dados do tipo. Numa mensagem de chat é `{"texto": "..."}` **ou** uma ação de grupo `{"acao": "criar_grupo", "nome": "...", "membros": [...]}`. Em controle: `{"ids_vistos": [...]}`, `{"lider": 7, "proximo_num_seq": 42}`, etc. |

`mensagem.py` centraliza a criação (`montar(...)`), a serialização e as constantes
de `tipo`, para não espalhar strings soltas pelo código.

---

## 5. Relógio vetorial (`relogio.py`)

Cada nó `i` mantém `vetor` = dict `{id_no: contador}` com uma entrada por nó do
`nos.json`. Regras (política escolhida e **documentada**, como o roteiro pede):

- **Evento de envio** (o nó manda uma mensagem de chat): `vetor[meu_id] += 1`;
  anexa uma cópia do vetor à mensagem.
- **Evento de entrega** (a mensagem sai do buffer e aparece na tela): para cada `j`,
  `vetor[j] = max(vetor[j], vetor_recebido[j])`; depois `vetor[meu_id] += 1`.
- A **recepção crua** de um datagrama não mexe no vetor — primeiro a mensagem
  precisa ser entregue na ordem do `num_seq`.

Funções:
- `evento_envio()` → devolve a cópia do vetor para anexar.
- `ao_entregar(vetor_recebido)` → funde e incrementa.
- `concorrentes(vetor_a, vetor_b)` → `True` se nem `a <= b` nem `b <= a`
  (usado só para pintar "concorrente" na tela e montar o exemplo do relatório).
- `__str__` → algo como `[1:3, 2:1, 3:0]` para a tela.

**O vetor não decide entrega.** Quem decide a ordem total é o `num_seq` (Seção 6).
O vetor serve para: mostrar o relógio atual na tela, marcar quais mensagens são
concorrentes, e alimentar o exemplo numérico do relatório (Seção 15).

---

## 6. Ordem total — sequenciador pelo líder (`ordem_total.py`)

### 6.1 Papéis

O sequenciador ordena **tudo que precisa de ordem total**: mensagens de chat e
pedidos de criação de grupo (`payload.acao`). É o mesmo caminho para os dois.

Um mesmo módulo, dois papéis conforme `eleicao.sou_lider`:

- **Sequenciador** (só o líder): recebe os `CHAT_PEDIDO`, atribui `num_seq` crescente,
  redifunde a mensagem completa como `CHAT_ENTREGA`, guarda histórico
  `historico_por_num_seq` para responder retransmissões.
- **Entrega ordenada** (todo nó, inclusive o líder): recebe os `CHAT_ENTREGA`,
  guarda em `pendentes` (dict `{num_seq: mensagem}`) e entrega em ordem estrita a
  partir de `proximo_num_seq_esperado`.

### 6.2 Fluxo de uma mensagem

1. **Nó A envia "oi" no grupo G.**
   `relogio.evento_envio()`; `seq_origem_local += 1`; monta `CHAT_PEDIDO`
   (`id_msg = "A:seq"`, `grupo = G`, `payload = {"texto": "oi"}`, `destino = lider`).
   Difunde por multicast. Guarda a mensagem em `enviadas_recentes` (para retransmitir
   se pedirem) e em `aguardando_carimbo[id_msg]` com o instante do envio.
2. **Todos recebem o `CHAT_PEDIDO`.** Só o líder age:
   - Se `id_msg` já foi sequenciado → reenvia o `CHAT_ENTREGA` do histórico (pedido
     duplicado por retransmissão).
   - Senão: `num_seq = proximo_num_seq; proximo_num_seq += 1`. Monta `CHAT_ENTREGA`
     (cópia do pedido + `num_seq` + `carimbado_por = lider`, `destino = "todos"`).
     Difunde. Guarda em `historico_por_num_seq[num_seq]`.
3. **Cada nó recebe o `CHAT_ENTREGA`:**
   - `num_seq < proximo_num_seq_esperado` → duplicata, ignora.
   - Senão → `pendentes[num_seq] = mensagem`; chama `tentar_entregar()`.
   - Remove `id_msg` de `aguardando_carimbo` (o autor viu sua mensagem voltar).
4. **`tentar_entregar()`** — enquanto `proximo_num_seq_esperado` estiver em `pendentes`:
   - `mensagem = pendentes.pop(proximo_num_seq_esperado)`.
   - `relogio.ao_entregar(mensagem["relogio_vetorial"])`.
   - Acrescenta à **fila global** (lista ordenada por `num_seq`, idêntica em todos).
   - Se `payload` tem `acao` (`criar_grupo`, …) → aplica em `grupos.py` (registra o
     grupo) em vez de mostrar texto.
   - Senão, se o nó é membro de `mensagem["grupo"]` → acrescenta o texto à vista
     daquela conversa e à **ordem local** (evento observado).
   - `proximo_num_seq_esperado += 1`.

Como todos os nós recebem todos os `CHAT_ENTREGA` e entregam na ordem `1, 2, 3, …`,
**a fila global é idêntica em todos** (R4). A privacidade não muda a ordem: um nó
que não é membro de `priv-2-5` ainda registra o `num_seq` na fila global, só não
mostra o texto.

### 6.3 Buracos e travas

- **Falta o `CHAT_ENTREGA` esperado** (chegou `num_seq` maior, o esperado não vem
  em `T_RETRANSMISSAO ≈ 1 s`): envia `RETRANSMITIR` ao líder com
  `payload = {"num_seq": faltante}`. O líder reenvia do histórico.
- **Falta o `CHAT_PEDIDO`** (o autor não vê o `CHAT_ENTREGA` do seu `id_msg` em
  `T_RETRANSMISSAO`): o autor **reenvia o `CHAT_PEDIDO`**.
- **Lacuna por origem** (recebeu `seq_origem = k+2` de A, falta `k+1`): pede
  `RETRANSMITIR` a A com `payload = {"seq_origem": k+1}`; A reenvia de
  `enviadas_recentes`.
- **Duplicatas**: `id_msg` já entregue → ignora; `num_seq` já passado → ignora.

### 6.4 Exemplo numérico (dois nós chegam à mesma ordem)

3 nós `{1, 2, 3}`, líder = 3, grupo `geral`, vetores começam `[1:0, 2:0, 3:0]`.

| Passo | Evento | Vetor da origem | Ação do líder |
|-------|--------|-----------------|---------------|
| 1 | Nó 1 envia "A" | `[1:1, 2:0, 3:0]` | — |
| 2 | Nó 2 envia "B" (concorrente com A) | `[1:0, 2:1, 3:0]` | — |
| 3 | Líder recebe "B" antes de "A" (rede reordenou) | | `num_seq(B) = 1` |
| 4 | Líder recebe "A" | | `num_seq(A) = 2` |
| 5 | Nós 1, 2 e 3 entregam | | ordem global = **[B, A]** nos três |

`vetor_B = [1:0, 2:1, 3:0]` e `vetor_A = [1:1, 2:0, 3:0]` são **concorrentes**
(nenhum ≤ o outro) → foi o `num_seq` do líder que desempatou. Isso ilustra
"ordem causal (parcial) × ordem total".

**Caso causal:** nó 1 envia "A" (`[1:1,2:0,3:0]`). Nó 2 entrega "A"
(vetor vira `[1:1,2:1,3:0]`) e só então envia "C" (`[1:1,2:2,3:0]`). Agora
`vetor_A < vetor_C` → A **precede causalmente** C. O sequenciador respeita isso
naturalmente: C só foi enviada depois de A ser entregue, então "A" recebe `num_seq`
menor. Qualquer ordem total válida põe A antes de C.

---

## 7. Grupos: `geral`, grupos nomeados e conversas privadas — `grupos.py`

`RegistroGrupos` guarda, por **id de grupo**, um registro `{nome, tipo, membros}`.

### 7.1 Três tipos de grupo

- **`geral`** — público, todos os nós do `nos.json` são membros desde o início. É
  o "grupo com N participantes". Não precisa ser criado.
- **Grupo nomeado** — id `g-<criador>-<seq>`, um **nome amigável** escolhido pelo
  usuário e uma **lista de membros escolhida na criação**. Ex.: id `g-3-1`, nome
  "Trabalho SD", membros `{1, 3, 5}`. O criador entra automaticamente.
- **`priv-a-b`** (a < b) — privado, 2 membros fixos `{a, b}`, **codificados no id**.
  Atalho para um grupo de 2 pessoas, sem nome. Quem abre "conversa privada" registra
  localmente; o outro participante registra ao receber a primeira mensagem
  (`garantir_privado` deriva os membros do id) — não precisa abrir antes.

### 7.2 Criar um grupo nomeado

1. No nó `C`, o usuário clica em **"Criar grupo"**, digita o nome e marca os
   membros numa lista com todos os ids do `nos.json` (o próprio `C` entra sozinho).
2. O nó monta um pedido com
   `payload = {"acao": "criar_grupo", "nome": ..., "membros": [...]}` e o envia
   **pelo mesmo caminho de uma mensagem de chat** (`CHAT_PEDIDO` → líder →
   `CHAT_ENTREGA`), com `id_msg = "C:seq"` e `grupo = "g-C-seq"` (o id do novo
   grupo, derivado do `id_msg`).
3. Ao **entregar** esse item na ordem do `num_seq`, cada nó chama
   `registro.criar(id_grupo, nome, membros)`. Como a criação recebe um `num_seq` e
   toda mensagem para o grupo recebe um `num_seq` **maior**, todos os nós registram
   o grupo antes de qualquer mensagem dele — a membresia converge sem caso especial
   e sem corrida "mensagem antes da criação".
4. Nos nós membros, a nova conversa aparece no seletor com o nome amigável; o
   primeiro item da conversa é "grupo criado por C — membros: …".

### 7.3 Enviar e privacidade

- O seletor "Conversa" lista `geral`, cada grupo nomeado de que o nó é membro e
  cada conversa privada da qual ele participa. Enviar funciona igual para todos.
  O painel "Mensagens do chat" mostra só a conversa selecionada.
- Na entrega, o texto só vai para a vista da conversa e a ordem local se
  `registro.sou_membro(grupo)`. Um nó **não-membro** ainda registra o `num_seq` na
  fila global (a ordem total não muda), mas não vê o conteúdo — e, como aquela
  conversa nem aparece no seletor dele, a tela não mostra "restrito".
- Privacidade é **lógica**: sem criptografia, o datagrama chega fisicamente a
  todos os nós do multicast. Limitação registrada no relatório.

### 7.4 Extensão opcional

Entrar/sair de um grupo já existente (`payload = {"acao": "entrar_grupo", ...}` /
`"sair_grupo"`), pelo mesmo caminho sequenciado. Não é necessário para R1/R2 — a
seleção de membros na criação já cobre o pedido.

---

## 8. Eleição — algoritmo do anel (`eleicao.py`)

### 8.1 Liveness

- **Todo nó** difunde `HEARTBEAT` a cada `INTERVALO_HEARTBEAT ≈ 2 s`, com
  `payload = {"lider_conhecido": id, "num_seq_visto": maior_num_seq}`.
- Cada nó mantém `ultimo_heartbeat = {id_no: instante}`.
- Um nó é considerado **caído** se `agora - ultimo_heartbeat[id] > T_FALHA ≈ 6 s`
  (3× o intervalo).

### 8.2 Anel lógico

- Anel = ids em ordem crescente, circular. `proximo_ativo(id)` = menor id ainda
  vivo maior que `id`; se não houver, o menor id vivo de todos (dá a volta).

### 8.3 Passo a passo

1. Nó percebe `agora - ultimo_heartbeat[lider_atual] > T_FALHA` → **inicia eleição**:
   monta `ELEICAO` com `payload = {"ids_vistos": [meu_id]}`,
   `destino = proximo_ativo(meu_id)`. Difunde.
2. Nó recebe `ELEICAO` e é o `destino`:
   - Se `meu_id` **já está** em `ids_vistos` → a mensagem deu a volta. Novo líder =
     `max(ids_vistos)`. Difunde `COORDENADOR` com
     `payload = {"lider": max_id, "proximo_num_seq": maior_num_seq_visto + 1}`,
     `destino = "todos"`.
   - Senão → acrescenta `meu_id` a `ids_vistos`, repassa `ELEICAO` para
     `proximo_ativo(meu_id)`.
3. Nó recebe `COORDENADOR` → `lider_atual = payload["lider"]`. Se eu sou o novo
   líder, assumo o papel de sequenciador com
   `proximo_num_seq = payload["proximo_num_seq"]`.

### 8.4 Continuidade da numeração

O novo líder retoma a numeração em `maior_num_seq_visto + 1`. Como todo nó viu
todos os `CHAT_ENTREGA`, esse valor é conhecido. Autores que tenham
`CHAT_PEDIDO` sem `CHAT_ENTREGA` correspondente há mais de `T_RETRANSMISSAO`
**reenviam o pedido**, e o novo líder os sequencia. Mensagens que o líder antigo
carimbou mas que ninguém recebeu antes da queda podem se perder — limitação
registrada no relatório.

### 8.5 Eleição inicial

No boot, sem heartbeats ainda, cada nó assume `lider_atual = max(todos_os_ids)`.
Quando esse nó sobe e manda heartbeat, confirma. Se o maior id nunca sobe, após
`T_FALHA` roda-se o anel e elege-se o maior id **ativo**. Assim dá para iniciar a
simulação com 3, 8 ou 15 nós sem precisar subir todos.

### 8.6 Demonstração (R8)

Botão **"Simular queda"** encerra o processo do líder. Após `T_FALHA` os demais
detectam, o anel circula, o `COORDENADOR` anuncia o novo líder (o maior id
restante) e o chat volta a ordenar. O log da tela mostra cada passo.

---

## 9. Estado global — Chandy-Lamport (`snapshot.py`)

### 9.1 Canais lógicos sobre multicast

Para o nó `i`, há **um canal de entrada por outro nó `j`**, identificado pelo campo
`origem`. A ordem FIFO desse canal é reconstruída pelo `seq_origem` das mensagens
de chat de `j`. Isso é o que Chandy-Lamport precisa (canais FIFO), sem usar
unicast.

### 9.2 O que é "estado" aqui

- **Estado do nó**: `proximo_num_seq_esperado` (quantas mensagens já entregou),
  cópia do `vetor`, `lider_atual`, tamanho de `pendentes`, e os últimos K itens da
  fila global.
- **Estado de um canal `j`**: lista das mensagens de chat de `j` recebidas
  **entre** o registro do estado local e a chegada do `MARCADOR` de `j`.

### 9.3 Passo a passo

1. **Iniciador** (o líder, via botão; qualquer nó pode iniciar): registra o próprio
   estado, marca "gravando" todos os canais dos outros nós, difunde `MARCADOR`
   (`payload = {"id_snapshot": <origem>-<contador>, "iniciador": id}`).
2. **Primeiro `MARCADOR` de um snapshot novo**: o nó registra seu estado agora; o
   canal por onde o marcador veio fica **vazio**; passa a gravar os demais canais;
   difunde `MARCADOR` uma vez.
3. **`MARCADOR` seguinte do mesmo snapshot, vindo do canal `j`**: para de gravar
   `j`; o estado do canal `j` é o que foi gravado.
4. Quando o nó recebeu `MARCADOR` de **todos** os outros `N-1` nós, seu snapshot
   local está completo. Ele difunde `RESULTADO_SNAPSHOT` com seu estado e os
   estados de canal.
5. Qualquer nó que junte os `N` `RESULTADO_SNAPSHOT` monta a **fotografia global**
   e a exibe (o iniciador sempre exibe; os outros exibem quando recebem tudo).

### 9.4 Nota prática

Em `localhost` a entrega é quase instantânea, então os canais normalmente aparecem
vazios. Para mostrar um canal **não-vazio** no relatório, dispare o snapshot
durante uma rajada de mensagens (botão "enviar" repetido) ou com um `time.sleep`
opcional de ~0,3 s no envio (uma constante em `configuracao.py`).

---

## 10. Confiabilidade sobre UDP multicast

| Problema do UDP | Tratamento |
|-----------------|------------|
| Perda de `CHAT_ENTREGA` | Lacuna em `num_seq` → `RETRANSMITIR` ao líder → líder reenvia do histórico. |
| Perda de `CHAT_PEDIDO` | Autor não vê seu `CHAT_ENTREGA` em `T_RETRANSMISSAO` → reenvia o pedido. |
| Perda no meio de um fluxo por origem | Lacuna em `seq_origem` → `RETRANSMITIR` à origem → origem reenvia de `enviadas_recentes`. |
| Duplicação | Dedup por `id_msg` na entrega; `num_seq` já passado é ignorado. |
| Reordenação | O buffer `pendentes` só entrega na ordem de `num_seq`. |
| Heartbeat perdido | `T_FALHA` = 3× o intervalo antes de declarar queda. |

`enviadas_recentes` e `historico_por_num_seq` são `deque` com limite (~200
mensagens) — não crescem sem parar.

---

## 11. A tela do nó (R5) — `interface.py`

Layout de uma janela (uma por nó):

```
+---------------------------------------------------------------+
| Nó 3 - Carol   |   Papel: comum                               |
| Nome deste nó: [ Carol        ] [ Definir nome ]              |
+----------------------------+--------------------------------- +
| Conversa: [ Trabalho SD [membros: No 1, No 3, No 5] v ]        |
|   (geral (todos) / Trabalho SD [.] / conversa privada com No 5)|
| [ digite a mensagem      ] | Relógio vetorial: [1:4, 2:2, 3:5]|
| [ Enviar ]                 | Próx. num_seq esperado: 12       |
| [ Criar grupo ] [ Nova conversa privada ]  Buffer pendentes: 1 |
+----------------------------+----------------------------------+
| ORDEM LOCAL (o que este nó emitiu/observou)                   |
|  envio    G  "oi"            v=[1:4,2:2,3:5]                   |
|  entrega  #10 de 7 "e ai"    v=[1:4,2:2,3:5]                   |
+---------------------------------------------------------------+
| MENSAGENS DO CHAT - Trabalho SD [membros: No 1, No 3, No 5]    |
|  #05  -- grupo "Trabalho SD" criado por Carol (No 3) (memb...) |
|  #08  Alice (No 1): bom dia                                   |
|  #10  Carol (No 3): e ai                                      |
|  (trocar de conversa no seletor troca o que aparece aqui)     |
+---------------------------------------------------------------+
| LOG DO SISTEMA                                                |
|  eleição iniciada por nó 4 ... COORDENADOR: líder = 7         |
|  MARCADOR recebido de 7 (snapshot 7-1)                        |
+---------------------------------------------------------------+
| [ Capturar estado global ]  [ Forçar eleição ]  [ Simular queda ] |
+---------------------------------------------------------------+
```

Elementos mínimos exigidos pelo R5, todos presentes:
- **Enviar para nó específico** → "Nova conversa privada" escolhe o id e abre
  `priv-a-b`.
- **Enviar para o grupo** → seletor em `geral` + Enviar.
- **Criar grupo** → botão "Criar grupo": campo de nome + lista de checkboxes com
  todos os ids do `nos.json` para escolher os membros. Ao confirmar, o grupo passa
  a aparecer no seletor "Conversa" dos nós membros.
- **Ordem local** → painel com cada envio e cada entrega observados por este nó, na
  ordem em que aconteceram, com o vetor no momento.
- **Ordem global** → painel "Mensagens do chat": as mensagens da conversa
  selecionada, na ordem do `num_seq`. Para `geral` (todos são membros) a lista é
  idêntica em todos os nós — é a evidência da ordem total.
- Extras sugeridos pelo roteiro: relógio vetorial atual e tamanho do buffer.

Atualização sem travar o Tkinter: o núcleo põe eventos (`"entrega"`, `"lider"`,
`"snapshot"`, `"log"`) em `fila_interface`; `janela.after(100, drenar)` consome e
repinta.

---

## 12. Módulos e arquivos

Um arquivo por classe/responsabilidade. Cada arquivo curto e focado.

Organização em pastas (todos os comandos rodam a partir da raiz do projeto):

```
raiz/
├── src/       todo o código (os módulos abaixo + interface.py, no.py, iniciar.py)
├── testes/    teste.py
├── docs/      manual_de_uso.md, plano_implementacao.md, roteiro.pdf
└── nos.json   gerado por src/iniciar.py (ou pelos testes)
```

`src/` é uma pasta plana (sem `__init__.py`): como o Python põe a pasta do script
em `sys.path`, os `import` entre os módulos continuam simples (`from eleicao import
...`). Só `src/iniciar.py` e `testes/teste.py` montam o caminho absoluto até
`src/no.py` para chamar o `subprocess`.

| Arquivo (em `src/`, salvo indicação) | Conteúdo |
|---------|----------|
| `iniciar.py` | Gera `nos.json` para `N` nós e sobe `N` processos `no.py` (via `subprocess`), cada um em sua janela. |
| `no.py` | Entrada de um nó: lê `--id`, `--nome` (opcional, só exibição) e `--config`, cria `Nucleo` e `Janela`, inicia as threads, chama `mainloop()`. Com `--sem-interface --script <arq> --saida <arq>` executa um roteiro de comandos e grava o estado final (usado nos testes). |
| `../testes/teste.py` | Sobe vários nós de verdade (processos separados), cada um com um roteiro, e compara as saídas: ordem total idêntica, criação de grupo, queda do líder, snapshot. |
| `configuracao.py` | Carrega `nos.json`; expõe `ids`, `N`, `grupo_multicast`, `porta`; constantes (`INTERVALO_HEARTBEAT`, `T_FALHA`, `T_RETRANSMISSAO`, `TTL`, atraso opcional de envio). |
| `mensagem.py` | Constantes de `tipo`; `montar(...)`, `serializar(dict)`, `desserializar(bytes)`. |
| `rede.py` | Socket multicast de envio e de recepção (`SO_REUSEADDR`, `IP_ADD_MEMBERSHIP`, TTL); `enviar(dict)`; thread receptora → `fila_recebidas`. |
| `relogio.py` | `RelogioVetorial`: `evento_envio`, `ao_entregar`, `concorrentes`, `copia`, `__str__`. |
| `grupos.py` | `RegistroGrupos`: `geral`, grupos nomeados (`id`, `nome`, `membros`), `priv-a-b`; `criar`, `abrir_privado`, `sou_membro`, `membros`, `nome_de`, `conversas_visiveis`. |
| `ordem_total.py` | `OrdemTotal`: papel sequenciador (líder) + papel entrega ordenada (todos); `pendentes`, `proximo_num_seq_esperado`, `tentar_entregar` (mensagem de chat **ou** ação de grupo), retransmissão. |
| `eleicao.py` | `Eleicao`: heartbeats, `ultimo_heartbeat`, `proximo_ativo`, trata `ELEICAO` / `COORDENADOR`, expõe `lider_atual` e `sou_lider`. |
| `snapshot.py` | `Snapshot`: inicia, trata `MARCADOR`, grava canais, agrega `RESULTADO_SNAPSHOT`, formata a fotografia. |
| `nucleo.py` | `Nucleo`: junta os módulos; laço de despacho por `tipo`; timers; `trava_estado`; API para a interface (`enviar_chat`, `criar_grupo`, `abrir_privada`, `capturar_estado`, `forcar_eleicao`, `simular_queda`); alimenta `fila_interface`. |
| `interface.py` | `Janela` (Tkinter): layout da Seção 11, `after(100)`, diálogo de "Criar grupo" (nome + checkboxes de membros), botões chamando o núcleo. |

`nos.json` é gerado, não versionado como código.

---

## 13. Ambiente de execução

### 13.1 `nos.json` (catálogo estático)

```json
{
  "grupo_multicast": "224.1.1.1",
  "porta_grupo": 5007,
  "nos": [
    {"id": 1, "host": "127.0.0.1", "porta": 5001},
    {"id": 2, "host": "127.0.0.1", "porta": 5002},
    {"id": 3, "host": "127.0.0.1", "porta": 5003}
  ]
}
```

`host`/`porta` são só catálogo (tudo é multicast); ficam no arquivo porque o
roteiro pede a tabela de endereços no relatório.

### 13.2 Subir os nós

- `python src/iniciar.py --n 3` → gera `nos.json` com 3 nós e abre 3 janelas.
- `python src/iniciar.py --n 8` e `--n 15` → idem (requisito R3, sem tocar no código).
- Manual: `python src/iniciar.py --n 3 --apenas-config` gera o `nos.json`; depois
  `python src/no.py --id 3 --config nos.json` em cada terminal.

O `nos.json` é gerado em cada execução e não é versionado (está no `.gitignore`).

Na mesma máquina, `SO_REUSEADDR` (e `SO_REUSEPORT` onde existir) permite vários nós
na mesma porta multicast; TTL baixo (1–2).

---

## 14. Convenções de código

- Python 3, **só biblioteca padrão**.
- Nomes **descritivos em português**: `socket_recepcao`, `proximo_num_seq_esperado`,
  `trava_estado`, `registrar_evento_local`, `proximo_ativo`. Nada de `s`, `p`, `x`,
  `_s`. Variáveis de laço curtas só quando triviais (`for membro in grupo`).
- Comentário de 1 linha no topo de cada função dizendo o que ela faz.
- Comentar o **porquê** de trechos não óbvios (condição de entrega, wrap do anel,
  política de incremento do vetor).
- Uma classe por arquivo; funções curtas (quebrar quando passar de ~30 linhas e
  fizer duas coisas).
- Sem bibliotecas externas, sem padrões de projeto além do necessário — as classes
  aqui são só "estado + operações".
- Constantes (endereços, intervalos, timeouts) juntas no topo de `configuracao.py`.
- Sem emojis no código nem nos logs.

---

## 15. Cenários de teste e evidências (para o relatório)

| # | Cenário | O que provar |
|---|---------|--------------|
| 1 | 3 nós, `geral`, duas mensagens quase simultâneas | A fila global (`num_seq`) é idêntica nos 3; as duas são concorrentes pelo vetor. |
| 2 | Dependência causal (A → C, B concorrente) | Vetores mostram `A < C` e `B ∥ A`; a ordem total põe A antes de C. |
| 3 | Conversa privada nó 2 ↔ nó 5, com 8 nós no ar | Os outros 6 registram o `num_seq` mas exibem `"[mensagem de grupo restrito]"`. |
| 3b | Nó 3 cria o grupo "Equipe" com membros `{1, 3, 5}` (8 nós no ar) | Os nós 1/3/5 veem a conversa e as mensagens; os outros 5 veem `"[mensagem de grupo restrito]"` na ordem global. Todos registram o grupo no mesmo `num_seq`. |
| 4 | Queda do líder (maior id) durante o chat | Anel elege o próximo maior id; log mostra `ELEICAO` → `COORDENADOR`; chat volta. |
| 5 | Snapshot com 15 nós durante rajada | Fotografia global consistente: `num_seq` entregue por nó, vetores, mensagens de canal. |
| 6 | Subir com 3, depois 8, depois 15 (`--n`) | Mesmo código; comunicação de grupo funciona nos três tamanhos. |
| 7 | Perda simulada de um `CHAT_ENTREGA` (descartar 1 datagrama) | `RETRANSMITIR` ao líder recupera; a ordem final não muda. |

---

## 16. Cronograma até 09/09/2026

| Data | Entregar funcionando |
|------|----------------------|
| **06/09 (hoje)** | `configuracao.py`, `mensagem.py`, `rede.py`, `iniciar.py`: dois nós trocam "olá" por multicast. `relogio.py`. Esqueleto de `interface.py`. |
| **07/09** | `ordem_total.py` (sequenciador + entrega) e `eleicao.py` (heartbeat + anel) integrados no `nucleo.py`. `grupos.py` com `geral`, grupos nomeados (criar + escolher membros) e privados. Tela com ordem local/global e diálogo "Criar grupo". Testar 3 e 8 nós. Cenários 1, 2, 3, 3b. |
| **08/09** | `snapshot.py`; cenários 4–7; teste com 15 nós; escrever o relatório. |
| **09/09** | Revisão final, checklist do roteiro (Seção 12), submissão via AVA. |
| 10–15/09 | Slides e ensaio do seminário. |
| **16/09** | Apresentação (Entrega 2). |

---

## 17. Limitações conhecidas (registrar no relatório, Seção 10.6)

- UDP/multicast pode perder, duplicar e reordenar; mitigamos com `seq_origem`,
  detecção de lacuna e retransmissão sob demanda, mas não há garantia absoluta.
- O sequenciador é ponto crítico; a queda é tratada com reeleição em anel, mas
  mensagens carimbadas e não propagadas na janela da queda podem se perder.
- Privacidade é lógica (o app filtra); sem criptografia, todo datagrama chega a
  todos os nós do grupo multicast.
- Multicast entre máquinas depende da rede/roteador; os testes são em `localhost`.
- Em `localhost` os canais do snapshot quase sempre aparecem vazios; usamos rajada
  ou atraso opcional para demonstrar canal não-vazio.
