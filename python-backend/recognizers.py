"""
PatternRecognizers customizados para entidades brasileiras.
Cada recognizer detecta um tipo de PII via regex + contexto.
Recognizers de documentos usam dígito verificador para eliminar falsos
positivos e elevar o score de candidatos confirmados.
"""

from __future__ import annotations

import re
from typing import Callable, Optional

from presidio_analyzer import Pattern, PatternRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from config_loader import load_context_words
from validators import (
    cnpj_valid,
    cpf_valid,
    pis_valid,
    processo_cnj_valid,
)


class ValidatingPatternRecognizer(PatternRecognizer):
    """
    PatternRecognizer que usa uma função de validação de dígito verificador
    para descartar candidatos inválidos e elevar o score dos válidos.

    - Se o candidato tem DV válido → score é elevado para `boosted_score`.
    - Se o candidato tem DV inválido → resultado é descartado.
    - Padrões com dv_required=False são deixados como estão (útil para
      formatos canônicos onde o regex já é bastante específico).
    """

    def __init__(
        self,
        supported_entity: str,
        patterns: list[Pattern],
        context: list[str],
        validator: Callable[[str], bool],
        boosted_score: float = 0.95,
        dv_required_patterns: Optional[set[str]] = None,
        supported_language: str = "pt",
    ):
        super().__init__(
            supported_entity=supported_entity,
            patterns=patterns,
            context=context,
            supported_language=supported_language,
        )
        self._validator = validator
        self._boosted_score = boosted_score
        self._dv_required = dv_required_patterns or set()

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: Optional[NlpArtifacts] = None,
        regex_flags: Optional[int] = None,
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts, regex_flags)
        if not results:
            return results

        filtered: list[RecognizerResult] = []
        for r in results:
            candidate = text[r.start:r.end]
            is_valid = self._validator(candidate)

            pattern_name = (
                r.analysis_explanation.pattern_name
                if r.analysis_explanation is not None
                else ""
            )

            if is_valid:
                r.score = max(r.score, self._boosted_score)
                filtered.append(r)
            elif pattern_name in self._dv_required:
                # Regex pediu DV e candidato falhou — descarta.
                continue
            else:
                # Formato canônico bastante específico: mantém score base.
                filtered.append(r)

        return filtered


class GroupAwarePatternRecognizer(PatternRecognizer):
    """
    PatternRecognizer que reduz o span ao grupo nomeado `valor`, quando o
    padrão o define.

    O Presidio usa `match.span()` — o casamento inteiro — para delimitar a
    entidade. Isso é um problema quando a evidência de que algo é PII está
    *fora* do dado: em "RG: 93002347504 SSP/CE", o rótulo e o órgão emissor
    precisam entrar no regex para dar confiança, mas não podem entrar na
    máscara, porque não são dado pessoal e mascará-los só degrada o documento.

    A solução é reaplicar o padrão sobre o trecho casado e recortar o span
    para o grupo `valor`.
    """

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: Optional[NlpArtifacts] = None,
        regex_flags: Optional[int] = None,
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts, regex_flags)

        por_nome = {p.name: p for p in self.patterns}
        ajustados: list[RecognizerResult] = []

        for r in results:
            nome = (
                r.analysis_explanation.pattern_name
                if r.analysis_explanation is not None
                else ""
            )
            padrao = por_nome.get(nome)
            if padrao is None or "(?P<valor>" not in padrao.regex:
                ajustados.append(r)
                continue

            trecho = text[r.start:r.end]
            m = re.search(padrao.regex, trecho)
            if m is None or m.group("valor") is None:
                ajustados.append(r)
                continue

            inicio, fim = m.span("valor")
            r.start, r.end = r.start + inicio, r.start + fim
            ajustados.append(r)

        return ajustados


