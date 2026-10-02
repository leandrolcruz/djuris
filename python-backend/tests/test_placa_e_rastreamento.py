"""
Placa de veículo e rastreamento dos Correios.

Os dois escaparam de uma peça real — `ELZ6I74` e `YH255487353BR` saíram em
claro num documento que o resto da anonimização tinha tratado. Nenhum é "dado
pessoal" no sentido do nome ou do CPF, e é justamente por isso que passam
despercebidos: são **identificadores indiretos**, e num processo que gira em
torno de um carro a placa identifica a parte com a mesma eficácia que o nome.
O rastreamento liga a pessoa a um endereço de entrega.

**Placa.** Dois formatos convivem: o antigo `ABC1234` e o Mercosul `ABC1D23`.
Não há dígito verificador em nenhum dos dois, então o risco de falso positivo é
real — `CNJ1234` numa referência qualquer tem a mesma forma. O score reflete
isso: baixo sozinho, alto quando a palavra "placa" aparece por perto (é o
mecanismo de contexto do Presidio).

**Rastreamento.** Aqui HÁ dígito verificador, módulo 11 com pesos
8-6-4-2-3-5-9-7, e ele é conferido: candidato com DV inválido é descartado em
vez de mascarado, que é a mesma régua do CPF, do CNPJ e do CNJ neste produto.
"""

import pytest

from recognizers import _dv_rastreamento_valido
from engine import get_engine


# --- O dígito verificador, sem motor ---------------------------------------


@pytest.mark.parametrize(
    "codigo",
    [
        "YH255487353BR",  # o da peça real
        "SS123456785BR",  # DV calculado, não inventado
    ],
)
def test_rastreamento_com_dv_valido(codigo):
    assert _dv_rastreamento_valido(codigo) is True


@pytest.mark.parametrize(
    "codigo",
    [
        "YH255487354BR",  # um dígito trocado
        "AA000000000BR",
    ],
)
def test_rastreamento_com_dv_invalido_e_descartado(codigo):
    assert _dv_rastreamento_valido(codigo) is False


# --- No documento ----------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    eng = get_engine()
    eng.initialize()
    return eng


def anonimizar(engine, texto: str) -> str:
    return engine.anonymize(
        text=texto, entities=[], language="pt", politica_mascara="placeholder"
    )["anonymized_text"]


def test_placa_antiga_e_mascarada(engine):
    saida = anonimizar(engine, "o veículo VW Jetta, placa ELZ6I74, foi adquirido")
    assert "ELZ6I74" not in saida
    assert "[PLACA_1]" in saida


def test_placa_mercosul_e_mascarada(engine):
    saida = anonimizar(engine, "o automóvel de placa RIO2A18 permanece em posse")
    assert "RIO2A18" not in saida


def test_a_mesma_placa_recebe_o_mesmo_numero(engine):
    texto = "A placa ELZ6I74 consta do registro; a placa ELZ6I74 foi multada."
    saida = anonimizar(engine, texto)
    assert saida.count("[PLACA_1]") == 2


def test_rastreamento_e_mascarado(engine):
    saida = anonimizar(engine, "expedida pelos Correios (rastreamento YH255487353BR)")
    assert "YH255487353BR" not in saida


def test_rastreamento_invalido_e_descartado_pelo_recognizer(engine):
    """
    DV inválido é descartado, não mascarado — a mesma régua do CPF.

    O que se mede é o TIPO achado, e não o texto final sair intacto: no modo
    spaCy, que é o desta suíte, o NER leve marca `AA000000000BR` como LOCATION
    com score 0.85 por conta própria. Essa é a "qualidade inferior" que o modo
    leve declara, e afirmar aqui que o texto sai limpo seria medir o NER em vez
    do recognizer — num teste que leva o nome dele.
    """
    texto = "o código AA000000000BR não existe"
    achados = engine.anonymize(
        text=texto, entities=[], language="pt", politica_mascara="placeholder"
    )["entities_found"]
    assert "RASTREAMENTO_CORREIOS" not in {e["type"] for e in achados}


# --- O contrapeso: o que NÃO pode virar placa ------------------------------


@pytest.mark.parametrize(
    "trecho",
    [
        "o art. 1022 do CPC",
        "a Lei 9099 de 1995",
        "o processo 5405543-19.2026.8.09.0025",
        "Mov. 12 dos autos",
    ],
)
def test_referencia_juridica_nao_vira_placa(engine, trecho):
    assert "[PLACA" not in anonimizar(engine, trecho)
