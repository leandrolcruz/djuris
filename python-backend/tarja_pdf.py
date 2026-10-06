"""
Tarja de redação em PDF.

A limitação nº 11 do projeto: até aqui a anonimização devolvia sempre texto, e
quem precisava juntar o documento aos autos ou mandá-lo a um cliente ficava sem
saída. Este módulo produz o PDF com o dado **coberto**.

**Por que a página é rasterizada.** Desenhar o retângulo e manter a camada de
texto é o erro clássico de redação — o texto continua no arquivo, basta
selecionar e copiar, e documento público já vazou exatamente assim. Aqui a
página vira imagem antes do desenho: o que sai não tem texto nenhum, e o
retângulo é pixel preto sobre pixel.

O preço é o PDF sair não-pesquisável. É o preço certo: a alternativa que
preserva a busca preserva junto o dado que se queria esconder.

**O que este módulo NÃO faz, e precisa ser dito:** ele cobre o que o detector
encontrou. Dado que o detector não viu continua visível — a tarja não é uma
segunda chance de detecção, é a aplicação fiel da primeira.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

# Caixas na mesma linha têm a base quase igual; "quase" porque acento e
# pontuação deslocam alguns décimos de ponto. 2pt separa linha de ruído sem
# juntar linhas vizinhas, que num texto a 12pt distam ~14pt.
TOLERANCIA_LINHA = 2.0

# Folga em volta da tarja, em pontos. Sem ela a borda da letra escapa pelo
# arredondamento do rasterizador e sobra um fio do caractere original.
FOLGA = 1.0


@dataclass
class Relatorio:
    """O que a tarja fez, para quem precisa conferir antes de enviar."""

    paginas: int = 0
    tarjas: int = 0
    por_tipo: dict[str, int] = field(default_factory=dict)
    caixas_px: list[tuple[int, int, int, int]] = field(default_factory=list)


def caixas_por_linha(
    chars: Sequence[tuple[float, float, float, float]]
) -> list[tuple[float, float, float, float]]:
    """
    Agrupa caixas de caractere em um retângulo POR LINHA.

    Um span que atravessa a quebra — e nome de parte atravessa o tempo todo —
    não pode virar um retângulo só: o envelope das duas linhas cobre a largura
    inteira da página e tudo que estiver entre elas. Cada linha ganha a sua.
    """
    if not chars:
        return []

    linhas: list[list[tuple[float, float, float, float]]] = []
    for caixa in chars:
        base = caixa[1]
        for linha in linhas:
            if abs(linha[0][1] - base) <= TOLERANCIA_LINHA:
                linha.append(caixa)
                break
        else:
            linhas.append([caixa])

    return [
        (
            min(c[0] for c in linha),
            min(c[1] for c in linha),
            max(c[2] for c in linha),
            max(c[3] for c in linha),
        )
        for linha in linhas
    ]


def _caixas_do_span(textpage, inicio: int, fim: int) -> list[tuple[float, float, float, float]]:
    chars = []
    for i in range(inicio, fim):
        try:
            chars.append(textpage.get_charbox(i))
        except Exception:
            # Caractere sem glifo (espaço de layout, marca de controle) não tem
            # caixa. Pular é certo: ele não desenha nada que precise cobrir.
            continue
    return caixas_por_linha(chars)


def tarjar(
    origem: str,
    destino: str,
    detectar: Callable[[str], Sequence[tuple[int, int, str]]],
    dpi: int = 150,
) -> Relatorio:
    """
    Escreve em `destino` o PDF de `origem` com as entidades cobertas.

    `detectar` recebe o texto de uma página e devolve `(inicio, fim, tipo)` em
    offsets desse texto. Ele é injetado de propósito: este módulo não importa o
    motor, e por isso os testes rodam em milissegundos, sem carregar modelo.
    """
    import pypdfium2 as pdfium
    from PIL import Image, ImageDraw

    doc = pdfium.PdfDocument(origem)
    escala = dpi / 72
    relatorio = Relatorio(paginas=len(doc))
    paginas_prontas: list[Image.Image] = []
    # Página e textpage são handles do pdfium, não objetos Python comuns: sem
    # fechar, o pdfium avisa no fim do processo ("objects are still open") e,
    # num documento grande, segura memória do começo ao fim do laço.
    abertos = []

    for pagina in doc:
        _, altura_pt = pagina.get_size()
        textpage = pagina.get_textpage()
        abertos.append((pagina, textpage))
        texto = textpage.get_text_range()

        imagem = pagina.render(scale=escala).to_pil().convert("RGB")
        desenho = ImageDraw.Draw(imagem)

        for inicio, fim, tipo in detectar(texto):
            for esq, base, dir_, topo in _caixas_do_span(textpage, inicio, fim):
                # O PDF conta o Y de baixo para cima e a imagem de cima para
                # baixo: sem inverter, a tarja cai espelhada na página.
                x0 = (esq - FOLGA) * escala
                x1 = (dir_ + FOLGA) * escala
                y0 = (altura_pt - topo - FOLGA) * escala
                y1 = (altura_pt - base + FOLGA) * escala
                caixa = (int(x0), int(y0), int(x1), int(y1))
                desenho.rectangle(caixa, fill=(0, 0, 0))
                relatorio.caixas_px.append(caixa)
                relatorio.tarjas += 1
                relatorio.por_tipo[tipo] = relatorio.por_tipo.get(tipo, 0) + 1

        paginas_prontas.append(imagem)

    for pagina, textpage in abertos:
        textpage.close()
        pagina.close()
    doc.close()

    # Documento NOVO, montado só das imagens: nada do dicionário de informação
    # do original (autor, título, produtor — que costumam trazer nome de pessoa
    # e caminho de rede) atravessa para a saída.
    #
    # E o `title=` explícito não é zelo: sem ele o Pillow grava o NOME DO
    # ARQUIVO de saída como título do PDF. Nome de arquivo jurídico carrega
    # número CNJ e nome de parte o tempo todo — seria o dado saindo pela porta
    # que este módulo existe para fechar, dentro do próprio arquivo tarjado.
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    paginas_prontas[0].save(
        destino,
        save_all=True,
        append_images=paginas_prontas[1:],
        resolution=dpi,
        title="",
        author="",
        subject="",
        keywords="",
        creator="",
        producer="",
    )
    return relatorio
