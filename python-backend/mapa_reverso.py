"""
Mapa reverso — o de-para entre `[PESSOA_1]` e o valor real.

## Para que serve

A resposta que volta de um modelo na nuvem fala em `[PESSOA_1]`. Quem lê precisa
do nome. Este módulo guarda o de-para e o aplica de volta.

## A regra que governa o desenho

**Reidratar não é ferramenta de agente.** Chamada por um modelo, ela devolve os
nomes reais ao contexto dele — que é a nuvem — e desfaz exatamente o que este
programa existe para fazer. Por isso `mcp_server.py` não a expõe e continua
declarando quatro ferramentas. Ela é comando de linha, roda nesta máquina, e
escreve arquivo. Se algum dia virar ferramenta, devolve o CAMINHO do arquivo,
nunca o conteúdo.

## Três desfechos de leitura, e por que não podem se confundir

Pedir um mapa termina de três maneiras. As três se parecem com "não veio mapa"
para quem só olha o resultado, e pedem reações opostas de quem cuida da máquina
— então ficam declaradas aqui, uma vez, no lugar em que as duas exceções deste
módulo podem ser lidas lado a lado:

- **`{}`** — o mapa não existe, ou venceu e foi apagado. Ausência benigna: é o
  expurgo funcionando, e não há nada a fazer.
- **`CifragemIndisponivel`** — a CHAVE não está em condições de uso: mora em
  volume montado com `noowners`, ou não está em `0600`. Vale igual para gravar e
  para ler, porque as duas passam por `_chave()`.
- **`MapaIlegivel`** — a chave está em condições de uso, e não é a que cifrou
  ESTE mapa: alguém a recriou ou a substituiu. É alarme, não ausência.

A fronteira entre as duas últimas é a que importa na prática: a primeira diz
"não consigo proteger", a segunda diz "a chave mudou". Uma se resolve apontando
`PRESIDIO_MAPA_CHAVE` para onde o dono valha; a outra, recuperando a chave
antiga — e nenhuma das duas se resolve tentando de novo.

## O que este módulo NÃO faz

Não detecta e não mascara. Recebe o mapa pronto de quem mascarou. É por isso que
ele não importa `engine` e roda sem carregar modelo — os testes dele levam
milissegundos.
"""

from __future__ import annotations

import functools
import os
import re
import stat
import subprocess
from pathlib import Path

# A forma da etiqueta vem de quem a CRIA. Repeti-la aqui daria duas descrições
# da mesma coisa, e a desatualizada continuaria parecendo atual — o sintoma
# seria texto "reidratado" com um pedaço ainda mascarado, sem erro nenhum. O
# nome local fica como apelido, para não mexer em quem já o usa.
#
# `mask_config` é regex e dicionário: importá-lo NÃO traz Presidio, spaCy nem
# torch, e a promessa de que os testes deste módulo rodam em milissegundos
# continua de pé (medido com `python -X importtime -c "import mapa_reverso"`).
#
# A varredura de `reidratar` é de UMA passagem, com consulta ao dicionário.
# Substituir rótulo por rótulo em laço é o defeito clássico: `[PESSOA_1]` é
# prefixo de `[PESSOA_10]`, e trocar o primeiro antes produz `Ana Souza0` — que
# não parece defeito de programa, parece erro de digitação do documento.
from mask_config import RE_ETIQUETA as RE_ROTULO


def reidratar(texto: str, mapa: dict[str, str]) -> str:
    """
    Devolve `texto` com cada rótulo trocado pelo valor do `mapa`.

    Rótulo sem entrada fica como está. É o caso de autos trocados ou de mapa
    vencido e apagado, e deixá-lo visível é a única saída honesta: apagar
    fingiria que o trecho não existia, e adivinhar seria pior que as duas.
    """
    return RE_ROTULO.sub(lambda m: mapa.get(m.group(0), m.group(0)), texto)


CHAVE_PADRAO = Path.home() / ".config" / "tecjustica-sigilo" / "mapa.key"


