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


# ---------------------------------------------------------------------------
# A chave e a falha fechada
#
# ## Por que quase todo teste daqui finge que o volume honra dono
#
# `_volume_honra_dono` lê o `mount` da máquina de verdade. Se os testes o
# deixassem real, eles passariam a depender de ONDE o pytest põe o `tmp_path` —
# nesta máquina cai sob `/`, que honra dono, e tudo passa. Numa máquina cujo
# temporário fique num volume `noowners`, ou num contêiner de integração
# contínua, os mesmos testes falhariam com `CifragemIndisponivel` reclamando de
# `noowners`: a mensagem certa para o ambiente e a errada para o que o teste
# queria medir, apontando o depurador para o lugar errado.
#
# Este fork pretende voltar ao upstream, onde roda na máquina de outra gente.
# Então: os testes que medem OUTRA coisa fixam a resposta em `True`, e os dois
# que medem a checagem em si a exercem de propósito.
# ---------------------------------------------------------------------------

import os
import stat

import pytest


@pytest.fixture
def volume_honra_dono(monkeypatch):
    """Isola os testes da configuração de montagem da máquina que os roda."""
    monkeypatch.setattr(mapa_reverso, "_volume_honra_dono", lambda _c: True)


def test_cria_a_chave_com_modo_0600(tmp_path, monkeypatch, volume_honra_dono):
    chave = tmp_path / "mapa.key"
    monkeypatch.setenv("PRESIDIO_MAPA_CHAVE", str(chave))
    primeira = mapa_reverso._chave()
    assert chave.exists()
    assert stat.S_IMODE(chave.stat().st_mode) == 0o600
    assert len(primeira) > 0


def test_reusa_a_chave_existente(tmp_path, monkeypatch, volume_honra_dono):
    """Recunhar a chave tornaria ilegível todo mapa já gravado."""
    chave = tmp_path / "mapa.key"
    monkeypatch.setenv("PRESIDIO_MAPA_CHAVE", str(chave))
    assert mapa_reverso._chave() == mapa_reverso._chave()


def test_recusa_chave_com_modo_frouxo(tmp_path, monkeypatch, volume_honra_dono):
    """
    Chave legível por outros não é chave. Corrigir o modo em silêncio seria
    pior: não há como saber quem já a leu, e o programa seguiria afirmando uma
    garantia que aquele arquivo não sustenta mais.
    """
    chave = tmp_path / "mapa.key"
    monkeypatch.setenv("PRESIDIO_MAPA_CHAVE", str(chave))
    mapa_reverso._chave()
    os.chmod(chave, 0o644)
    with pytest.raises(mapa_reverso.CifragemIndisponivel, match="0600"):
        mapa_reverso._chave()


def test_recusa_chave_em_volume_que_ignora_dono(tmp_path, monkeypatch):
    """Este exerce a checagem, então NÃO usa a fixture que a neutraliza."""
    chave = tmp_path / "mapa.key"
    monkeypatch.setenv("PRESIDIO_MAPA_CHAVE", str(chave))
    monkeypatch.setattr(mapa_reverso, "_volume_honra_dono", lambda _c: False)
    with pytest.raises(mapa_reverso.CifragemIndisponivel, match="noowners"):
        mapa_reverso._chave()
    assert not chave.exists(), "recusou, então não pode ter criado a chave"


def test_volume_honra_dono_reconhece_noowners():
    """
    A leitura vem do `mount`, não de um palpite pelo caminho. O volume externo
    desta máquina monta com noowners, e um `/Volumes/...` hardcoded como
    'inseguro' reprovaria um volume corretamente montado de outra pessoa.

    Recebe a tabela pronta, então não toca no sistema e vale em qualquer máquina.
    """
    montagens = {"/": "apfs, local, journaled", "/Volumes/X": "apfs, local, noowners"}
    assert mapa_reverso._analisar_montagens(montagens, "/Users/x/.config/k") is True
    assert mapa_reverso._analisar_montagens(montagens, "/Volumes/X/k") is False