# Vocabulário processual que o OCR cola no fim de um nome, porque tudo em volta
# também está capitalizado. O nome termina no primeiro destes termos.
_TERMOS_PROCESSUAIS = {
    "certifico", "certidao", "certidão", "vistos", "designo", "conforme",
    "denuncia", "denúncia", "mandado", "oficio", "ofício", "cota", "ministerial",
    "pedido", "diligencias", "diligências", "trata", "considerando", "inquerito",
    "inquérito", "termo", "audiencia", "audiência", "ata", "decisao", "decisão",
    "sentenca", "sentença", "despacho", "peticao", "petição", "laudo", "exame",
    "auto", "autos", "prisao", "prisão", "flagrante", "boletim", "ocorrencia",
    "ocorrência", "envio", "publicacao", "publicação", "intimacao", "intimação",
    "citacao", "citação", "acordo", "alegacoes", "alegações", "memoriais",
    "requerido", "requerida", "requerente", "acusado", "acusada", "vitima",
    "vítima", "testemunha", "declarante", "denunciado", "denunciada",
    "indiciado", "indiciada", "advogado", "advogada", "reu", "réu", "autor",
    "autora", "oficial", "justica", "justiça", "juiz", "juiza", "juíza",
    "promotor", "promotora", "delegado", "delegada", "escrivao", "escrivão",
    "secretaria", "diretora", "vara", "comarca", "estado", "poder",
    "judiciario", "judiciário", "tribunal", "ministerio", "ministério",
    "publico", "público", "defensoria", "defensor", "policia", "polícia",
    "policial", "militar", "civil", "delegacia", "forum", "fórum", "cartorio",
    "cartório", "central", "nome", "endereco", "endereço", "data", "hora",
    "local", "processo", "numero", "número", "classe", "assunto", "cpf", "rg",
    "filiacao", "filiação", "naturalidade", "profissao", "profissão",
    "observacoes", "observações", "para", "conferir", "protocolado", "informe",
    "codigo", "código", "sob", "esta", "este", "não", "nao", "informado",
}


class NomeRotuladoRecognizer(GroupAwarePatternRecognizer):
    """
    Detecta nome de pessoa a partir do rótulo que o introduz.

    O NER erra justamente onde o documento é mais explícito: nomes em caixa
    alta dentro de blocos de assinatura e listas de partes, cercados de outras
    palavras capitalizadas, sem estrutura de frase que ajude o modelo. Mas
    nesses lugares o documento diz textualmente o que vem a seguir —
    "REQUERENTE:", "ADV:", "assinado digitalmente por" — e essa âncora é mais
    confiável que a inferência do modelo.

    O regex é guloso à direita, então o span é aparado aqui: tudo a partir do
    primeiro termo processual é descartado.
    """

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: Optional[NlpArtifacts] = None,
        regex_flags: Optional[int] = None,
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts, regex_flags)

        aparados: list[RecognizerResult] = []
        for r in results:
            trecho = text[r.start:r.end]
            corte = len(trecho)
            posicao = 0
            for token in re.split(r"(\s+)", trecho):
                if token.strip() and _normalizar_token(token) in _TERMOS_PROCESSUAIS:
                    corte = posicao
                    break
                posicao += len(token)

            nome = trecho[:corte].strip()
            significativas = [
                t for t in nome.split()
                if _normalizar_token(t) not in {"de", "da", "do", "das", "dos", "e"}
                and len(t) > 1
            ]
            if len(significativas) < 2:
                continue

            r.end = r.start + len(nome.rstrip())
            aparados.append(r)

        return aparados


def _normalizar_token(token: str) -> str:
    import unicodedata

    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", token)
        if unicodedata.category(c) != "Mn"
    )
    return sem_acento.strip(".,;:()[]").lower()


