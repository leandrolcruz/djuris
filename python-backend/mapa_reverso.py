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

import re

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