def test_ponto_de_montagem_com_parentese_no_nome_casa_por_prefixo():
    """
    Mede o CASAMENTO DE PREFIXO sobre um ponto de montagem cujo nome tem
    parêntese — `/Volumes/Backup (2024)` é nome legítimo.

    A docstring anterior afirmava que este teste exercia a separação do ponto e
    das flags pelo último ` (`, e não era verdade: a tabela chega pronta, então o
    `rpartition` do parser nunca roda aqui. Quem exerce o parser é
    `test_parser_do_mount_*`, adiante — e ele não existia, de modo que a garantia
    "vem do `mount`, não de um palpite pelo caminho" tinha cobertura zero
    enquanto um teste afirmava na docstring que a cobria.
    """
    montagens = {"/": "apfs, local", "/Volumes/Backup (2024)": "apfs, noowners"}
    assert mapa_reverso._analisar_montagens(montagens, "/Volumes/Backup (2024)/k") is False


def test_caminho_sem_montagem_correspondente_recusa():
    """
    Não saber em que volume o caminho está não é saber que ele é seguro. Numa
    tabela real `/` prefixa tudo e este ramo não acontece — ele é a política da
    função para tabela parcial, e o que impede uma falha ABERTA no meio de um
    módulo que fecha em todo o resto.
    """
    montagens = {"/Volumes/X": "apfs, local"}
    assert mapa_reverso._analisar_montagens(montagens, "/Users/x/.config/k") is False


# ---------------------------------------------------------------------------
# Gravação, leitura e prazo
# ---------------------------------------------------------------------------


from pathlib import Path


@pytest.fixture
def cofre(tmp_path, monkeypatch, volume_honra_dono):
    """
    Chave e mapas em tmp_path — nunca no cofre real do usuário.

    Recebe `volume_honra_dono` pela política declarada no bloco da chave, acima:
    teste que mede OUTRA coisa fixa a checagem de montagem em `True`. Sem isso,
    todos os testes daqui passariam nesta máquina só porque o `tmp_path` cai sob
    `/`, e falhariam de uma vez numa CI cujo temporário esteja em volume
    `noowners` — com `CifragemIndisponivel` reclamando de `noowners`, que é a
    mensagem certa para o ambiente e errada para o que o teste mede.
    """
    monkeypatch.setenv("PRESIDIO_MAPA_CHAVE", str(tmp_path / "mapa.key"))
    monkeypatch.setenv("PRESIDIO_MAPA_DIR", str(tmp_path / "mapas"))
    return tmp_path


def test_grava_e_le_o_mesmo_mapa(cofre):
    mapa = {"[PESSOA_1]": "Ana Souza", "[CPF_1]": "529.982.247-25"}
    mapa_reverso.gravar("5626981", mapa)
    assert mapa_reverso.ler("5626981") == mapa


def test_o_arquivo_gravado_nao_contem_o_valor_em_claro(cofre):
    """O teste que importa: se este passar por acidente, a cifragem não rodou."""
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    bruto = (cofre / "mapas" / "5626981.mapa").read_bytes()
    assert b"Ana Souza" not in bruto
    assert b"PESSOA_1" not in bruto


def test_gravar_de_novo_funde_em_vez_de_substituir(cofre):
    """
    Cada peça dos autos chega numa execução. Substituir perderia o mapa da peça
    anterior e a reidratação sairia parcial — pior que falhar, porque parece
    completa.
    """
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    mapa_reverso.gravar("5626981", {"[PESSOA_2]": "Bruno Lima"})
    assert mapa_reverso.ler("5626981") == {
        "[PESSOA_1]": "Ana Souza",
        "[PESSOA_2]": "Bruno Lima",
    }


def test_gravar_nao_sobrescreve_mapa_que_nao_decifra(cofre):
    """
    Gravar em cima apagaria o de-para de tudo que já foi anonimizado nestes
    autos, e a causa da ilegibilidade pode ser benigna e reversível (a chave
    errada na variável de ambiente, o arquivo vindo de outra máquina).
    """
    from cryptography.fernet import Fernet

    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    antes = (cofre / "mapas" / "5626981.mapa").read_bytes()
    Path(os.environ["PRESIDIO_MAPA_CHAVE"]).write_bytes(Fernet.generate_key())

    with pytest.raises(mapa_reverso.MapaIlegivel):
        mapa_reverso.gravar("5626981", {"[PESSOA_2]": "Bruno Lima"})
    assert (cofre / "mapas" / "5626981.mapa").read_bytes() == antes, (
        "recusou, então o arquivo anterior tem de estar byte a byte intacto"
    )


