"""
O mapa reverso é o de-para entre `[PESSOA_1]` e o valor real.

Ele existe para uma coisa só: a resposta que voltou de um modelo na nuvem fala
em `[PESSOA_1]`, e quem lê precisa do nome. Três propriedades sustentam isso, e
nenhuma é óbvia.

**Um rótulo designa um valor só.** `ROTULO_ENTIDADE` manda dois tipos
(`PHONE_NUMBER_BR` e `PHONE_NUMBER`) para o mesmo `TELEFONE`, e o motor suporta
os dois. Numerar por tipo dava `[TELEFONE_1]` a dois telefones diferentes: texto
ambíguo antes de qualquer reidratação, e substituição do valor errado depois. A
numeração é por RÓTULO porque o rótulo é a identidade que o leitor e o modelo
enxergam — `entity_type` é detalhe interno de quem detectou.

**A grafia tem de ser a original.** A chave de deduplicação é
`_normalizar(texto)`, que tira acento e caixa de propósito — é o que faz
`JOÃO DA SILVA` e `joao da silva` receberem o mesmo número, e é o que o OCR
exige. Guardar a chave como valor devolveria `joao da silva` na reidratação:
não é erro que quebre nada, é erro que entrega um documento com nome errado
parecendo certo.

**As políticas `parcial` e `total` não têm mapa, e não é omissão.** Elas não
passam pelo `_placeholder`, então nada é numerado e `mapa()` devolve `{}`.
Reidratar `J**** d* S****` é impossível — a informação não existe mais no texto.
Quem pedir mapa com essas políticas tem de receber vazio, não uma aproximação.
"""

import json

import pytest

from mask_config import Mascarador


def test_um_rotulo_designa_um_valor_so_entre_tipos_diferentes():
    """
    O defeito que esta tarefa conserta. Antes, os dois viravam `[TELEFONE_1]`.
    """
    m = Mascarador("placeholder")
    a = m.mascarar("PHONE_NUMBER_BR", "(64) 99999-1111")
    b = m.mascarar("PHONE_NUMBER", "+55 11 98888-2222")
    assert a == "[TELEFONE_1]"
    assert b == "[TELEFONE_2]", "dois telefones diferentes não podem colidir"
    assert m.mapa() == {
        "[TELEFONE_1]": "(64) 99999-1111",
        "[TELEFONE_2]": "+55 11 98888-2222",
    }


def test_mesmo_valor_em_tipos_diferentes_recebe_um_numero_so():
    """
    O outro lado da mesma moeda: se dois detectores acham o MESMO telefone e o
    classificam diferente, ele é um telefone, e merece um rótulo.
    """
    m = Mascarador("placeholder")
    assert m.mascarar("PHONE_NUMBER_BR", "(64) 99999-1111") == "[TELEFONE_1]"
    assert m.mascarar("PHONE_NUMBER", "(64) 99999-1111") == "[TELEFONE_1]"
    assert m.mapa() == {"[TELEFONE_1]": "(64) 99999-1111"}


def test_mapa_devolve_a_grafia_original_com_acento_e_caixa():
    m = Mascarador("placeholder")
    assert m.mascarar("PERSON", "JOÃO DA SILVA") == "[PESSOA_1]"
    assert m.mapa() == {"[PESSOA_1]": "JOÃO DA SILVA"}


def test_a_primeira_grafia_vista_e_a_que_fica():
    """
    O mesmo valor escrito de dois jeitos recebe um número só — e o mapa guarda a
    PRIMEIRA aparição. É arbitrário, mas tem de ser determinístico: a alternativa
    (a última) faria o mapa depender de quantas vezes o documento repetiu o nome.
    """
    m = Mascarador("placeholder")
    assert m.mascarar("PERSON", "JOÃO DA SILVA") == "[PESSOA_1]"
    assert m.mascarar("PERSON", "joao da silva") == "[PESSOA_1]"
    assert m.mapa() == {"[PESSOA_1]": "JOÃO DA SILVA"}


def test_numeracao_segue_a_ordem_de_chamada_e_separa_rotulos():
    m = Mascarador("placeholder")
    m.mascarar("PERSON", "Ana Souza")
    m.mascarar("CPF_BR", "529.982.247-25")
    m.mascarar("PERSON", "Bruno Lima")
    assert m.mapa() == {
        "[PESSOA_1]": "Ana Souza",
        "[PESSOA_2]": "Bruno Lima",
        "[CPF_1]": "529.982.247-25",
    }


