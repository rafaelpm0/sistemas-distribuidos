---
name: codigo-trabalhos-aula
description: Use esta skill sempre que o usuário pedir ajuda para escrever, revisar ou corrigir código de um trabalho, exercício, lista ou projeto de aula/faculdade em qualquer linguagem de programação. Aplique mesmo que o usuário não peça explicitamente "código simples" — o objetivo é sempre entregar a solução mais direta que atende ao enunciado, com comentários enxutos e organização clara, evitando abstrações, bibliotecas externas ou padrões de projeto desnecessários para o escopo pedido. Não use para código de produção, sistemas reais em produção, ou quando o usuário pedir explicitamente algo "profissional", "escalável" ou "pronto para produção".
---

# Código para trabalhos de aula

Objetivo: código que um estudante entregaria com confiança — correto, legível e do tamanho certo para o problema. Nada de resolver um exercício de "somar dois números" com um framework de plugins.

## 1. Simplicidade acima de tudo (evitar over-engineering)

- Resolva exatamente o que o enunciado pede — nem mais, nem menos. Não adicione tratamento de casos que o enunciado não menciona, nem generalize "pra caso precise no futuro".
- Prefira estruturas de controle simples (if/for/while) a abstrações (classes, interfaces, padrões de projeto, injeção de dependência) a menos que o enunciado peça explicitamente POO ou uma estrutura específica.
- Use só a biblioteca padrão da linguagem, salvo se o exercício pedir uma biblioteca específica (numpy, pandas etc.).
- Não crie múltiplos arquivos/módulos para um exercício pequeno — um único arquivo é normal e esperado em trabalhos de aula, a menos que o enunciado peça separação.
- Se existirem duas formas de resolver, uma "elegante/genérica" e outra "direta e óbvia", escolha a direta — desde que sem perda relevante de legibilidade ou eficiência para o tamanho do problema.
- Evite otimizações prematuras (ex: memoização, complexidade O(log n) via estrutura avançada) quando uma solução O(n) simples já resolve o problema no tamanho pedido.

## 2. Comentários simples

- Comente o "porquê", não o "o quê" — o código já mostra o que faz; o comentário explica a decisão ou a lógica não óbvia.
- Evite comentar linha a linha ou parafrasear o código (`i += 1  # incrementa i` é ruído, não comentário).
- Um comentário curto (1 linha) no topo de cada função explicando o que ela faz é suficiente — não precisa de docstring completa estilo biblioteca profissional, a menos que peçam.
- Comente partes que exigem raciocínio (uma fórmula, uma condição não óbvia, por que um caso especial foi tratado assim).

## 3. Organização de código

- Nomes de variáveis e funções devem ser descritivos e no idioma predominante do enunciado/curso (geralmente português, salvo se o curso for em inglês).
- Separe claramente: leitura de entrada → processamento/lógica → saída. Mesmo em um único arquivo, isso pode ser feito com funções pequenas e bem nomeadas.
- Indentação e formatação consistentes com o padrão da linguagem (PEP8 para Python, etc.), sem precisar de linters ou ferramentas extras.
- Evite funções gigantes: se uma função passa de ~20-30 linhas ou faz claramente duas coisas, considere quebrar em duas — mas só se isso deixar o código mais claro, não por regra rígida.

## Ao entregar a resposta

- Depois do código, se fizer sentido, adicione 1-3 frases explicando a lógica geral da solução (não repita o que já está comentado).
- Se o usuário pedir algo que claramente foge do escopo de um trabalho de aula (ex: "faz isso com padrão Factory" num exercício básico), pode seguir o pedido, mas é válido comentar rapidamente que uma versão mais simples também resolveria, caso ele queira comparar.