def test_ler_autos_inexistente_devolve_vazio(cofre):
    assert mapa_reverso.ler("nao-existe") == {}


def test_mapa_que_nao_decifra_levanta_alarme_em_vez_de_devolver_vazio(cofre):
    """
    A distinção que esta exceção preserva. Foi medida na Task 9: `Fernet` aceita
    qualquer chave bem-formada de 44 bytes e só falha no `decrypt`, com
    `InvalidToken` sem argumento nenhum — o mesmo evento de um mapa adulterado.

    Devolver `{}` aqui faria a reidratação entregar o texto com os rótulos em
    claro e sem mensagem, e quem lê concluiria "o prazo venceu". São coisas
    muito diferentes e merecem reações muito diferentes.
    """
    from cryptography.fernet import Fernet

    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})

    # Troca a chave por OUTRA bem-formada — não corrompe, substitui.
    Path(os.environ["PRESIDIO_MAPA_CHAVE"]).write_bytes(Fernet.generate_key())

    with pytest.raises(mapa_reverso.MapaIlegivel, match="5626981"):
        mapa_reverso.ler("5626981")


def test_mapa_ilegivel_nao_e_apagado(cofre):
    """
    Apagar seria irreversível e a causa pode ser benigna (a chave recriada de
    propósito). Quem decide é a pessoa, com o arquivo ainda na mão.
    """
    from cryptography.fernet import Fernet

    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    alvo = cofre / "mapas" / "5626981.mapa"
    Path(os.environ["PRESIDIO_MAPA_CHAVE"]).write_bytes(Fernet.generate_key())

    with pytest.raises(mapa_reverso.MapaIlegivel):
        mapa_reverso.ler("5626981")
    assert alvo.exists(), "mapa ilegível não pode ser apagado pela leitura"


def test_mapa_vencido_e_apagado_e_nao_lido(cofre):
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    alvo = cofre / "mapas" / "5626981.mapa"
    antigo = alvo.stat().st_mtime - (8 * 86400)
    os.utime(alvo, (antigo, antigo))
    assert mapa_reverso.ler("5626981") == {}
    assert not alvo.exists(), "vencido tem de ser apagado, não só ignorado"


def test_prazo_configuravel_por_ambiente(cofre, monkeypatch):
    monkeypatch.setenv("PRESIDIO_MAPA_PRAZO_DIAS", "30")
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    alvo = cofre / "mapas" / "5626981.mapa"
    antigo = alvo.stat().st_mtime - (8 * 86400)
    os.utime(alvo, (antigo, antigo))
    assert mapa_reverso.ler("5626981") == {"[PESSOA_1]": "Ana Souza"}


def test_esquecer_apaga(cofre):
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    assert mapa_reverso.esquecer("5626981") is True
    assert mapa_reverso.ler("5626981") == {}
    assert mapa_reverso.esquecer("5626981") is False


def test_etiqueta_conflitante_e_recusada_em_vez_de_sobrescrita(cofre):
    """
    O defeito que esta recusa existe para impedir, demonstrado antes de existir:

        segunda:  anonimizar inicial.pdf    --autos X  ->  [PESSOA_1] = Ana
        quarta:   anonimizar procuracao.pdf --autos X  ->  [PESSOA_1] = Bruno
        fusão sem recusa: {'[PESSOA_1]': 'Bruno Lima'}   <- a Ana desapareceu

    Cada invocação da CLI é um processo novo, com Mascarador novo, numerando do
    1. Sem recusa, reidratar a resposta sobre a peça de segunda escreveria
    "Bruno Lima" onde estava a Ana — com confiança, num texto bem formado.
    """
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    with pytest.raises(mapa_reverso.EtiquetaConflitante, match="PESSOA_1"):
        mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Bruno Lima"})
    assert mapa_reverso.ler("5626981") == {"[PESSOA_1]": "Ana Souza"}, (
        "recusou, então o mapa anterior tem de estar intacto"
    )