def _dv_rastreamento_valido(codigo: str) -> bool:
    """
    Confere o dígito verificador de um objeto dos Correios.

    Formato: duas letras de serviço, nove dígitos (dos quais o último é o DV) e
    duas letras de país. O DV é módulo 11 sobre os oito primeiros dígitos, com
    pesos 8-6-4-2-3-5-9-7; resto 0 vira 5 e resto 1 vira 0, que são as duas
    exceções da regra e o motivo de isto não ser um módulo 11 genérico.

    Existe pelo mesmo motivo que o DV do CPF existe neste produto: candidato que
    não fecha é DESCARTADO em vez de mascarado. Sem isso, qualquer sequência com
    a forma de rastreamento viraria tarja, e o documento sairia salpicado de
    máscara onde não há dado.
    """
    limpo = codigo.replace(" ", "").replace("-", "").upper()
    if len(limpo) != 13 or not limpo[:2].isalpha() or not limpo[11:].isalpha():
        return False
    digitos = limpo[2:11]
    if not digitos.isdigit():
        return False

    pesos = (8, 6, 4, 2, 3, 5, 9, 7)
    soma = sum(int(d) * peso for d, peso in zip(digitos[:8], pesos))
    resto = soma % 11
    if resto == 0:
        esperado = 5
    elif resto == 1:
        esperado = 0
    else:
        esperado = 11 - resto
    return int(digitos[8]) == esperado


