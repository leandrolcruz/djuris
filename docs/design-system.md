# Design system — segurança judicial

A interface é uma estação de trabalho para quem responde pelo sigilo: três
painéis (trilho de operações, tela, inspetor), superfícies claras de tinta
lavanda, cobalto para o que é ação, esmeralda para o que está selado, violeta
para marcador estrutural.

Tudo o que é valor vive em [`src/styles/tokens.css`](../src/styles/tokens.css).
Este documento explica as decisões; o arquivo é a fonte da verdade.

---

## De onde os valores vieram

Da referência `stitch_data_anonymization_platform_redesign`, que traz quatro
telas em PNG e o HTML que as gerou.

**Ela discorda de si mesma em três lugares.** O frontmatter do `DESIGN.md` lista
uma paleta, a prosa do mesmo arquivo descreve outra (`#F8F9FA`, `#1D4ED8`,
tintas de entidade), e o `tailwind.config` embutido no `code.html` usa uma
terceira, em Material 3. Foi o `code.html` que gerou as capturas — **é dele que
os valores saem**, verbatim. A prosa continua valendo para intenção: regras de
elevação, comportamento responsivo, e as âncoras de cor de entidade.

O tema escuro não existe na referência e **não foi inventado**. Medindo o HCT de
cada token do claro, as seis paletas tonais se revelaram recuperáveis:

| família | matiz | croma |
|---|---|---|
| neutra | 270 | 16 |
| neutra-variante | 276 | 13 |
| primária | 275 | 69 |
| secundária | 166 | 50 |
| terciária | 302 | 79 |
| erro | 25 | 84 |

Reconstruir o esquema **claro** a partir delas erra no máximo 1,2 de distância
HCT, o que não se vê. O escuro é a leitura dessas mesmas paletas nos tons que o
Material 3 usa para fundo escuro. Menor contraste medido: 5,87:1
(`outline` sobre `surface`).

---

## As três vozes

| voz | fonte | o que carrega |
|---|---|---|
| **estrutura** | Plus Jakarta Sans (`font-display`) | título de tela, rótulo de botão, item de menu, cabeçalho de cartão |
| **leitura** | Inter (`font-body`) | prosa do app, texto do processo, resposta do modelo |
| **dado literal** | JetBrains Mono (`font-mono`) | número CNJ, nome de arquivo, chip de categoria, contagem, hash, caminho, comando |

Num revisor de tarjas, confundir o texto do aplicativo com o texto do documento
é o erro mais caro que existe. A terceira voz é a que mais protege disso: **o
que está em mono é dado**, e dado não é opinião do programa.

A caixa é baixa em tudo, exceto rótulo de seção com 12px ou menos. A versão
anterior escrevia todo botão e item de menu em caixa alta com entreletra, e foi
a única mudança que, sozinha, mudou a impressão do produto.

### Escala

`display` 30/38 · `headline-lg` 22/28 · `headline-sm` 16/24 · `body-lg` 15/24 ·
`body-md` 14/22 · `body-sm` 13/18 · `mono-code` 13/20 · `mono-tag` 11/14 ·
`label` 12/16.

---

## Cor

Quarenta tokens Material 3. Os que aparecem em quase toda tela:

- `surface` / `background` — o chão.
- `surface-container-lowest` — o cartão. **Mais claro** que o fundo no tema
  claro; mais escuro no tema noite, que é como o M3 trata elevação no escuro.
- `surface-container-low` — campo de busca, linha de ajuste, área rebaixada.
- `primary` — a ação. `primary-hover` acompanha, e existe porque a direção do
  hover se inverte entre os temas (ver abaixo).
- `secondary` — o que está selado, conferido, garantido.
- `tertiary` — marcador estrutural e atenção que não é erro.
- `error` — o que não tem volta.
- `outline` / `on-surface-variant` — metadado e prosa secundária.

### `--color-primary-hover` não é token do M3

