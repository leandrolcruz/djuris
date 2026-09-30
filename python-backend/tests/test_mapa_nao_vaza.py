"""
As duas promessas que só um teste segura.

**O MCP não expõe reidratar.** É a regra de ouro do desenho, e é frágil do jeito
pior: expor a ferramenta parece uma conveniência óbvia para quem chegar depois,
o código funcionaria perfeitamente, e nenhum teste reclamaria. O efeito é que os
nomes reais voltam ao contexto do modelo — a nuvem — e o programa passa a
desfazer o que existe para fazer.

**As rotas HTTP não devolvem o mapa.** `anonymize()` passou a incluir
`mapa_reverso` no dicionário de retorno. Uma rota que serialize o resultado
inteiro entrega o de-para a qualquer cliente pareado, inclusive uma extensão de
navegador.
"""

import mcp_server


def test_mcp_declara_exatamente_quatro_ferramentas():
    assert len(mcp_server.FERRAMENTAS) == 4


def test_nenhuma_ferramenta_de_mcp_reidrata():
    nomes = " ".join(str(chave) for chave in mcp_server.FERRAMENTAS).lower()
    assert "reidrat" not in nomes
    assert not hasattr(mcp_server, "ferramenta_reidratar")


def test_o_modulo_de_mcp_nao_importa_mapa_reverso():
    """
    Import é o começo do caminho. Não importando, a ferramenta não pode nascer
    por descuido — e o dia em que alguém a importar, este teste fala.
    """
    from pathlib import Path
    fonte = Path(mcp_server.__file__).read_text(encoding="utf-8")
    assert "mapa_reverso" not in fonte


def test_rotas_de_anonimizacao_nao_devolvem_o_mapa():
    """
    O que se mede é a ausência do MAPA — o de-para que desfaz a anonimização do
    documento inteiro. O nome real continua em `entities_found`, pelo mesmo
    contrato do `-f json` da CLI: a lista existe para auditar o que foi
    mascarado, e é anterior a toda esta rodada (o `EntityFound` do `server.py`
    sempre teve o campo `text`). Confundir os dois faria este teste reprovar uma
    escolha de desenho que não está em discussão aqui.

    A defesa da rota é estrutural, não um `pop`: `response_model` do Pydantic é
    lista de permissão, e campo novo no motor não sai por ele sem alguém
    escrever o nome. É o mesmo padrão que o `_formatar` da CLI adotou na Task 12.
    """
    import os

    from fastapi.testclient import TestClient

    import server
    from engine import get_engine

    # O token vem do conftest, que o define antes de qualquer import de
    # `server` — ler do ambiente é o padrão desta suíte (`test_api_v1.py:23`),
    # e importar `conftest` como módulo não funciona.
    token = os.environ["PRESIDIO_TOKEN"]

    # Sem isto a rota devolve 500 com "Engine não inicializado", e o teste
    # passaria por não achar "mapa_reverso" numa mensagem de erro — medindo o
    # motor desligado em vez do vazamento.
    get_engine().initialize()

    cliente = TestClient(server.app)
    resposta = cliente.post(
        "/anonymize",
        json={"text": "O autor JOÃO DA SILVA ajuizou.", "entities": []},
        headers={"X-Presidio-Token": token},
    )
    assert resposta.status_code == 200, resposta.text
    assert "mapa_reverso" not in resposta.text

    corpo = resposta.json()
    assert "mapa_reverso" not in corpo
    assert "[PESSOA_1]" in corpo["anonymized_text"]
    # E o de-para não se remonta do que sobrou: a ocorrência diz onde o nome
    # estava, não que rótulo ele virou.
    assert all("PESSOA_1" not in str(v) for v in corpo["entities_found"])
