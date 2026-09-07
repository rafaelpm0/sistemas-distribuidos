# Manual de Uso — Chat Distribuído

Trabalho 1 de Sistemas Distribuídos (UNIVALI, Prof. Ramicés).

Este manual explica **como executar e usar** o sistema e **por que** cada decisão
de projeto foi tomada. A parte "como fazer" vem primeiro; a justificativa das
escolhas está na Seção 6 e serve de base para o relatório.

Para a **base teórica** (relógios lógicos, ordem total, Chandy-Lamport, eleição) e
a preparação do seminário, ver `manual_teorico.md`.

---

## 1. O que é

Um chat em que **cada nó é um participante** rodando como processo separado. Os nós
só se falam por **mensagens de rede multicast**. O sistema garante:

- **Comunicação de grupo**: uma mensagem enviada ao grupo chega a todos.
- **Ordem total**: todos os nós veem as mensagens de grupo na mesma ordem.
- **Grupos com nome e membros escolhidos**: qualquer nó cria um grupo, dá um nome
  e seleciona quem participa.
- **Conversas privadas**: entre exatamente dois nós.
- **Estado global**: um comando tira uma "fotografia" consistente de todo o sistema.
- **Eleição de líder**: se o líder cai, os nós elegem outro automaticamente.

---

## 2. Requisitos

- Python 3.8 ou superior (só biblioteca padrão — nada de `pip install`).
- Windows, Linux ou macOS.
- `tkinter` disponível (vem com o Python padrão; no Linux pode ser o pacote
  `python3-tk`).
- Multicast em `localhost` habilitado (padrão na maioria dos sistemas).

---

## 3. Como executar

Todos os comandos são rodados **a partir da raiz do projeto** (a pasta que contém
`src/`, `testes/` e `docs/`). O código fica em `src/`, os testes em `testes/`.

### 3.1 Forma rápida (recomendada para a demonstração)

```
python src/iniciar.py --n 3
```

Isso gera o `nos.json` para 3 nós e abre **3 janelas**, uma por nó. Para os outros
tamanhos exigidos pelo roteiro:

```
python src/iniciar.py --n 8
python src/iniciar.py --n 15
```

O código não muda entre os tamanhos — só o argumento `--n`.

Opcionalmente dá para nomear os nós (aparece no cabeçalho e no título da janela,
facilita achar cada nó na tela):

```
python src/iniciar.py --n 3 --nomes Alice Bob Carol
```

Os nomes são associados aos ids na ordem (1 = Alice, 2 = Bob, …); ids sem nome
ficam sem nome.

### 3.2 Forma manual (uma janela por terminal)

Útil para ver a tela de cada nó separada. Primeiro gere o catálogo (ou use um
`nos.json` já pronto) e então, em cada terminal:

```
python src/no.py --id 1 --config nos.json
python src/no.py --id 2 --config nos.json
python src/no.py --id 3 --config nos.json
```

Não é preciso subir todos os nós do catálogo ao mesmo tempo: o sistema funciona
com o subconjunto que estiver no ar.

Para identificar melhor o nó na tela, passe um nome com `--nome`:

```
python src/no.py --id 1 --nome Alice --config nos.json
```

O nome é só para exibição (cabeçalho e título da janela); a coordenação continua
usando o `--id`. Também dá para definir ou trocar o nome depois, pela própria tela
(campo "Nome deste nó" + botão "Definir nome").

### 3.3 Testes automatizados

```
python testes/teste.py
```

Sobe nós de verdade (processos separados, só rede), cada um executa um roteiro de
comandos e grava a saída; o script compara as saídas. Cobre: ordem total idêntica
com 5 e 15 nós, criação de grupo com membros escolhidos, conversa privada, queda
do líder com reeleição pelo anel e continuidade da numeração, e a captura do
estado global. O modo sem interface (`python src/no.py --id K --sem-interface
--script <arquivo> --saida <arquivo>`) também serve para montar cenários próprios
para o relatório.

---

## 4. A tela do nó

