# macOS (Apple Silicon)

A CLI e o servidor MCP rodam nativamente. A interface gráfica roda em modo dev;
`.dmg` ainda não é gerado — a seção [O que ainda não existe no
Mac](#o-que-ainda-não-existe-no-mac) lista o que falta, porque quem procura e
não acha menção nenhuma supõe defeito, não ausência.

## Pré-requisitos

| | |
|---|---|
| macOS | 14+ **arm64** — o wheel do `onnxruntime` é `macosx_14_0_arm64` |
| Python | 3.12 (o `setup-macos.sh` pina essa versão) |
| Node | 20+, só para a interface em modo dev |
| `uv` | cria o venv e resolve as dependências |
| Espaço | ~5 GB num volume à escolha, para o venv e os modelos |

As dependências resolvem em arm64 **nos pins exatos** do `requirements.txt` —
`torch`, `onnxruntime 1.28.0` (wheel `cp312-macosx_14_0_arm64`), `presidio`.
Nenhuma cirurgia de versão foi necessária: o backend Python não tinha
acoplamento a Windows.

## Instalação

```bash
scripts/setup-macos.sh
```

Ele cria o venv no volume de peso, baixa o modelo do spaCy, e deixa
`.venv` no repositório como **symlink** para lá.

O symlink não é detalhe de arrumação: tudo neste projeto já procura
`.venv/bin/python` — `fetch-ocr-models.sh`, o `electron/main.ts` em modo dev.
Apontar um link faz esses caminhos continuarem certos sem um único `if` novo.

### Por que o peso sai do disco interno

O venv com torch, o BERT e os pesos de OCR passam de 2 GB, e nem toda máquina
tem isso sobrando no disco interno. O destino é `DJURIS_PESO`:

```bash
DJURIS_PESO=/Volumes/<seu volume>/djuris scripts/setup-macos.sh
```

O default está escrito no `scripts/setup-macos.sh` e aponta para o volume
externo desta máquina — quem clonar o repositório passa a variável, ou edita a
linha.

Com o volume desmontado, os comandos avisam com essas palavras em vez de soltar
um `ModuleNotFoundError` de torch — que mandaria a pessoa depurar dependência
quando o problema é um cabo.

## Abrir sem terminal

```bash
scripts/instalar-atalho-macos.sh
```

Põe um **Direito&Juris.app** em `~/Applications`, com ícone, que abre a
interface com um duplo-clique. Arraste para o Dock se quiser.

O `.app` é uma casca de uma linha; a lógica mora em `scripts/abrir-djuris.sh`, e
é lá que se mexe. Três coisas que ele resolve e um `npm run dev:electron` solto
não:

- **o PATH.** Aplicativo lançado pelo Finder recebe
  `/usr/gnu/bin:/usr/local/bin:/bin:/usr/bin:.` e nada mais — o `node` do nvm
  fica de fora, e o duplo-clique morreria com "command not found" sem nada na
  tela. O script resolve o caminho por glob, não por versão cravada.
- **o erro visível.** Sem terminal, `echo` não chega a ninguém: volume
  desmontado, Node ausente ou interface que não sobe saem em diálogo do sistema,
  com o caminho do log.
- **o fechamento.** O `dev:electron` roda Vite e Electron sob `concurrently` sem
  `--kill-others`, e o Vite ficaria para trás a cada abertura. Aqui ele morre
  junto, por `trap`.

Abrir com o aplicativo já aberto avisa e não sobe uma segunda cópia.

## A CLI

O shim é `python-backend/djuris.sh`, instalado por symlink:

```bash
ln -sf "$PWD/python-backend/djuris.sh" ~/.local/bin/djuris
```

```bash
djuris autos.pdf                    # PDF, DOCX, XLSX, imagem — com OCR
djuris peticao.txt -o saida.md
cat peticao.txt | djuris
djuris ler autos.pdf                # extrai o texto SEM anonimizar
djuris ocr pagina.png
```

### O servidor MCP

```bash
claude mcp add djuris -- ~/.local/bin/djuris mcp
```

Registrado em escopo de usuário, vale em todos os projetos. São **quatro**
ferramentas: `anonimizar_texto`, `ler_documento`, `ocr_imagem` e `status`.
Repare no default do `ler_documento`: `anonimizar: true`. Precisa pedir
explicitamente `false` para ver o texto cru — é o default certo para a
ferramenta que um agente na nuvem chama.

`reidratar` **não está aí, e não vai estar** — veja
[A regra de ouro](#a-regra-de-ouro-reidratar-não-é-ferramenta-de-mcp).

## O ciclo de reidratação

```bash
djuris anonimizar peca.txt --offline --autos 5626981 -o mascarada.txt
# manda mascarada.txt pro Claude e pergunta o que quiser;
# a resposta volta falando em [PESSOA_1], [CPF_1]…
djuris reidratar resposta.txt --autos 5626981
```

O `--autos` dá às peças de um mesmo processo um espaço de pseudônimos comum:
`[PESSOA_1]` é a mesma pessoa na inicial e na procuração, **inclusive entre
invocações em dias diferentes**. Sem isso, um modelo que leia as duas juntas
responde trocando as pessoas.

Três coisas que o `--autos` recusa, e por quê:

- **`-m parcial` e `-m total`.** Elas não deixam o que reidratar — o valor não
  está mais no texto. Aceitar gravaria um mapa vazio prometendo um ciclo que
  nunca fecharia, com o sintoma aparecendo só depois do envio.
- **modo remoto.** Por ora, `--autos` só funciona com `--offline`.
- **nome de autos que escaparia do diretório** (`../algo`, `a/b`). Ele vira nome
  de arquivo.

O nome dos autos é **dobrado para minúsculas**: `--autos Caso-Ana` e
`--autos caso-ana` são os mesmos autos. Isso existe porque APFS e NTFS são
insensíveis a maiúsculas e ext4 não é — sem dobrar, a mesma sequência de
comandos produziria um mapa no Mac e dois no Linux.

## Certidão de anonimização

```bash
djuris anonimizar peca.pdf --offline --certidao
djuris tarjar autos.pdf --offline --certidao
```

Grava, ao lado do arquivo gerado, um `.certidao.md` com o que foi feito: os dois
SHA-256 (origem e saída), a contagem por TIPO, a política, o motor e o modelo, a
base normativa e o escopo da busca.

**Ela não contém nenhum valor mascarado** — só contagem. Listá-los faria dela o
índice de dados pessoais que a anonimização existe para evitar, viajando anexado
ao arquivo que os escondeu.

Três campos que não são enfeite: o **motor**, porque anonimizar em spaCy
acreditando ter BERT é o risco que este projeto documenta; o **escopo**, porque
com `-e` a ausência de um tipo não é "não havia", é "não foi procurado"; e o
**limite**, escrito na própria certidão — ela registra o procedimento, não
garante que nada escapou.

## Tarja de redação em PDF

```bash
djuris tarjar autos.pdf --offline -o autos_tarjado.pdf
```

Devolve o PDF com o dado **coberto** — não o texto substituído. É o que serve
para juntar aos autos ou mandar a um cliente.

**A página é rasterizada antes do desenho**, e isso não é detalhe: retângulo
preto sobre texto preservado se desfaz com um seleciona-e-copia, e documento
público já vazou exatamente assim. O preço é o PDF sair não-pesquisável — é o
preço certo, porque a alternativa que preserva a busca preserva junto o dado.

`--dpi` controla a resolução (padrão 150). Os metadados não atravessam: a saída
é documento novo, e o título vai vazio de propósito, senão o nome do arquivo —
que carrega CNJ e nome de parte — viraria `/Title` do PDF.

⚠️ **A tarja aplica a detecção, não a repete.** Dado que o detector não viu
continua visível, e por isso o comando pede conferência toda vez. Foi olhando um
PDF tarjado que apareceram três vazamentos que nenhuma lista de ocorrências
mostrava — endereço em prosa, RG com "de" no meio, e o nome dentro da assinatura
digital ICP-Brasil.

### A regra de ouro: `reidratar` não é ferramenta de MCP

E nunca vai ser. Chamada por um modelo, ela devolve os nomes reais ao contexto
dele — que é a nuvem — e desfaz exatamente o que o programa existe para fazer.
É comando de linha, roda local, escreve arquivo.

É a regra mais frágil do desenho: expor a ferramenta parece conveniência óbvia
para quem chega depois, funcionaria perfeitamente, e nada reclamaria. Por isso
ela é travada por teste (`tests/test_mapa_nao_vaza.py`), que confere as quatro
ferramentas e que o `mcp_server.py` nem **importa** o `mapa_reverso` — import é
o começo do caminho.

## A chave e os mapas

| Variável | Padrão | O que é |
|---|---|---|
| `PRESIDIO_MAPA_CHAVE` | `~/.config/djuris/mapa.key` | a chave Fernet, `0600`, em diretório `0700` |
| `PRESIDIO_MAPA_DIR` | `<DJURIS_PESO>/mapas` | os mapas cifrados, um `.mapa` por autos |
| `PRESIDIO_MAPA_PRAZO_DIAS` | `7` | prazo de guarda; vencido, o mapa é apagado |

**Os dois ficam em volumes diferentes de propósito.** Medido: o SSD externo é
APFS e honra `chmod 0600`, **mas monta com `noowners`**
(`diskutil info` diz `Owners: Disabled`). Com o dono ignorado, qualquer usuário
da máquina responde como proprietário e o `0600` ali não protege ninguém. A
chave fica no disco interno; o programa **recusa** cunhá-la num volume
`noowners`, em vez de prometer uma proteção que não existe. De brinde: o volume
que pode ser levado embora não carrega a chave dele.

**Keychain foi descartado.** A CLI e o servidor MCP rodam em tmux, fora da
sessão gráfica, e é ali que o Keychain falha nesta máquina.

Uma gravação interrompida pode deixar um `<autos>.mapa.parcial`, e **o expurgo o
alcança** — tanto o prazo de guarda quanto o `esquecer()`. Isso teve de ser
consertado: na primeira versão os dois olhavam só o `.mapa`, e o `.parcial` era
a única coisa do módulo que sobrevivia ao prazo. Prazo que deixa resíduo não é
prazo.

## Os dois alarmes, e o que fazer com cada um

Não são erros de uso. São as duas recusas que o mapa reverso emite, e a reação
certa é diferente. Nos dois casos **nada é gravado**, e a mensagem diz isso.

| | O que houve | O que fazer |
|---|---|---|
| `MapaIlegivel` | o mapa **existe** e não decifra: a chave não é mais a que o cifrou | Se você recriou a chave de propósito, os mapas gravados antes dela são perda esperada — apague-os. Se **não** recriou, alguém mexeu na chave. O arquivo não é apagado automaticamente, de propósito |
| `EtiquetaConflitante` | `[PESSOA_1]` vale uma coisa no disco e chegou valendo outra | A numeração recomeçou. Normalmente significa que a semeadura não rodou — confira se o `--autos` está escrito igual ao da vez anterior |

### "O mapa venceu" e "o mapa não decifra" não são a mesma coisa

As duas deixam você sem reidratação, e é por isso que elas não podem ter a mesma
cara. **Vencido** é o prazo de guarda funcionando: o arquivo foi apagado e a
saída simplesmente não tem mapa. **Ilegível** é alarme, com a palavra `ALARME`
na saída.

Se você vê rótulo em claro **sem** nenhuma mensagem, foi vencimento; com
mensagem, foi a chave.

## Um limite que nenhuma cifragem alcança

Medido ao implementar a chave, e vale saber porque define o que a ferramenta
promete: **quem consegue trocar a chave pode recifrar um mapa forjado com ela.**
Aí o `decrypt` tem sucesso, nenhum alarme dispara, e a reidratação escreve os
valores que essa pessoa escolheu — sem erro e sem sintoma. Cifragem autenticada
não ajuda: ela prova "isto foi escrito por quem tem esta chave", e nesse cenário
o atacante tem a chave.

Consequência, dita com todas as letras: **o `0600` do arquivo e a recusa em
volume `noowners` não são defesa periférica — são a única coisa que faz "esta
chave" significar "eu".**

E o de sempre: nada disso protege contra programa malicioso rodando **como
você**. Para o sistema, ele é você, e recebe o dado decifrado se pedir.

## O que ainda não existe no Mac

- **`.dmg` / `.app`** — o `build:dist` só gera instalador Windows.
- **interface gráfica empacotada** — roda em modo dev (`npm run dev:electron`).
- **`--autos` no modo remoto** — só com `--offline`.
- **`status` e `conectar`** — dependem do aplicativo aberto, que aqui só existe
  em modo dev. Por isso os dois ficam de fora dos exemplos do shim POSIX.

## Testes

```bash
export DJURIS_PESO=/Volumes/<seu volume>/djuris   # o mesmo do setup

cd python-backend && \
  HF_HOME="$DJURIS_PESO/hf-cache" \
  ../.venv/bin/python -m pytest tests -q

npm run test:electron    # suíte Node
npm test                 # suíte do renderer (vitest)
```

O `HF_HOME` importa: sem ele o `transformers` procura o BERT em `~/.cache` e
baixa os ~415 MB de novo, no disco que justamente não tem espaço.

### Uma lacuna de cobertura, declarada

Dois testes dependem de `PRESIDIO_CORPUS_OCR` apontando para uma pasta com PDF
**sem camada de texto**. Sem ela eles são pulados — e teste pulado passa por
teste aprovado em log corrido, que é o motivo de isto estar escrito aqui.

O corpus original (22 PDFs reais) nunca saiu da máquina de origem, e no acervo
desta máquina não há substituto: 40 PDFs testados, todos já OCRizados. Para
fechar a lacuna:

```bash
cd python-backend
python -m eval.fabricar_corpus_ocr <um-pdf-nativo> "$TECJUSTICA_PESO/corpus-ocr"
export PRESIDIO_CORPUS_OCR="$TECJUSTICA_PESO/corpus-ocr"
```

Ele rasteriza um PDF nativo — a imagem resultante não tem camada de texto — e
gera dois arquivos, um limpo e um degradado (papel torto, foco mole, sujeira,
contraste baixo). A suíte passa de **317 com 2 pulados** para **319 com zero**.

**O limite, porque ele importa:** palavras recuperadas contra o original são
**94,7%** no limpo e **77,0%** no degradado. Isso é um PISO. Rasterização não
reproduz fotocópia de fotocópia nem datilografado, que é onde o OCR sofre de
verdade. E o que o OCR não lê não vaza — sai um documento mutilado parecendo
completo.

O **gate de acurácia sobre acervo próprio** também não existe: medir exige
corpus com gabarito. Fica como item aberto, não como passo fingido.

## Duas ressalvas medidas durante o porte

**`uv venv --allow-existing` sobre um venv de outra versão de Python não falha**
— deixa `lib/python3.11/` órfão ao lado do novo. Não acontece hoje: o
`setup-macos.sh` pina 3.12 e é o único criador do caminho. Passa a importar no
dia em que a versão pinada subir; aí, apague o venv antes.

**O teto de 40 saltos do `djuris.sh` é inalcançável pelo caminho
normal de invocação neste sistema.** O macOS tem `SYMLOOP_MAX=32`, e o kernel
recusa abrir o arquivo antes de qualquer linha do script rodar, com mensagem
própria (`Too many levels of symbolic links`, código 126). O teto segue como
defesa das vias que não passam pelo `open()` do kernel — mas quem for depurar
uma cadeia de symlinks vai ver a mensagem do sistema, não a do shim, e procurar
a do shim no log seria procurar a errada.
