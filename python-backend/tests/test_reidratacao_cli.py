"""
`--autos` e `reidratar` pela linha de comando.

Estes testes rodam a CLI em processo, com `PRESIDIO_NLP_MODE=spacy` (herdado do
conftest) e arquivos de texto puro — não carregam BERT nem OCR. O que medem é o
contrato da interface: que o mapa vai para o disco, que ele NÃO vai para o
stdout, e que o ciclo fecha.
"""

import json
import os
from pathlib import Path

import pytest

import cli
import mapa_reverso


@pytest.fixture
def cofre(tmp_path, monkeypatch):
    """
    Espelho da fixture de `test_mapa_reverso.py`. Aqui NÃO se neutraliza a
    checagem de montagem, e é de propósito: estes testes chamam a CLI inteira,
    que é o caminho real, e o `tmp_path` desta suíte cai sob `/`. Se um dia
    falharem por `noowners`, é sinal de que o temporário mudou de volume — e a
    resposta é a mesma fixture da outra suíte, não um remendo aqui.
    """
    monkeypatch.setenv("PRESIDIO_MAPA_CHAVE", str(tmp_path / "mapa.key"))
    monkeypatch.setenv("PRESIDIO_MAPA_DIR", str(tmp_path / "mapas"))
    return tmp_path


def _peca(pasta, nome, texto):
    caminho = pasta / nome
    caminho.write_text(texto, encoding="utf-8")
    return str(caminho)


def test_autos_grava_o_mapa_e_o_ciclo_fecha(cofre, capsys):
    peca = _peca(cofre, "inicial.txt", "O autor JOÃO DA SILVA ajuizou a ação.")
    assert cli.main(["anonimizar", peca, "--offline", "--autos", "5626981", "-o", "-"]) == 0

    saida = capsys.readouterr().out
    assert "[PESSOA_1]" in saida
    assert "JOÃO DA SILVA" not in saida

    mapa = mapa_reverso.ler("5626981")
    assert mapa == {"[PESSOA_1]": "JOÃO DA SILVA"}
    assert mapa_reverso.reidratar(saida, mapa).count("JOÃO DA SILVA") == 1


def test_o_mapa_nunca_aparece_no_stdout_nem_em_json(cofre, capsys):
    """
    O teste mais importante deste arquivo. `anonymize()` devolve `mapa_reverso`
    porque a CLI precisa dele para gravar; imprimi-lo desfaria, numa linha de
    log ou num pipe, o que o programa inteiro existe para fazer.

    O que se mede é a ausência do MAPA, e não a do nome. O nome real está sim
    na saída, dentro de `entities_found`, e isso é o contrato documentado do
    `-f json` ("json = com a lista de ocorrências"), travado desde a Task 7b em
    `test_formatar_json_nao_expoe_mapa_reverso_mas_preserva_o_resto`: a lista
    existe para AUDITAR o que foi mascarado, e auditoria sem o valor não audita
    nada. Quem não quer o valor real na saída usa o formato `text`, que é o
    padrão.

    Os dois são coisas diferentes: `entities_found` diz "achei este nome aqui";
    o mapa diz "[PESSOA_1] é este nome" — só o segundo desfaz a anonimização do
    documento inteiro.
    """
    peca = _peca(cofre, "inicial.txt", "O autor JOÃO DA SILVA ajuizou a ação.")
    cli.main(["anonimizar", peca, "--offline", "--autos", "5626981", "-f", "json", "-o", "-"])

    saida = capsys.readouterr().out
    assert "mapa_reverso" not in saida
    corpo = json.loads(saida)
    assert "mapa_reverso" not in corpo
    assert corpo["anonymized_text"] == "O autor [PESSOA_1] ajuizou a ação."

    # E o de-para não se remonta a partir do que sobrou: `entities_found` diz
    # onde o nome estava, não que rótulo ele virou.
    assert all("[PESSOA_1]" not in str(v) for v in corpo["entities_found"])