def test_gravar_a_mesma_etiqueta_com_o_mesmo_valor_nao_e_conflito(cofre):
    """Reprocessar a mesma peça é idempotente, não erro."""
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza", "[CPF_1]": "529.982.247-25"})
    assert mapa_reverso.ler("5626981") == {
        "[PESSOA_1]": "Ana Souza",
        "[CPF_1]": "529.982.247-25",
    }


@pytest.mark.parametrize("ruim", ["../fuga", "a/b", "", ".", "../FUGA"])
def test_nome_de_autos_que_escaparia_do_diretorio_e_recusado(cofre, ruim):
    """
    O nome dos autos vem da linha de comando e vira nome de arquivo. Sem
    validação, `--autos ../../algo` grava fora do diretório de mapas.

    `../FUGA` está aqui por causa da ORDEM: a régua roda antes do `casefold()`,
    e nada travava isso — um revisor trocou `_caminho` por uma versão que dobra
    a caixa primeiro e os 50 testes passaram. Dobrando antes, a mensagem citaria
    `'../fuga'` para quem digitou `../FUGA`, e a pessoa procuraria no terminal um
    nome que não escreveu. Daí o assert sobre a grafia, e não só sobre o tipo do
    erro.
    """
    with pytest.raises(ValueError, match="autos") as erro:
        mapa_reverso.gravar(ruim, {"[PESSOA_1]": "Ana"})
    assert ruim in str(erro.value)


# ---------------------------------------------------------------------------
# Os buracos da rodada de revisão
# ---------------------------------------------------------------------------

import subprocess


def test_parser_do_mount_le_ponto_e_flags(monkeypatch):
    """
    O parser do `mount` é onde repousa a garantia "vem do `mount`, não de um
    palpite pelo caminho" — e ele não tinha teste nenhum.

    A saída é fabricada, então não depende de como ESTA máquina está montada: é
    a mesma razão pela qual `_analisar_montagens` recebe a tabela pronta. A
    terceira linha tem parêntese no nome do ponto, que é o caso que obriga o
    `rpartition(" (")` a separar pelo ÚLTIMO ` (` em vez do primeiro.
    """
    saida = (
        "/dev/disk3s5 on / (apfs, local, journaled, nobrowse)\n"
        "/dev/disk4s1 on /Volumes/SSD (apfs, local, noowners)\n"
        "/dev/disk5s1 on /Volumes/Backup (2024) (apfs, local, noowners)\n"
        "map -hosts on /net (autofs, nosuid, automounted)\n"
        "linha sem forma de montagem que deve ser ignorada\n"
    )

    def falso_run(*_a, **_k):
        return subprocess.CompletedProcess(["/sbin/mount"], 0, stdout=saida, stderr="")

    monkeypatch.setattr(mapa_reverso.subprocess, "run", falso_run)

    # O cache é por processo, e é o único teste da suíte que o popula. Limpa
    # ANTES (para não ler o que outra corrida deixou) e DEPOIS, num `finally`
    # (para a tabela fabricada não vazar para quem vier a seguir). O `monkeypatch`
    # desfaz o `subprocess.run`, mas não tem como desfazer um `lru_cache` — e
    # cache que sobrevive entre testes é a fonte clássica do teste que passa
    # sozinho e falha em conjunto.
    mapa_reverso._tabela_de_montagens.cache_clear()
    try:
        tabela = mapa_reverso._tabela_de_montagens()
        _conferir_tabela(tabela)
    finally:
        mapa_reverso._tabela_de_montagens.cache_clear()


def _conferir_tabela(tabela):
    assert tabela["/"] == "apfs, local, journaled, nobrowse"
    assert tabela["/Volumes/SSD"] == "apfs, local, noowners"
    assert tabela["/Volumes/Backup (2024)"] == "apfs, local, noowners", (
        "o parêntese do NOME não pode ser confundido com o que abre as flags"
    )
    assert "linha sem forma de montagem que deve ser ignorada" not in tabela

    # E a tabela lida do `mount` responde a pergunta que interessa.
    assert mapa_reverso._analisar_montagens(tabela, "/Users/x/.config/k") is True
    assert mapa_reverso._analisar_montagens(tabela, "/Volumes/SSD/k") is False
    assert mapa_reverso._analisar_montagens(tabela, "/Volumes/Backup (2024)/k") is False