class CifragemIndisponivel(RuntimeError):
    """
    Não há como cifrar com a garantia prometida — e então nada é gravado.

    É a mesma escolha do `cofre.ts` (que recusa gravar onde o sistema não
    oferece cifragem) e do `fetch-ocr-models.sh` (que recusa um download sem
    pin). Quando a garantia não pode ser dada, a operação não acontece: um mapa
    reverso em claro é um índice de CPF e nome, exatamente o artefato que este
    programa existe para não criar.

    **Levantada por `gravar` e por `ler`**, porque as duas passam por `_chave()`.
    O "nada é gravado" acima descreve a escrita, não o escopo desta exceção: na
    leitura o desfecho é o mesmo em espírito — sem chave em condições, o módulo
    não afirma nada sobre o mapa, em vez de devolver `{}` como se ele não
    existisse.
    """


def _caminho_chave() -> Path:
    return Path(os.environ.get("PRESIDIO_MAPA_CHAVE") or CHAVE_PADRAO)


def _analisar_montagens(montagens: dict[str, str], caminho: str) -> bool:
    """
    Dado `{ponto_de_montagem: flags}`, diz se `caminho` cai num volume que honra
    dono. Separado de `_volume_honra_dono` para ser testável sem tocar o
    sistema — a alternativa seria um teste que só passa nesta máquina.

    O ponto de montagem que vale é o MAIS LONGO que prefixa o caminho: `/` casa
    com tudo, e escolhê-lo diria que todo volume honra dono.
    """
    escolhido, flags = "", ""
    for ponto, valor in montagens.items():
        if (caminho == ponto or caminho.startswith(ponto.rstrip("/") + "/")) and len(ponto) > len(escolhido):
            escolhido, flags = ponto, valor
    if not escolhido:
        # Nenhum ponto prefixa o caminho: não se sabe em que volume ele está, e
        # isso NÃO é o mesmo que saber que o volume é seguro. Esta função responde
        # pergunta de segurança, então a ignorância recusa — a mesma direção do
        # `_tabela_de_montagens` quando o `mount` falha.
        #
        # Numa tabela real `/` prefixa tudo e este ramo não acontece; ele existe
        # para quem chamar a função com tabela parcial, e para não deixar aqui uma
        # falha ABERTA no meio de um módulo cuja política é fechar.
        return False
    return "noowners" not in flags


@functools.lru_cache(maxsize=1)
def _tabela_de_montagens() -> dict[str, str]:
    """
    `{ponto_de_montagem: flags}`, lido uma vez por processo.

    O cache existe porque `gravar()` chama `_chave()` e também `ler()`, que
    chama `_chave()` de novo — sem ele, cada gravação de mapa gastaria dois
    processos `/sbin/mount`, e a CLI grava uma vez por lote de peças.

    Cachear é seguro para o que se pergunta aqui: a chave mora no disco interno,
    cuja montagem não muda no meio de uma execução. O volume EXTERNO pode ser
    desmontado a qualquer momento, mas quem responde por ele é a falha de
    leitura do arquivo cifrado, não esta tabela.
    """
    try:
        saida = subprocess.run(
            ["/sbin/mount"], capture_output=True, text=True, timeout=5, check=True
        ).stdout
    except (OSError, subprocess.SubprocessError):
        # Não sabendo, devolve tabela vazia — e `_analisar_montagens` não acha
        # montagem, o que `_volume_honra_dono` trata como recusa. É a direção
        # certa do erro: o custo de um falso alarme é uma mensagem; o de um
        # falso "seguro" é um mapa desprotegido.
        return {}

    montagens: dict[str, str] = {}
    for linha in saida.splitlines():
        # `/dev/disk3s5 on / (apfs, local, journaled)`
        if " on " not in linha or "(" not in linha:
            continue
        resto = linha.split(" on ", 1)[1]
        ponto, _, flags = resto.rpartition(" (")
        montagens[ponto.strip()] = flags.rstrip(")")
    return montagens


def _volume_honra_dono(caminho: Path) -> bool:
    """
    `noowners` faz o sistema ignorar o dono: todo arquivo do volume responde
    como se fosse do usuário atual, e o `0600` deixa de proteger contra outro
    usuário da máquina.

    A informação vem do `mount`, não de um palpite pelo prefixo do caminho. O
    SSD desta máquina monta com noowners, mas tratar `/Volumes/` como inseguro
    por definição reprovaria o volume corretamente montado de outra pessoa —
    seria uma regra que acerta aqui por coincidência.
    """
    montagens = _tabela_de_montagens()
    if not montagens:
        return False
    return _analisar_montagens(montagens, str(caminho.resolve()))


