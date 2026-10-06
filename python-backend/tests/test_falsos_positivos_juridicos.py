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


# --- 4. Data processual não é dado pessoal ---------------------------------


def test_datas_processuais_sobrevivem(engine):
    """
    A cronologia é o esqueleto do processo. Mascarar "ajuizada em 08/05/2026"
    não protege ninguém — a data de distribuição é pública — e tira do modelo
    do outro lado a capacidade de contar prazo, que costuma ser exatamente o
    que se quer perguntar a ele.
    """
    texto = "A ação foi ajuizada em 08/05/2026 e a intimação expedida em 10/07/2026."
    saida = anonimizar(engine, texto)
    assert "08/05/2026" in saida
    assert "10/07/2026" in saida


@pytest.mark.parametrize(
    "texto",
    [
        "nascido em 12/03/1985, portador do RG 1234567",
        "data de nascimento: 12/03/1985",
        "nascida aos 12/03/1985",
    ],
)
def test_data_de_nascimento_ROTULADA_continua_mascarada(engine, texto):
    """
    O contrapeso. `DATE_OF_BIRTH` tem recognizer próprio, com as palavras de
    qualificação como contexto, e ele não depende do `DATE_TIME` genérico.
    """
    assert "12/03/1985" not in anonimizar(engine, texto)


def test_LIMITE_CONHECIDO_data_de_nascimento_sem_rotulo_escapa(engine):
    """
    O limite que esta decisão aceita, escrito para quem vier depois não
    descobri-lo num documento enviado.

    Na qualificação típica de petição — "FULANO, brasileiro, solteiro,
    12/03/1985, CPF…" — a data vem SEM a palavra "nascido". Sem ela o
    recognizer de nascimento não dispara, e com `DATE_TIME` fora do padrão a
    data sai em claro.

    Por que a decisão ainda assim é essa: o nome ao lado JÁ está mascarado, e
    uma data sozinha, sem nome, sem CPF, sem RG e sem endereço — todos
    mascarados — tem pouco poder de reidentificar. Quem precisar do rigor
    antigo pede `-e` com DATE_TIME junto.

    Se um dia o recognizer de nascimento passar a cobrir este caso, este teste
    falha — e é para falhar: aí o limite deixou de existir e o texto acima
    precisa sair daqui.
    """
    texto = "JOÃO DA SILVA, brasileiro, solteiro, 12/03/1985, residente nesta comarca"
    saida = anonimizar(engine, texto)
    assert "[PESSOA_1]" in saida, "o nome continua mascarado, que é o que importa"
    assert "12/03/1985" in saida, (
        "limite conhecido: data de nascimento sem rótulo sai em claro"
    )


def test_quem_quiser_as_datas_mascaradas_pede(engine):
    texto = "A ação foi ajuizada em 08/05/2026."
    assert "[DATA" in anonimizar(engine, texto, entities=["DATE_TIME"])


# --- 5. Ruído institucional: medido em quatro processos reais --------------
#
# Auditoria sobre o acervo do gabinete, 06/10/2026: nenhum dado pessoal vazou
# nos quatro documentos, mas três tipos enchiam o texto de tarja sem proteger
# ninguém — e os números vêm da contagem, não de impressão:
#
#   LOCATION      125 ocorrências, 107 delas a palavra "JATAÍ" (a comarca)
#   URL           119 ocorrências,  82 delas https://projudi.tjgo.jus.br/…
#   ORGANIZATION   37 ocorrências,  CNJ (18×), STJ, União
#
# Comarca, tribunal e endereço do sistema estão no cabeçalho de toda peça e são
# públicos. Mascará-los tira do modelo a competência territorial e o próprio
# nome do juízo, sem esconder parte alguma.


def test_a_comarca_nao_e_mascarada(engine):
    texto = "AO JUÍZO DA 2ª VARA CÍVEL DA COMARCA DE JATAÍ, ESTADO DE GOIÁS"
    saida = anonimizar(engine, texto)
    assert "JATAÍ" in saida
    assert "GOIÁS" in saida


def test_endereco_completo_continua_mascarado_mesmo_com_cidade(engine):
    """
    O contrapeso de LOCATION: a cidade sozinha é pública, mas o endereço da
    parte não — e ele continua saindo inteiro pelo `ENDERECO_BR`, que casa do
    logradouro em diante.
    """
    saida = anonimizar(engine, "residente na Rua das Flores, 120, Jataí, Goiás")
    assert "[ENDEREÇO_1]" in saida
    assert "Rua das Flores" not in saida


def test_orgao_publico_nao_e_mascarado(engine):
    texto = "conforme o Tema 1066 do STJ e a Resolução do CNJ, ouvida a União"
    saida = anonimizar(engine, texto)
    for orgao in ("STJ", "CNJ", "União"):
        assert orgao in saida, f"{orgao} é órgão público, não dado pessoal"


def test_url_do_sistema_do_tribunal_nao_e_mascarada(engine):
    texto = "disponível em https://projudi.tjgo.jus.br/BuscaProcesso e em www.gov.br/inss"
    saida = anonimizar(engine, texto)
    assert "projudi.tjgo.jus.br" in saida
    assert "gov.br" in saida


def test_url_de_fora_continua_mascarada(engine):
    """
    O contrapeso de URL: o que se libera é o domínio PÚBLICO do Judiciário e do
    governo. Link de terceiro pode carregar identificador na própria rota.
    """
    saida = anonimizar(engine, "o anúncio está em https://olx.com.br/anuncio/joao-silva-9912")
    assert "olx.com.br" not in saida