def test_resumo_continua_contando_por_TIPO_e_nao_por_rotulo():
    """
    Contrato antigo que NÃO pode mudar de forma: `resumo()` vira
    `valores_distintos` e atravessa `api_v1.py:152`, `server.py:331` e a
    interface (`src/hooks/useLote.ts`). A numeração passou a ser por rótulo; a
    contagem continua por tipo.
    """
    m = Mascarador("placeholder")
    m.mascarar("PERSON", "Ana Souza")
    m.mascarar("PERSON", "ana souza")
    m.mascarar("PERSON", "Bruno Lima")
    assert m.resumo() == {"PERSON": 2}


def test_resumo_separa_os_dois_tipos_de_telefone_mesmo_com_rotulo_comum():
    m = Mascarador("placeholder")
    m.mascarar("PHONE_NUMBER_BR", "(64) 99999-1111")
    m.mascarar("PHONE_NUMBER", "+55 11 98888-2222")
    assert m.resumo() == {"PHONE_NUMBER_BR": 1, "PHONE_NUMBER": 1}


@pytest.mark.parametrize("politica", ["parcial", "total"])
def test_politicas_sem_placeholder_nao_tem_mapa(politica):
    m = Mascarador(politica)
    m.mascarar("PERSON", "João da Silva")
    assert m.mapa() == {}


# ---------------------------------------------------------------------------
# Numeração compartilhada entre peças dos mesmos autos
#
# Estes testes não carregam modelo: chamam `_aplicar_mascaras`, que é estático e
# recebe os spans prontos. O que se mede é o contrato do Mascarador
# compartilhado, não a qualidade da detecção.
# ---------------------------------------------------------------------------

from engine import PresidioEngine


def test_mascarador_compartilhado_da_o_mesmo_numero_em_duas_pecas():
    """
    Sem compartilhar, `[PESSOA_1]` designa Ana na inicial e Bruno na procuração.
    Juntas num contexto, o modelo troca as pessoas — e a resposta sai bem
    escrita, plausível e errada.
    """
    inicial = "Ana Souza propôs a ação."
    procuracao = "Bruno Lima outorga poderes."

    m = Mascarador("placeholder")
    saida_inicial = PresidioEngine._aplicar_mascaras(
        inicial, [(0, 9, "PERSON", 0.99)], m
    )
    saida_procuracao = PresidioEngine._aplicar_mascaras(
        procuracao, [(0, 10, "PERSON", 0.99)], m
    )

    assert saida_inicial == "[PESSOA_1] propôs a ação."
    assert saida_procuracao == "[PESSOA_2] outorga poderes."
    assert m.mapa() == {"[PESSOA_1]": "Ana Souza", "[PESSOA_2]": "Bruno Lima"}


def test_mesma_pessoa_em_duas_pecas_recebe_um_numero_so():
    m = Mascarador("placeholder")
    PresidioEngine._aplicar_mascaras("Ana Souza propôs.", [(0, 9, "PERSON", 0.99)], m)
    saida = PresidioEngine._aplicar_mascaras(
        "ANA SOUZA foi ouvida.", [(0, 9, "PERSON", 0.99)], m
    )
    assert saida == "[PESSOA_1] foi ouvida."
    assert m.mapa() == {"[PESSOA_1]": "Ana Souza"}


def test_anonymize_recusa_mascarador_de_outra_politica():
    """
    Injetar um Mascarador 'total' e pedir política 'placeholder' é ambiguidade:
    um dos dois seria silenciosamente ignorado. Recusar é a única saída que não
    mente sobre o que foi aplicado.
    """
    motor = PresidioEngine()
    with pytest.raises(ValueError, match="política"):
        motor.anonymize(
            text="x",
            entities=[],
            politica_mascara="placeholder",
            mascarador=Mascarador("total"),
        )


# ---------------------------------------------------------------------------
# Task 7b — o comentário de `engine.py` (linha 675: "A CLI e o MCP NUNCA o
# imprimem — nem em `-f json`") era uma garantia escrita que o código não
# cumpria: `_formatar` fazia `json.dumps(resultado)` sobre o dicionário CRU
# devolvido por `anonymize()`, que desde a Task 7 carrega `mapa_reverso`. O
# conserto filtra a chave no único ponto por onde a saída em json passa.
#
# `entities_found` continua expondo o texto real de cada ocorrência — isso é
# por desenho (serve para auditar o que foi mascarado) e não muda aqui.
# ---------------------------------------------------------------------------

import cli


def _resultado_de_exemplo() -> dict:
    return {
        "anonymized_text": "O autor [PESSOA_1] ajuizou a ação.",
        "entities_found": [
            {
                "type": "PERSON",
                "text": "JOÃO DA SILVA",
                "start": 8,
                "end": 21,
                "score": 0.85,
            }
        ],
        "politica_mascara": "placeholder",
        "valores_distintos": {"PERSON": 1},
        "mapa_reverso": {"[PESSOA_1]": "JOÃO DA SILVA"},
    }


