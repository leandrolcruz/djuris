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

# A classe de caracteres cobre `Ç` (U+00C7) e as vogais acentuadas porque
# `ENDEREÇO` é um dos rótulos. Com `[A-Z_]+` ele ficaria de fora em silêncio:
# o texto sairia reidratado, sem erro nenhum, e com o endereço ainda mascarado.
#
# Conferido contra os 27 tipos que o motor suporta: todos os rótulos derivados
# deles casam, incluindo os que caem no fallback `rotulo == entity_type` por não
# estarem em `ROTULO_ENTIDADE` (`ORGANIZATION`, `DATE_TIME`, `LAW`).
#
# A varredura é de UMA passagem, com consulta ao dicionário. Substituir rótulo
# por rótulo em laço é o defeito clássico: `[PESSOA_1]` é prefixo de
# `[PESSOA_10]`, e trocar o primeiro antes produz `Ana Souza0` — que não parece
# defeito de programa, parece erro de digitação do documento.
RE_ROTULO = re.compile(r"\[[A-ZÀ-Þ_]+_\d+\]")


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
                f"{caminho} não está em 0600. Não corrijo em silêncio: não há "
                f"como saber quem já a leu, e seguir usando afirmaria uma "
                f"garantia que este arquivo não sustenta mais. "
                f"Confira quem teve acesso, apague-a (os mapas gravados ficam "
                f"ilegíveis) e deixe-a ser recriada."
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
    # Cria já fechado: gravar e depois chmod deixa uma janela em que o arquivo
    # existe legível. `0o600` no `os.open`, e não `write_bytes` seguido de
    # `chmod`.
    descritor = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descritor, "wb") as arquivo:
        arquivo.write(nova)
    return nova
