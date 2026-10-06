"""
Certidão de anonimização.

A Res. CNJ 615/2025 admite processamento externo de dado do Judiciário desde que
anonimizado na origem. Quem junta aos autos — ou manda a um colega — um documento
mascarado precisa poder dizer **o que foi feito**: com que motor, quando, quantas
ocorrências, e sobre qual arquivo exatamente. É isso que este módulo declara.

**O que ela não tem é o que a define.** Uma certidão que listasse os valores
mascarados seria o índice de CPFs que o produto existe para evitar, viajando
anexado ao arquivo que os escondeu. Aqui só entram contagens por TIPO e hashes.

**E ela declara o que foi feito, não que nada escapou.** Certidão que só afirma
acerto vira carimbo; o limite está escrito nela mesma, não no manual.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BASE_NORMATIVA = (
    "Resolução CNJ 615/2025, que admite o processamento de dado do Judiciário "
    "fora do órgão desde que anonimizado na origem."
)


def _sha256(caminho: str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


@dataclass
class Certidao:
    origem: str
    destino: str
    sha256_origem: str
    sha256_destino: str
    quando: str
    por_tipo: dict[str, int]
    politica: str
    motor: str
    modelo: str
    entidades_pedidas: list[str]

    @property
    def total(self) -> int:
        return sum(self.por_tipo.values())

    def markdown(self) -> str:
        if self.por_tipo:
            linhas = "\n".join(
                f"| `{tipo}` | {n} |" for tipo, n in sorted(self.por_tipo.items())
            )
            tabela = (
                "| Tipo de dado | Ocorrências |\n|---|---|\n"
                + linhas
                + f"\n| **Total** | **{self.total}** |"
            )
            resumo = f"**{self.total} ocorrência(s)** de dado pessoal foram mascaradas."
        else:
            tabela = ""
            resumo = (
                "**Nenhuma ocorrência** de dado pessoal foi encontrada neste "
                "documento. Isso não é o mesmo que afirmar que não havia."
            )

        if self.entidades_pedidas:
            escopo = (
                "A busca foi **restringida** aos tipos "
                + ", ".join(f"`{e}`" for e in self.entidades_pedidas)
                + ". Tipo fora dessa lista não foi procurado — a ausência dele "
                "abaixo não significa que não existia no documento."
            )
        else:
            escopo = (
                "A busca usou o conjunto padrão de tipos. Referência legal, data "
                "processual, comarca e órgão público ficam de fora por decisão de "
                "desenho: não são dado pessoal, e mascará-los cegaria quem lê sem "
                "proteger ninguém."
            )

        return f"""# Certidão de anonimização

Documento gerado automaticamente por **Direito&Juris**, em {self.quando}.

## O que foi anonimizado

| | |
|---|---|
| Arquivo de origem | `{Path(self.origem).name}` |
| SHA-256 da origem | `{self.sha256_origem}` |
| Arquivo gerado | `{Path(self.destino).name}` |
| SHA-256 do gerado | `{self.sha256_destino}` |

Os dois resumos criptográficos permitem conferir, a qualquer tempo, que o
arquivo em mãos é exatamente o que esta certidão descreve.

## O que foi encontrado e mascarado

{resumo}

{tabela}

Esta certidão **não contém** nenhum dos valores mascarados — só a contagem por
tipo. Listá-los faria dela o índice de dados pessoais que a anonimização existe
para evitar.

## Como foi feito

| | |
|---|---|
| Política de máscara | `{self.politica}` |
| Motor de detecção | `{self.motor}` |
| Modelo | `{self.modelo}` |

{escopo}

O processamento ocorreu **inteiramente nesta máquina**: nenhuma página do
documento foi enviada a serviço externo durante a anonimização.

## Base normativa

{BASE_NORMATIVA}

## Limite desta certidão

Ela declara **o que foi feito**, e não que nada escapou. A detecção é
automática e tem margem de erro conhecida; um dado que o detector não
reconheceu permanece no documento gerado. **Confira o resultado antes de
enviar** — esta certidão registra o procedimento, não substitui a conferência.
"""


def gerar(
    origem: str,
    destino: str,
    por_tipo: dict[str, int],
    politica: str,
    motor: str,
    modelo: str,
    entidades_pedidas: list[str] | None = None,
) -> Certidao:
    """Monta a certidão a partir do que a execução de fato produziu."""
    return Certidao(
        origem=origem,
        destino=destino,
        sha256_origem=_sha256(origem),
        sha256_destino=_sha256(destino),
        # Fuso explícito: certidão sem fuso é ambígua a quem lê noutro lugar, e
        # ela existe justamente para ser lida por terceiro.
        quando=datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y às %H:%M:%S %Z"),
        por_tipo=dict(por_tipo),
        politica=politica,
        motor=motor,
        modelo=modelo,
        entidades_pedidas=list(entidades_pedidas or []),
    )