def test_a_chave_sai_0600_mesmo_com_umask_que_tira_bits(tmp_path, volume_honra_dono):
    """
    O `0600` do `os.open` é MASCARADO pelo umask, e o comentário do módulo
    afirmava o contrário com apoio numa medição que não se sustentava (o
    `PermissionError` observado vinha do `mkdir` do diretório dentro de um
    intermediário sem escrita, não do `os.open`).

    Com o diretório da chave JÁ existente — o estado normal depois da primeira
    execução — `umask 0o200` deixava a chave em `0400`. E o desfecho era o pior
    do módulo sem atacante nenhum: o primeiro `gravar()` cifrava um mapa com
    aquela chave, e toda chamada seguinte recusava por modo diferente de 0600.

    Não usa `monkeypatch.setenv` porque o umask é estado de processo e precisa
    ser restaurado na mesma função que o mexeu.
    """
    chave = tmp_path / "existente" / "mapa.key"
    chave.parent.mkdir()  # criado ANTES do umask: o ramo que o bug alcançava
    anterior_env = os.environ.get("PRESIDIO_MAPA_CHAVE")
    anterior_umask = os.umask(0o200)
    try:
        os.environ["PRESIDIO_MAPA_CHAVE"] = str(chave)
        mapa_reverso._chave()
        assert stat.S_IMODE(chave.stat().st_mode) == 0o600
    finally:
        os.umask(anterior_umask)
        if anterior_env is None:
            os.environ.pop("PRESIDIO_MAPA_CHAVE", None)
        else:
            os.environ["PRESIDIO_MAPA_CHAVE"] = anterior_env


def test_symlink_pendurado_no_caminho_da_chave_e_explicado(tmp_path, monkeypatch, volume_honra_dono):
    """
    `Path.exists()` segue o symlink e diz `False` para link pendurado, então o
    ramo de criação é alcançável; o `O_EXCL` se recusa a seguir o link e devolve
    `FileExistsError`. Era o único desfecho sem explicação num módulo em que toda
    recusa é explicada.
    """
    chave = tmp_path / "mapa.key"
    chave.symlink_to(tmp_path / "alvo-que-nao-existe")
    assert not chave.exists(), "link pendurado se diz ausente — é a premissa do teste"
    monkeypatch.setenv("PRESIDIO_MAPA_CHAVE", str(chave))

    with pytest.raises(mapa_reverso.CifragemIndisponivel, match="symlink"):
        mapa_reverso._chave()


def test_o_parcial_nao_fica_para_tras_quando_a_troca_falha(cofre, monkeypatch):
    """
    O `.parcial` é o de-para COMPLETO e fundido, cifrado — quem tem a chave lê
    tudo. Ficando para trás, era a única coisa deste módulo fora do alcance do
    prazo de guarda e do `esquecer()`, que olham só o `<autos>.mapa`. Prazo que
    deixa resíduo não é prazo.
    """
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    parcial = cofre / "mapas" / "5626981.mapa.parcial"

    # A falha é ligada e desligada por bandeira, em vez de `monkeypatch.undo()`:
    # o `undo` desfaz TUDO o que aquele `monkeypatch` fez, e a fixture `cofre`
    # usa o mesmo objeto — desfazendo também o `setenv` de PRESIDIO_MAPA_DIR.
    # A leitura seguinte iria para o diretório real do usuário e devolveria `{}`,
    # o que se lê como "o mapa anterior foi perdido" quando o que houve foi o
    # teste perder o isolamento.
    real = mapa_reverso.os.replace
    falhar = {"agora": True}

    def replace_que_falha(*a, **k):
        if falhar["agora"]:
            raise OSError(28, "No space left on device")
        return real(*a, **k)

    monkeypatch.setattr(mapa_reverso.os, "replace", replace_que_falha)
    with pytest.raises(OSError):
        mapa_reverso.gravar("5626981", {"[PESSOA_2]": "Bruno Lima"})

    assert not parcial.exists(), "a troca falhou, então o temporário não pode ficar"

    falhar["agora"] = False
    assert mapa_reverso.ler("5626981") == {"[PESSOA_1]": "Ana Souza"}, (
        "e o mapa anterior segue intacto — é para isso que a troca é atômica"
    )