def test_formatar_json_nao_expoe_mapa_reverso_mas_preserva_o_resto():
    saida = cli._formatar(_resultado_de_exemplo(), "json")
    assert "mapa_reverso" not in saida

    corpo = json.loads(saida)
    assert "mapa_reverso" not in corpo
    # O contrato do `-f json` não pode ser quebrado pela correção: a lista de
    # ocorrências (que documentadamente expõe o texto real) continua ali.
    assert corpo["anonymized_text"] == "O autor [PESSOA_1] ajuizou a ação."
    assert corpo["entities_found"] == [
        {
            "type": "PERSON",
            "text": "JOÃO DA SILVA",
            "start": 8,
            "end": 21,
            "score": 0.85,
        }
    ]


def test_formatar_text_devolve_so_o_texto_anonimizado():
    saida = cli._formatar(_resultado_de_exemplo(), "text")
    assert saida == "O autor [PESSOA_1] ajuizou a ação."


# ---------------------------------------------------------------------------
# A rota `/processar/{job_id}/resultado` serializa o dicionário do motor sem
# `response_model` — sem o filtro, ela devolveria `mapa_reverso` também.
#
# O job é fabricado diretamente (sem rodar extração/análise de verdade): o
# que se testa é o comportamento da rota sobre um resultado pronto, não a
# qualidade da detecção — mais barato e é a mesma coisa que os outros testes
# de rota fazem para status/cancelamento.
# ---------------------------------------------------------------------------

import os

TOKEN = os.environ["PRESIDIO_TOKEN"]


@pytest.fixture(scope="module")
def cliente_api():
    from fastapi.testclient import TestClient

    import server

    return TestClient(server.app)


def test_rota_resultado_do_job_nao_expoe_mapa_reverso(cliente_api):
    import jobs

    job = jobs.registro.criar("autos.txt")
    job.resultado = _resultado_de_exemplo()
    job.estado = jobs.CONCLUIDO

    resposta = cliente_api.get(
        f"/processar/{job.id}/resultado",
        headers={"X-Presidio-Token": TOKEN},
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert "mapa_reverso" not in corpo
    assert corpo["anonymized_text"] == "O autor [PESSOA_1] ajuizou a ação."


# ---------------------------------------------------------------------------
# A substituição
# ---------------------------------------------------------------------------

import mapa_reverso


def test_reidrata_substituindo_os_rotulos():
    texto = "[PESSOA_1] alega que [PESSOA_2] não pagou. CPF: [CPF_1]."
    mapa = {
        "[PESSOA_1]": "Ana Souza",
        "[PESSOA_2]": "Bruno Lima",
        "[CPF_1]": "529.982.247-25",
    }
    assert mapa_reverso.reidratar(texto, mapa) == (
        "Ana Souza alega que Bruno Lima não pagou. CPF: 529.982.247-25."
    )


def test_dois_digitos_nao_sao_corrompidos_pelo_de_um_digito():
    """
    O defeito clássico: substituir `[PESSOA_1]` por varredura ingênua atinge o
    prefixo de `[PESSOA_10]` e produz `Ana Souza0` — que não parece defeito de
    programa, parece erro de digitação de quem escreveu o documento.
    """
    mapa = {f"[PESSOA_{i}]": f"Pessoa{i}" for i in range(1, 13)}
    texto = " ".join(f"[PESSOA_{i}]" for i in (1, 10, 2, 11, 12))
    assert mapa_reverso.reidratar(texto, mapa) == (
        "Pessoa1 Pessoa10 Pessoa2 Pessoa11 Pessoa12"
    )


def test_rotulo_com_cedilha_e_reconhecido():
    """`ENDEREÇO` tem cedilha: uma classe [A-Z_] o deixaria de fora em silêncio."""
    mapa = {"[ENDEREÇO_1]": "Rua Cassiano Correia, 4"}
    assert mapa_reverso.reidratar("Reside em [ENDEREÇO_1].", mapa) == (
        "Reside em Rua Cassiano Correia, 4."
    )


def test_rotulo_fora_do_mapa_fica_como_esta():
    """
    Um rótulo sem entrada é o caso de autos trocados, ou de mapa vencido e
    apagado. Deixá-lo visível é a única saída honesta: apagar fingiria que o
    trecho não existia, e adivinhar seria pior.
    """
    saida = mapa_reverso.reidratar("[PESSOA_1] e [PESSOA_9]", {"[PESSOA_1]": "Ana"})
    assert saida == "Ana e [PESSOA_9]"


def test_texto_sem_rotulo_atravessa_intacto():
    assert mapa_reverso.reidratar("Nada a substituir.", {"[PESSOA_1]": "Ana"}) == (
        "Nada a substituir."
    )
