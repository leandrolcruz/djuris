"""
Três falsos positivos que tornavam a peça anonimizada inútil.

Medidos numa peça real de embargos de declaração, com o motor BERT. O texto
saía assim:

    fundamento no [LAW_1]. 48 da Lei nº 9.[TELEFONE_1] e no [LAW_1]. 1.022, II
    contra a [ENDEREÇO_1] de Mov. 12

Três causas distintas, e nenhuma delas protege pessoa nenhuma:

1. **`art.` virava `[LAW_1]`.** O modelo jurídico devolve `LEGISLACAO`, que o
   motor mapeia para `LAW` — e LAW era mascarado como qualquer outra entidade.
   Referência a lei NÃO é dado pessoal: mascará-la não esconde ninguém e
   destrói o documento, porque o modelo do outro lado deixa de saber que norma
   foi invocada.

2. **`9.099/1995` virava telefone.** O recognizer genérico de telefone casa
   `099/1995` com score 0.40.

3. **`r. decisão` virava endereço, engolindo 58 caracteres.** O Presidio aplica
   `re.IGNORECASE` por padrão, então o `R\\.` do padrão de logradouro casa o
   `r.` de "r. decisão" (respeitável decisão) — e, pela mesma flag, o
   `[A-ZÁÀ…]` que deveria exigir nome próprio passa a aceitar a minúscula de
   "decisão". O match então corre até o fim da linha.

O contrapeso, testado junto: endereço de verdade continua mascarado. A cura não
pode ser desligar a entidade — endereço de parte É dado pessoal.
"""

import pytest

from engine import get_engine


@pytest.fixture(scope="module")
def engine():
    eng = get_engine()
    eng.initialize()
    return eng


def anonimizar(engine, texto: str, entities=None) -> str:
    return engine.anonymize(
        text=texto,
        entities=entities or [],
        language="pt",
        politica_mascara="placeholder",
    )["anonymized_text"]


# --- 1. Referência legal não é dado pessoal --------------------------------


def test_artigo_e_lei_ficam_legiveis(engine):
    texto = "com fundamento no art. 48 da Lei nº 9.099/1995 e no art. 1.022, II, do CPC"
    saida = anonimizar(engine, texto)
    assert "art. 48" in saida
    assert "9.099/1995" in saida, "o número da lei não pode virar telefone"
    assert "art. 1.022" in saida
    assert "[LAW" not in saida
    assert "[TELEFONE" not in saida


def test_quem_pedir_LAW_explicitamente_continua_recebendo(engine):
    """
    Tirar do padrão não é tirar do produto: quem passa `entities=["LAW"]` está
    dizendo que quer aquilo mascarado, e a escolha é dele.

    Só que LAW **não tem recognizer**: ele nasce do NER jurídico (`LEGISLACAO`
    → `LAW`, ver `engine.py`), que só existe no modo transformer. Pedi-lo em
    spaCy — o modo desta suíte — levanta `ValueError: No matching recognizers
    were found to serve the request` lá no registro do Presidio, antes de
    qualquer código nosso.

    Então o teste mede as duas realidades, e nenhuma delas é suposição: no
    transformer, pedir LAW mascara; em spaCy, pedir LAW é erro — e saber disso
    vale mais que pular o caso, porque quem rodar `-e LAW` com o modo leve vai
    receber esse traceback.
    """
    texto = "com fundamento no art. 48 da Lei nº 9.099/1995"

    # O padrão, que é o que esta tarefa conserta: sai inteiro, em qualquer modo.
    assert "[LAW" not in anonimizar(engine, texto)

    if engine.nlp_mode == "transformer":
        assert "[LAW_1]" in anonimizar(engine, texto, entities=["LAW"])
    else:
        with pytest.raises(ValueError, match="No matching recognizers"):
            anonimizar(engine, texto, entities=["LAW"])


# --- 2. "r." de respeitável não é logradouro -------------------------------


def test_r_de_respeitavel_nao_vira_endereco(engine):
    texto = "contra a r. decisão de Mov. 12, pelos motivos a seguir"
    saida = anonimizar(engine, texto)
    assert "r. decisão" in saida
    assert "[ENDEREÇO" not in saida


@pytest.mark.parametrize(
    "trecho",
    [
        "a r. sentença merece reforma",
        "o r. despacho de fl. 10",
        "a r. decisão agravada",
    ],
)
def test_outras_formas_do_respeitavel(engine, trecho):
    assert "[ENDEREÇO" not in anonimizar(engine, trecho)


# --- O contrapeso: endereço de verdade continua saindo ---------------------


@pytest.mark.parametrize(
    "endereco",
    [
        "residente na Rua das Flores, 120, Caldas Novas",
        "domiciliado na Avenida Paulista, 1500",
        "com sede na R. Vinte e Cinco de Março, 300",
    ],
)
def test_endereco_de_verdade_continua_mascarado(engine, endereco):
    """
    Metade desta suíte existe para a cura não virar buraco: endereço de parte é
    dado pessoal, e a correção dos falsos positivos não pode apagar a detecção.
    A abreviação `R.` seguida de NOME PRÓPRIO continua valendo.
    """
    saida = anonimizar(engine, endereco)
    assert "[ENDEREÇO_1]" in saida, f"deixou de mascarar: {endereco!r}"


def test_o_endereco_nao_engole_a_frase_inteira(engine):
    """
    O match voraz pegava 58 caracteres a partir do `r.`. Mesmo quando há
    endereço de verdade, o que vem ANTES dele não faz parte do endereço.
    """
    texto = "contra a r. decisão, o autor reside na Rua das Flores, 120."
    saida = anonimizar(engine, texto)
    assert "contra a r. decisão" in saida
    assert "[ENDEREÇO_1]" in saida