| Área | Para que serve |
|------|----------------|
| Cabeçalho | `No <id>` e, se definido, o nome do nó; e o papel (líder ou comum). |
| "Nome deste nó" + "Definir nome" | Campo para digitar/alterar o nome do nó em tempo de execução (mesma coisa que o `--nome`, mas pela tela). |
| Seletor "Conversa" | Escolhe a conversa ativa: `geral`, um grupo de que o nó é membro, ou uma conversa privada. **Também define o que o painel "Mensagens do chat" mostra.** |
| Campo de texto + "Enviar" | Envia a mensagem para a conversa selecionada. |
| "Criar grupo" | Nome do grupo + seleção de membros; abre a conversa nos nós escolhidos. |
| "Nova conversa privada" | Escolhe o id do outro nó e abre a conversa `priv-a-b`. |
| Painel "Relógio vetorial" | O vetor atual do nó e o `num_seq` que ele espera entregar em seguida. |
| **Ordem local** | Tudo que **este** nó emitiu ou entregou, na ordem em que aconteceu. |
| **Mensagens do chat** | As mensagens **da conversa selecionada**, na ordem global (`num_seq`). Trocar de conversa no seletor troca o que aparece aqui. Para a mesma conversa (ex.: `geral`), a lista é **idêntica em todos os nós** — é a evidência da ordem total (R4). |
| Log do sistema | Eleições, marcadores de snapshot, retransmissões, abertura de conversa privada pelo outro lado. |
| "Capturar estado global" | Dispara o snapshot de Chandy-Lamport. |
| "Forçar eleição" | Inicia o algoritmo do anel sem esperar o líder cair. |
| "Simular queda" | Encerra este processo — use no nó líder para demonstrar a reeleição. |

---

## 5. Como fazer cada coisa

### Enviar mensagem para o grupo
Seletor em `geral`, digite, "Enviar". Em segundos a mensagem aparece no painel
**Mensagens do chat** de todos os nós, na mesma posição (`num_seq`).

### Alternar entre conversas
O seletor "Conversa" define a conversa ativa. O painel **Mensagens do chat** mostra
só as mensagens dessa conversa — trocar no seletor troca a vista. Nós que não são
membros de um grupo simplesmente não têm aquela conversa no seletor (não aparece
"mensagem restrita" para poluir a tela). A ordem/`num_seq` das mensagens que você
vê continua sendo a ordem global.

### Criar um grupo com membros escolhidos
"Criar grupo" → digite o nome → marque os ids que vão participar (você entra
automaticamente) → confirmar. O grupo aparece no seletor "Conversa" nos nós
membros. Como o pedido passa pelo sequenciador do líder, todos os nós registram o
grupo na mesma posição da ordem global, antes de qualquer mensagem dele.

### Abrir e usar uma conversa privada
"Nova conversa privada" → escolha o id do outro nó. A conversa `priv-a-b` aparece
no seletor e fica ativa. **Não é preciso o outro lado abrir primeiro:** ao chegar a
primeira mensagem, o nó de destino registra a conversa automaticamente (o log
avisa) e ela aparece no seletor dele. Os demais nós não participam e não veem a
conversa.

### Capturar o estado global
Clique em "Capturar estado global" (normalmente no líder). O sistema executa
Chandy-Lamport e, quando todos os pedaços chegam, exibe a fotografia: quantas
mensagens cada nó já entregou, o vetor de cada nó e as mensagens que estavam "em
trânsito" em cada canal. Para ver um canal **não-vazio**, dispare o snapshot
durante uma rajada de envios.

### Ver a eleição acontecendo
Clique em "Forçar eleição" em qualquer nó, ou "Simular queda" no líder. O log
mostra a mensagem de eleição circulando o anel e depois o anúncio do coordenador.
O maior id ativo vira o novo líder e o chat volta a ordenar normalmente.

### Provar a ordem total (critério de correção do roteiro)
Deixe a conversa `geral` selecionada em dois ou mais nós e compare o painel
**Mensagens do chat**: a sequência de `#num_seq` e de mensagens deve ser exatamente
igual em todos (todos os nós são membros de `geral`, então nada fica escondido).

---

## 6. Justificativa das escolhas

O roteiro pede que cada decisão de projeto seja justificada. Abaixo, cada escolha
com a alternativa que foi descartada e o porquê.

### 6.1 Comunicação: só multicast (não unicast)

**Escolha:** um único grupo multicast `224.1.1.1:5007` para tudo — chat e controle.
Mensagens direcionadas (eleição, retransmissão) também vão por multicast, com um
campo `destino`; quem não é o alvo ignora.

**Por quê:** um app de mensagens é, por natureza, comunicação de grupo — um envio
precisa chegar a todos os participantes. O multicast IP faz isso nativamente, com
um datagrama só, sem o nó emissor iterar sobre a lista de destinos. O código de
rede fica pequeno.

**Alternativa descartada (unicast/TCP):** daria entrega confiável e FIFO de graça,
mas exigiria N conexões por nó e uma difusão "manual" (laço sobre todos os nós)
para cada mensagem de grupo — mais código e menos fiel à ideia de "comunicação de
grupo nativa".

**Custo assumido:** UDP não é confiável. Tratamos isso na camada de ordenação com
número de sequência por origem, detecção de lacuna e retransmissão sob demanda
(Seção 10 do plano).

### 6.2 Ordem total: sequenciador definido pelo líder (Abordagem B)

