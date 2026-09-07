# Manual Teórico — Chat Distribuído

Trabalho 1 de Sistemas Distribuídos (UNIVALI, Prof. Ramicés dos Santos Silva).

Este documento reúne a **base teórica** por trás do sistema e explica **como a
implementação realiza cada conceito**. Serve de apoio para a Entrega 1 (relatório,
Seção 10 do roteiro) e para a Entrega 2 (slides + seminário). Onde couber, o texto
indica o arquivo e a função correspondentes em `src/`.

Os outros dois documentos são complementares: `manual_de_uso.md` (como executar e a
justificativa de cada decisão) e `plano_implementacao.md` (o projeto detalhado,
módulo a módulo).

---

## Sumário

1. [O problema e o que o sistema entrega](#1-o-problema-e-o-que-o-sistema-entrega)
2. [Modelo de sistema](#2-modelo-de-sistema)
3. [Fundamentos teóricos](#3-fundamentos-teóricos)
4. [Arquitetura da implementação](#4-arquitetura-da-implementação)
5. [Formato das mensagens](#5-formato-das-mensagens)
6. [Da teoria ao código, módulo a módulo](#6-da-teoria-ao-código-módulo-a-módulo)
7. [Fluxos completos](#7-fluxos-completos)
8. [Exemplo numérico: dois nós chegam à mesma ordem total](#8-exemplo-numérico-dois-nós-chegam-à-mesma-ordem-total)
9. [Requisitos do roteiro → onde são atendidos](#9-requisitos-do-roteiro--onde-são-atendidos)
10. [Limitações conhecidas](#10-limitações-conhecidas)
11. [Roteiro do seminário](#11-roteiro-do-seminário)
12. [Glossário](#12-glossário)
13. [Referências](#13-referências)

---

## 1. O problema e o que o sistema entrega

O trabalho pede um **sistema distribuído de comunicação de grupo** com múltiplos
nós, que exercite três blocos de teoria: **relógios lógicos**, **ordem total de
mensagens** e **estado global**. O tema escolhido foi **chat distribuído**: cada nó
é um participante, roda como um processo separado do sistema operacional e só se
comunica com os outros por **mensagens de rede**.

### 1.1 Objetivos de aprendizagem (roteiro, Seção 1)

- Compreender e implementar **relógios de Lamport e vetoriais** na prática.
- **Distinguir ordem causal (parcial) de ordem total** e garantir a ordem total das
  mensagens difundidas.
- Implementar **comunicação de grupo** com primitivas de rede (aqui, multicast).
- Modelar e capturar um **estado global consistente**.
- Exercitar **eleição de líder** e o papel de um **nó coordenador/sequenciador**.
- Projetar, documentar e **defender oralmente** a solução.

### 1.2 Requisitos funcionais (roteiro, Seção 3)

| # | Requisito | Como é demonstrado |
|---|-----------|--------------------|
| R1 | Comunicação de grupo (multicast) | Uma mensagem enviada por um nó chega a todos os demais. |
| R2 | Tema (chat) | Mensagem privada, mensagem de grupo, criação de grupos com membros escolhidos. |
| R3 | Nº de nós configurável, ≥ 15, sem alterar código | `python src/iniciar.py --n 3 / 8 / 15`. |
| R4 | Ordem total | A fila global (por número de sequência) é idêntica em todos os nós. |
| R5 | Tela do nó | Envio p/ nó, envio p/ grupo, ordem local, ordem global, relógio vetorial, buffer. |
| R6 | Estado global | Um comando dispara um snapshot de Chandy-Lamport e o exibe. |
| R7 | Relatório | Documento com os itens da Seção 10 do roteiro. |
| R8 | Eleição de líder | Passo a passo do algoritmo do anel + demonstração de reeleição. |

---

## 2. Modelo de sistema

Antes da teoria dos algoritmos, é preciso fixar **em que mundo eles rodam**. As
premissas abaixo valem para todo o trabalho.

### 2.1 Processos e ausência de estado compartilhado

O sistema é um conjunto de **processos** `p1, p2, …, pN`, cada um com **estado
privado em memória**. Não há memória compartilhada, banco de dados comum, arquivo
em disco compartilhado nem variável global entre threads de processos diferentes.
A **única** forma de coordenação é a troca de mensagens pela rede (regra 11 do
roteiro).

Exceção permitida: um **arquivo de configuração estático** (`nos.json`), lido só na
inicialização, com a lista de nós (id, host, porta). Ele é o "catálogo de
endereços", não um canal de coordenação em tempo de execução.

> **Consequência prática:** rodar todos os nós como threads de um único processo,
> compartilhando estruturas de dados, descaracteriza o trabalho. Por isso
> `src/iniciar.py` faz `subprocess` de N cópias de `src/no.py`.

### 2.2 Modelo de tempo: assíncrono

Não existe **relógio global**. Os relógios físicos dos nós não são sincronizados e
não são usados para ordenar eventos. Não há limite superior conhecido para o tempo
de entrega de uma mensagem nem para a velocidade relativa dos processos — é o
**modelo assíncrono**.

A única "hora" que o sistema usa é `time.monotonic()` **dentro de cada nó**, para
medir intervalos locais (quando mandar o próximo heartbeat, quando um timeout
estourou). Isso é tempo local, não um relógio compartilhado.

### 2.3 Modelo de falhas: crash / fail-stop

Um nó pode **parar** (crash) — deixa de enviar e receber mensagens e não volta.
Não tratamos:

- **falhas bizantinas** (nó malicioso ou com comportamento arbitrário);
- **partição de rede** prolongada;
- **recuperação** de um nó que caiu (ele não reingressa no meio da simulação).

A queda que **é** tratada, e é obrigatória (R8), é a do **líder-sequenciador**:
os demais detectam e elegem outro.

### 2.4 Canais: UDP multicast (best-effort)

Toda a comunicação passa por **um único grupo multicast IP** (`224.1.1.1:5007`).
UDP multicast é *best-effort*: um datagrama pode ser **perdido**, **duplicado** ou
**reordenado**. Não há entrega confiável nem ordem FIFO nativa por canal.

Essa escolha (em vez de TCP unicast) é deliberada — comunicação de grupo nativa,
um `sendto` chega a todos — e o **custo** (não-confiabilidade) é tratado na camada
de ordenação (Seção 3.11). A alternativa, TCP unicast, daria FIFO confiável de
graça, mas exigiria N conexões por nó e uma difusão manual (laço sobre a lista)
para cada mensagem de grupo.

---

## 3. Fundamentos teóricos

### 3.1 Comunicação de grupo e multicast IP

**Unicast** é um-para-um; **broadcast** é um-para-todos-na-sub-rede; **multicast**
é um-para-um-grupo: só os hosts inscritos no grupo recebem.

No **multicast IP**:

- O grupo é identificado por um endereço da faixa **224.0.0.0 – 239.255.255.255**
  (classe D). Usamos `224.1.1.1`.
- Um host entra no grupo com `IP_ADD_MEMBERSHIP` (por baixo, o protocolo **IGMP**
  informa o roteador local).
- O **TTL** limita o alcance dos datagramas. `TTL = 1` = não sai da máquina local
  (ideal para testar N nós em `localhost`).
- Vários processos na mesma máquina escutam a mesma porta do grupo com
  `SO_REUSEADDR` (e `SO_REUSEPORT` onde existir).

**Propriedades que um multicast pode ou não garantir:**

| Propriedade | Significado | Neste trabalho |
|-------------|-------------|----------------|
| Integridade | mensagem entregue não foi corrompida e foi enviada por alguém | sim (JSON malformado é descartado) |
| Validade | se um processo correto envia, ele mesmo entrega | aproximada (best-effort + retransmissão) |
| Acordo | se um processo correto entrega `m`, todos os corretos entregam `m` | aproximada (retransmissão sob demanda; ver 3.11 e Seção 10) |

Um multicast pode ainda ser **ordenado** (FIFO, causal ou total). O multicast IP
puro **não** oferece nenhuma ordem — a ordem total é construída por cima
(Seção 3.6).

### 3.2 A relação "aconteceu-antes" (Lamport, 1978)

A ordem dos eventos num sistema distribuído é definida pela relação
**happened-before** `→`, a menor relação tal que:

1. Se `a` e `b` são eventos do **mesmo processo** e `a` ocorre antes de `b`, então
   `a → b`.
2. Se `a` é o **envio** de uma mensagem e `b` é a **recepção** dessa mensagem,
   então `a → b`.
3. Transitividade: se `a → b` e `b → c`, então `a → c`.

Se **nem** `a → b` **nem** `b → a`, os eventos são **concorrentes** (`a ∥ b`):
aconteceram "ao mesmo tempo" no sentido de que nenhum pôde influenciar o outro.

`→` é uma **ordem parcial**: existem pares não comparáveis (os concorrentes).

### 3.3 Relógio escalar de Lamport

Cada nó mantém um contador inteiro `C`. Regras:

- **Evento local ou envio:** `C = C + 1`; o valor de `C` acompanha a mensagem.
- **Recepção com carimbo `Cm`:** `C = max(C, Cm) + 1`.

Propriedade: `a → b ⟹ C(a) < C(b)`. Ou seja, o relógio escalar é **consistente
com a causalidade**.

**Limitação (a razão de existir o vetorial):** a recíproca é falsa.
`C(a) < C(b)` **não** implica `a → b` — os eventos podem ser concorrentes. O
relógio escalar não permite **detectar concorrência**.

> Neste trabalho o relógio escalar aparece só como conceito. O nó usa relógio
> **vetorial** (Seção 3.4). O roteiro pede que os dois sejam compreendidos.

### 3.4 Relógio vetorial

Cada nó `i` mantém um **vetor** `V` de tamanho `N` (um contador por nó).
`V[j]` é "o que o nó `i` sabe sobre a atividade do nó `j`".

**Regras (política adotada, documentada como o roteiro exige):**

- **Ao enviar** uma mensagem de chat (`RelogioVetorial.evento_envio`):
  `V[i] = V[i] + 1`; anexa uma **cópia** de `V` à mensagem.
- **Ao entregar** uma mensagem de **outro** nó, já na ordem do `num_seq`
  (`RelogioVetorial.ao_entregar`): para cada `j`, `V[j] = max(V[j], Vm[j])`;
  depois `V[i] = V[i] + 1` (o evento local de entrega conta).
- A **recepção crua** de um datagrama **não** mexe no vetor — a mensagem primeiro
  precisa ser entregue na ordem do `num_seq`.
- Mensagem do **próprio** nó não incrementa de novo na entrega (o envio já contou).

> O enunciado observa que, no problema original, eventos de recepção às vezes não
> incrementam o vetor. O essencial é que a **política seja consistente e
> documentada** — a nossa é a acima.

**Comparação de vetores:**

- `V(a) ≤ V(b)` se `V(a)[k] ≤ V(b)[k]` para **todo** `k`.
- `V(a) < V(b)` se `V(a) ≤ V(b)` e `V(a) ≠ V(b)`.

**Propriedade fundamental** (Fidge / Mattern, 1988):

```
V(a) < V(b)  ⟺  a → b
a ∥ b        ⟺  nem V(a) ≤ V(b) nem V(b) ≤ V(a)
```

Ou seja, o vetorial **caracteriza exatamente** a causalidade — inclusive detecta
concorrência. É isso que `relogio.concorrentes(Va, Vb)` calcula e é isso que a tela
usa para mostrar que duas mensagens são concorrentes.

### 3.5 Ordem de entrega: FIFO, causal, total

Difusão (multicast) pode garantir diferentes **ordens de entrega**:

- **FIFO:** se um nó envia `m1` antes de `m2`, nenhum nó entrega `m2` antes de `m1`.
  (Ordena só as mensagens **da mesma origem**.)
- **Causal:** se `envio(m1) → envio(m2)`, nenhum nó entrega `m2` antes de `m1`.
  (Generaliza FIFO usando `→`; ainda é **ordem parcial** — não diz nada sobre
  mensagens concorrentes.)
- **Total:** todos os nós entregam **todas** as mensagens na **mesma sequência**,
  mesmo as concorrentes. É uma **ordem total** sobre as mensagens.
- **Total + causal (atomic broadcast):** ordem total que também respeita `→`.

#### 3.5.1 O ponto central: ordem causal ≠ ordem total

*(Esta é a decisão de projeto mais importante do trabalho — roteiro, Seção 5.3.)*

O relógio vetorial, sozinho, garante **ordem causal**, que é **parcial**: duas
mensagens **concorrentes** podem ser entregues em ordens diferentes em nós
diferentes, e isso não viola a causalidade. Mas um chat precisa de **ordem
total** — todos os participantes têm de ver a conversa na mesma sequência.

Logo, é preciso um **critério extra além do vetor** para desempatar as mensagens
concorrentes. As duas formas clássicas de obter esse critério estão em 3.6.

O vetor **não desaparece**: ele continua sendo mantido e exibido, para mostrar
**quais** mensagens eram concorrentes e para o exemplo numérico do relatório
(Seção 8). Quem **decide a entrega** é o critério de ordem total.

### 3.6 Como garantir ordem total

O roteiro apresenta duas abordagens. **Escolhemos a B.**

#### Abordagem A — relógio vetorial + desempate determinístico

Mantém-se o vetor e define-se uma **função de ordenação total** que todos os nós
aplicam de forma idêntica, por exemplo:

```
chave(m) = (soma(Vm), id_do_no_de_origem, contador_local_da_origem)
```

Compara-se pela soma dos componentes do vetor (um "relógio escalar derivado");
empates pelo id do nó e depois pelo contador local.

Um nó só pode **entregar** `m` quando tem **certeza de que nenhuma mensagem com
chave menor ainda pode chegar** — isso exige a propriedade de **estabilidade**:
ter recebido "algo" (mensagem ou ACK) de **todos** os nós. Para não travar quando
um nó fica quieto, todos mandam **mensagens periódicas de batimento**.

- **Vantagem:** totalmente descentralizado, sem ponto único de falha.
- **Custo:** maior latência de entrega, mais mensagens de controle, mais casos de
  borda (deadlock por silêncio). A eleição de líder passa a ser opcional.

#### Abordagem B — sequenciador / super-servidor eleito *(a escolhida)*

Um nó atua como **sequenciador**: recebe as mensagens de grupo, atribui um
**número de sequência global** crescente e as **redifunde** já carimbadas. Todos os
nós entregam **estritamente na ordem do número de sequência**.

Na taxonomia de Défago, Schiper e Urbán (2004), isto é um **sequenciador fixo**
(*fixed sequencer*): um processo designado ordena tudo; se ele cai, um novo é
**eleito** (daí a eleição de líder ser **obrigatória** nesta abordagem).

- **Vantagem:** ordem total **simples e eficiente** — um inteiro crescente que
  todos respeitam. A entrega acontece assim que o `num_seq` esperado chega, sem
  esperar confirmação de todos. Casa direto com os outros dois requisitos: o
  **líder** já existe (é o sequenciador) e é o **iniciador natural do snapshot**.
- **Custo:** o sequenciador é um **ponto crítico** — a queda dele é obrigatória de
  tratar (Seção 3.7). Mensagens que ele carimbou mas não conseguiu propagar na
  janela da queda podem se perder (limitação registrada).

**Por que a ordem total aqui também é causal (atomic broadcast).** Uma mensagem só
é enviada **depois** que suas causas foram entregues no emissor (o `evento_envio`
acontece após os `ao_entregar` anteriores). Quando o líder recebe o `CHAT_PEDIDO`
dessa mensagem, ele já recebeu (e carimbou com `num_seq` menor) os pedidos das
mensagens que a precedem causalmente. Portanto o `num_seq` crescente **respeita
`→`** — sem nenhum código extra de verificação causal.

#### Relação com consenso e o resultado FLP

Difusão com ordem total (**atomic broadcast**) é **equivalente ao consenso**
(Chandra & Toueg, 1996). O resultado de **Fischer, Lynch e Paterson (1985 — FLP)**
diz que **não existe** algoritmo determinístico de consenso num sistema
**puramente assíncrono** se um único processo pode falhar. A saída prática é
adicionar uma **suposição de temporização**: um **detector de falhas** baseado em
timeout (Seção 3.8). Nosso `T_FALHA` sobre heartbeats é exatamente essa suposição
— assumimos *sincronia parcial*.

### 3.7 Eleição de líder

**Problema:** após a queda do líder, os nós restantes precisam concordar, apenas
por troca de mensagens, sobre **um único** novo líder.

**Premissa:** os nós têm **ids únicos e totalmente ordenados** (inteiros do
`nos.json`). A regra de escolha é determinística: **vence o maior id ativo**.

#### Algoritmo do anel (Chang & Roberts, 1979) — o adotado

1. Os nós formam um **anel lógico**: ids em ordem crescente, circular. O "próximo"
   de um nó é o menor id ativo maior que ele; se não houver, o menor id ativo de
   todos (dá a volta).
2. Quem detecta a falha **inicia** a eleição: monta uma mensagem `ELEICAO` com
   `ids_vistos = [meu_id]` e a envia para o **próximo nó ativo**.
3. Cada nó que recebe a `ELEICAO`:
   - se **já está** em `ids_vistos` → a mensagem deu a volta → o **maior id** da
     lista é o novo líder; anuncia com `COORDENADOR` (difusão a todos);
   - senão → **acrescenta** seu id e repassa a `ELEICAO` ao próximo ativo.
4. Ao receber `COORDENADOR`, cada nó adota o novo líder. Se for o novo líder,
   assume o papel de sequenciador.

Custo: a mensagem percorre o anel **uma volta** acumulando ids; o anúncio é **uma
difusão**. `O(N)` mensagens para o percurso.

#### Algoritmo do Valentão / Bully (Garcia-Molina, 1982) — alternativa descrita

1. Ao notar que o líder caiu, o nó envia `ELEICAO` a **todos** os nós de id **maior**
   que o seu.
2. Se ninguém maior responde dentro do timeout, ele se declara líder e envia
   `COORDENADOR` a todos.
3. Se algum id maior responde `OK`, ele desiste e espera o anúncio.
4. O nó de maior id ativo sempre vence.

Custo: no pior caso `O(N²)` mensagens; vários timeouts concorrentes para raciocinar.

#### Por que o anel neste trabalho

Sobre multicast com campo `destino`, cada passo do anel é **uma** mensagem
direcionada ao "próximo nó ativo". O fluxo é **determinístico e fácil de mostrar
passo a passo** no seminário (a mensagem dá exatamente uma volta e o anúncio é uma
difusão). O Bully gera mais mensagens simultâneas e mais timeouts concorrentes.

#### Continuidade da numeração

O novo líder precisa retomar o `num_seq` **sem buraco e sem repetição**. Como
**todo nó viu todos os `CHAT_ENTREGA`**, cada um conhece o maior `num_seq` que
circulou. O novo líder retoma em `max(base, maior_conhecido + 1)`. Autores que
tenham um `CHAT_PEDIDO` **sem** `CHAT_ENTREGA` correspondente há mais de
`T_RETRANSMISSAO` **reenviam o pedido**, e o novo líder os sequencia.

#### Eleição inicial (boot)

No boot ainda não há heartbeats. Cada nó **assume `lider = max(todos_os_ids)`** até
um heartbeat confirmar. Se o maior id nunca sobe, após `T_FALHA` roda-se o anel e
elege-se o maior id **ativo**. Assim a simulação inicia com 3, 8 ou 15 nós sem
precisar subir todos.

### 3.8 Detecção de falhas

Num sistema **assíncrono** não dá para distinguir com certeza um nó **caído** de um
nó **lento** (ou de uma mensagem atrasada). Detectores de falhas perfeitos são
impossíveis; usa-se um detector **não confiável** baseado em tempo:

- **Heartbeats:** todo nó difunde `HEARTBEAT` a cada `INTERVALO_HEARTBEAT` (2 s).
- **Suspeita:** se um nó fica sem heartbeat de outro por mais de `T_FALHA` (6 s =
  3× o intervalo), passa a considerá-lo caído.
- O fator 3× dá folga para heartbeats perdidos (UDP) e atrasos, reduzindo
  **falsos positivos**.

Na classificação de Chandra & Toueg, isto se aproxima de um detector
**◊P (eventually perfect)**: pode errar por um tempo (suspeitar de um nó vivo), mas
"eventualmente" acerta. É o suficiente para a eleição terminar.

### 3.9 Estado global e cortes consistentes

**Estado global** = a coleção dos estados locais de todos os nós **mais** o
conteúdo dos canais (mensagens em trânsito) num "instante".

Como não há relógio global, "instante" é definido por um **corte**: para cada nó,
escolhe-se um ponto na sua linha de eventos. Um corte é **consistente** se, para
toda mensagem cuja **recepção** está **antes** do corte, o **envio** também está
antes do corte. Informalmente: **nenhuma mensagem aparece como recebida sem ter
sido enviada** — não há "efeito antes da causa".

#### Algoritmo de snapshot de Chandy-Lamport (1985)

Produz um corte consistente **sem parar o sistema** e **sem relógio sincronizado**,
usando só mensagens de rede.

**Pressupostos do algoritmo:** canais **confiáveis** e **FIFO**; processos não
falham durante o snapshot.

**Regras:**

1. O **iniciador** registra seu estado local e envia um **MARCADOR** por todos os
   canais de saída.
2. Ao receber o **primeiro** MARCADOR de um snapshot: o nó registra seu estado
   **agora**; considera **vazio** o canal por onde o marcador veio; começa a
   **gravar** os demais canais de entrada; propaga o MARCADOR pelos seus canais de
   saída.
3. Ao receber um MARCADOR **seguinte** (do mesmo snapshot) por um canal `j`: para
   de gravar `j`; o **estado do canal `j`** é o que foi gravado entre o registro do
   estado local e a chegada desse marcador.
4. O snapshot local está completo quando o nó recebeu MARCADOR de **todos** os
   outros nós. A fotografia global é a união dos estados locais e de canal.

**Por que Chandy-Lamport e não "o líder pergunta a todos":** a variante
centralizada é mais simples de codar, mas concentra tudo num ponto único de falha e
pode capturar um estado **inconsistente** se as respostas chegam em momentos
diferentes sem controle dos canais. Chandy-Lamport garante consistência pela
própria definição.

**Usos clássicos:** detecção de deadlock, detecção de terminação, checkpointing
para recuperação, depuração de propriedades estáveis.

### 3.10 Replicação de máquina de estados

O modelo por trás de "todos veem a mesma conversa" é a **replicação de máquina de
estados** (Schneider, 1990): se todas as réplicas **começam no mesmo estado** e
**aplicam as mesmas operações na mesma ordem**, elas terminam **no mesmo estado**.

Aqui, a "máquina de estados" é o conjunto {fila global de mensagens, registro de
grupos}. A **ordem** vem do `num_seq` do líder. A **fila global** (`ordem_global`
em cada nó) **é** o log replicado — e o critério de correção do trabalho é
justamente: essa fila tem de ser **byte a byte igual** em todos os nós ao fim de
uma simulação.

Criar um grupo é só mais uma operação nesse log (`payload.acao = "criar_grupo"`),
sequenciada junto com as mensagens — por isso a membresia converge sem corrida
(Seção 7.2).

### 3.11 Confiabilidade sobre UDP

UDP multicast perde, duplica e reordena. A camada de ordenação trata isso com
técnicas clássicas de protocolo confiável, **sob demanda** (só reage quando
percebe um problema):

| Problema | Detecção | Recuperação |
|----------|----------|-------------|
| Perda de `CHAT_ENTREGA` | buraco na sequência de `num_seq` | `RETRANSMITIR` ao líder → líder reenvia do histórico (**NAK** — ACK negativo) |
| Perda de `CHAT_PEDIDO` | o autor não vê seu `CHAT_ENTREGA` em `T_RETRANSMISSAO` | o autor **reenvia o pedido** |
| Perda no fluxo de uma origem | buraco no `seq_origem` daquele nó | `RETRANSMITIR` à origem → origem reenvia de `enviadas_recentes` |
| Duplicação | `id_msg` já entregue / `num_seq` já passado | **descarta** (entrega **idempotente**) |
| Reordenação | `num_seq` fora de ordem | buffer `pendentes` só entrega em ordem estrita |

`seq_origem` é um contador **FIFO por origem** (`"{origem}:{contador}"` = `id_msg`),
que permite detectar perda mesmo antes de a mensagem ser sequenciada. Os históricos
(`historico_por_num_seq`, `enviadas_recentes`) são **limitados** a
`TAMANHO_HISTORICO` (300) — não crescem sem parar.

---

## 4. Arquitetura da implementação

### 4.1 Um processo do SO por nó

Cada nó é um processo `python src/no.py --id K`. `src/iniciar.py` gera o `nos.json`
e faz `subprocess` de N desses processos, um por nó, cada um abrindo sua janela.
Estado em memória privada; comunicação só por multicast.

### 4.2 Três atividades concorrentes dentro do nó

O roteiro (Seção 7) recomenda separar, **dentro** de cada processo, (a) escuta de
rede, (b) processamento/entrega e (c) interface. Isso é **concorrência interna** —
permitida; entre nós, só rede.

| Thread | Arquivo | Papel |
|--------|---------|-------|
| Receptora | `rede.py` | `recvfrom` no socket multicast, `json.loads`, põe o dict em `fila_recebidas`. |
| Núcleo | `nucleo.py` | Consome `fila_recebidas`, despacha por `tipo`, roda as tarefas periódicas (heartbeat, timeouts, lacunas). **Toda alteração de estado sob `trava_estado`.** Empurra eventos para `fila_interface`. |
| Interface (principal) | `interface.py` | `janela.mainloop()`. `janela.after(100, drenar)` lê `fila_interface` e repinta. Botões chamam métodos do núcleo (que pegam o lock rapidinho). |

Tkinter **não é thread-safe**: por isso o núcleo nunca toca em widgets — ele só põe
eventos numa fila, e a janela lê a fila a cada 100 ms.

### 4.3 Estruturas compartilhadas entre as threads

Apenas:

- `fila_recebidas` (`queue.Queue`) — receptora → núcleo;
- `fila_interface` (`queue.Queue`) — núcleo → interface;
- o estado do nó, protegido por **um** `threading.Lock` (`trava_estado`).

`queue.Queue` já é thread-safe. O lock serializa as mudanças de estado (entrega de
mensagem, mudança de líder, criação de grupo) contra as leituras da interface.

### 4.4 Estrutura de pastas

```
raiz/
├── src/       todo o código
├── testes/    teste.py
├── docs/      manual_de_uso.md, plano_implementacao.md, manual_teorico.md, roteiro.pdf
└── nos.json   gerado
```

`src/` é uma pasta **plana** (sem `__init__.py`): como o Python põe a pasta do
script em `sys.path`, os `import` entre módulos continuam simples. Rodar sempre a
partir da raiz: `python src/iniciar.py --n 3`, `python testes/teste.py`.

---

## 5. Formato das mensagens

Um dicionário serializado com `json.dumps` (`mensagem.py`). Campos:

| Campo | Quando aparece | Significado |
|-------|----------------|-------------|
| `tipo` | sempre | `CHAT_PEDIDO`, `CHAT_ENTREGA`, `HEARTBEAT`, `ELEICAO`, `COORDENADOR`, `RETRANSMITIR`, `MARCADOR`, `RESULTADO_SNAPSHOT`. |
| `origem` | sempre | Id do nó que **gerou** o conteúdo (no `CHAT_ENTREGA` continua sendo o autor, não o líder). |
| `destino` | sempre | Id do nó alvo ou `"todos"`. Quem não é o alvo ignora. |
| `seq_origem` | mensagens de chat | Contador FIFO por origem, para detectar perda/lacuna sobre UDP. |
| `id_msg` | mensagens de chat | `"{origem}:{seq_origem}"`. Casa pedido ↔ entrega e remove duplicatas. |
| `relogio_vetorial` | mensagens de chat | Cópia do vetor da origem no momento do envio. |
| `grupo` | mensagens de chat | `"geral"`, `"priv-a-b"` (a < b) ou o id de um grupo nomeado `"g-<criador>-<seq>"`. |
| `num_seq` | só `CHAT_ENTREGA` | Número de sequência **global** atribuído pelo líder. **Define a ordem total.** |
| `carimbado_por` | só `CHAT_ENTREGA` | Id do líder que sequenciou (para log/relatório). |
| `payload` | sempre | Dados do tipo. Chat: `{"texto": "..."}` **ou** `{"acao": "criar_grupo", "nome": ..., "membros": [...]}`. Controle: `{"ids_vistos": [...]}`, `{"lider": 7, "proximo_num_seq": 42}`, `{"id_snapshot": ...}`, etc. |

**Mensagens direcionadas também vão por multicast**, com `destino` = um id. Não há
unicast em lugar nenhum. Quem não é o alvo simplesmente descarta.

---

## 6. Da teoria ao código, módulo a módulo

### 6.1 `rede.py` — multicast IP

Realiza a **Seção 3.1**. Dois sockets UDP:

- **Envio:** `IP_MULTICAST_TTL` = 1. `enviar(dict)` faz um `sendto` para
  `(224.1.1.1, 5007)` — **um** datagrama chega a todos.
- **Recepção:** `SO_REUSEADDR` (+ `SO_REUSEPORT` se existir) para vários nós na
  mesma porta; `bind(("", 5007))`; `IP_ADD_MEMBERSHIP` para entrar no grupo. Uma
  **thread receptora** faz `recvfrom(65536)` em laço, desserializa e chama o
  callback do núcleo. Datagrama corrompido (`json` inválido) é **ignorado**
  (integridade).

### 6.2 `mensagem.py` — tipos e serialização

Centraliza as **constantes de `tipo`** e `montar(...)` / `serializar` /
`desserializar`, para não espalhar strings soltas. `montar(tipo, origem,
destino="todos", **campos)` monta o dict base.

### 6.3 `relogio.py` — relógio vetorial

Realiza a **Seção 3.4**. `RelogioVetorial`:

- `evento_envio()` → `V[i] += 1`, retorna `dict(V)` para anexar à mensagem;
- `ao_entregar(Vm)` → `V[j] = max(V[j], Vm[j])` para cada `j`, depois `V[i] += 1`;
- `concorrentes(Va, Vb)` → `True` se nem `Va ≤ Vb` nem `Vb ≤ Va` (usado só para a
  tela e o exemplo do relatório);
- `__str__` → `[1:3, 2:1, 3:0]`.

Detalhe de implementação: chaves de dict vindas de JSON chegam como **string**;
`_com_chaves_inteiras` padroniza para `int` antes de comparar.

### 6.4 `ordem_total.py` — sequenciador fixo + entrega ordenada

Realiza a **Abordagem B (Seção 3.6)**. Um mesmo objeto, dois papéis:

**Papel de sequenciador (só enquanto o nó é líder):**

- `ao_receber_pedido(m)`: se `id_msg` **já** foi sequenciado (pedido duplicado por
  retransmissão) → reenvia o `CHAT_ENTREGA` do histórico. Senão →
  `num_seq = proximo_num_seq; proximo_num_seq += 1`; monta o `CHAT_ENTREGA` (cópia
  do pedido + `num_seq` + `carimbado_por` + `destino = "todos"`); guarda em
  `historico_por_num_seq`; difunde.
- `responder_retransmissao(m)`: reenvia um `CHAT_ENTREGA` pedido por `num_seq`.
- `ao_virar_lider(base)`: reconstrói o histórico a partir de `ordem_global` +
  `pendentes` e ajusta `proximo_num_seq` (continuidade da numeração — Seção 3.7).

**Papel de entrega ordenada (todo nó, inclusive o líder):**

- `proximo_num_seq_esperado` (começa em 1), `pendentes` (`{num_seq: mensagem}`),
  `entregues_id_msg` (dedup).
- `ao_receber_entrega(m)`: se `num_seq < esperado` → descarta (duplicata). Senão →
  `pendentes[num_seq] = m` e chama `_tentar_entregar`.
- `_tentar_entregar()`: **enquanto** `esperado ∈ pendentes` → remove, entrega
  (`nucleo.entregar_mensagem`), `esperado += 1`. É o buffer de reordenação: só
  entrega em sequência estrita → **fila global idêntica em todos** (R4).

**Timeouts (`verificar_timeouts`, roda a cada volta do laço do núcleo):**

1. Autor sem carimbo há > `T_RETRANSMISSAO` → reenvia o `CHAT_PEDIDO` ao líder atual.
2. Há `pendentes` futuros mas o `esperado` não chega há > `T_RETRANSMISSAO` →
   `RETRANSMITIR` ao líder pedindo aquele `num_seq`.

### 6.5 `grupos.py` — geral, nomeados e privados; privacidade lógica

`RegistroGrupos` guarda, por **id de grupo**, `{nome, tipo, membros: set}`.

- **`geral`** — público, todos os nós são membros desde o início.
- **Grupo nomeado** — id `g-<criador>-<seq>`, nome amigável, membros escolhidos na
  criação (o criador entra sozinho). Criado via ação sequenciada (Seção 7.2).
  `criar()` é **idempotente** (a entrega pode repetir).
- **`priv-a-b`** (a < b) — privado, 2 membros fixos, **codificados no próprio id**.
  Atalho para um grupo de 2, sem nome. Quem abre chama `abrir_privado` (registro
  **local**); o outro participante registra a conversa **na entrega da primeira
  mensagem**, via `garantir_privado(grupo_id)` — não precisa ter aberto antes.

**Privacidade é lógica:** em `entregar_mensagem`, o texto só entra na vista da
conversa e na ordem local se `sou_membro(grupo)`. Um **não-participante** registra
o `num_seq` na fila global mas **não vê o conteúdo** — a **posição continua
visível** (a ordem total não muda). Na tela, o painel "Mensagens do chat" mostra só
a conversa selecionada; um nó que não participa de um grupo simplesmente não tem
aquela conversa no seletor. Sem criptografia: o datagrama chega fisicamente a todos.

### 6.6 `eleicao.py` — anel + heartbeats

Realiza as **Seções 3.7 e 3.8**.

- `tarefas_periodicas()`: manda `HEARTBEAT` a cada `INTERVALO_HEARTBEAT` com
  `{lider_conhecido, num_seq_visto}`. Se não é líder e o líder está silencioso há
  mais de `T_FALHA` → `iniciar_eleicao()`.
- `nos_vivos()` / `proximo_ativo(id)`: o anel lógico sobre os ids com heartbeat
  recente.
- `iniciar_eleicao()`: `ELEICAO` com `ids_vistos = [meu_id]` para o próximo ativo.
- `ao_receber_eleicao(m)`: se sou o `destino` — se meu id **já** está em
  `ids_vistos` → `COORDENADOR` com `lider = max(ids_vistos)`; senão → acrescento e
  repasso.
- `ao_receber_coordenador(m)`: adoto o novo líder; se **virei** líder agora →
  `ordem.ao_virar_lider(base)`.
- `ao_receber_heartbeat(m)`: atualizo `ultimo_heartbeat[origem]`; se um heartbeat
  anuncia um líder de id **maior** que o meu e esse líder está vivo, **aceito** —
  evita disputa desnecessária logo após o boot.

### 6.7 `snapshot.py` — Chandy-Lamport sobre multicast

Realiza a **Seção 3.9**. O **canal lógico `j → i`** são as mensagens de chat que o
nó `i` recebe do nó `j` (campo `origem`); a ordem **FIFO** desse canal é
reconstruída pelo `seq_origem` — é assim que se atende o pressuposto de canais
FIFO **sem usar unicast**.

- `iniciar()`: `id_snapshot = "{meu_id}-{timestamp}"`; `_registrar_estado` (sem
  canal de entrada); difunde `MARCADOR`.
- `_registrar_estado`: o **estado local** guarda `num_seq_entregue`,
  `relogio_vetorial`, `lider`, `pendentes`, últimas entregas. Para cada outro nó: o
  canal do marcador entra **vazio**; os demais começam a **gravar**.
- `ao_receber_marcador(m)`: primeiro marcador do snapshot → registra estado e
  propaga; marcador seguinte → **fecha** o canal por onde veio.
- `ao_receber_mensagem_app(m)`: toda `CHAT_ENTREGA` recebida enquanto o canal
  daquela origem está aberto entra no **estado do canal**.
- `_talvez_concluir()`: quando fechou o canal de **todos** os outros → difunde
  `RESULTADO_SNAPSHOT` com seu pedaço.
- `_talvez_montar_fotografia()`: quem juntar os N resultados monta a fotografia
  global e a exibe (coleta simples por multicast; o iniciador quase sempre é quem
  junta todos, pois começou antes).

### 6.8 `nucleo.py` — o laço único e a cola

- `_laco()`: `while ativo` — pega uma mensagem de `fila_recebidas` (timeout 0,2 s),
  **sob `trava_estado`**: despacha por `tipo` (`_tratar`), roda
  `eleicao.tarefas_periodicas()` e `ordem.verificar_timeouts()`. Um **único laço**
  = não há duas threads mexendo no estado do protocolo ao mesmo tempo.
- `_novo_pedido(grupo, payload)`: `seq_origem_atual += 1`; `vetor =
  relogio.evento_envio()`; `id_msg = "{meu_id}:{seq}"`; monta `CHAT_PEDIDO`
  (`destino = lider_atual`); guarda em `enviadas_recentes`; `aguardar_carimbo`;
  difunde.
- `entregar_mensagem(m)`: chamado pela `OrdemTotal` quando um `num_seq` sai do
  buffer em ordem. Se a origem é outra → `relogio.ao_entregar`. Acrescenta a
  `ordem_global`. Se `payload.acao` → aplica no `RegistroGrupos`; senão, se membro
  → acrescenta à ordem local. Notifica a interface.
- `_detectar_lacuna_por_origem(m)`: buraco no `seq_origem` de um nó → `RETRANSMITIR`
  à origem.
- API para a interface: `enviar_chat`, `criar_grupo`, `abrir_privada`,
  `definir_nome`, `capturar_estado`, `forcar_eleicao`, `simular_queda`.

### 6.9 `interface.py` — a tela do nó (R5)

Tkinter, uma janela por nó. Elementos exigidos pelo R5, todos presentes:

- **Cabeçalho:** `No <id>` + `- <nome>` (se definido) + `| Papel: <LIDER/comum>`.
- **Nome deste nó:** campo + botão "Definir nome" (também via `--nome`).
- **Enviar para nó específico:** "Nova conversa privada" escolhe o id e abre
  `priv-a-b`.
- **Enviar para o grupo:** seletor de conversa + campo + "Enviar".
- **Criar grupo:** diálogo com nome + checkboxes de todos os ids.
- **Ordem local:** cada envio e cada entrega **observados por este nó**, na ordem
  em que aconteceram.
- **Mensagens do chat:** as mensagens **da conversa selecionada** no seletor, na
  ordem global (`#num_seq`). Trocar de conversa troca a vista. Para a mesma
  conversa (ex.: `geral`), a lista é **idêntica em todos os nós** — evidência da
  ordem total (R4). Mensagens de conversas de que o nó não participa não aparecem
  (a conversa nem está no seletor), então a tela não fica poluída com "restrito".
- **Extras:** relógio vetorial atual, `proximo num_seq esperado`, buffer de
  pendentes, log do sistema.
- Botões: "Capturar estado global", "Forçar eleição", "Simular queda".

A janela lê `fila_interface` a cada 100 ms (`_drenar_fila`) e repinta os painéis.

---

## 7. Fluxos completos

*(Bons para narrar no seminário, um por slide.)*

### 7.1 Uma mensagem de chat, do clique à ordem global

1. **Nó A** digita "oi" no grupo G e clica em Enviar. `interface._enviar` →
   `nucleo.enviar_chat("G", "oi")`.
2. `_novo_pedido`: `relogio.evento_envio()` (`V[A] += 1`); `seq_origem_atual += 1`;
   `id_msg = "A:seq"`; monta `CHAT_PEDIDO` (`grupo = G`, `payload = {"texto":"oi"}`,
   `relogio_vetorial = V`, `destino = líder`). Guarda em `enviadas_recentes` e em
   `aguardando_carimbo`. **Difunde por multicast.**
3. **Todos** recebem o `CHAT_PEDIDO`. Só o **líder** age (`ao_receber_pedido`):
   `num_seq = proximo_num_seq++`; monta `CHAT_ENTREGA` (cópia + `num_seq` +
   `carimbado_por`); guarda no histórico; **difunde**.
4. **Cada nó** recebe o `CHAT_ENTREGA` (`ao_receber_entrega`): guarda em
   `pendentes[num_seq]`; remove `id_msg` de `aguardando_carimbo`; `_tentar_entregar`.
5. `_tentar_entregar`: enquanto `proximo_num_seq_esperado ∈ pendentes` →
   `entregar_mensagem`: `relogio.ao_entregar` (se origem ≠ eu); **acrescenta à
   `ordem_global`**; se membro de G, acrescenta o texto à ordem local;
   `proximo_num_seq_esperado += 1`.
6. Como **todos** os nós recebem **todos** os `CHAT_ENTREGA` e entregam na ordem
   `1, 2, 3, …`, a **`ordem_global` fica idêntica em todos** (R4).

### 7.2 Criação de um grupo — por que não há corrida

Criar grupo é `payload = {"acao": "criar_grupo", "nome": ..., "membros": [...]}`
enviado pelo **mesmo caminho** de uma mensagem de chat (`CHAT_PEDIDO` → líder →
`CHAT_ENTREGA`), com `grupo = "g-<criador>-<seq>"`.

Ao **entregar** esse item na ordem do `num_seq`, cada nó chama
`RegistroGrupos.criar(...)`. Como a criação recebe um `num_seq` e **toda** mensagem
para o grupo recebe um `num_seq` **maior**, **todos** os nós registram o grupo
**antes** de qualquer mensagem dele. A membresia converge **sem caso especial** e
sem a corrida "mensagem chega antes da criação". É a replicação de máquina de
estados (Seção 3.10) aplicada à membresia.

### 7.3 Queda do líder e reeleição pelo anel

1. **"Simular queda"** no líder → `nucleo.simular_queda()` → `encerrar()`. O líder
   para de mandar heartbeat.
2. Após `T_FALHA` (6 s), o primeiro nó a notar o silêncio chama `iniciar_eleicao()`
   → `ELEICAO` com `ids_vistos = [meu_id]` para o próximo ativo.
3. A `ELEICAO` percorre o anel acumulando ids. Ao voltar a um nó **já presente** na
   lista → `COORDENADOR` com `lider = max(ids_vistos)`, difundido.
4. Cada nó adota o novo líder. O novo líder chama `ordem.ao_virar_lider(base)` e
   retoma o `num_seq` em `max(base, maior_conhecido + 1)`.
5. Autores com pedido sem carimbo há > `T_RETRANSMISSAO` reenviam; o novo líder
   sequencia. O chat volta a ordenar. O **log da tela** mostra cada passo
   (`eleicao iniciada…`, `anel completo […] -> lider N`, `COORDENADOR: lider = N`).

### 7.4 Captura de estado global

1. **"Capturar estado global"** (normalmente no líder) → `snapshot.iniciar()`:
   registra o estado local, difunde `MARCADOR`.
2. Cada nó, ao ver o **primeiro** marcador: registra seu estado, esvazia o canal do
   marcador, começa a gravar os outros canais, propaga o marcador.
3. Marcadores seguintes fecham os canais correspondentes.
4. Quando um nó fechou o canal de todos os outros, difunde `RESULTADO_SNAPSHOT`.
5. Quem junta os N resultados exibe a **fotografia global**: por nó, quantas
   mensagens entregou, o vetor, o líder; por canal, as mensagens em trânsito.

> Em `localhost` a entrega é quase instantânea, então os canais quase sempre
> aparecem **vazios**. Para mostrar um canal **não-vazio** no relatório: dispare o
> snapshot durante uma **rajada** de envios, ou use `ATRASO_ENVIO > 0` em
> `configuracao.py`.

### 7.5 Perda de um datagrama e recuperação

- Um `CHAT_ENTREGA` (`num_seq = 7`) se perde. Chega o 8. O nó tem `pendentes = {8}`
  mas `proximo_num_seq_esperado = 7` → **não entrega** (buffer de reordenação).
- Após `T_RETRANSMISSAO`, `verificar_timeouts` manda `RETRANSMITIR {num_seq: 7}` ao
  líder.
- O líder responde com o `CHAT_ENTREGA` 7 do `historico_por_num_seq`.
- O nó recebe o 7, entrega 7 e 8 em sequência. **A ordem final não muda.**

---

## 8. Exemplo numérico: dois nós chegam à mesma ordem total

*(Item obrigatório do relatório — roteiro, Seção 10.8. Mostra ordem causal ×
ordem total.)*

**Cenário:** 3 nós `{1, 2, 3}`, líder = 3, grupo `geral`. Vetores iniciam
`[1:0, 2:0, 3:0]`.

### 8.1 Duas mensagens concorrentes

| Passo | Evento | Vetor anexado | Ação do líder (3) |
|-------|--------|---------------|-------------------|
| 1 | Nó 1 envia **"A"** — `evento_envio` | `V(A) = [1:1, 2:0, 3:0]` | — |
| 2 | Nó 2 envia **"B"** — `evento_envio` | `V(B) = [1:0, 2:1, 3:0]` | — |
| 3 | A rede reordena: o líder recebe **"B"** primeiro | | `num_seq(B) = 1`, difunde `CHAT_ENTREGA` |
| 4 | O líder recebe **"A"** | | `num_seq(A) = 2`, difunde `CHAT_ENTREGA` |
| 5 | Nós 1, 2 e 3 entregam por `num_seq` | | **ordem global = [B, A]** nos três |

`V(A) = [1:1, 2:0, 3:0]` e `V(B) = [1:0, 2:1, 3:0]` são **concorrentes**: nem
`V(A) ≤ V(B)` (falha em `k = 1`) nem `V(B) ≤ V(A)` (falha em `k = 2`). Logo
`A ∥ B` — não havia relação de causa e efeito a respeitar. Foi o **`num_seq` do
líder** que definiu a ordem total. Sem esse critério extra, o nó 1 (que viu "A"
primeiro localmente) poderia entregar `[A, B]` e o nó 2 poderia entregar `[B, A]` —
**divergência**. É exatamente o problema da Seção 3.5.1.

### 8.2 Caso com dependência causal (A → C)

| Passo | Evento | Vetor |
|-------|--------|-------|
| 1 | Nó 1 envia **"A"** | `V(A) = [1:1, 2:0, 3:0]`; o líder dá `num_seq(A) = 1` |
| 2 | Nó 2 **entrega "A"** — `ao_entregar` | `V2 = max([0,0,0], [1:1,2:0,3:0]) = [1:1,2:0,3:0]`, depois `V2[2]++` → `[1:1, 2:1, 3:0]` |
| 3 | Nó 2 envia **"C"** — `evento_envio` | `V(C) = [1:1, 2:2, 3:0]` |

Agora `V(A) = [1:1, 2:0, 3:0] < V(C) = [1:1, 2:2, 3:0]` (menor-ou-igual em todo
componente e diferente) → **`A → C`**: "A" precede causalmente "C".

O sequenciador respeita isso **naturalmente**: "C" só foi enviada **depois** de o
nó 2 entregar "A", e "A" já tinha ido ao líder e recebido `num_seq = 1`. Quando o
líder recebe o pedido de "C", atribui `num_seq ≥ 2`. Qualquer ordem total válida
põe **A antes de C**. Isso ilustra "ordem parcial (causal) ⊆ ordem total".

---

## 9. Requisitos do roteiro → onde são atendidos

| # | Requisito | Teoria | Código |
|---|-----------|--------|--------|
| R1 | Comunicação de grupo | 3.1 | `rede.py` + grupo `224.1.1.1:5007` |
| R2 | Chat (privada, grupo, criar grupo) | 3.10, 6.5 | `nucleo.py`, `grupos.py`, `interface.py` |
| R3 | N configurável ≥ 15 | 2.1 | `iniciar.py --n K` gera `nos.json` |
| R4 | Ordem total | 3.5, 3.6 (Abordagem B) | `ordem_total.py` |
| R5 | Tela do nó | 4.2 | `interface.py` |
| R6 | Estado global | 3.9 (Chandy-Lamport) | `snapshot.py` |
| R7 | Relatório | — | este documento + `manual_de_uso.md` + `plano_implementacao.md` |
| R8 | Eleição de líder | 3.7 (anel), 3.8 | `eleicao.py` |

---

## 10. Limitações conhecidas

*(Roteiro, Seção 10.6 — registrar no relatório. Reconhecer as limitações **conta a
favor**: mostra domínio do modelo.)*

1. **UDP/multicast não é confiável.** Mitigamos com `seq_origem`, detecção de
   lacuna e retransmissão sob demanda (NAK), mas **não há garantia absoluta** de
   entrega. Multicast entre máquinas depende do roteador; os testes são em
   `localhost`.
2. **O sequenciador é um ponto crítico.** A queda é tratada com reeleição em anel,
   mas mensagens que o líder **carimbou** e não conseguiu **propagar** na janela da
   queda podem se perder. (Um sistema de produção usaria consenso replicado — Raft,
   Paxos — para o log; aqui isso está fora de escopo.)
3. **Privacidade é lógica**, não criptográfica. O app filtra o que exibe, mas o
   datagrama chega fisicamente a todos os nós do multicast.
4. **Snapshot pressupõe canais FIFO e confiáveis.** Reconstruímos FIFO por
   `seq_origem`; sob perda de datagrama durante o snapshot, um canal pode ficar
   incompleto. Em `localhost` os canais quase sempre aparecem vazios.
5. **Nome do nó é local.** Serve só para identificar a janela; não é propagado na
   rede, então um nó não mostra o nome que os outros escolheram — as mensagens
   sempre identificam o autor por `No <id>`.
6. **Detecção de falha não é perfeita** (modelo assíncrono — Seção 3.8). Um nó
   muito lento pode ser suspeitado como caído e disparar uma eleição desnecessária.
7. **Sem recuperação:** um nó que caiu não reingressa no meio da simulação.

---

## 11. Roteiro do seminário

Entrega 2: **slides + apresentação em aula, 16/09/2026**. Alvo ~15 min +
perguntas.

### 11.1 Estrutura de slides sugerida

| # | Slide | Conteúdo | Fonte |
|---|-------|----------|-------|
| 1 | Capa | Tema, equipe, disciplina | — |
| 2 | O problema | Chat distribuído, N processos, só rede; R1–R8 em uma linha | §1 |
| 3 | Modelo de sistema | Assíncrono, crash, canais UDP multicast best-effort | §2 |
| 4 | Comunicação de grupo | Multicast IP: grupo, TTL, um `sendto` → todos | §3.1, §6.1 |
| 5 | Relógios lógicos | Lamport escalar → limitação → vetorial; `V(a)<V(b) ⟺ a→b` | §3.2–3.4 |
| 6 | **Causal ≠ Total** | O slide mais importante: parcial vs total, por que o vetor não basta | §3.5.1 |
| 7 | Ordem total | Abordagem A × B; escolhemos **sequenciador fixo eleito**; trade-offs | §3.6 |
| 8 | Exemplo numérico | Tabela: dois nós, mensagens concorrentes, mesma ordem `[B, A]` | §8 |
| 9 | Eleição de líder | Anel (Chang-Roberts) passo a passo; por que não Bully; continuidade do `num_seq` | §3.7 |
| 10 | Estado global | Corte consistente; Chandy-Lamport (marcadores); canais por `origem` | §3.9, §6.7 |
| 11 | Arquitetura | 1 processo/nó; 3 threads + 2 filas + 1 lock; diagrama | §4 |
| 12 | Demonstração ao vivo | (roteiro em 11.2) | — |
| 13 | Limitações | UDP, ponto único no sequenciador, privacidade lógica | §10 |
| 14 | Encerramento | O que cada requisito comprova; perguntas | §9 |

### 11.2 Demonstração ao vivo — passo a passo

Prepare **antes**: terminal na raiz do projeto; janelas organizadas lado a lado.

1. **Subir 3 nós:**
   `python src/iniciar.py --n 3 --nomes Alice Bob Carol`
   Aponte: 3 janelas, cabeçalho `No X - <nome> | Papel`. O nó 3 já é `LIDER` (maior
   id, eleição de boot — §3.7).
2. **Ordem total (R4):** com `geral` selecionado nos 3 nós, envie 2–3 mensagens
   rápidas de nós diferentes. Mostre o painel **Mensagens do chat** das 3 janelas
   lado a lado: **mesma sequência de `#num_seq`** em todas. Esse é o critério de
   correção.
3. **Relógio vetorial (§3.4):** aponte o vetor mudando a cada entrega; comente que
   ele mostra causalidade, não decide a ordem.
4. **Criar grupo (R2):** no nó 1, "Criar grupo", nome "Equipe", marque o nó 2.
   A conversa "Equipe" aparece no seletor dos nós 1 e 2 (não no nó 3). Selecione-a e
   troque a vista de `geral` para "Equipe": o painel só mostra as mensagens dela.
   Mande uma mensagem; o nó 3 não a vê (nem tem essa conversa), mas o `num_seq`
   dela existe na ordem global de todos — a ordem total não muda (§6.5).
5. **Conversa privada (R2):** no nó 1, "Nova conversa privada" → id 2. Mande uma
   mensagem **antes** de o nó 2 abrir nada. No nó 2, a conversa `priv-1-2` aparece
   sozinha no seletor (o log avisa "conversa privada … aberta com o no 1") e a
   mensagem está lá — a correção do bug em que o alvo via "restrito" (§6.5).
6. **Estado global (R6):** clique "Capturar estado global" no líder. Mostre a
   janela da fotografia: `num_seq` entregue por nó, vetores, líder. Comente que os
   canais aparecem vazios porque é `localhost` (§7.4).
7. **Eleição (R8):** clique "Simular queda" no nó 3 (líder). Espere ~6 s
   (`T_FALHA`). Mostre o **log** dos nós 1 e 2: `eleicao iniciada…` →
   `anel completo [1, 2] -> lider 2` → `COORDENADOR: lider = 2`. O cabeçalho do
   nó 2 vira `LIDER`. Envie uma mensagem: o chat volta a ordenar, `num_seq`
   continua sem buraco (§7.3).
8. **Recuperação de perda (opcional):** se der tempo, comente como o buffer
   `pendentes` + `RETRANSMITIR` recuperam um `CHAT_ENTREGA` perdido (§7.5).
9. **Testes:** `python testes/teste.py` — 3 cenários automatizados (5 nós, queda
   do líder, 15 nós + snapshot), todos passando.

### 11.3 Perguntas prováveis da banca (e respostas curtas)

- **"Por que o vetor não garante ordem total?"** Porque ele só ordena eventos
  causalmente relacionados; mensagens concorrentes ficam incomparáveis e podem ser
  entregues em ordens diferentes. Precisa de um desempate que todos apliquem igual
  — aqui, o `num_seq` do líder. (§3.5.1)
- **"Por que sequenciador e não a abordagem descentralizada?"** Simplicidade,
  latência baixa (entrega assim que o `num_seq` esperado chega, sem esperar todos)
  e encaixe direto com eleição e snapshot. O custo é o ponto único, que tratamos
  com reeleição. (§3.6)
- **"E se o líder cair no meio de uma mensagem?"** As mensagens já entregues estão
  a salvo (todos as viram). Uma que ele carimbou e não propagou pode se perder — é
  limitação registrada. O autor reenvia o pedido se não vir o carimbo. (§3.7, §10)
- **"Como o snapshot funciona sem parar o sistema?"** Marcadores de Chandy-Lamport:
  o marcador separa "antes" de "depois" em cada canal; mensagens que chegam depois
  do estado local e antes do marcador daquele canal são o estado do canal. Corte
  consistente por construção. (§3.9)
- **"Vocês usam memória compartilhada entre os nós?"** Não. Só multicast. O
  `nos.json` é catálogo estático lido no boot; as filas e o lock são **internos** a
  cada processo. (§2.1)
- **"Por que anel e não Bully?"** Sobre multicast com `destino`, o anel é um
  caminho único e previsível (uma volta + um anúncio), fácil de mostrar passo a
  passo. Bully gera `O(N²)` mensagens e vários timeouts concorrentes. (§3.7)
- **"A ordem total respeita a causalidade?"** Sim. Uma mensagem só é enviada após
  suas causas serem entregues no emissor, então o líder a recebe (e carimba) depois
  das que a precedem. É um atomic broadcast. (§3.6)

---

## 12. Glossário

- **Multicast IP:** difusão a um grupo de hosts inscritos; um datagrama chega a
  todos. Faixa 224.0.0.0–239.255.255.255.
- **happened-before (`→`):** relação de causalidade potencial entre eventos
  (Lamport). Ordem **parcial**.
- **Eventos concorrentes (`∥`):** nem `a → b` nem `b → a`.
- **Relógio de Lamport (escalar):** contador que cresce em eventos e em recepções;
  `a → b ⟹ C(a) < C(b)` (só a ida).
- **Relógio vetorial:** um contador por processo; `V(a) < V(b) ⟺ a → b`
  (ida e volta). Detecta concorrência.
- **Ordem FIFO / causal / total:** ver §3.5.
- **Atomic broadcast (difusão atômica):** difusão com ordem total (e, aqui, também
  causal). Equivalente a consenso.
- **Sequenciador fixo:** processo designado que numera todas as mensagens; se cai,
  outro é eleito. (Taxonomia de Défago et al.)
- **`num_seq`:** número de sequência global atribuído pelo líder; define a ordem
  total.
- **Detector de falhas:** componente que suspeita de processos caídos por timeout;
  no assíncrono é necessariamente **imperfeito**.
- **FLP:** impossibilidade de consenso determinístico no modelo assíncrono com uma
  falha (Fischer, Lynch, Paterson, 1985).
- **Corte consistente:** corte do sistema em que nenhuma mensagem é recebida sem
  ter sido enviada.
- **Snapshot / Chandy-Lamport:** algoritmo que grava um corte consistente com
  marcadores, sem parar o sistema.
- **Replicação de máquina de estados:** mesmas entradas na mesma ordem →
  mesmo estado em todas as réplicas.
- **NAK (ACK negativo):** pedido de retransmissão do que faltou (`RETRANSMITIR`).

---

## 13. Referências

**Textos base**

- COULOURIS, G.; DOLLIMORE, J.; KINDBERG, T.; BLAIR, G. *Distributed Systems:
  Concepts and Design*. 5. ed. (capítulos de tempo/coordenação e multicast
  confiável/ordenado).
- TANENBAUM, A. S.; VAN STEEN, M. *Distributed Systems: Principles and Paradigms*
  (relógios lógicos, exclusão mútua, eleição, snapshots).

**Artigos seminais**

- LAMPORT, L. "Time, Clocks, and the Ordering of Events in a Distributed System".
  *Communications of the ACM*, 1978.
- MATTERN, F. "Virtual Time and Global States of Distributed Systems". 1988 —
  relógios vetoriais (também FIDGE, C., 1988).
- CHANDY, K. M.; LAMPORT, L. "Distributed Snapshots: Determining Global States of
  Distributed Systems". *ACM TOCS*, 1985.
- CHANG, E.; ROBERTS, R. "An Improved Algorithm for Decentralized Extrema-Finding
  in Circular Configurations of Processes". *CACM*, 1979 — algoritmo do anel.
- GARCIA-MOLINA, H. "Elections in a Distributed Computing System". *IEEE
  Transactions on Computers*, 1982 — algoritmo Bully.
- FISCHER, M.; LYNCH, N.; PATERSON, M. "Impossibility of Distributed Consensus with
  One Faulty Process". *Journal of the ACM*, 1985 — FLP.
- CHANDRA, T.; TOUEG, S. "Unreliable Failure Detectors for Reliable Distributed
  Systems". *Journal of the ACM*, 1996.
- DÉFAGO, X.; SCHIPER, A.; URBÁN, P. "Total Order Broadcast and Multicast
  Algorithms: Taxonomy and Survey". *ACM Computing Surveys*, 2004.
- SCHNEIDER, F. B. "Implementing Fault-Tolerant Services Using the State Machine
  Approach: A Tutorial". *ACM Computing Surveys*, 1990.

**Documentação técnica**

- Python Software Foundation. Módulo `socket` (multicast, `IP_ADD_MEMBERSHIP`,
  `IP_MULTICAST_TTL`, `SO_REUSEADDR`) e `struct`.
- RFC 1112 — *Host Extensions for IP Multicasting*.