def _chave() -> bytes:
    """
    Devolve a chave Fernet, criando-a na primeira vez.

    Nunca recunha uma chave existente: isso tornaria ilegível todo mapa já
    gravado, e o sintoma seria "reidratar parou de funcionar", que não aponta
    para aqui.
    """
    from cryptography.fernet import Fernet

    caminho = _caminho_chave()

    # `resolve()` não exige que o arquivo exista, então a checagem vale antes da
    # primeira criação também — e é aí que ela mais importa.
    if not _volume_honra_dono(caminho):
        raise CifragemIndisponivel(
            f"{caminho} está num volume montado com noowners — o dono é "
            f"ignorado e o modo 0600 não protege contra outro usuário. "
            f"Aponte PRESIDIO_MAPA_CHAVE para o disco interno."
        )

    if caminho.exists():
        if stat.S_IMODE(caminho.stat().st_mode) != 0o600:
            raise CifragemIndisponivel(
                f"{caminho} está em "
                f"{stat.S_IMODE(caminho.stat().st_mode):04o}, não em 0600. A "
                f"causa viva é alguém ter mudado o modo: desde o os.fchmod na "
                f"criação, chave cunhada por este código não nasce fora de "
                f"0600, qualquer que seja o umask. As outras duas são "
                f"herdadas — chave cunhada por uma VERSÃO ANTERIOR desta "
                f"ferramenta, quando o umask do processo ainda tirava bits na "
                f"criação (0o200 deixava a chave em 0400), plausível agora na "
                f"transição; ou o arquivo ter vindo de outra máquina. Não "
                f"corrijo em silêncio: se o modo foi AFROUXADO, "
                f"não há como saber quem já a leu, e seguir usando afirmaria "
                f"uma garantia que este arquivo não sustenta mais. Confira o "
                f"modo e quem teve acesso; se decidir apagá-la, saiba que todo "
                f"mapa gravado com ela fica ilegível."
            )
        return caminho.read_bytes()

    # `0700` porque o nome, a existência e o mtime da chave também dizem algo:
    # quem lista o diretório sabe que o produto está em uso e quando o mapa foi
    # cunhado — metadado de um índice de CPF e nome.
    #
    # Três coisas que o `mode` NÃO promete, e é melhor dizê-las que deixar a
    # impressão de garantia mais forte:
    #
    # 1. Ele vale só para o diretório FINAL. Os intermediários que o `parents=True`
    #    cria — `~/.config`, se ainda não existir — saem pelo `umask`, medido em
    #    0755. Está certo assim: o que precisa fechar é a pasta que guarda a
    #    chave, e `~/.config` é diretório de propósito geral do usuário.
    # 2. Um `~/.config` preexistente fica com o modo que tem — não é nosso
    #    diretório para reapertar.
    # 3. Com `exist_ok=True`, um `tecjustica-sigilo/` preexistente e frouxo também
    #    fica como está. Reapertá-lo em silêncio seria o mesmo erro que esta função
    #    recusa cometer com a chave: consertar bit sem saber quem já leu.
    caminho.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    nova = Fernet.generate_key()

    # Cria já fechado, e é por isso que não há `write_bytes` seguido de `chmod`:
    # aquela sequência deixa uma janela em que o arquivo existe legível.
    #
    # O `O_EXCL` recusa criar sobre coisa existente. Vale pela corrida (dois
    # processos cunhando ao mesmo tempo: o perdedor não sobrescreve a chave do
    # vencedor) e, mais realisticamente, pelo symlink pendurado — `Path.exists()`
    # segue o link e diz `False` para link quebrado, então o ramo de criação é
    # alcançável com um link no caminho, e o `O_EXCL` se recusa a seguí-lo.
    try:
        descritor = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as erro:
        raise CifragemIndisponivel(
            f"algo já ocupa {caminho}, e a checagem anterior o tinha dado por "
            f"ausente — então apareceu no meio da cunhagem, ou é um symlink "
            f"pendurado (que se diz ausente e existe). Confira o que está "
            f"nesse caminho antes de tentar de novo: a chave NÃO foi criada, e "
            f"o que está lá não foi tocado."
        ) from erro

    with os.fdopen(descritor, "wb") as arquivo:
        # O modo do `os.open` é MASCARADO pelo umask, e o comentário anterior
        # afirmava o contrário. Medido nesta máquina, com o diretório já
        # existente (o estado normal depois da primeira execução): sob
        # `umask 0o200` o arquivo nasce `0400`. O desfecho era o pior do módulo
        # e não precisava de atacante nenhum — o primeiro `gravar()` cifrava um
        # mapa com aquela chave, e toda chamada seguinte recusava por modo
        # diferente de 0600, aconselhando apagar a chave e com ela o mapa que
        # tinha acabado de ser gravado.
        #
        # O `fchmod` corre sobre o DESCRITOR já aberto, então não há janela nem
        # corrida de caminho: o arquivo nasce em `0600 & ~umask`, que nunca é
        # mais LARGO que 0600, e isto só estreita-para-exato.
        os.fchmod(arquivo.fileno(), 0o600)
        arquivo.write(nova)
    return nova