**Escolha:** o líder recebe cada mensagem de grupo, atribui um `num_seq` global
crescente e **redifunde a mensagem completa** já carimbada. Todos os nós entregam
estritamente na ordem do `num_seq`.

**Por quê:** a ordem total sai simples e barata — um inteiro crescente que todos
respeitam. Encaixa diretamente com os outros dois requisitos: a **eleição de
líder** (o líder já existe, é o sequenciador) e o **estado global** (o líder é o
iniciador natural do snapshot). Para um chat, latência baixa de entrega importa, e
o sequenciador entrega assim que o `num_seq` esperado chega, sem esperar
confirmação de todos os nós.

**Alternativa descartada (Abordagem A — relógio vetorial + desempate
determinístico):** é totalmente descentralizada e sem ponto único de falha, mas
para entregar uma mensagem cada nó precisa ter certeza de que nenhuma mensagem com
chave menor ainda pode chegar — o que exige esperar "algo" de todos os nós
(mensagens estáveis/ACK) e batimentos periódicos para não travar quando um nó fica
quieto. Mais latência, mais mensagens de controle e mais casos de borda. Trocamos
robustez a ponto único por simplicidade e latência.

**Custo assumido:** o líder é ponto crítico. Obrigatório tratar a queda — feito com
reeleição em anel (Seção 6.4). Mensagens que o líder carimbou mas não conseguiu
propagar na janela da queda podem se perder; registrado como limitação.

### 6.3 Relógio vetorial mesmo com sequenciador

**Escolha:** cada nó mantém um relógio vetorial, atualizado no envio e na entrega,
e o exibe na tela. Ele **não** decide a ordem de entrega — isso é do `num_seq`.

**Por quê:** um dos objetivos de aprendizagem do trabalho é **distinguir ordem
causal (parcial) de ordem total**. O vetor é o que torna essa distinção visível:
na tela dá para ver que duas mensagens são concorrentes e que foi o líder quem
desempatou; no relatório, o vetor alimenta o exemplo numérico obrigatório. É o
"controle interno de causalidade" de cada nó.

**Política de incremento (documentada, como o roteiro exige):** incrementa a
própria posição no **envio** e na **entrega**; a recepção crua de um datagrama não
mexe no vetor (a mensagem primeiro precisa ser entregue na ordem do `num_seq`).

**Alternativa descartada (buffer de entrega causal por vetor, além do `num_seq`):**
seguraria a mensagem se o vetor apontasse dependência ausente. Com um sequenciador
único isso é praticamente redundante — o líder já ordena, e uma mensagem só é
enviada depois que suas causas foram entregues no emissor, então o `num_seq`
respeita a causalidade. Não vale o código extra.

### 6.4 Eleição: algoritmo do anel (não Bully)

**Escolha:** os nós formam um anel lógico pelos ids em ordem crescente. Todo nó
manda um batimento a cada ~2 s; se o líder some por ~6 s, um nó inicia uma mensagem
de eleição que circula o anel acumulando ids. Quando ela volta à origem, o maior
id é o novo líder, anunciado em outra volta.

**Por quê:** sobre multicast com campo `destino`, o anel é direto — cada passo é
uma mensagem para o "próximo nó ativo". O fluxo é determinístico e fácil de mostrar
passo a passo no seminário (a mensagem dá exatamente uma volta e meia).

**Alternativa descartada (Bully):** ao detectar a queda, o nó dispara `ELEIÇÃO`
para **todos** os ids maiores e espera respostas com timeout; cada um desses pode
disparar a sua. Gera mais mensagens simultâneas e mais timeouts concorrentes para
raciocinar. O anel troca isso por um caminho único e previsível.

**Continuidade:** o novo líder retoma a numeração em `maior_num_seq_visto + 1`
(todos os nós conhecem esse valor); autores com pedido sem carimbo reenviam o
pedido.

### 6.5 Estado global: Chandy-Lamport (não coleta centralizada pelo líder)

**Escolha:** o algoritmo de snapshot de Chandy-Lamport. O iniciador registra seu
estado e difunde um `MARCADOR`; ao receber o primeiro marcador, cada nó registra
seu estado, esvazia o canal de onde veio o marcador, propaga o marcador e grava as
mensagens dos outros canais até o marcador de cada um chegar.

**Por quê:** é a solução canônica vista em aula e respeita a regra "somente
mensagens de rede". Não exige parar o sistema nem relógio sincronizado, e produz um
corte **consistente** (nenhuma mensagem aparece como recebida sem ter sido
enviada). Os canais lógicos são identificados pelo campo `origem` e a ordem FIFO de
cada canal é reconstruída pelo `seq_origem` — não precisa de unicast.