def test_esquecer_apaga_o_parcial_tambem(cofre):
    """
    Quem manda esquecer pede que o de-para saia do disco. Dizer `True` com um
    `.parcial` ainda lá afirmaria um expurgo que não aconteceu.
    """
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    parcial = cofre / "mapas" / "5626981.mapa.parcial"
    parcial.write_bytes(b"resto de uma troca interrompida")

    assert mapa_reverso.esquecer("5626981") is True
    assert not parcial.exists()

    # E um `.parcial` órfão, sem mapa definitivo, ainda conta como "havia algo".
    parcial.write_bytes(b"orfao")
    assert mapa_reverso.esquecer("5626981") is True
    assert not parcial.exists()


def test_o_parcial_orfao_vence_pelo_mesmo_prazo(cofre):
    """
    Morto o processo entre a escrita e a troca (SIGKILL não roda `except`), sobra
    um `.parcial` sem mapa definitivo. A partir daí toda leitura devolve `{}` na
    primeira linha e nunca mais olharia para ele — ficaria no disco para sempre.
    """
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    parcial = cofre / "mapas" / "5626981.mapa.parcial"
    parcial.write_bytes(b"orfao cifrado")
    (cofre / "mapas" / "5626981.mapa").unlink()

    antigo = parcial.stat().st_mtime - (8 * 86400)
    os.utime(parcial, (antigo, antigo))

    assert mapa_reverso.ler("5626981") == {}
    assert not parcial.exists(), "vencido é apagado, mesmo sendo o temporário"


def test_a_caixa_do_nome_dos_autos_e_dobrada(cofre):
    """
    `--autos abc` e `--autos ABC` apontam para o MESMO arquivo no APFS desta
    máquina e para arquivos DIFERENTES no ext4. Sem dobrar, a mesma sequência de
    comandos produz um mapa no macOS e dois no Linux — comportamento contratado
    por teste dependendo de como o sistema foi formatado, a mesma armadilha do
    `noowners`. Este fork pretende voltar ao upstream.
    """
    mapa_reverso.gravar("Proc-ABC", {"[PESSOA_1]": "Ana Souza"})
    assert mapa_reverso.ler("proc-abc") == {"[PESSOA_1]": "Ana Souza"}
    assert mapa_reverso.ler("PROC-ABC") == {"[PESSOA_1]": "Ana Souza"}

    arquivos = sorted(p.name for p in (cofre / "mapas").iterdir())
    assert arquivos == ["proc-abc.mapa"], (
        "um arquivo só, com o nome dobrado — em qualquer sistema de arquivos"
    )

    # E a fusão alcança o mesmo mapa, em vez de abrir um segundo.
    mapa_reverso.gravar("PROC-abc", {"[PESSOA_2]": "Bruno Lima"})
    assert mapa_reverso.ler("proc-ABC") == {
        "[PESSOA_1]": "Ana Souza",
        "[PESSOA_2]": "Bruno Lima",
    }


# ---------------------------------------------------------------------------
# Semeadura: a numeração continua entre invocações
# ---------------------------------------------------------------------------


def test_semear_continua_a_numeracao_em_vez_de_recomecar():
    """
    O caso que motiva o método. A segunda invocação sobre os mesmos autos tem de
    dar `[PESSOA_2]` a quem chegou depois, não `[PESSOA_1]` de novo.
    """
    primeira = Mascarador("placeholder")
    assert primeira.mascarar("PERSON", "Ana Souza") == "[PESSOA_1]"

    segunda = Mascarador("placeholder")
    segunda.semear(primeira.mapa())
    assert segunda.mascarar("PERSON", "Bruno Lima") == "[PESSOA_2]"
    assert segunda.mapa() == {"[PESSOA_1]": "Ana Souza", "[PESSOA_2]": "Bruno Lima"}