import json
import time

# O volume onde o peso deste projeto mora — o mesmo que o `setup-macos.sh` e o
# `tecjustica-sigilo.sh` já leem de `TECJUSTICA_PESO`, com o mesmo default.
# Repetido aqui porque este módulo não pode importar shell; se o default mudar
# lá, muda aqui junto.
PESO_PADRAO = "/Volumes/SSD do Leandro/tecjustica-sigilo"
PRAZO_DIAS_PADRAO = 7

# O nome dos autos vem da linha de comando e vira nome de arquivo. Sem esta
# régua, `--autos ../../algo` grava fora do diretório de mapas.
RE_AUTOS = re.compile(r"^[A-Za-z0-9._-]{1,120}$")


def _dir_mapas() -> Path:
    """
    Onde os mapas moram, na ordem do mais explícito para o menos.

    `PRESIDIO_MAPA_DIR` manda; na falta dela, os mapas seguem o volume de peso,
    porque é o `setup-macos.sh` quem cria `$TECJUSTICA_PESO/mapas` e seria
    estranho criar o diretório num volume e gravar noutro. Antes disto o
    caminho era literal e ignorava `TECJUSTICA_PESO`: quem apontasse a variável
    para outro volume teria o diretório criado num lugar e a gravação tentando
    outro — e descobriria DEPOIS de anonimizar, que é quando o mapa é a única
    coisa que falta para o ciclo fechar.

    Lido a cada chamada, e não na carga do módulo, para que mudar a variável no
    processo tenha efeito — é do que as fixturas da suíte dependem.
    """
    explicito = os.environ.get("PRESIDIO_MAPA_DIR")
    if explicito:
        return Path(explicito)
    return Path(os.environ.get("TECJUSTICA_PESO") or PESO_PADRAO) / "mapas"


def _prazo_dias() -> int:
    bruto = os.environ.get("PRESIDIO_MAPA_PRAZO_DIAS")
    if not bruto:
        return PRAZO_DIAS_PADRAO
    try:
        return max(1, int(bruto))
    except ValueError:
        return PRAZO_DIAS_PADRAO


def _caminho(autos: str) -> Path:
    if not RE_AUTOS.match(autos) or autos in {".", ".."}:
        raise ValueError(
            f"nome de autos inválido: {autos!r} — use letras, números, ponto, "
            f"hífen e sublinhado (é nome de arquivo)"
        )
    # A caixa é dobrada DE PROPÓSITO, e depois da régua acima (que é ASCII puro,
    # então `casefold` aqui não tem o problema de normalização Unicode que o
    # tornaria insuficiente).
    #
    # O motivo é portabilidade, não estética: `--autos abc` e `--autos ABC`
    # apontam para o MESMO arquivo no APFS desta máquina, insensível à caixa, e
    # para arquivos DIFERENTES no ext4. Sem dobrar, a mesma sequência de comandos
    # produz um mapa no macOS e dois no Linux — comportamento contratado por
    # teste dependendo de como o sistema foi formatado, que é a mesma armadilha
    # do `noowners`. Este fork pretende voltar ao upstream.
    #
    # O caso perigoso (dois autos distintos com etiquetas em conflito) já é
    # recusado por `EtiquetaConflitante`, que pega por conflito de de-para e não
    # sabe de caixa. O que se conserta aqui é a divergência entre sistemas.
    return _dir_mapas() / f"{autos.casefold()}.mapa"


