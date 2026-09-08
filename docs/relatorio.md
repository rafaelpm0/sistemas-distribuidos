# Relatório Técnico — Chat Distribuído

**Trabalho 1 — Comunicação de Grupo, Ordem Total de Mensagens e Estado Global**
Disciplina de Sistemas Distribuídos — UNIVALI — Prof. Ramicés dos Santos Silva
1º semestre de 2026 · Entrega 1 (código + relatório)

Documentos complementares no diretório `docs/`: `manual_de_uso.md` (como executar),
`plano_implementacao.md` (projeto detalhado por módulo) e `manual_teorico.md`
(fundamentação teórica aprofundada e roteiro do seminário).

**Equipe:**

1. Rafael Pinho Medeiros
2. Lucas Bitencourt
3. Vinícius Faraco Madalena
4. Guilherme Da Silva Schveitzer

---

## Sumário

1. [Descrição do problema e do tema escolhido](#1-descrição-do-problema-e-do-tema-escolhido)
2. [Papel de cada membro da equipe](#2-papel-de-cada-membro-da-equipe)
3. [Arquitetura da solução](#3-arquitetura-da-solução)
4. [Endereços de rede utilizados](#4-endereços-de-rede-utilizados)
5. [Simulações realizadas](#5-simulações-realizadas)
6. [Limitações do modelo escolhido](#6-limitações-do-modelo-escolhido)
7. [Tecnologia, linguagem e como executar](#7-tecnologia-linguagem-e-como-executar)
8. [Passo a passo da ordem total e da eleição de líder](#8-passo-a-passo-da-ordem-total-e-da-eleição-de-líder)
9. [Justificativa do estado global escolhido](#9-justificativa-do-estado-global-escolhido)

---

## 1. Descrição do problema e do tema escolhido

O trabalho pede um **sistema de comunicação de grupo** com vários nós (a quantidade
é configurável; testamos com até 15). Ele junta três assuntos da disciplina:
**relógios lógicos**, **ordem total das mensagens enviadas ao grupo** e **captura de
um estado global consistente**. Os nós só podem conversar por **mensagens de rede**
— não vale usar memória, banco de dados, arquivo ou variável compartilhada para
coordená-los. A única exceção é um arquivo de configuração fixo (`nos.json`), lido
só quando o nó inicia, que serve de lista de endereços.

**Tema escolhido: chat distribuído.** Cada nó é um participante, executado como um
**processo independente do sistema operacional**, com estado em memória privada. O
sistema oferece:

- **Mensagem de grupo** (`geral`): difusão para todos os participantes.
- **Grupos nomeados**: qualquer nó cria um grupo, dá um nome e escolhe os membros.
- **Conversa privada**: entre exatamente dois nós.
- **Entrega ordenada (ordem total)**: as mensagens de grupo aparecem na **mesma
  sequência em todos os participantes**.
- **Ordem local × ordem global**: cada nó exibe o que ele emitiu/entregou e a fila
  global de mensagens por número de sequência.
- **Estado global**: um comando dispara a captura de uma fotografia consistente.
- **Eleição de líder**: se o líder cai, os nós elegem outro automaticamente.

Mapa dos requisitos do roteiro:

| # | Requisito | Onde é atendido |
|---|-----------|-----------------|
| R1 | Comunicação de grupo (multicast) | `rede.py` + grupo `224.1.1.1:5007` |
| R2 | Tema (chat: privada, grupo, criar grupo) | `nucleo.py`, `grupos.py`, `interface.py` |
| R3 | Nº de nós configurável, ≥ 15, sem alterar código | `iniciar.py --n 3 / 8 / 15` |
| R4 | Ordem total | `ordem_total.py` (sequenciador pelo líder) |
| R5 | Tela do nó | `interface.py` (Tkinter) |
| R6 | Estado global | `snapshot.py` (Chandy-Lamport) |
| R7 | Relatório | este documento |
| R8 | Eleição de líder | `eleicao.py` (algoritmo do anel) |

---

## 2. Papel de cada membro da equipe

O trabalho foi dividido por **subsistema**: cada integrante cuidou de um conjunto
de módulos que se encaixam e das seções do relatório ligadas a eles. As
**decisões de projeto** (transporte, forma de garantir a ordem total, algoritmo de
eleição, mecanismo de estado global) foram discutidas e fechadas **por toda a
equipe** antes de começar a programar.

| Integrante | Subsistema | Módulos | Seções do relatório |
|------------|------------|---------|---------------------|
| Rafael Pinho Medeiros | Camada de rede e formato de mensagens | `rede.py`, `mensagem.py`, `configuracao.py` | 4 (endereços de rede), parte de 3 (fluxo), parte de 6 (limitações de UDP) |
|  Guilherme Da Silva Schveitzer | Ordem total (sequenciador) e relógio lógico | `ordem_total.py`, `relogio.py`, integração no `nucleo.py` | 8 (ordem total + exemplo numérico), parte de 3 |
| Vinícius Faraco Madalena | Coordenação: eleição de líder e estado global | `eleicao.py`, `snapshot.py` | 8 (eleição de líder), 9 (estado global), parte de 6 |
| Lucas Bitencourt | Aplicação, interface e validação | `grupos.py`, `interface.py`, `iniciar.py`, `no.py`, `testes/teste.py` | 1 (descrição), 3 (arquitetura e diagrama), 5 (simulações e prints), 7 (execução) |

Tarefas de todos: escrever e revisar o relatório, rodar juntos os cenários de
simulação e preparar o seminário (Entrega 2).

---

## 3. Arquitetura da solução

### 3.1 Componentes

**Entre nós:** N processos do SO, cada um com estado privado, todos inscritos no
**mesmo grupo multicast**. Todo datagrama chega a todos; o campo `destino` (`"todos"`
ou um id) diz quem deve processar. Não há unicast e não há estado compartilhado.

**Dentro de um nó:** três atividades concorrentes (a concorrência interna é
permitida; entre nós, só rede):

| Thread | Arquivo | Papel |
|--------|---------|-------|
| Receptora | `rede.py` | `recvfrom` no socket multicast, `json.loads`, coloca o dicionário em `fila_recebidas`. |
| Núcleo | `nucleo.py` | Consome `fila_recebidas`, despacha por `tipo`, roda tarefas periódicas (heartbeat, timeouts, detecção de lacuna). **Toda alteração de estado sob um único `Lock` (`trava_estado`).** Empurra eventos para `fila_interface`. |
| Interface | `interface.py` | `janela.mainloop()` do Tkinter; a cada 100 ms lê `fila_interface` e repinta. Botões chamam métodos do núcleo. |

Estruturas compartilhadas entre threads: apenas as duas filas (`queue.Queue`, já
thread-safe) e o estado protegido pelo `Lock`.

### 3.2 Diagrama

```
                    grupo multicast  224.1.1.1 : 5007   (TTL 1)
   ┌───────────────┬───────────────┬───────────────┬─────────────── ...
   │               │               │               │
┌──┴───────┐   ┌───┴──────┐   ┌────┴─────┐   ┌──────┴───┐
│  Nó 1    │   │  Nó 2    │   │  Nó 3    │   │  Nó 15   │   ← 1 processo do SO por nó
│ (proc.)  │   │ (proc.)  │   │ (proc.)  │   │ (proc.)  │
└──────────┘   └──────────┘   └──────────┘   └──────────┘

Dentro de um nó:

   rede (UDP multicast)
        │  recvfrom + json.loads
        ▼
   ┌──────────────┐   fila_recebidas   ┌──────────────────────────────┐
   │  thread      │ ─────────────────▶ │  thread NÚCLEO                │
   │  RECEPTORA   │                    │  laço: despacha por 'tipo'    │
   └──────────────┘                    │  + heartbeat / timeouts       │
                                       │  estado sob trava_estado      │
   ┌──────────────┐   fila_interface   │  relógio vetorial | grupos    │
   │  thread      │ ◀───────────────── │  ordem_total | eleição        │
   │  INTERFACE   │   (eventos)        │  snapshot                     │
   │  (Tkinter)   │                    └──────────────┬───────────────┘
   └──────────────┘                                   │ rede.enviar (sendto)
        ▲  botões → métodos do núcleo                 ▼
        └──────────────────────────────────  grupo multicast
```

### 3.3 Fluxo de mensagens

Tipos de mensagem (JSON, módulo `mensagem.py`):

| Tipo | Direção | Uso |
|------|---------|-----|
| `CHAT_PEDIDO` | autor → líder | "sequencie esta mensagem de chat / ação de grupo" |
| `CHAT_ENTREGA` | líder → todos | mensagem completa já com `num_seq` global |
| `HEARTBEAT` | nó → todos | "continuo vivo" + líder conhecido |
| `ELEICAO` | nó → próximo do anel | mensagem de eleição circulando |
| `COORDENADOR` | novo líder → todos | anúncio do vencedor |
| `RETRANSMITIR` | nó → líder ou origem | pedido de retransmissão do que faltou (NAK) |
| `MARCADOR` | nó → todos | marcador de Chandy-Lamport |
| `RESULTADO_SNAPSHOT` | nó → todos | pedaço local da fotografia global |

O caminho de uma mensagem de chat: **`CHAT_PEDIDO` → o líder atribui `num_seq` →
`CHAT_ENTREGA` → todos entregam na ordem do `num_seq`** (detalhado na Seção 8).
Mensagens direcionadas (`ELEICAO`, `RETRANSMITIR`) também vão por multicast, com o
campo `destino` preenchido; quem não é o alvo descarta.

### 3.4 Justificativa da arquitetura

A decisão central foi **usar só multicast UDP**: um único grupo e um sequenciador
para a ordem total. Dois motivos:

**(a) O multicast deixa a comunicação de grupo simples.** Num chat, cada mensagem
precisa chegar a todos. O multicast IP já faz isso: um único `sendto` alcança o
grupo inteiro. Assim a camada de rede fica pequena (`rede.py` tem cerca de 60
linhas) — não precisamos abrir e manter uma conexão para cada nó, nem repetir o
envio nó a nó, nem tratar reconexão. Com unicast/TCP teríamos entrega confiável e
em ordem sem esforço, mas em troca de bem mais código e de um envio repetido para
cada destinatário.

**(b) A conversa privada também é um grupo.** Tratamos a conversa entre duas
pessoas como um **grupo de 2 membros** (`priv-a-b`): as mensagens vão pelo **mesmo
grupo multicast** e passam **pelo mesmo sequenciador**; o conteúdo privado só é
escondido na hora de mostrar na tela. Não abrimos um canal separado entre os dois
nós. Com isso há **um só jeito de transportar e um só jeito de ordenar** tudo —
chat geral, chat de grupo, chat privado, criação de grupo e mensagens de controle
seguem o mesmo caminho e pegam o `num_seq` da mesma fonte. Isso evita vários
problemas (por exemplo, uma mensagem privada e uma de grupo aparecerem em ordens
diferentes em nós diferentes) e faz a ordem total, a privacidade e o estado global
usarem a mesma base.

**Custo assumido:** UDP não é confiável (tratado na camada de ordenação — Seção 6)
e o sequenciador vira um ponto fraco (tratado com eleição de líder — Seção 8).

---

## 4. Endereços de rede utilizados

**Transporte: multicast UDP.**

| Item | Valor |
|------|-------|
| Faixa multicast IPv4 (classe D) | `224.0.0.0` – `239.255.255.255` |
| Endereço do grupo usado | `224.1.1.1` |
| Porta do grupo | `5007` |
| TTL | `1` (os datagramas não saem da máquina local — testes em `localhost`) |
| Socket de recepção | `SO_REUSEADDR` (+ `SO_REUSEPORT` onde existe), `bind(("", 5007))`, `IP_ADD_MEMBERSHIP` no grupo |
| Socket de envio | `IP_MULTICAST_TTL = 1` |

**Somente o par `224.1.1.1:5007` recebe `bind` e `IP_ADD_MEMBERSHIP`.** `SO_REUSEADDR`
(e `SO_REUSEPORT` quando disponível) permite que os N processos-nó na mesma máquina
escutem a mesma porta do grupo.

### Tabela de nós (catálogo `nos.json`)

O `nos.json` guarda, por nó, `id`, `host` e `porta` — mas **esses campos são só
catálogo / referência**: a comunicação é toda multicast e **nenhum socket faz
`bind` nas portas por nó**. O `iniciar.py` gera as portas como `5000 + id`.

| Id do nó | Host (catálogo) | Porta (catálogo, apenas referência) |
|----------|-----------------|-------------------------------------|
| 1  | 127.0.0.1 | 5001 |
| 2  | 127.0.0.1 | 5002 |
| 3  | 127.0.0.1 | 5003 |
| 4  | 127.0.0.1 | 5004 |
| 5  | 127.0.0.1 | 5005 |
| 6  | 127.0.0.1 | 5006 |
| 7  | 127.0.0.1 | 5007 * |
| 8  | 127.0.0.1 | 5008 |
| …  | 127.0.0.1 | 5000 + id |
| 15 | 127.0.0.1 | 5015 |

\* A porta de catálogo do nó 7 é `5007`, a mesma do grupo. Isso não atrapalha: as
portas por nó não são usadas — nenhum socket faz `bind` nelas, só o grupo
multicast recebe tráfego.

---

## 5. Simulações realizadas

Todos os cenários abaixo sobem **processos-nó de verdade** (`python src/no.py ...`),
que só trocam mensagens pela rede. As saídas foram capturadas do modo sem
interface (`--sem-interface --script <roteiro> --saida <arquivo.json>`), que grava
o estado final de cada nó (fila de entrega, relógio, líder, grupos, snapshot).

### Cenário 1 — Ordem total com mensagens quase simultâneas (5 nós)

Roteiro: os 5 nós (Alice…Ester) enviam uma saudação em `geral` quase ao mesmo
tempo; em seguida o nó 2 cria o grupo "TrabalhoSD" com membros {2, 3, 5} e manda
uma mensagem nele; o nó 1 abre conversa privada com o nó 3 e manda uma mensagem
privada.

**Fila de entrega — painel "Mensagens do chat" na conversa `geral`, nos 5 nós:**

```
 Nó 1 (Alice)            Nó 2 (Bruno)            Nó 3 (Carla) / Nó 4 / Nó 5
 #1  Alice (No 1): bom-dia      #1  Alice (No 1): bom-dia      (idêntico)
 #2  Bruno (No 2): ola          #2  Bruno (No 2): ola
 #3  Carla (No 3): oi           #3  Carla (No 3): oi
 #4  Diego (No 4): cheguei      #4  Diego (No 4): cheguei
 #5  Ester (No 5): presente     #5  Ester (No 5): presente
```

A fila interna completa (`ordem_global`), que inclui também as mensagens de grupo e
a privada, foi conferida como **exatamente igual nos 5 nós** (comparando o
`(num_seq, id_msg)` de todas as posições → `True`). O líder eleito no início (o de
maior id) é o **nó 5**, reconhecido por todos.

**Mesmo cenário, conversas restritas:**

- Nó 2 seleciona "TrabalhoSD [membros: No 2, No 3, No 5]" → vê `#6 -- grupo criado
  por Bruno (No 2) --` e `#8 Bruno (No 2): recado-do-grupo`. O `#7` não aparece
  (pertence à conversa privada 1–3).
- Nó 3 seleciona "conversa privada com No 1" → vê `#7 Alice (No 1): mensagem-privada`.
- **Conversas que cada nó consegue selecionar:**
  Nó 1 → `geral, priv-1-3` · Nó 2 → `geral, TrabalhoSD` ·
  Nó 3 → `geral, TrabalhoSD, priv-1-3` · **Nó 4 → só `geral`** ·
  Nó 5 → `geral, TrabalhoSD`.

O nó 4, que não participa de nenhum grupo restrito, registra os `num_seq` `#6`, `#7`
e `#8` na fila global (a **posição** existe em todos os nós — a ordem total não
muda), mas **não vê o conteúdo** e nem tem essas conversas no seletor.

### Cenário 2 — Queda do líder e reeleição pelo anel (5 nós)

Roteiro: os nós 1–4 enviam uma mensagem "antes-da-queda", o **nó 5 (líder) é
encerrado** (`cair`) por volta de t = 2,5 s, e depois os nós 1–4 enviam
"depois-da-queda".

```
No 1: lider=4 | #1..#4 antes-da-queda-{1..4}  #5..#8 depois-da-queda-{1..4}
No 2: lider=4 | #1..#4 antes-da-queda-{1..4}  #5..#8 depois-da-queda-{1..4}
No 3: lider=4 | #1..#4 antes-da-queda-{1..4}  #5..#8 depois-da-queda-{1..4}
No 4: lider=4 | #1..#4 antes-da-queda-{1..4}  #5..#8 depois-da-queda-{1..4}
No 5: lider=5 | #1..#4 antes-da-queda-{1..4}          (encerrou aqui)
```

Os 4 sobreviventes elegem o **nó 4** (maior id ativo), suas filas de entrega são
**idênticas** e os `num_seq` **continuam 1..8 sem buraco** apesar da troca de
líder.

### Cenário 3 — 15 nós, ordem total e estado global (suíte automatizada)

Executado por `python testes/teste.py`. Os 15 nós enviam uma mensagem cada; o nó 15
dispara o snapshot. Verificações:

```
Teste 3: 15 nos, ordem total e estado global (Chandy-Lamport)
  [ok  ] os 15 nos gravaram saida
  [ok  ] a ordem global e identica nos 15 nos
  [ok  ] as 15 mensagens foram entregues
  [ok  ] todos reconhecem o no 15 como lider
  [ok  ] ao menos um no montou a fotografia global
  [ok  ] a fotografia tem o estado dos 15 nos
```

### Cenário 4 — Fotografia global (snapshot de Chandy-Lamport)

No Cenário 1, o nó 5 dispara o snapshot após a rajada de mensagens. Fotografia
montada (um nó juntou os 5 `RESULTADO_SNAPSHOT`):

```
SNAPSHOT 5-<timestamp>
  No 1: entregou ate num_seq 7  relogio [1:7, 2:6, 3:3, 4:4, 5:5]  lider 5
  No 2: entregou ate num_seq 7  relogio [1:7, 2:7, 3:3, 4:4, 5:5]  lider 5
  No 3: entregou ate num_seq 7  relogio [1:7, 2:6, 3:7, 4:4, 5:5]  lider 5
  No 4: entregou ate num_seq 7  relogio [1:7, 2:6, 3:3, 4:7, 5:5]  lider 5
  No 5: entregou ate num_seq 7  relogio [1:7, 2:6, 3:3, 4:4, 5:7]  lider 5
```

Corte consistente: todos os nós concordam no líder e no ponto da fila global até
onde entregaram; os relógios vetoriais diferem apenas na própria posição (evento
local de entrega). Em `localhost` os canais aparecem vazios (a entrega é quase
instantânea) — para exibir um canal não-vazio no seminário, dispara-se o snapshot
durante uma rajada ou com `ATRASO_ENVIO > 0` em `configuracao.py`.

### Suíte automatizada completa

`python testes/teste.py` — **todas as verificações passam**:

```
Teste 1: ordem total, criacao de grupo e conversa privada (5 nos)   [7/7 ok]
Teste 2: queda do lider e reeleicao pelo anel (5 nos)               [5/5 ok]
Teste 3: 15 nos, ordem total e estado global (Chandy-Lamport)       [6/6 ok]
RESULTADO: todos os testes passaram.
```

---

## 6. Limitações do modelo escolhido

1. **UDP/multicast não é confiável.** Pode perder, duplicar e reordenar datagramas.
   Mitigamos com número de sequência por origem (`seq_origem`), detecção de lacuna e
   retransmissão sob demanda (NAK) — mas **não há garantia absoluta** de entrega.
   Multicast entre máquinas diferentes depende da rede/roteador; os testes são em
   `localhost` com TTL 1.

2. **O sequenciador é um ponto crítico** (custo da Abordagem B). A queda do líder é
   tratada com reeleição em anel e continuidade da numeração, mas mensagens que o
   líder **carimbou** e não conseguiu **propagar** na janela da queda podem se
   perder. Um sistema de produção replicaria o log por consenso (Raft/Paxos); está
   fora do escopo.

3. **A alternativa descartada (Abordagem A) é mais lenta.** A abordagem
   descentralizada (relógio vetorial + regra de desempate + espera por
   estabilidade) não tem ponto único de falha, mas para entregar uma mensagem cada
   nó precisa ter certeza de que nenhuma mensagem "menor" ainda vai chegar. Para
   isso ele tem de esperar notícia (uma mensagem ou um ACK) de **todos** os outros
   nós e ainda mandar sinais periódicos para não travar quando alguém fica quieto.
   Resultado: entrega mais demorada e mais mensagens de controle. Preferimos abrir
   mão da robustez a ponto único em troca de um código mais simples e de entrega
   mais rápida.

4. **Privacidade é lógica, não criptográfica.** O aplicativo não exibe mensagens de
   conversas de que o nó não participa, mas o datagrama chega fisicamente a todos os
   nós do grupo multicast.

5. **O snapshot supõe canais em ordem e sem perda.** Reconstruímos a ordem de cada
   canal pelo `seq_origem`; se um datagrama se perde durante o snapshot, aquele
   canal pode ficar incompleto.

6. **Detecção de falha imperfeita** (modelo assíncrono). Não há como distinguir com
   certeza um nó caído de um nó lento; um nó muito lento pode ser suspeitado e
   disparar uma eleição desnecessária. Usamos `T_FALHA = 3 × INTERVALO_HEARTBEAT`
   para reduzir falsos positivos.

7. **Sem recuperação.** Um nó que caiu não reingressa no meio da simulação.

8. **Nome do nó é cosmético.** Viaja junto de cada mensagem de chat (`nome_origem`)
   só para a tela mostrar "Alice (No 1)"; nenhuma decisão (ordem, eleição, snapshot)
   usa o nome — sempre o `id`.

---

## 7. Tecnologia, linguagem e como executar

### Tecnologia

- **Linguagem:** Python 3 (testado em 3.8).
- **Bibliotecas:** apenas a **biblioteca padrão** — `socket`, `struct`, `json`,
  `threading`, `queue`, `time`, `subprocess`, `argparse`, `tkinter`. **Nenhum
  `pip install`.**
- **Interface:** Tkinter (uma janela por processo-nó).
- **Tamanho:** ~1.330 linhas de código em `src/` (13 arquivos).

### Estrutura de pastas

```
raiz/
├── src/       todo o código (rede, mensagem, relogio, grupos, ordem_total,
│               eleicao, snapshot, nucleo, interface, no, iniciar, configuracao)
├── testes/    teste.py  (3 cenários automatizados com processos reais)
├── docs/      manual_de_uso.md, plano_implementacao.md, manual_teorico.md,
│               relatorio.md, roteiro.pdf
└── nos.json   catálogo gerado por src/iniciar.py (não versionado)
```

### Como executar (a partir da raiz do projeto)

```bash
# forma rápida: gera nos.json e abre N janelas
python src/iniciar.py --n 3            # (ou --n 8, --n 15)
python src/iniciar.py --n 3 --nomes Alice Bruno Carla   # nomes opcionais

# forma manual: gera o nos.json uma vez e sobe uma janela por terminal
python src/iniciar.py --n 3 --apenas-config
python src/no.py --id 1 --config nos.json
python src/no.py --id 2 --config nos.json
python src/no.py --id 3 --config nos.json

# testes automatizados
python testes/teste.py
```

Na tela de cada nó: seletor de conversa (`geral`, grupos, privadas — com nome e
membros), campo de envio, "Criar grupo", "Nova conversa privada", painel **Ordem
local**, painel **Mensagens do chat** (ordem global da conversa selecionada, por
`num_seq`), relógio vetorial, e os botões "Capturar estado global", "Forçar
eleição" e "Simular queda".

---

## 8. Passo a passo da ordem total e da eleição de líder

### 8.1 Ordem total — Abordagem B (sequenciador definido pelo líder)

**Papéis.** Um mesmo módulo (`ordem_total.py`), dois papéis:
- **Sequenciador** — só o líder: recebe os `CHAT_PEDIDO`, atribui um `num_seq`
  global crescente e redifunde a mensagem completa como `CHAT_ENTREGA`.
- **Entrega ordenada** — todo nó (inclusive o líder): guarda os `CHAT_ENTREGA` num
  buffer e entrega **estritamente na ordem do `num_seq`**.

**Passo a passo de uma mensagem de chat (nó A envia "oi" no grupo G):**

1. **A monta o pedido.** `relogio.evento_envio()` incrementa `V[A]` e devolve uma
   cópia do vetor. `seq_origem_atual += 1`; `id_msg = "A:seq"`. Monta o
   `CHAT_PEDIDO` (`grupo = G`, `payload = {"texto": "oi"}`, `relogio_vetorial = V`,
   `nome_origem`, `destino = líder`). Guarda em `enviadas_recentes` e marca
   `aguardando_carimbo`. **Difunde por multicast.**

2. **Todos recebem o `CHAT_PEDIDO`; só o líder age:**
   - se `id_msg` **já** foi sequenciado (pedido duplicado por retransmissão) →
     reenvia o `CHAT_ENTREGA` do histórico;
   - senão → `num_seq = proximo_num_seq; proximo_num_seq += 1`. Monta o
     `CHAT_ENTREGA` (cópia do pedido + `num_seq` + `carimbado_por = líder`,
     `destino = "todos"`). Guarda em `historico_por_num_seq`. **Difunde.**

3. **Cada nó recebe o `CHAT_ENTREGA`:**
   - `num_seq < proximo_num_seq_esperado` → duplicata, ignora;
   - senão → `pendentes[num_seq] = mensagem`; remove `id_msg` de
     `aguardando_carimbo`; chama `_tentar_entregar()`.

4. **`_tentar_entregar()`** — enquanto `proximo_num_seq_esperado` estiver em
   `pendentes`:
   - `mensagem = pendentes.pop(proximo_num_seq_esperado)`;
   - se a origem é outra, `relogio.ao_entregar(vetor_recebido)` (funde por `max`,
     depois incrementa a própria posição);
   - acrescenta à **fila global** (`ordem_global`);
   - se `payload` tem `acao` → aplica em `grupos.py` (registra o grupo); senão, se o
     nó é membro do grupo → mostra o texto na conversa e na ordem local;
   - `proximo_num_seq_esperado += 1`.

Como **todos** os nós recebem **todos** os `CHAT_ENTREGA` e entregam na ordem
`1, 2, 3, …`, a **fila global é idêntica em todos** (R4 — comprovado no Cenário 1).

**Confiabilidade sobre UDP:**

| Problema | Recuperação |
|----------|-------------|
| `CHAT_ENTREGA` perdido (buraco no `num_seq`) | `RETRANSMITIR {num_seq}` ao líder → líder reenvia do histórico |
| `CHAT_PEDIDO` perdido (autor não vê seu carimbo em `T_RETRANSMISSAO`) | o autor reenvia o pedido |
| Lacuna no `seq_origem` de um nó | `RETRANSMITIR {seq_origem}` à origem → origem reenvia de `enviadas_recentes` |
| Duplicata (`id_msg` já entregue / `num_seq` já passado) | descarta (entrega idempotente) |

### 8.2 Exemplo numérico — dois nós chegam à mesma ordem total

3 nós `{1, 2, 3}`, líder = 3, grupo `geral`, vetores iniciam `[1:0, 2:0, 3:0]`.

| Passo | Evento | Vetor anexado | Ação do líder |
|-------|--------|---------------|---------------|
| 1 | Nó 1 envia **"A"** (`evento_envio`) | `V(A) = [1:1, 2:0, 3:0]` | — |
| 2 | Nó 2 envia **"B"** (`evento_envio`) | `V(B) = [1:0, 2:1, 3:0]` | — |
| 3 | A rede reordena: o líder recebe **"B"** primeiro | | `num_seq(B) = 1` |
| 4 | O líder recebe **"A"** | | `num_seq(A) = 2` |
| 5 | Nós 1, 2 e 3 entregam por `num_seq` | | **ordem global = [B, A]** nos três |

`V(A) = [1:1, 2:0, 3:0]` e `V(B) = [1:0, 2:1, 3:0]` são **concorrentes**: nem
`V(A) ≤ V(B)` (falha em k=1) nem `V(B) ≤ V(A)` (falha em k=2). Não havia relação de
causa e efeito a respeitar — foi o **`num_seq` do líder** que definiu a ordem
total. Sem esse critério, o nó 1 poderia entregar `[A, B]` e o nó 2 `[B, A]`
(divergência). É a distinção **ordem causal (parcial) × ordem total** que o roteiro
destaca como a decisão de projeto mais importante.

**Caso com dependência causal (A → C):** nó 1 envia "A" (`V(A) = [1:1,2:0,3:0]`,
`num_seq(A) = 1`). O nó 2 **entrega** "A" (`ao_entregar`: `V2 = [1:1, 2:1, 3:0]`) e
só então envia "C" (`V(C) = [1:1, 2:2, 3:0]`). Agora `V(A) < V(C)` → **A precede
causalmente C**. Como "C" só foi enviada depois de "A" ser entregue (e "A" já
recebera `num_seq = 1`), o líder dá a "C" um `num_seq ≥ 2`. Qualquer ordem total
válida põe **A antes de C** — o sequenciador respeita a causalidade naturalmente.

### 8.3 Eleição de líder — algoritmo do anel (Chang & Roberts)

**Condição:** cada nó tem um id único e os ids podem ser comparados entre si; vence
o **maior id ativo**.

**Detecção de falha.** Todo nó difunde `HEARTBEAT` a cada `INTERVALO_HEARTBEAT`
(2 s). Se um nó fica sem heartbeat do líder por mais de `T_FALHA` (6 s = 3× o
intervalo), passa a considerá-lo caído.

**Anel lógico.** Ids em ordem crescente, circular. "Próximo" de um nó = menor id
ativo maior que ele; se não houver, o menor id ativo de todos (dá a volta).

**Passo a passo:**

1. O nó que detecta a falha **inicia**: monta `ELEICAO` com
   `payload = {"ids_vistos": [meu_id]}`, `destino = proximo_ativo(meu_id)`. Difunde.
2. O nó que é o `destino` da `ELEICAO`:
   - se `meu_id` **já está** em `ids_vistos` → a mensagem deu a volta → novo líder =
     `max(ids_vistos)`; difunde `COORDENADOR` com
     `payload = {"lider": max_id, "proximo_num_seq": base}`, `destino = "todos"`;
   - senão → acrescenta `meu_id` a `ids_vistos` e repassa a `ELEICAO` para
     `proximo_ativo(meu_id)`.
3. Ao receber `COORDENADOR`, cada nó adota `lider_atual`. Se for o novo líder,
   assume o papel de sequenciador retomando a numeração em
   `max(base, maior_num_seq_conhecido + 1)`.

**Continuidade da numeração.** Como todo nó viu todos os `CHAT_ENTREGA`, o maior
`num_seq` que circulou é conhecido por todos. Autores com `CHAT_PEDIDO` sem
`CHAT_ENTREGA` correspondente há mais de `T_RETRANSMISSAO` reenviam o pedido, e o
novo líder os sequencia — por isso, no Cenário 2, os `num_seq` continuam `1..8` sem
buraco após a troca de líder.

**Eleição inicial (boot).** Sem heartbeats ainda, cada nó assume
`lider = max(todos_os_ids)`. Quando esse nó sobe e manda heartbeat, confirma. Se o
maior id nunca sobe, após `T_FALHA` roda-se o anel e elege-se o maior id **ativo** —
por isso a simulação pode iniciar com 3, 8 ou 15 nós sem subir todos.

**Por que o anel e não o Bully.** Sobre multicast com campo `destino`, cada passo
do anel é **uma** mensagem para o "próximo nó ativo"; o fluxo é determinístico e
fácil de mostrar passo a passo no seminário (uma volta + um anúncio, `O(N)`
mensagens). O Bully dispara `ELEICAO` para todos os ids maiores e espera respostas
com timeout, gerando mais mensagens simultâneas e mais timeouts concorrentes.

---

## 9. Justificativa do estado global escolhido

**Escolhemos o algoritmo de snapshot de Chandy-Lamport** (1985).

**O que é capturado.** Para cada nó: `proximo_num_seq_esperado - 1` (quantas
mensagens já entregou), cópia do relógio vetorial, `lider_atual`, tamanho do buffer
de pendentes e as últimas entregas. Para cada **canal lógico `j → i`** (as
mensagens de chat que o nó `i` recebe do nó `j`, identificadas pelo campo `origem`):
a lista de mensagens recebidas entre o registro do estado local e a chegada do
marcador daquele canal. A ordem de cada canal é reconstruída pelo `seq_origem`.

**Passo a passo (`snapshot.py`):**

1. O **iniciador** (o líder, via botão; qualquer nó pode iniciar) registra o
   próprio estado e difunde um `MARCADOR` (`id_snapshot = "<id>-<timestamp>"`).
2. Ao receber o **primeiro** `MARCADOR` de um snapshot: o nó registra seu estado
   agora; o canal por onde o marcador veio fica **vazio**; passa a **gravar** os
   demais canais; propaga o `MARCADOR`.
3. `MARCADOR` **seguinte** do mesmo snapshot, vindo do canal `j`: para de gravar
   `j`; o estado do canal `j` é o que foi gravado.
4. Quando o nó recebeu `MARCADOR` de **todos** os outros `N-1` nós, difunde
   `RESULTADO_SNAPSHOT` com seu pedaço.
5. Quem juntar os `N` `RESULTADO_SNAPSHOT` monta a **fotografia global** e a exibe
   (o iniciador quase sempre é quem junta todos, pois começou antes).

**Por que Chandy-Lamport:**

- É a **solução clássica** vista em aula para o problema de estado global.
- Respeita a regra "**só mensagens de rede**" — os marcadores viajam no mesmo grupo
  multicast.
- **Não para o sistema** e **não precisa de relógio sincronizado**.
- Sempre produz um **corte consistente**: nenhuma mensagem aparece como recebida
  sem ter sido enviada (o marcador separa o "antes" do "depois" em cada canal).
  Comprovado no Cenário 4: todos os nós concordam no líder e no ponto da fila
  global até onde entregaram.

**Alternativa descartada — o líder pergunta a todos e junta as respostas:** seria
mais fácil de programar, mas (a) coloca tudo num **ponto único de falha** e (b)
pode capturar um estado **inconsistente**, já que as respostas dos nós chegam em
momentos diferentes e não há controle sobre o que estava nos canais no instante do
corte. Chandy-Lamport resolve os dois problemas pela própria definição; em troca,
exige um pouco mais de código para coordenar os marcadores — o que vale a pena.