def test_semear_reconhece_quem_ja_tinha_numero():
    """
    A mesma pessoa numa peça nova recebe o número que já era dela — é isso que
    faz o modelo entender que a Ana da inicial é a Ana da procuração.
    """
    primeira = Mascarador("placeholder")
    primeira.mascarar("PERSON", "Ana Souza")

    segunda = Mascarador("placeholder")
    segunda.semear(primeira.mapa())
    assert segunda.mascarar("PERSON", "ANA SOUZA") == "[PESSOA_1]"


def test_semear_com_buraco_na_sequencia_nao_reusa_numero():
    """
    `remascarar()` renumera do zero ao liberar um falso positivo, e um mapa
    gravado antes disso pode chegar com buraco. Numerar por `len()+1` reusaria um
    número já tomado e faria duas pessoas virarem a mesma. O próximo é
    `max(...)+1`.
    """
    m = Mascarador("placeholder")
    m.semear({"[PESSOA_1]": "Ana Souza", "[PESSOA_3]": "Carla Dias"})
    assert m.mascarar("PERSON", "Bruno Lima") == "[PESSOA_4]"


def test_semear_separa_rotulos():
    m = Mascarador("placeholder")
    m.semear({"[PESSOA_1]": "Ana Souza", "[CPF_1]": "529.982.247-25"})
    assert m.mascarar("PERSON", "Bruno Lima") == "[PESSOA_2]"
    assert m.mascarar("CPF_BR", "111.444.777-35") == "[CPF_2]"


def test_semear_nao_conta_para_o_resumo():
    """
    `resumo()` vira `valores_distintos` e diz o que ESTA execução encontrou.
    Semear não é encontrar: contar o que veio do disco inflaria o número que a
    interface mostra sobre o documento que acabou de ser lido.
    """
    m = Mascarador("placeholder")
    m.semear({"[PESSOA_1]": "Ana Souza"})
    assert m.resumo() == {}
    m.mascarar("PERSON", "Bruno Lima")
    assert m.resumo() == {"PERSON": 1}


def test_a_forma_da_etiqueta_nao_aceita_simbolo():
    """
    `×` (U+00D7) fica no meio do bloco Latin-1 maiúsculo e não é letra. A irmã em
    TypeScript o exclui por usar `\\p{Lu}`; o intervalo partido `À-Ö`/`Ø-Þ` faz o
    Python concordar. Nenhum rótulo real usaria símbolo — o teste existe para as
    duas camadas não divergirem em rigor sem ninguém notar.
    """
    from mask_config import RE_ETIQUETA

    assert RE_ETIQUETA.fullmatch("[ENDEREÇO_1]") is not None
    assert RE_ETIQUETA.fullmatch("[PESSOA_12]") is not None
    assert RE_ETIQUETA.fullmatch("[ORGANIZATION_1]") is not None
    assert RE_ETIQUETA.fullmatch("[×_1]") is None
    assert RE_ETIQUETA.fullmatch("[pessoa_1]") is None
    assert RE_ETIQUETA.fullmatch("[PESSOA_]") is None
    assert RE_ETIQUETA.fullmatch("[PESSOA_1") is None


def test_semear_recusa_etiqueta_fora_de_forma():
    m = Mascarador("placeholder")
    with pytest.raises(ValueError, match="etiqueta"):
        m.semear({"PESSOA_1": "Ana Souza"})


def test_semear_recusa_dois_numeros_para_o_mesmo_valor():
    """
    Mapa em que a mesma pessoa aparece com dois números é mapa corrompido, e
    seguir com ele escolheria um dos dois em silêncio.
    """
    m = Mascarador("placeholder")
    with pytest.raises(ValueError, match="dois números"):
        m.semear({"[PESSOA_1]": "Ana Souza", "[PESSOA_2]": "ana souza"})


def test_semear_em_politica_sem_placeholder_e_recusado():
    """Semear um Mascarador que não numera é pedido sem sentido — e silencioso."""
    for politica in ("parcial", "total"):
        m = Mascarador(politica)
        with pytest.raises(ValueError, match="placeholder"):
            m.semear({"[PESSOA_1]": "Ana Souza"})