def _parcial(caminho: Path) -> Path:
    """
    O temporário da troca atômica, derivado do caminho definitivo.

    Existe como função para que `gravar`, o vencimento e `esquecer` falem do
    MESMO arquivo. Enquanto o nome vivia só dentro do `gravar`, ele era o único
    resíduo deste módulo que sobrevivia ao expurgo.
    """
    return caminho.with_suffix(".mapa.parcial")


def _vencido(caminho: Path) -> bool:
    return time.time() - caminho.stat().st_mtime > _prazo_dias() * 86400


class EtiquetaConflitante(RuntimeError):
    """
    A mesma etiqueta designa valores diferentes no mapa gravado e no que chega.

    É o sintoma de numeração que recomeçou: `Mascarador` novo numera do 1, então
    uma segunda invocação da CLI sobre os mesmos autos produz `[PESSOA_1]` para
    outra pessoa. Fundir sobrescreveria, e a reidratação da primeira peça
    escreveria o nome de quem apareceu na segunda — num texto bem formado.

    A cura é semear o `Mascarador` com o mapa gravado (ver `Mascarador.semear`),
    e esta exceção é a rede embaixo dela: se a semeadura falhar ou for esquecida,
    a gravação para em vez de corromper.
    """


def gravar(autos: str, mapa: dict[str, str]) -> Path:
    """
    Funde `mapa` no que já estava gravado para estes autos e grava cifrado.

    Funde, e não substitui, porque cada peça chega numa execução: substituir
    perderia o mapa da peça anterior e a reidratação sairia PARCIAL — pior que
    falhar, porque um documento meio reidratado tem toda a aparência de
    completo.

    **Recusa etiqueta conflitante**, e isso é o oposto de fundir cegamente. Se
    `[PESSOA_1]` já vale "Ana Souza" no disco e chega valendo "Bruno Lima", não
    há fusão possível que preserve as duas — e escolher uma em silêncio produz
    reidratação errada na outra. Levanta `EtiquetaConflitante`.

    **Propaga `MapaIlegivel`** — vindo do `ler()` desta mesma função —, e isso é
    de propósito: um mapa que existe e não decifra não pode ser sobrescrito por
    um novo. Gravar em cima apagaria o de-para de tudo que já foi anonimizado
    nestes autos, e o que motiva a ilegibilidade pode ser benigno e reversível
    (a chave errada em `PRESIDIO_MAPA_CHAVE`, o volume de outra máquina). Quem
    decide apagar é a pessoa, com o arquivo na mão.

    E `CifragemIndisponivel`, de `_chave()`, pela mesma razão do módulo inteiro:
    sem poder cifrar, não grava.
    """
    from cryptography.fernet import Fernet

    caminho = _caminho(autos)
    chave = _chave()  # antes de criar diretório: falhando, nada toca o disco

    gravado = ler(autos)
    for etiqueta, valor in mapa.items():
        anterior = gravado.get(etiqueta)
        if anterior is not None and anterior != valor:
            raise EtiquetaConflitante(
                f"{etiqueta} vale {anterior!r} no mapa dos autos {autos!r} e "
                f"chegou valendo {valor!r}. A numeração recomeçou — semeie o "
                f"Mascarador com o mapa gravado antes de anonimizar (ver "
                f"Mascarador.semear). Nada foi gravado."
            )

    juntos = {**gravado, **mapa}
    caminho.parent.mkdir(parents=True, exist_ok=True)
    corpo = Fernet(chave).encrypt(json.dumps(juntos, ensure_ascii=False).encode())

    # Grava em temporário e renomeia: a troca é atômica no mesmo volume, então
    # uma interrupção no meio deixa o mapa anterior intacto em vez de um
    # arquivo truncado que não decifra.
    #
    # E o temporário é removido se algo der errado antes da troca. Ele não é
    # rascunho inofensivo: é o de-para COMPLETO e fundido (o gravado mais o que
    # chegou), cifrado e em 0600 — quem tem a chave lê tudo. Ficando para trás,
    # era a única coisa deste módulo fora do alcance do prazo de guarda e do
    # `esquecer()`, que olham só o `<autos>.mapa`. Prazo que deixa resíduo não é
    # prazo.
    temporario = _parcial(caminho)
    try:
        descritor = os.open(temporario, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descritor, "wb") as arquivo:
            os.fchmod(arquivo.fileno(), 0o600)  # pelo mesmo umask que a chave
            arquivo.write(corpo)
        os.replace(temporario, caminho)
    except BaseException:
        # `BaseException` porque KeyboardInterrupt e SIGTERM traduzido são
        # justamente quando a interrupção acontece — e o resíduo importa mais
        # nesse caso, não menos. Re-levanta sempre: limpar não é tratar.
        temporario.unlink(missing_ok=True)
        raise
    return caminho