def test_o_gate_de_acuracia_nao_e_afetado_por_nada_disto(engine):
    """
    A trava que protege a baseline de 99,97%.

    O `eval/run_eval.py` mede com a lista EXPLÍCITA das 14 entidades da
    interface (`ENTIDADES_DA_INTERFACE`), que inclui LOCATION, DATE_TIME e
    ORGANIZATION — os três que saíram do padrão nesta rodada. O filtro
    `NAO_E_DADO_PESSOAL` só age quando o chamador NÃO pede entidade nenhuma, e
    é por isso que o gate continua medindo o que sempre mediu.

    Se alguém mover o filtro para fora desse `else`, a baseline passa a
    reprovar três tipos de uma vez, e o diagnóstico seria "o motor piorou" —
    quando o que mudou foi quem decide a lista. Este teste falha primeiro.
    """
    from engine import NAO_E_DADO_PESSOAL
    from eval.run_eval import ENTIDADES_DA_INTERFACE

    fora_do_padrao = NAO_E_DADO_PESSOAL & set(ENTIDADES_DA_INTERFACE)
    assert fora_do_padrao, "o teste só tem sentido se houver interseção"

    texto = "o imóvel fica em JATAÍ, Goiás"
    assert "JATAÍ" in anonimizar(engine, texto), "sem pedir: sai limpo"
    pedindo = anonimizar(engine, texto, entities=["LOCATION"])
    assert "JATAÍ" not in pedindo, "pedindo: o gate continua medindo"


# --- 6. O que a tarja em PDF revelou (06/10/2026) --------------------------
#
# Ver o documento tarjado mostra o que a lista de ocorrências esconde: numa
# petição real, o endereço completo do autor e o RG saíram EM CLARO, no meio de
# dados que o resto da anonimização tinha coberto. Nenhum dos dois aparecia como
# falha em lugar nenhum — a lista mostra o que foi achado, nunca o que faltou.


def test_endereco_em_prosa_corrida_e_mascarado(engine):
    """
    O caso real: "residente e domiciliado na Rua Capitão Serafim de Barros,
    2101, Santa Maria, em Jataí – GO, vem diante deste juízo".

    O padrão exigia que o endereço terminasse em `;`, CEP, "Fone", e-mail, fim
    de linha ou ponto final — e endereço em petição não termina em nada disso:
    ele continua na frase. Com `;` no fim era detectado; sem, passava inteiro.
    A terminação por UF é a que a prosa jurídica de fato tem.
    """
    texto = (
        "residente e domiciliado na Rua Capitão Serafim de Barros, 2101, "
        "Santa Maria, em Jataí – GO, vem diante deste juízo propor"
    )
    saida = anonimizar(engine, texto)
    assert "Capitão Serafim de Barros" not in saida
    assert "2101" not in saida
    assert "vem diante deste juízo" in saida, "a tarja não pode comer a frase inteira"


@pytest.mark.parametrize(
    "texto",
    [
        "residente na Avenida Paulista, 1500, São Paulo - SP, onde recebe",
        "domiciliada na Rua XV de Novembro, 30, Centro, Jataí/GO, vem",
    ],
)
def test_outras_formas_de_endereco_com_UF(engine, texto):
    assert "[ENDEREÇO_1]" in anonimizar(engine, texto)


def test_rg_com_palavra_entre_a_ancora_e_o_numero(engine):
    """
    "portador do RG de nº 139003 SSP-GO" saía em claro: entre a âncora `RG` e o
    número, o padrão só aceitava pontuação e espaço — e ali há a palavra "de".
    """
    saida = anonimizar(engine, "portador do RG de nº 139003 SSP-GO, residente")
    assert "139003" not in saida


@pytest.mark.parametrize(
    "texto",
    [
        "portador do RG nº 1.390.034 SSP-GO",
        "RG: 139003 SSP-GO",
        "cédula de identidade de nº 1390034 SSP/GO",
    ],
)
def test_as_formas_de_RG_que_ja_funcionavam_continuam(engine, texto):
    saida = anonimizar(engine, texto)
    assert "139003" not in saida.replace("[RG_1]", "")


def test_nome_na_assinatura_digital_ICP_e_mascarado(engine):
    """
    O formato do certificado ICP-Brasil: `NOME:CPF`, sem espaço.

    Aparece no rodapé de TODA peça assinada digitalmente no PJe e no Projudi —
    "Assinado por ANA CLARA ALVES DE BARROS:05142104196" — e o nome saía em
    claro. O CPF ao lado era mascarado (é regex), o que deixava a linha com cara
    de tratada.

    O NER não pega porque `BARROS:05142104196` não é um token de nome: os dois
    pontos colam o número na última palavra e o modelo vê outra coisa. Quem
    resolve é padrão ancorado no formato, não o modelo.
    """
    texto = "Assinado por ANA CLARA ALVES DE BARROS:05142104196\nLocalizar pelo código"
    saida = anonimizar(engine, texto)
    assert "ANA CLARA ALVES DE BARROS" not in saida
    assert "05142104196" not in saida
    assert "Localizar pelo código" in saida


@pytest.mark.parametrize(
    "texto",
    [
        "JOAO DA SILVA JUNIOR:12345678901",
        "Assinado eletronicamente por MARIA DE FATIMA SOUZA:98765432100",
    ],
)
def test_outras_assinaturas_ICP(engine, texto):
    saida = anonimizar(engine, texto)
    assert "SILVA" not in saida and "FATIMA" not in saida


def test_dois_pontos_com_numero_curto_nao_e_assinatura(engine):
    """
    O contrapeso: a âncora é o CPF de 11 dígitos. Sem ele, dois-pontos seguido
    de número é hora, item de lista, artigo — e mascarar isso encheria o
    documento de tarja.
    """
    saida = anonimizar(engine, "PRAZO: 15 dias. HORARIO: 14:30. ITEM: 1234")
    assert "15 dias" in saida and "14:30" in saida and "1234" in saida