def test_a_forma_da_etiqueta_repete_a_estrutura_da_irma_em_typescript():
    """
    `electron/pseudonimos.ts` usa `/\\[(\\p{Lu}+(?:_\\p{Lu}+)*)_(\\d+)\\]/gu` — a
    estrutura é `PALAVRA(_PALAVRA)*`, não um punhado de maiúsculas e sublinhados
    em qualquer ordem. Um `[A-Z_]+` solto aceitaria os três casos abaixo, e as
    duas camadas discordariam sobre um mesmo texto sem ninguém notar: o Electron
    reidrataria um trecho que o Python deixaria mascarado, ou o contrário.
    """
    from mask_config import RE_ETIQUETA

    assert RE_ETIQUETA.fullmatch("[DATE_TIME_1]") is not None, "sublinhado INTERNO é real"
    assert RE_ETIQUETA.fullmatch("[_PESSOA_1]") is None
    assert RE_ETIQUETA.fullmatch("[PESSOA__1]") is None
    assert RE_ETIQUETA.fullmatch("[PESSOA_1]_") is None


def test_todo_rotulo_que_o_produto_gera_casa_com_a_forma():
    """
    A varredura que sustenta o comentário do `RE_ETIQUETA`, sem carregar motor:
    `ROTULO_ENTIDADE` é a fonte dos rótulos traduzidos, e o fallback
    `rotulo == entity_type` responde pelo resto. Conferido uma vez contra o
    motor de verdade (27 tipos, 25 rótulos, todos casam); daqui em diante quem
    acrescentar rótulo que não case quebra aqui, e não em produção com um
    documento meio reidratado na tela.
    """
    from mask_config import ROTULO_ENTIDADE, RE_ETIQUETA

    fallbacks = ["ORGANIZATION", "DATE_TIME", "LAW", "IP_ADDRESS", "MEDICAL_LICENSE"]
    for rotulo in list(ROTULO_ENTIDADE.values()) + fallbacks:
        etiqueta = f"[{rotulo}_1]"
        achado = RE_ETIQUETA.fullmatch(etiqueta)
        assert achado is not None, f"{etiqueta} não casa com RE_ETIQUETA"
        assert achado.group(1) == rotulo
        assert achado.group(2) == "1"


# ---------------------------------------------------------------------------
# Onde os mapas moram
# ---------------------------------------------------------------------------


def test_o_diretorio_de_mapas_segue_o_volume_de_peso(monkeypatch, tmp_path):
    """
    `TECJUSTICA_PESO` é a variável que o `setup-macos.sh` e o shim já leem, e é
    ela que decide onde o venv e os modelos vão parar. O setup chega a criar
    `$TECJUSTICA_PESO/mapas`.

    Sem isto, quem apontasse a variável para outro volume teria o diretório
    criado num lugar e a gravação tentando outro — o literal desta máquina, que
    naquela pode nem existir. E a falha chegaria DEPOIS da anonimização, quando
    o mapa é a única coisa que falta para o ciclo fechar.
    """
    monkeypatch.delenv("PRESIDIO_MAPA_DIR", raising=False)
    monkeypatch.setenv("TECJUSTICA_PESO", str(tmp_path / "peso"))
    assert mapa_reverso._dir_mapas() == tmp_path / "peso" / "mapas"


def test_presidio_mapa_dir_tem_precedencia_sobre_o_volume_de_peso(monkeypatch, tmp_path):
    """A variável específica manda na genérica — é a mais explícita das duas."""
    monkeypatch.setenv("TECJUSTICA_PESO", str(tmp_path / "peso"))
    monkeypatch.setenv("PRESIDIO_MAPA_DIR", str(tmp_path / "escolhido"))
    assert mapa_reverso._dir_mapas() == tmp_path / "escolhido"


def test_sem_nenhuma_das_duas_o_default_nao_muda(monkeypatch):
    """O comportamento de quem não define nada continua o mesmo."""
    monkeypatch.delenv("PRESIDIO_MAPA_DIR", raising=False)
    monkeypatch.delenv("TECJUSTICA_PESO", raising=False)
    assert mapa_reverso._dir_mapas() == Path(mapa_reverso.PESO_PADRAO) / "mapas"