class MapaIlegivel(RuntimeError):
    """
    O arquivo do mapa existe, está no prazo, e não decifra.

    **Isto é alarme, não ausência**, e a distinção foi o achado que reescreveu
    esta função. Arquivo ausente é benigno e esperado — é o expurgo funcionando.
    Arquivo presente e ilegível significa que a chave não é mais a que cifrou
    aquele mapa: ela foi recriada, ou substituída.

    Colapsar os dois em `{}` seria o defeito pior: a reidratação devolveria o
    texto com `[PESSOA_1]` em claro e nenhuma mensagem, e quem lê concluiria
    "venceu, normal" — quando o que houve foi a chave ser trocada. É a mesma
    lição que o `CLAUDE.md` deste repositório registra sobre o contador de OCR:
    "na dúvida não afirme" é boa regra para afirmar fato e péssima para calar
    alarme.
    """


def ler(autos: str) -> dict[str, str]:
    """
    Devolve o mapa destes autos, ou `{}` se não existe ou venceu.

    Vencido é **apagado**, não apenas ignorado: prazo de guarda que só esconde
    não é prazo de guarda — o índice de CPF e nome continuaria no disco.

    Levanta `MapaIlegivel` quando o arquivo existe, está no prazo e não decifra.
    O porquê de não devolver `{}` está na exceção.
    """
    from cryptography.fernet import Fernet, InvalidToken

    caminho = _caminho(autos)
    parcial = _parcial(caminho)

    # O temporário é varrido pelo MESMO prazo, e antes do desvio de ausência
    # abaixo. Sem isto, um `.parcial` órfão — o mapa definitivo já vencido e
    # apagado, ou o processo morto por SIGKILL entre a escrita e a troca —
    # ficaria no disco para sempre, porque a partir daí toda leitura devolve `{}`
    # na primeira linha e nunca mais olha para ele.
    if parcial.exists() and _vencido(parcial):
        parcial.unlink(missing_ok=True)

    if not caminho.exists():
        return {}

    if _vencido(caminho):
        caminho.unlink(missing_ok=True)
        parcial.unlink(missing_ok=True)
        return {}

    try:
        corpo = Fernet(_chave()).decrypt(caminho.read_bytes())
    except InvalidToken as erro:
        raise MapaIlegivel(
            f"o mapa dos autos {autos!r} existe em {caminho} e não decifra com "
            f"a chave atual. A chave foi recriada (o que torna ilegível todo "
            f"mapa gravado antes dela) ou substituída. O arquivo NÃO foi "
            f"apagado — apagá-lo é irreversível, e a decisão é sua."
        ) from erro
    return json.loads(corpo)


def esquecer(autos: str) -> bool:
    """
    Apaga o mapa destes autos. `False` se não havia nada.

    Apaga o temporário também. Quem manda esquecer está pedindo que o de-para
    saia do disco, e um `.parcial` deixado por uma troca interrompida é o de-para
    inteiro — dizer `True` com ele ainda lá seria afirmar um expurgo que não
    aconteceu.
    """
    caminho = _caminho(autos)
    parcial = _parcial(caminho)
    havia = caminho.exists() or parcial.exists()
    caminho.unlink(missing_ok=True)
    parcial.unlink(missing_ok=True)
    return havia