def test_campo_novo_no_motor_nao_escapa_pelo_json(cofre):
    """
    A direção do filtro, travada.

    A versão anterior de `_formatar` negava `mapa_reverso` pelo nome: conserta o
    campo conhecido e falha aberto no próximo. E não é hipótese — a Task 7
    acrescentou uma chave ao retorno do motor e ela escapou por duas saídas que
    ninguém tinha revisado. Com lista de permissão, quem acrescentar campo
    sensível ao motor tem de vir aqui escrever o nome dele para que saia.
    """
    resultado = {
        "anonymized_text": "O autor [PESSOA_1] ajuizou a ação.",
        "entities_found": [],
        "campo_sensivel_futuro": {"[PESSOA_1]": "JOÃO DA SILVA"},
    }
    corpo = json.loads(cli._formatar(resultado, "json"))
    assert "campo_sensivel_futuro" not in corpo
    assert corpo["anonymized_text"] == "O autor [PESSOA_1] ajuizou a ação."


def test_duas_pecas_dos_mesmos_autos_compartilham_a_numeracao(cofre, capsys):
    a = _peca(cofre, "inicial.txt", "ANA SOUZA propôs a ação.")
    b = _peca(cofre, "procuracao.txt", "BRUNO LIMA outorga poderes.")
    assert cli.main([
        "anonimizar", a, b, "--offline", "--autos", "5626981",
        "--output-dir", str(cofre / "saida"),
    ]) == 0

    assert mapa_reverso.ler("5626981") == {
        "[PESSOA_1]": "ANA SOUZA",
        "[PESSOA_2]": "BRUNO LIMA",
    }


def test_duas_invocacoes_nos_mesmos_autos_continuam_a_numeracao(cofre, capsys):
    """
    O caso que o `--autos` promete e que só a semeadura entrega: acrescentar peça
    dias depois é o uso normal de um processo.

    Sem semear, a segunda invocação daria `[PESSOA_1]` a Bruno — e a gravação
    recusaria por EtiquetaConflitante, porque aquele número já é da Ana.
    """
    a = _peca(cofre, "inicial.txt", "ANA SOUZA propôs a ação.")
    assert cli.main(["anonimizar", a, "--offline", "--autos", "5626981", "-o", "-"]) == 0

    b = _peca(cofre, "procuracao.txt", "BRUNO LIMA outorga poderes.")
    assert cli.main(["anonimizar", b, "--offline", "--autos", "5626981", "-o", "-"]) == 0

    saida = capsys.readouterr().out
    assert "[PESSOA_2]" in saida, "a segunda peça tem de continuar a numeração"

    assert mapa_reverso.ler("5626981") == {
        "[PESSOA_1]": "ANA SOUZA",
        "[PESSOA_2]": "BRUNO LIMA",
    }


def test_a_mesma_pessoa_em_invocacoes_diferentes_mantem_o_numero(cofre, capsys):
    a = _peca(cofre, "inicial.txt", "ANA SOUZA propôs a ação.")
    cli.main(["anonimizar", a, "--offline", "--autos", "5626981", "-o", "-"])
    capsys.readouterr()

    b = _peca(cofre, "depoimento.txt", "Ana Souza foi ouvida em audiência.")
    cli.main(["anonimizar", b, "--offline", "--autos", "5626981", "-o", "-"])

    assert "[PESSOA_1]" in capsys.readouterr().out
    assert mapa_reverso.ler("5626981") == {"[PESSOA_1]": "ANA SOUZA"}


def test_anonimizar_para_quando_o_mapa_dos_autos_nao_decifra(cofre, capsys):
    """
    A chave trocada tem de parar a anonimização ANTES de escrever arquivo, não
    depois. Seguir criaria um segundo mapa para os mesmos autos, e ficariam duas
    numerações incompatíveis sem nada dizendo qual explica qual peça.
    """
    from cryptography.fernet import Fernet

    a = _peca(cofre, "inicial.txt", "ANA SOUZA propôs a ação.")
    assert cli.main(["anonimizar", a, "--offline", "--autos", "5626981", "-o", "-"]) == 0
    capsys.readouterr()

    Path(os.environ["PRESIDIO_MAPA_CHAVE"]).write_bytes(Fernet.generate_key())

    b = _peca(cofre, "procuracao.txt", "BRUNO LIMA outorga poderes.")
    saida_b = cofre / "saida-b.txt"
    assert cli.main([
        "anonimizar", b, "--offline", "--autos", "5626981", "-o", str(saida_b)
    ]) == 1
    assert "ALARME" in capsys.readouterr().err
    assert not saida_b.exists(), "parou antes de escrever, como tem de ser"


