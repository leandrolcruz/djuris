"""
Certidão de anonimização.

A Res. CNJ 615/2025 admite processamento externo de dado do Judiciário desde
que anonimizado na origem. Quem junta aos autos um documento mascarado precisa
poder dizer **o que foi feito** — com que motor, quando, quantas ocorrências, e
sobre qual arquivo exatamente. É isso que a certidão declara.

**A propriedade que a define é o que ela NÃO tem.** Uma certidão que listasse os
valores mascarados seria o índice de CPFs que o produto existe para evitar, e
viajaria junto do documento anonimizado — desfazendo o trabalho no anexo. Ela
traz contagens por TIPO e hashes, nunca valor.

Os hashes são o que a torna verificável: quem recebe confere que o arquivo em
mãos é o mesmo que a certidão descreve, sem precisar do original.
"""

import hashlib
import re
from pathlib import Path

import pytest

from certidao import Certidao, gerar


@pytest.fixture
def certidao(tmp_path) -> tuple[Certidao, Path, Path]:
    origem = tmp_path / "peca.txt"
    origem.write_text("O autor JOAO DA SILVA, CPF 529.982.247-25, de Jataí.", encoding="utf-8")
    saida = tmp_path / "peca_anonimizada.txt"
    saida.write_text("O autor [PESSOA_1], CPF [CPF_1], de Jataí.", encoding="utf-8")

    c = gerar(
        origem=str(origem),
        destino=str(saida),
        por_tipo={"PERSON": 1, "CPF_BR": 1},
        politica="placeholder",
        motor="transformer",
        modelo="dominguesm/legal-bert-ner-base-cased-ptbr",
        entidades_pedidas=[],
    )
    return c, origem, saida


def test_a_certidao_nao_carrega_nenhum_valor_mascarado(certidao):
    """
    O teste que define o documento. Uma certidão com os valores seria o índice
    de dados pessoais viajando anexado ao arquivo que os escondeu.
    """
    c, origem, _ = certidao
    texto = c.markdown()
    for segredo in ("JOAO", "SILVA", "529.982.247-25", "529982247"):
        assert segredo not in texto, f"{segredo!r} vazou na certidão"


def test_declara_as_contagens_por_tipo(certidao):
    texto = certidao[0].markdown()
    assert "PERSON" in texto and "CPF_BR" in texto
    assert re.search(r"2\s+ocorrência", texto), "o total precisa estar escrito"


def test_os_hashes_batem_com_os_arquivos(certidao):
    """
    O que torna a certidão verificável: quem recebe confere o arquivo em mãos
    contra o hash, sem precisar do original — e o hash do ORIGINAL permite
    provar, com ele em mãos, que foi aquele documento que entrou.
    """
    c, origem, saida = certidao
    assert c.sha256_origem == hashlib.sha256(origem.read_bytes()).hexdigest()
    assert c.sha256_destino == hashlib.sha256(saida.read_bytes()).hexdigest()
    assert c.sha256_origem in c.markdown()
    assert c.sha256_destino in c.markdown()


def test_declara_o_motor_porque_a_qualidade_depende_dele(certidao):
    """
    Anonimizar em spaCy acreditando ter BERT é o risco que o próprio produto
    documenta. Quem lê a certidão tem de saber com qual dos dois foi feito.
    """
    texto = certidao[0].markdown()
    assert "transformer" in texto
    assert "legal-bert-ner-base-cased-ptbr" in texto


def test_declara_que_rodou_localmente_e_a_base_normativa(certidao):
    texto = certidao[0].markdown()
    assert "615/2025" in texto
    assert "nesta máquina" in texto or "local" in texto.lower()


def test_o_limite_vai_escrito_na_propria_certidao(certidao):
    """
    Certidão que só afirma acerto vira carimbo. O que ela declara é o que foi
    FEITO, não que nada escapou — e a diferença precisa estar no documento, não
    no manual.
    """
    texto = certidao[0].markdown().lower()
    assert "não" in texto and ("garantia" in texto or "escapou" in texto or "confer" in texto)


def test_entidades_pedidas_explicitamente_aparecem(tmp_path):
    """
    Quem restringiu as entidades mudou o que foi procurado, e isso muda o que a
    certidão significa: ausência de LOCATION com `-e PERSON` não é "não havia",
    é "não foi procurado".
    """
    origem = tmp_path / "a.txt"; origem.write_text("x", encoding="utf-8")
    saida = tmp_path / "b.txt"; saida.write_text("y", encoding="utf-8")
    c = gerar(
        origem=str(origem), destino=str(saida), por_tipo={"PERSON": 3},
        politica="placeholder", motor="transformer", modelo="m",
        entidades_pedidas=["PERSON", "CPF_BR"],
    )
    texto = c.markdown()
    assert "PERSON, CPF_BR" in texto or "PERSON" in texto
    assert "restrin" in texto.lower() or "apenas" in texto.lower()


def test_sem_nenhuma_ocorrencia_a_certidao_diz_isso(tmp_path):
    origem = tmp_path / "a.txt"; origem.write_text("nada aqui", encoding="utf-8")
    saida = tmp_path / "b.txt"; saida.write_text("nada aqui", encoding="utf-8")
    c = gerar(
        origem=str(origem), destino=str(saida), por_tipo={},
        politica="placeholder", motor="spacy", modelo="pt_core_news_lg",
        entidades_pedidas=[],
    )
    texto = c.markdown()
    assert "nenhuma" in texto.lower()