O botão preenchido do desenho é `bg-primary hover:bg-primary-container`, e essa
direção só está certa no claro. No escuro, `primary` é T80 (claro) e
`primary-container` é T30 (escuro): o hover **apagaria** em vez de acender. Cada
tema define o seu, e a receita do botão fica igual nos dois.

### As 14 cores de entidade ficam fora do `@theme`

O Tailwind v4 faz tree-shaking dos tokens de tema, emitindo no `:root` só os
`--color-*` que alguma utility gerada referencia. O acesso a elas é sempre
dinâmico — `corDaEntidade()` monta `var(--color-entity-${token})` por
interpolação —, e uma string montada em runtime é invisível para quem escaneia
arquivos. **Treze das catorze eram descartadas**, e o sintoma seria uma cor que
não pinta, sem erro nenhum. Elas são declaradas à mão no `:root`.

A rampa é uma volta completa em OKLCH: passo de 360/14 = 25,7°, ancorada em 27°
para CPF cair no vermelho, e-mail no ciano, endereço no verde e telefone no
violeta. A luminosidade é **intercalada de propósito**: com L constante, dezoito
pares ficavam perceptualmente confundíveis.

Ela atravessou a repaginação sem mudar, e não por descuido — melhorou nas
superfícies novas:

| | antes | agora |
|---|---|---|
| menor contraste sobre a superfície (claro) | 4,70:1 | **5,04:1** |
| sobre o cartão, onde as tarjas vivem | — | 5,31:1 |
| menor contraste (escuro) | 5,05:1 | **5,17:1** |
| menor distância ΔOK entre pares | 0,086 | 0,086 |

Ainda assim **a cor é canal secundário**: 14 categorias é mais do que a visão de
cor separa com folga, e quem tem deficiência de cor não recebe nenhuma delas. O
rótulo textual é o canal primário em toda a interface (WCAG 1.4.1) — nenhuma
tela informa o tipo só pela cor.

---

## Forma

A referência embaralha a escala do Tailwind: redefine `lg` para 4px e deixa `md`
em 6px, de modo que `rounded-lg` sai **menor** que `rounded-md`. Os pixels estão
certos — foram eles que geraram as capturas —, os nomes é que não. A escala foi
reordenada preservando os valores:

| classe na referência | px | classe aqui |
|---|---|---|
| `rounded` / `rounded-sm` | 2 | `rounded-xs` |
| `rounded-lg` | 4 | `rounded-sm` |
| `rounded-md` | 6 | `rounded-md` |
| `rounded-xl` | 8 | `rounded-lg` |
| `rounded-full` | 12 | `rounded-pill` |
| `rounded-2xl` | 16 | `rounded-xl` |

`rounded-full` fica com o padrão do Tailwind (infinito) e continua significando
círculo de verdade — é o que os pontos indicadores usam.

**Não há borda no sistema.** A separação entre camadas é diferença de tom mais
sombra curta, em três níveis: cartão apoiado, painel flutuante, diálogo.

---

## Duas camadas de token, e por quê

As **primitivas** (`--surface`, `--on-surface`, `--primary`…) carregam os valores
e são a única coisa que a troca de tema mexe. Os **semânticos** (`--color-*`)
apenas apontam para elas, e existem porque é deles que o Tailwind gera as
utilities.

O bloco é `@theme inline`, não `@theme`, e a diferença decide se o alternador de
tema funciona: com `@theme`, a utility referenciaria `var(--color-surface)` e o
valor poderia ser resolvido em tempo de build, congelando o tema em que o CSS foi
compilado. Com `inline`, a utility emite a referência à primitiva, então
redefinir `--surface` em `[data-tema="noite"]` repinta a interface na hora.

Consequência prática, que é regra: **toda cor tem seu valor no `:root`.** Um
token que só nasce dentro do modo escuro fica indefinido para quem está no claro,
e o navegador não avisa — a cor simplesmente não pinta.

