"""
Tarja de redação em PDF: queimar pixels, não trocar texto.

Até aqui a saída da anonimização era sempre `.txt`/`.md` — é a limitação nº 11
do projeto. Para juntar aos autos ou mandar a um cliente, o que se precisa é do
PDF com o dado **coberto**, e coberto de um jeito que não se desfaça: retângulo
desenhado por cima de texto que continua no arquivo é o erro clássico de
redação, e jornal já publicou documento assim.

Por isso a página é RASTERIZADA antes do desenho: o texto deixa de existir como
texto no arquivo de saída, e o que sobra é imagem com o retângulo queimado. O
preço é o PDF sair não-pesquisável, e ele é o preço certo — a alternativa que
preserva a camada de texto preserva junto o dado que se queria esconder.

Um span que atravessa a quebra de linha vira DUAS tarjas, uma por linha. Com um
retângulo só, o envelope das duas cobriria a largura inteira da página e tudo
que estivesse entre elas.
"""

import zlib
from pathlib import Path

import pytest

from tarja_pdf import caixas_por_linha, tarjar


def _pdf_de_uma_linha(destino: Path, texto: str = "O autor JOAO DA SILVA pede") -> str:
    """
    Um PDF mínimo e determinístico, escrito à mão.

    Nada de biblioteca: o teste precisa saber exatamente onde cada caractere
    está, e um gerador de terceiro traria fonte embutida e espaçamento que
    mudam com a versão. Helvetica a 12pt em (72, 700), página A4.
    """
    conteudo = f"BT /F1 12 Tf 72 700 Td ({texto}) Tj ET".encode("latin-1")
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(conteudo) + conteudo + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    saida = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objetos, start=1):
        offsets.append(len(saida))
        saida += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    inicio_xref = len(saida)
    saida += b"xref\n0 %d\n" % (len(objetos) + 1)
    saida += b"0000000000 65535 f \n"
    for off in offsets:
        saida += b"%010d 00000 n \n" % off
    saida += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objetos) + 1,
        inicio_xref,
    )
    destino.write_bytes(bytes(saida))
    return str(destino)


# --- O agrupamento por linha, sem PDF --------------------------------------


def test_span_numa_linha_so_vira_uma_caixa():
    # (left, bottom, right, top) de três caracteres vizinhos, mesma linha.
    chars = [(10, 700, 16, 712), (16, 700, 22, 712), (22, 700, 28, 712)]
    assert caixas_por_linha(chars) == [(10, 700, 28, 712)]


def test_span_que_atravessa_a_quebra_vira_duas_caixas():
    """
    O caso que um retângulo só estragaria: com o envelope das duas linhas, a
    tarja cobriria a largura inteira da página e tudo que houvesse no meio.
    """
    chars = [
        (500, 700, 506, 712),  # fim da linha de cima
        (520, 700, 526, 712),
        (10, 680, 16, 692),    # começo da linha de baixo
        (16, 680, 22, 692),
    ]
    caixas = caixas_por_linha(chars)
    assert len(caixas) == 2
    assert caixas[0] == (500, 700, 526, 712)
    assert caixas[1] == (10, 680, 22, 692)


def test_caixa_vazia_nao_produz_tarja():
    assert caixas_por_linha([]) == []


# --- O documento inteiro ---------------------------------------------------


@pytest.fixture
def pdf(tmp_path):
    return _pdf_de_uma_linha(tmp_path / "entrada.pdf")


def _detectar_joao(texto):
    """Detector de mentira: acha "JOAO DA SILVA" e devolve o span."""
    i = texto.find("JOAO DA SILVA")
    return [] if i < 0 else [(i, i + len("JOAO DA SILVA"), "PERSON")]


def test_o_texto_nao_sobrevive_no_arquivo_de_saida(pdf, tmp_path):
    """
    A propriedade que define redação: o dado sai do ARQUIVO, não só da vista.
    Retângulo preto sobre texto preservado é o erro que já vazou documento
    público — basta selecionar e copiar.
    """
    saida = tmp_path / "tarjado.pdf"
    tarjar(pdf, str(saida), _detectar_joao)

    bruto = saida.read_bytes()
    assert b"JOAO DA SILVA" not in bruto
    # Nem comprimido: um stream deflate esconderia o texto de um grep ingênuo.
    for pedaco in bruto.split(b"stream"):
        try:
            assert b"JOAO DA SILVA" not in zlib.decompress(pedaco.strip()[:10_000])
        except zlib.error:
            pass


def test_a_regiao_do_nome_fica_coberta(pdf, tmp_path):
    """Os pixels onde o nome estava ficam escuros; o resto da linha, não."""
    import pypdfium2 as pdfium

    saida = tmp_path / "tarjado.pdf"
    rel = tarjar(pdf, str(saida), _detectar_joao, dpi=100)
    assert rel.tarjas == 1

    img = pdfium.PdfDocument(str(saida))[0].render(scale=100 / 72).to_pil().convert("L")
    (x0, y0, x1, y1) = rel.caixas_px[0]
    meio = img.getpixel(((x0 + x1) // 2, (y0 + y1) // 2))
    assert meio < 40, "o centro da tarja tem de estar preto"
    assert img.getpixel((x0 + x1 + 40, (y0 + y1) // 2)) > 200, "fora dela, claro"


def test_sem_deteccao_nenhuma_o_pdf_sai_sem_tarja(pdf, tmp_path):
    saida = tmp_path / "limpo.pdf"
    rel = tarjar(pdf, str(saida), lambda t: [])
    assert rel.tarjas == 0
    assert saida.exists()


def test_o_nome_do_arquivo_nao_vira_titulo_do_pdf(tmp_path):
    """
    O Pillow grava o NOME DO ARQUIVO como `/Title` quando ninguém diz o
    contrário — e nome de arquivo jurídico carrega CNJ e nome de parte. Seria o
    dado saindo dentro do próprio arquivo tarjado, pela porta dos metadados.

    O teste mede o VALOR, não a presença da chave: `/Title` existir vazio é
    inofensivo, e a primeira versão deste teste reprovava por isso — media a
    chave e chamava de vazamento o que era só estrutura do formato.
    """
    entrada = _pdf_de_uma_linha(tmp_path / "entrada.pdf")
    saida = tmp_path / "0071087-46 JOAO DA SILVA x BANCO.pdf"
    tarjar(entrada, str(saida), _detectar_joao)

    bruto = saida.read_bytes()
    # O nome do arquivo vai em UTF-16BE no dicionário de informação.
    for pedaco in ("0071087", "JOAO", "SILVA", "BANCO"):
        assert pedaco.encode("utf-16-be") not in bruto, f"{pedaco} vazou nos metadados"
        assert pedaco.encode("latin-1") not in bruto
