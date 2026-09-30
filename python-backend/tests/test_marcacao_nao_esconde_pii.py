"""
Marcação de markdown não pode esconder dado pessoal do detector.

O caminho principal do produto produz markdown: `bot-convert` roteia PDF para o
docling justamente para preservar títulos e tabelas, e a conversão por pandoc
faz o mesmo. Nesse texto, nome de parte aparece em negrito e em título o tempo
todo — é assim que peça judicial é escrita.

E era exatamente ali que o nome escapava. Medido com o motor BERT, mesmo texto,
mesma pessoa:

    O autor **JOÃO DA SILVA**, CPF 529.982.247-25  ->  **JOÃO DA SILVA** intacto
    O autor JOÃO DA SILVA, CPF 529.982.247-25      ->  [PESSOA_1]

O CPF saía mascarado nos dois (é regex), o que torna o defeito pior: a saída
tem cara de anonimizada, com tarja visível logo ao lado do nome que ficou.

A cura segue o padrão que o motor já usava para quebra de linha e para CAIXA
ALTA no modo spaCy: uma VISTA de mesmo comprimento, em que os marcadores viram
espaço. Os offsets continuam valendo no texto original, então a máscara cai no
lugar certo e a marcação sobrevive na saída — `**[PESSOA_1]**`, não
`[PESSOA_1]` sem negrito.
"""

import pytest

from engine import _vista_sem_marcacao, get_engine


# --- A vista, sem motor ----------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "O autor **JOÃO DA SILVA** propõe",
        "## JOÃO DA SILVA",
        "###### título",
        "Um `trecho` de código",
        "~~riscado~~",
        "*ênfase* e **forte**",
        "sem marcação nenhuma",
        "",
    ],
)
def test_a_vista_preserva_o_comprimento(texto):
    """
    A regra que sustenta tudo: mesmo comprimento, para que os offsets achados
    na vista valham no texto original sem tabela de tradução. Uma vista mais
    curta não daria exceção — daria máscara no lugar errado.
    """
    assert len(_vista_sem_marcacao(texto)) == len(texto)


def test_a_vista_apaga_o_negrito_e_o_titulo():
    assert _vista_sem_marcacao("**JOÃO**") == "  JOÃO  "
    assert _vista_sem_marcacao("## JOÃO") == "   JOÃO"
    assert _vista_sem_marcacao("`x`") == " x "


def test_a_vista_nao_mexe_no_que_nao_e_marcacao():
    """
    `#` no meio da linha é número de processo, não título; sublinhado é nome de
    arquivo. Apagá-los mudaria o texto que o detector lê sem necessidade.
    """
    assert _vista_sem_marcacao("Processo # 123") == "Processo # 123"
    assert _vista_sem_marcacao("contrato_final.pdf") == "contrato_final.pdf"


# --- O efeito no documento -------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    eng = get_engine()
    eng.initialize()
    return eng


def anonimizar(engine, texto: str) -> str:
    return engine.anonymize(
        text=texto, entities=["PERSON"], language="pt", politica_mascara="placeholder"
    )["anonymized_text"]


def test_nome_em_negrito_e_mascarado(engine):
    """O defeito que este arquivo existe para fechar."""
    saida = anonimizar(engine, "O autor **MARIA OLIVEIRA** propõe a presente ação.")
    assert "MARIA OLIVEIRA" not in saida


def test_nome_em_titulo_e_mascarado(engine):
    saida = anonimizar(engine, "## MARIA OLIVEIRA\n\nPropõe a presente ação.")
    assert "MARIA OLIVEIRA" not in saida


def test_a_marcacao_sobrevive_a_mascara(engine):
    """
    A tarja entra, o negrito fica. Se os asteriscos sumissem junto, o markdown
    se desmontaria — e o documento estruturado que o docling produziu para a IA
    ler perderia justamente a estrutura.
    """
    saida = anonimizar(engine, "O autor **MARIA OLIVEIRA** propõe a presente ação.")
    assert "**" in saida


def test_a_ordem_da_composicao_com_a_vista_linear():
    """
    A marcação sai ANTES de as quebras de linha virarem espaço, e isso não é
    detalhe de gosto: `#` só é título no começo da linha, então compor na ordem
    errada faz `^` achar só o começo do documento e todo título do meio do
    texto passar batido. O teste do nome em título passava mesmo assim — ali o
    `##` vem separado do nome por espaço, e o detector o ignorava sozinho. Uma
    garantia que depende de sorte não é garantia.
    """
    from engine import _vista_linear, _vista_sem_marcacao

    texto = "Autor da ação.\n## MARIA OLIVEIRA\nPropõe."
    certa = _vista_linear(_vista_sem_marcacao(texto))
    errada = _vista_sem_marcacao(_vista_linear(texto))

    assert "#" not in certa
    assert "#" in errada, "se isto falhar, a ordem deixou de importar — reveja o porquê"
    assert len(certa) == len(texto)
