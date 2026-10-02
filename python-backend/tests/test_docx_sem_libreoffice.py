"""
`.docx` tem de ser lido sem LibreOffice.

O leitor do produto (`liteparse`) converte documento de escritório chamando
LibreOffice headless — ele procura em `/Applications/LibreOffice.app/` no macOS
e em `C:\\Program Files\\Libreoffice\\` no Windows. Onde não houver, a leitura
morre com:

    conversion error: LibreOffice is not installed. Please install LibreOffice
    to convert office documents.

No Mac isso significava que DOCX simplesmente não funcionava — e peça judicial
em Word é o caso mais comum do escritório. O porte declarou sucesso sem pegar
isso porque a suíte não tinha nenhum `.docx` de verdade.

A cura não acrescenta dependência: `.docx` é um zip com `word/document.xml`
dentro, e o formato é estável desde 2007. O extrator lê os parágrafos e as
tabelas na ordem do documento, e só entra em ação quando o LibreOffice não
está disponível — onde ele existe, o caminho antigo continua valendo, porque
converte mais coisa (campos, notas, caixas de texto).
"""

import zipfile
from pathlib import Path

import pytest

from documentos import _texto_de_docx, docx_legivel_sem_libreoffice


DOC_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>AO JUIZADO ESPECIAL CÍVEL</w:t></w:r></w:p>
    <w:p><w:r><w:t xml:space="preserve">O autor </w:t></w:r><w:r><w:t>JOÃO DA SILVA</w:t></w:r><w:r><w:t>, CPF 529.982.247-25.</w:t></w:r></w:p>
    <w:p/>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>Verba</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Valor</w:t></w:r></w:p></w:tc>
      </w:tr>
      <w:tr>
        <w:tc><w:p><w:r><w:t>Danos morais</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>R$ 10.000,00</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
    <w:p><w:r><w:t>Termos em que pede deferimento.</w:t></w:r></w:p>
  </w:body>
</w:document>
"""


@pytest.fixture
def docx(tmp_path) -> str:
    caminho = tmp_path / "peca.docx"
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("word/document.xml", DOC_XML)
    return str(caminho)


def test_extrai_os_paragrafos_na_ordem(docx):
    texto = _texto_de_docx(docx)
    assert "AO JUIZADO ESPECIAL CÍVEL" in texto
    assert texto.index("AO JUIZADO") < texto.index("Termos em que pede")


def test_junta_os_pedacos_de_um_paragrafo_partido(docx):
    """
    O Word quebra um parágrafo em vários `<w:r>` a cada troca de formatação —
    negritar o nome basta. Lendo `<w:t>` solto, "O autor ", "JOÃO DA SILVA" e
    ", CPF…" viram três linhas, e o detector perde o nome por falta de
    contexto à volta.
    """
    assert "O autor JOÃO DA SILVA, CPF 529.982.247-25." in _texto_de_docx(docx)


def test_a_tabela_sai_como_tabela(docx):
    texto = _texto_de_docx(docx)
    assert "| Verba | Valor |" in texto
    assert "| Danos morais | R$ 10.000,00 |" in texto


def test_arquivo_que_nao_e_docx_e_recusado_com_clareza(tmp_path):
    ruim = tmp_path / "falso.docx"
    ruim.write_bytes(b"isto nao e um zip")
    with pytest.raises(ValueError, match="não é um .docx"):
        _texto_de_docx(str(ruim))


def test_zip_sem_document_xml_e_recusado(tmp_path):
    vazio = tmp_path / "vazio.docx"
    with zipfile.ZipFile(vazio, "w") as z:
        z.writestr("leiame.txt", "nada aqui")
    with pytest.raises(ValueError, match="não é um .docx"):
        _texto_de_docx(str(vazio))


def test_a_decisao_de_usar_o_atalho_depende_do_libreoffice(monkeypatch):
    """
    Onde o LibreOffice existe, o caminho antigo continua: ele converte mais
    coisa (campos, notas de rodapé, caixas de texto) que este extrator mínimo.
    """
    monkeypatch.setattr("documentos._libreoffice_disponivel", lambda: True)
    assert docx_legivel_sem_libreoffice() is False
    monkeypatch.setattr("documentos._libreoffice_disponivel", lambda: False)
    assert docx_legivel_sem_libreoffice() is True