def criar_recognizers_brasil() -> list[PatternRecognizer]:
    """Retorna lista de recognizers para entidades brasileiras."""

    ctx = load_context_words()

    # --- CPF ---
    # Padrão formatado: confia no formato + eleva com DV.
    # Padrão cru (11 dígitos): exige DV válido + contexto próximo (o Presidio
    # elevará o score via ContextAwareEnhancer se houver palavras como "cpf").
    cpf = ValidatingPatternRecognizer(
        supported_entity="CPF_BR",
        patterns=[
            Pattern("cpf_fmt", r"(?<!\d)\d{3}\.\d{3}\.\d{3}\s{0,30}-\s{0,30}\d{2}", 0.6),
            # O OCR troca a pontuação do CPF por espaço: "030 736 473 -92".
            Pattern(
                "cpf_espacado",
                r"(?<![\d.])\d{3}[.\s]\s{0,3}\d{3}[.\s]\s{0,3}\d{3}\s{0,3}-\s{0,3}\d{2}(?!\d)",
                0.55,
            ),
            # OCR troca dígitos por letras parecidas: g/9, O/0, l/1, S/5, B/8.
            Pattern(
                "cpf_fmt_ocr",
                r"\b[\dOoIlSBgq]{3}\.[\dOoIlSBgq]{3}\.[\dOoIlSBgq]{3}-[\dOoIlSBgq]{2}\b",
                0.55,
            ),
            Pattern("cpf_raw", r"(?<!\d)\d{11}(?!\d)", 0.3),
        ],
        context=ctx["CPF_BR"],
        validator=cpf_valid,
        boosted_score=0.95,
        dv_required_patterns={"cpf_raw"},
    )

    # --- CNPJ ---
    cnpj = ValidatingPatternRecognizer(
        supported_entity="CNPJ_BR",
        patterns=[
            Pattern("cnpj_fmt", r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", 0.6),
            Pattern("cnpj_raw", r"(?<!\d)\d{14}(?!\d)", 0.3),
        ],
        context=ctx["CNPJ_BR"],
        validator=cnpj_valid,
        boosted_score=0.95,
        dv_required_patterns={"cnpj_raw"},
    )

    # --- RG ---
    # RG não tem algoritmo universal de DV (cada UF é diferente), então a
    # evidência vem da âncora textual, não de checksum.
    #
    # A âncora fica DENTRO do regex, e não na lista de context words, por dois
    # motivos: o enhancer de contexto do Presidio olha só o prefixo (5 tokens
    # antes) e compara lemas — frágil demais para "RG nº93002347504 SSPDSCE" —
    # e ele some quando o recognizer roda sem pipeline NLP.
    #
    # Comprimentos reais observados em OCR de processo: 7 a 13 dígitos, com e
    # sem hífen, com o órgão emissor grudado, separado por barra ou ausente.
    # O órgão emissor fica FORA do span: "SSP/CE" não é dado pessoal.
    rg = GroupAwarePatternRecognizer(
        supported_entity="RG_BR",
        patterns=[
            Pattern(
                "rg_ancorado",
                r"(?:RG|R\.\s?G\.?|[Rr]egistro\s+[Gg]eral|[Ii]dentidade|"
                r"[Cc][ée]dula\s+de\s+[Ii]dentidade|[Cc]arteira\s+de\s+[Ii]dentidade)"
                # "RG DE nº 139003" saía em claro: entre a âncora e o número só
                # passava pontuação e espaço, e ali há uma palavra. As duas
                # ligações que a qualificação usa — "de" e "sob o" — entram
                # explicitamente, em vez de abrir a classe para letra qualquer,
                # o que faria a âncora alcançar o número da linha seguinte.
                r"(?:\s+(?:de|sob\s+o|n[uú]mero))?"
                r"[\s.:n°ºo/-]{0,24}"
                r"(?P<valor>\d[\d.\s-]{4,16}[\dXx])"
                r"(?=\s*(?:SSP|SESP|DETRAN|PC|IFP|SDS|[^\d]|$))",
                0.85,
            ),
            Pattern(
                "rg_com_orgao",
                r"(?P<valor>\d[\d.\s-]{5,16}[\dXx])\s*[-/]?\s*"
                r"(?=(?:SSP|SSPDS|SESP|DETRAN|IFP|SDS)\b)",
                0.8,
            ),
            Pattern("rg_fmt", r"\b\d{1,2}\.\d{3}\.\d{3}-[\dxX]\b", 0.7),
        ],
        supported_language="pt",
        context=ctx["RG_BR"],
    )

    # --- CEP ---
    # Não filtramos por faixa de numeração: 9xxxx-xxx é faixa válida do Rio
    # Grande do Sul, e descartá-la perderia CEP legítimo. O que separa CEP de
    # celular truncado é o contexto — daí o padrão ancorado ter score alto e o
    # livre depender de vizinhança de endereço.
    cep = GroupAwarePatternRecognizer(
        supported_entity="CEP_BR",
        patterns=[
            Pattern(
                "cep_ancorado",
                r"CEP[\s.:nºo°-]{0,6}(?P<valor>\d{2}\.?\s?\d{3}[\s.-]{0,3}\d{3})(?!\d)",
                0.9,
            ),
            Pattern(
                "cep_livre",
                r"(?<![\d-])(?P<valor>\d{2}\.?\d{3}-\d{3})(?!\d)",
                0.45,
            ),
        ],
        supported_language="pt",
        context=ctx["CEP_BR"],
    )

    # --- Endereço ---
    # Cobre o logradouro e o que vem depois dele (número, complemento, bairro),
    # parando em terminador explícito. Score moderado: o recognizer é guloso de
    # propósito, e o custo de mascarar um trecho a mais é baixo perto do custo
    # de deixar o endereço de uma parte exposto.
    endereco = PatternRecognizer(
        supported_entity="ENDERECO_BR",
        patterns=[
            # Logradouro por EXTENSO: a palavra inteira não é ambígua, então
            # a insensibilidade a caixa que o Presidio aplica por padrão não
            # faz mal — e ajuda, porque o OCR entrega tanto "RUA" quanto "rua".
            Pattern(
                "logradouro",
                r"\b(?:Rua|Avenida|Travessa|Alameda|Estrada|Rodovia|Sítio|Sitio|"
                r"Distrito|Localidade|Conjunto|Praça|Praca|Vila|Loteamento|"
                r"Assentamento|Povoado|Fazenda|Quadra)\s+"
                r"[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ0-9][^\n;]{2,80}?"
                r"(?=\s*(?:;|CEP|[Ff]one|[Tt]el|[Ee]-?mail|$|\.\s+[A-ZÁÉÍÓÚ]))",
                0.5,
            ),
            # Logradouro em PROSA, terminando na UF.
            #
            # O padrão acima exige que o endereço acabe em `;`, CEP, "Fone",
            # e-mail, fim de linha ou ponto final — e endereço em petição não
            # acaba em nada disso: ele continua na frase. "residente na Rua
            # Capitão Serafim de Barros, 2101, Santa Maria, em Jataí – GO, vem
            # diante deste juízo" saía INTEIRO em claro, num documento em que o
            # resto estava mascarado. Achado ao olhar o PDF tarjado: a lista de
            # ocorrências mostra o que foi achado, nunca o que faltou.
            #
            # A UF é o fecho natural — `– GO`, `/GO`, `- SP` — e ela entra no
            # match, senão a sigla do estado ficaria de fora da tarja.
            Pattern(
                "logradouro_ate_uf",
                r"\b(?:Rua|Avenida|Travessa|Alameda|Estrada|Rodovia|Praça|Praca|"
                r"Vila|Quadra|Conjunto|Loteamento|Setor)\s+"
                r"[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ0-9][^\n;]{2,80}?"
                r"\s*[-–—/]\s*(?-i:[A-Z]{2})(?![A-Za-z])",
                0.5,
            ),
            # Logradouro ABREVIADO, com a caixa travada por `(?-i:…)`.
            #
            # `R.` é a abreviação mais útil e a mais perigosa: em peça judicial
            # brasileira, "r." é "respeitável" — "a r. decisão", "o r. despacho"
            # — e aparece muito mais vezes que "Rua" abreviada. O Presidio liga
            # `re.IGNORECASE` por padrão, e com ela o `R\.` casava o "r."
            # minúsculo E o `[A-ZÁÀ…]` seguinte passava a aceitar a minúscula de
            # "decisão". O match então corria até o fim da linha: 58 caracteres
            # de texto jurídico mascarados como endereço, numa peça em que
            # endereço nenhum havia.
            #
            # `(?-i:…)` desliga a flag só aqui dentro, então a abreviação exige
            # maiúscula e o que vem depois exige nome próprio — "R. Vinte e
            # Cinco de Março" passa, "r. decisão" não.
            Pattern(
                "logradouro_abreviado",
                r"\b(?-i:(?:R|Av|Trav|Al|Rod|Conj)\.)\s+"
                r"(?-i:[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ0-9])[^\n;]{2,80}?"
                r"(?=\s*(?:;|CEP|[Ff]one|[Tt]el|[Ee]-?mail|$|\.\s+[A-ZÁÉÍÓÚ]))",
                0.5,
            ),
        ],
        supported_language="pt",
        context=ctx["ENDERECO_BR"],
    )

    # --- Telefone brasileiro ---
    # Inclui formato internacional +55, DDD entre parênteses, formato com
    # hífen, e variante colada sem separador (11 dígitos ou 10 dígitos).
    telefone = PatternRecognizer(
        supported_entity="PHONE_NUMBER_BR",
        patterns=[
            Pattern(
                "tel_br_intl",
                r"\+55\s{0,3}\(?\d{2}\)?[\s.-]{0,30}9?\d{4}[\s.-]{0,3}\d{4}\b",
                0.85,
            ),
            Pattern(
                "tel_br_parenteses",
                r"\(\d{2}\)[\s.-]{0,30}\d{4,5}[\s.-]{0,3}\d{4}\b",
                0.8,
            ),
            Pattern(
                "tel_br_hifen",
                r"\b\d{2}[\s.]{0,3}\d{4,5}[\s.-]{0,3}\d{4}\b",
                0.7,
            ),
        ],
        supported_language="pt",
        context=ctx["PHONE_NUMBER_BR"],
    )

    # --- OAB ---
    # Aceita "OAB/CE 12345", "OAB CE 12345", "OAB nº 12345", "OAB/CE 12.345".
    oab = GroupAwarePatternRecognizer(
        supported_entity="OAB_BR",
        patterns=[
            Pattern(
                "oab_estado",
                r"\bOAB(?![A-Za-zÀ-ÿ])\s*[/\-]?\s*[A-Z]{2}\s*[/\-:]?\s*(?:n\.?[ºo°]?\.?)?\s*(?P<valor>\d[\d.]{2,7}\d)(?!\d)",
                0.9,
            ),
            Pattern(
                "oab_generico",
                r"\bOAB(?![A-Za-zÀ-ÿ])[/\s]?[A-Z]{2}[/\s]?\d[\d.]{3,7}\b",
                0.85,
            ),
            Pattern(
                "oab_numero_antes",
                r"\bOAB(?![A-Za-zÀ-ÿ])[\s.:nºo°-]{0,4}(?P<valor>\d[\d.]{2,7})\s*/\s*[A-Z]{2}\b",
                0.9,
            ),
        ],
        supported_language="pt",
        context=ctx["OAB_BR"],
    )

    # --- Data de nascimento ---
    data_nascimento = GroupAwarePatternRecognizer(
        supported_entity="DATE_OF_BIRTH",
        patterns=[
            Pattern(
                "data_nasc_ancorada",
                # `nascid[oa]` aceita as preposições que a qualificação usa de
                # verdade: "nascido EM", "nascida AOS", "nascido NO DIA", "nascido
                # A". Só `em` deixava "nascida aos 12/03/1985" passar em claro —
                # e a forma com "aos" é corriqueira em petição.
                r"(?:nascid[oa]\s+(?:em|aos?|no\s+dia)|nascimento|nasc\.?|"
                r"dt\.?\s*nasc\.?|data\s+de\s+nascimento)[\s.:nºo°-]{0,8}"
                r"(?P<valor>\d{2}/\d{2}/\d{4})",
                0.85,
            ),
            Pattern("data_nasc", r"\b\d{2}/\d{2}/\d{4}\b", 0.20),
        ],
        supported_language="pt",
        context=ctx["DATE_OF_BIRTH"],
    )

    # --- NIT / PIS / PASEP ---
    nit = ValidatingPatternRecognizer(
        supported_entity="NIT_PIS_PASEP",
        patterns=[
            Pattern("nit_fmt", r"\b\d{3}\.\d{5}\.\d{2}-\d\b", 0.6),
            Pattern("nit_raw", r"(?<!\d)\d{11}(?!\d)", 0.3),
        ],
        context=ctx["NIT_PIS_PASEP"],
        validator=pis_valid,
        boosted_score=0.9,
        dv_required_patterns={"nit_raw"},
    )

    # --- Número de processo CNJ ---
    # Formato formatado: NNNNNNN-DD.AAAA.J.TR.OOOO.
    # Formato sem pontuação: 20 dígitos contíguos → exige checksum.
    processo_cnj = ValidatingPatternRecognizer(
        supported_entity="NUMERO_PROCESSO_CNJ",
        patterns=[
            Pattern(
                "processo_cnj_fmt",
                r"(?<!\d)\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}",
                0.75,
            ),
            Pattern(
                "processo_cnj_raw",
                r"(?<!\d)\d{20}(?!\d)",
                0.3,
            ),
        ],
        context=ctx["NUMERO_PROCESSO_CNJ"],
        validator=processo_cnj_valid,
        boosted_score=0.98,
        dv_required_patterns={"processo_cnj_raw"},
    )

    # --- Conta bancária ---
    conta_bancaria = PatternRecognizer(
        supported_entity="CONTA_BANCARIA",
        patterns=[
            Pattern(
                "conta_ag_cc",
                r"\b[Aa]g(?:[êe]ncia)?[:\s]*\d{3,5}[\s,\-]*(?:[Cc](?:onta)?[:\s]*|[Cc]{2}[:\s]*|[Cc][Pp][:\s]*)\d{4,12}-?\d?\b",
                0.75,
            ),
        ],
        supported_language="pt",
        context=ctx["CONTA_BANCARIA"],
    )

    # --- E-mail com o texto seguinte grudado ---
    # O OCR cola a palavra seguinte no fim do endereço ("ocara@tjce.jus.brOcara"),
    # e o EmailRecognizer padrão do Presidio não casa porque "brOcara" não é um
    # TLD válido. O span termina no TLD, deixando de fora o que veio junto.
    email_ocr = GroupAwarePatternRecognizer(
        supported_entity="EMAIL_ADDRESS",
        patterns=[
            Pattern(
                "email_tld_grudado",
                r"(?P<valor>[A-Za-z0-9._%+-]+@(?:[a-z0-9-]+\.)+[a-z]{2,})(?![a-z])",
                0.85,
            ),
        ],
        supported_language="pt",
        context=["email", "e-mail", "correio", "endereço eletrônico"],
    )

    # --- Nome introduzido por rótulo processual ou bloco de assinatura ---
    #
    # O antigo "nome_antes_papel" ("FULANO DE TAL (ADVOGADO)") foi removido em
    # 02/09/2026: o Presidio aplica re.IGNORECASE global aos patterns, e o
    # regex desenhado para caixa alta virou catch-all — qualquer duas palavras
    # antes de um parêntese ("relatório técnico (art. 33...)", "devido processo
    # legal (§ ...)") entrava como PERSON com score 0,6. Medido na decisão 036
    # do processo 0201848-86.2025.8.06.0303: 26 de 29 valores únicos de PERSON
    # eram frase jurídica, todos vindos daquele recognizer. Nome de pessoa é
    # papel do NER e do nome_rotulado, que exige âncora textual.
    nome_rotulado = NomeRotuladoRecognizer(
        supported_entity="PERSON",
        patterns=[
            Pattern(
                "nome_apos_rotulo",
                r"(?:REQUERENTE|REQUERIDO|REQUERIDA|ACUSADO|ACUSADA|DENUNCIADO|"
                r"DENUNCIADA|INDICIADO|INDICIADA|INVESTIGADO|INVESTIGADA|"
                r"V[ÍI]TIMA|OFENDIDO|OFENDIDA|TESTEMUNHA|DECLARANTE|DEPOENTE|"
                r"AUTOR|AUTORA|R[ÉE]U|R[ÉE]|EXEQUENTE|EXECUTADO|EXECUTADA|"
                r"ADV|ADVOGADO|ADVOGADA|DEFENSOR|DEFENSORA|QUERELANTE|QUERELADO|"
                r"Requerente|Requerido|Requerida|Acusado|Acusada|Denunciado|"
                r"Denunciada|Indiciado|Indiciada|V[íi]tima|Testemunha|Declarante|"
                r"Autor|Autora|R[ée]u|Advogado|Advogada)"
                r"\s*(?:\([as]\))?\s*:\s*"
                r"(?P<valor>[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÁ-Úá-úÀ-ÿÇç']+"
                r"(?:\s{1,30}(?:d[aeo]s?|D[AEO]S?|e|E)?\s{0,30}"
                r"[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÁ-Úá-úÀ-ÿÇç']+){1,5})",
                0.8,
            ),
            Pattern(
                "nome_assinatura",
                r"assinado\s+digitalmente\s+por\s+"
                r"(?P<valor>[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÁ-Úá-úÀ-ÿÇç']+"
                r"(?:\s{1,30}(?:d[aeo]s?|D[AEO]S?|e|E)?\s{0,30}"
                r"[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÁ-Úá-úÀ-ÿÇç']+){1,5})",
                0.8,
            ),
        ],
        supported_language="pt",
        context=ctx["PERSON"],
    )

    # --- Nome na assinatura digital ICP-Brasil ---
    #
    # O certificado traz o titular como `NOME:CPF`, sem espaço, e isso aparece
    # no rodapé de TODA peça assinada no PJe e no Projudi: "Assinado por ANA
    # CLARA ALVES DE BARROS:05142104196". O nome saía em claro — o CPF ao lado
    # era mascarado por ser regex, o que deixava a linha com cara de tratada.
    #
    # O NER não pega porque `BARROS:05142104196` não é token de nome: os dois
    # pontos colam o número na última palavra e o modelo vê outra coisa. Aqui
    # quem resolve é o formato, não o modelo.
    #
    # A âncora é o CPF de 11 dígitos colado. Sem ela, dois-pontos seguido de
    # número é hora, item e artigo — e a caixa alta sozinha não distingue nome
    # de cabeçalho. `(?-i:…)` porque o Presidio liga IGNORECASE por padrão, e
    # sem travar a caixa isto casaria qualquer palavra antes de `:`.
    assinatura_icp = GroupAwarePatternRecognizer(
        supported_entity="PERSON",
        patterns=[
            Pattern(
                "assinatura_icp",
                r"(?P<valor>(?-i:[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ]+"
                r"(?:\s+(?-i:[A-ZÀ-ÖØ-Þ]{1,}))+))\s*:\s*\d{11}(?!\d)",
                0.85,
            ),
        ],
        supported_language="pt",
        context=ctx["PERSON"],
    )

    # --- Placa de veículo ---
    #
    # Identificador INDIRETO: não é nome nem documento, e é por isso que passa
    # despercebido. Num processo que gira em torno de um carro — e o acervo
    # tem muitos —, a placa identifica a parte com a mesma eficácia que o nome.
    #
    # Dois formatos convivem desde 2018: o antigo `ABC1234` e o Mercosul
    # `ABC1D23`. Nenhum tem dígito verificador, então o score sozinho é baixo
    # de propósito: `CNJ1234` numa referência qualquer tem a mesma forma. O
    # mecanismo de contexto do Presidio eleva o score quando "placa" ou
    # "veículo" aparecem por perto, que é o caso real.
    #
    # `(?<![A-Z0-9])`/`(?![A-Z0-9])` em vez de `\b`: sem isso o padrão casaria
    # o miolo de um código maior, como as sete primeiras posições de um
    # rastreamento.
    placa = PatternRecognizer(
        supported_entity="PLACA_VEICULO",
        patterns=[
            Pattern(
                "placa_mercosul",
                r"(?<![A-Za-z0-9])(?-i:[A-Z]{3})\s?\d(?-i:[A-Z])\d{2}(?![A-Za-z0-9])",
                0.5,
            ),
            Pattern(
                "placa_antiga",
                r"(?<![A-Za-z0-9])(?-i:[A-Z]{3})\s?-?\s?\d{4}(?![A-Za-z0-9])",
                0.45,
            ),
        ],
        supported_language="pt",
        context=ctx["PLACA_VEICULO"],
    )

    # --- Rastreamento dos Correios ---
    #
    # Liga a pessoa a um endereço de entrega, e aparece em peça toda vez que se
    # discute intimação pelo correio — foi assim que escapou de uma peça real.
    # Aqui HÁ dígito verificador, então vale a régua do CPF: inválido é
    # descartado, não mascarado.
    rastreamento = ValidatingPatternRecognizer(
        supported_entity="RASTREAMENTO_CORREIOS",
        patterns=[
            Pattern(
                "rastreamento_br",
                r"(?<![A-Za-z0-9])(?-i:[A-Z]{2})\d{9}(?-i:[A-Z]{2})(?![A-Za-z0-9])",
                0.6,
            ),
        ],
        context=ctx["RASTREAMENTO_CORREIOS"],
        validator=_dv_rastreamento_valido,
        dv_required_patterns={"rastreamento_br"},
    )

    return [
        cpf, cnpj, rg, cep, endereco, telefone, oab,
        data_nascimento, nit, processo_cnj, conta_bancaria,
        nome_rotulado, email_ocr, placa, rastreamento, assinatura_icp,
    ]