---

## A moldura da janela é do aplicativo

`titleBarStyle: "hidden"` tira a barra do sistema e deixa só os três controles
sobrepostos ao canto superior direito. O cabeçalho de 64px é o que resta, e é ele
que arrasta a janela.

Três coisas que não se deduzem olhando:

1. **Todo controle no cabeçalho precisa de `.sem-arrasto`**, ou o clique vira
   arrasto e o botão nunca dispara.
2. **Os últimos ~140px pertencem ao sistema.** A referência põe exatamente ali um
   cartão de usuário com avatar; aqui ele não existe, e o espaço fica reservado.
3. **O bloco de marca no topo do trilho também arrasta.** Sem isso a janela fica
   imóvel por toda a coluna esquerda.

A cor da moldura é pintada pelo Electron, fora do CSS. `aplicarTema` lê
`--fundo-moldura` e `--simbolo-moldura` do `:root` já pintado e as manda por IPC.
**As duas têm de ser hexadecimal de seis dígitos**: `getPropertyValue` devolve o
valor *autorado*, então `oklch()`, `rgb()` ou `color-mix()` fariam a validação do
`main.ts` recusar em silêncio, e a moldura congelaria na cor do tema anterior —
sem nada no console.

---

## Camadas

Escrita uma vez, para não haver dúvida:

```
z-30   sub-barra grudada da Revisão
z-40   cabeçalho do aplicativo
z-50   trilho lateral
z-100  popover e gaveta
z-200  aviso (toast)
       <dialog> vive na top-layer, acima de tudo
```

Os tokens `--z-*` **não** existem e não podem existir: o Tailwind v4 só gera
utilities a partir dos namespaces que conhece, e `--z-*` não é um deles. Já
houve `z-sticky`, `z-overlay` e `z-toast` no código, e as três nunca produziram
uma linha de CSS.

---

## Responsivo

Regra da própria referência, e a janela pode chegar a 800px:

| largura | trilho | inspetor |
|---|---|---|
| ≥ 1280px | 240px, com rótulos | coluna fixa |
| 1024–1279px | 240px, com rótulos | gaveta |
| < 1024px | rail de 64px, só ícones | gaveta |

A janela abre em 1440×900 porque o desenho de três painéis só cabe inteiro a
partir de 1280 — com 1100 o aplicativo abria sempre no modo colapsado, que é o
plano B.

---

## Movimento

120 ms é o tempo canônico de toda transição de hover e foco. A única exceção
orquestrada é a varredura das tarjas ao abrir a Revisão: 240 ms no total,
escalonadas pela ordem da ocorrência — o documento sendo carimbado.

Quem pediu menos movimento no sistema operacional não recebe nenhum, pelo bloco
`prefers-reduced-motion` do `tokens.css`.

---

## Ícones

**Material Symbols Outlined**, a fonte variável, servida do pacote
`material-symbols` instalado localmente — o CSP da janela tem `font-src 'self'` e
nenhuma fonte entra pela rede. O glifo é escolhido por ligadura: o texto do
`<span>` é o nome do ícone.

O ícone é **sempre decoração**: `aria-hidden` é fixo em `Icone` e não há como
desligá-lo. O nome acessível pertence ao elemento que envolve — o botão, o link,
a linha da tabela.

O eixo **FILL** separa o item ativo do inativo no trilho e a conversa aberta das
outras. É canal redundante à cor, nunca o único. O eixo **opsz** acompanha o
corpo do ícone, preso à faixa 20–48 que a fonte cobre — fora dela o valor é
ignorado, e ignorado não é neutro: o traço volta ao padrão, que é o errado para o
corpo pedido.

`NomeIcone` é uma união curada. Ela custa uma linha por ícone novo e paga isso na
hora em que alguém digita `visibilty`: com `string`, a ligadura não casa, a fonte
desenha o nome cru na tela e nada acusa o erro.