**Alternativa descartada (o líder pergunta a todos e junta as respostas):** seria
mais simples de codar, mas concentra tudo num ponto único de falha e pode capturar
um estado inconsistente se as respostas chegam em momentos diferentes sem controle
dos canais. Chandy-Lamport resolve isso pela definição.

### 6.6 Interface: Tkinter, uma janela por nó

**Por quê:** Tkinter é biblioteca padrão (sem dependências) e uma janela por
processo deixa o requisito R5 visível ao vivo — dá para pôr as 3, 8 ou 15 janelas
lado a lado e comparar a **ordem global** entre elas durante a demonstração. O
Tkinter não é thread-safe, então a rede roda em threads separadas que empurram
eventos por uma fila, e a janela lê essa fila a cada 100 ms.

### 6.7 Grupos (nomeados e privados) no mesmo multicast e no mesmo sequenciador

**Escolha:** além do `geral` (todos), qualquer nó cria um grupo com **nome** e
**lista de membros escolhida na criação**. A criação é um pedido que passa pelo
**sequenciador do líder**, igual a uma mensagem de chat: recebe um `num_seq` e é
aplicada por todos os nós nessa ordem. Uma conversa privada é o caso particular de
um grupo de 2 membros.

**Por quê:** manter **um único** mecanismo de transporte (o multicast) e **um
único** mecanismo de ordem (o `num_seq` do líder). Ordenar a criação do grupo
junto com as mensagens elimina o caso de corrida "mensagem chega antes da
criação" — todos os nós veem a criação no mesmo ponto da sequência, então a lista
de membros converge sem código especial.

**Custo assumido:** a privacidade é **lógica** — o app não exibe mensagens de grupo
em que o nó não é membro, mas o datagrama chega fisicamente a todos os nós do
multicast. Sem criptografia. Se o líder está caído, criar grupo espera a
reeleição, como qualquer outra operação. Registrado como limitação.

### 6.8 Processos separados + `nos.json` estático

**Por quê:** a regra 11 do roteiro proíbe qualquer memória, banco, arquivo ou
variável compartilhada como canal de coordenação. Cada nó é um processo do SO com
estado privado. O `nos.json` é lido só na inicialização e serve apenas de catálogo
de endereços (ids e total de nós) — não é usado para coordenar nada em tempo de
execução.

---

## 7. Endereços de rede (para o relatório)

- **Grupo multicast:** `224.1.1.1`, porta `5007`, TTL `1` (testes em `localhost`).
  Faixa multicast IPv4: `224.0.0.0` a `239.255.255.255`.
- **Catálogo de nós** (`host`/`porta` só como referência; a comunicação é toda
  multicast):

| Id | Host | Porta (catálogo) |
|----|------|------------------|
| 1 | 127.0.0.1 | 5001 |
| 2 | 127.0.0.1 | 5002 |
| 3 | 127.0.0.1 | 5003 |
| … | 127.0.0.1 | 5000 + id |

- `SO_REUSEADDR` (e `SO_REUSEPORT` onde existir) permite vários nós na mesma
  máquina escutando a porta do grupo.

---

## 8. Limitações conhecidas

- UDP/multicast pode perder, duplicar ou reordenar datagramas. Mitigado com
  `seq_origem`, detecção de lacuna e retransmissão sob demanda — não é garantia
  absoluta.
- O líder-sequenciador é ponto crítico. A queda é tratada com reeleição em anel,
  mas mensagens carimbadas e não propagadas na janela da queda podem se perder.
- Privacidade é lógica (filtro no app), sem criptografia.
- Multicast entre máquinas diferentes depende da rede/roteador; os testes são em
  `localhost`.
- Em `localhost`, os canais no snapshot quase sempre aparecem vazios; use uma
  rajada de mensagens ou o atraso opcional de envio para demonstrar canal
  não-vazio.

---

## 9. Solução de problemas

| Sintoma | Causa provável | O que fazer |
|---------|----------------|-------------|
| Janelas abrem mas não trocam mensagens | Firewall bloqueando UDP multicast em `localhost` | Liberar o Python no firewall; testar com TTL 1. |
| "Address already in use" ao subir nós | Porta do grupo presa de uma execução anterior | Fechar as janelas antigas; esperar alguns segundos; `SO_REUSEADDR` já está ligado. |
| Um nó nunca vira líder | O maior id não está no ar | Normal — o anel elege o maior id **ativo**. Suba o nó de maior id ou use "Forçar eleição". |
| Ordem global diferente entre dois nós | Um `CHAT_ENTREGA` perdido e ainda não retransmitido | Aguardar o `T_RETRANSMISSAO`; a fila converge. Se persistir, é bug a investigar. |
| `tkinter` não encontrado (Linux) | Pacote separado | Instalar `python3-tk`. |