def test_autos_com_mascara_sem_mapa_e_recusado(cofre, capsys):
    """
    `parcial` e `total` não produzem mapa. Aceitar `--autos` com elas gravaria
    um mapa vazio e prometeria uma reidratação que nunca funcionaria.
    """
    peca = _peca(cofre, "inicial.txt", "O autor JOÃO DA SILVA ajuizou.")
    assert cli.main([
        "anonimizar", peca, "--offline", "--autos", "x", "-m", "total", "-o", "-"
    ]) == 1
    assert "placeholder" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# reidratar
# ---------------------------------------------------------------------------


def test_reidratar_devolve_os_nomes(cofre, capsys):
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "João da Silva"})
    resposta = _peca(cofre, "resposta.txt", "Segundo a peça, [PESSOA_1] alega quitação.")
    assert cli.main(["reidratar", resposta, "--autos", "5626981", "-o", "-"]) == 0
    assert capsys.readouterr().out.strip() == (
        "Segundo a peça, João da Silva alega quitação."
    )


def test_reidratar_le_de_stdin(cofre, capsys, monkeypatch):
    import io
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "João da Silva"})
    monkeypatch.setattr("sys.stdin", io.StringIO("[PESSOA_1] compareceu."))
    assert cli.main(["reidratar", "--autos", "5626981", "-o", "-"]) == 0
    assert capsys.readouterr().out.strip() == "João da Silva compareceu."


def test_reidratar_recusa_arquivo_binario(cofre, capsys):
    """
    O engano natural é passar o PDF dos autos: o `anonimizar` aceita PDF, e nada
    na linha de comando sugere que este subcomando não aceita. Sem a recusa, sai
    um UnicodeDecodeError cru.
    """
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "João da Silva"})
    pdf = cofre / "autos.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    assert cli.main(["reidratar", str(pdf), "--autos", "5626981", "-o", "-"]) == 1
    erro = capsys.readouterr().err
    assert "não é texto" in erro
    assert "autos.pdf" in erro


def test_reidratar_recusa_texto_que_nao_e_utf8(cofre, capsys):
    """Extensão de texto com bytes latin-1 — sai de sistema judicial antigo."""
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "João da Silva"})
    ruim = cofre / "resposta.txt"
    ruim.write_bytes("[PESSOA_1] compareceu à audiência.".encode("latin-1"))
    assert cli.main(["reidratar", str(ruim), "--autos", "5626981", "-o", "-"]) == 1
    assert "não é UTF-8" in capsys.readouterr().err


def test_reidratar_sem_mapa_avisa_e_falha(cofre, capsys):
    """
    Sem mapa, devolver o texto com os rótulos e sair 0 seria o pior resultado:
    parece que funcionou. Autos errado e mapa vencido são os dois casos, e os
    dois merecem código de saída diferente de zero.
    """
    resposta = _peca(cofre, "resposta.txt", "[PESSOA_1] alega quitação.")
    assert cli.main(["reidratar", resposta, "--autos", "inexistente", "-o", "-"]) == 1
    assert "não há mapa" in capsys.readouterr().err


def test_reidratar_avisa_rotulo_sem_entrada(cofre, capsys):
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "João da Silva"})
    resposta = _peca(cofre, "resposta.txt", "[PESSOA_1] e [PESSOA_7] discordam.")
    assert cli.main(["reidratar", resposta, "--autos", "5626981", "-o", "-"]) == 0
    capturado = capsys.readouterr()
    assert "João da Silva e [PESSOA_7]" in capturado.out
    assert "[PESSOA_7]" in capturado.err
