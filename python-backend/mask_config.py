"""
Políticas de mascaramento.

Três políticas, e a escolha é do operador porque o compromisso é real:

- **placeholder** — `[PESSOA_1]`, `[CPF_2]`. Nada do dado sobrevive, e a
  numeração estável dentro do documento deixa acompanhar quem é quem na
  leitura. É a única que não permite reidentificação por fragmento.
- **parcial** — `J**** d* S****`, `123.***.***-09`. Preserva pistas para
  conferência visual, ao custo de manter iniciais e alguns dígitos. Em
  documento longo, esses fragmentos somados costumam bastar para reidentificar.
- **total** — cobre tudo com `*`, sem revelar sequer o formato.

`aplicar_mascaras` é o ponto de entrada; `apply_mask` fica para quem chama uma
entidade isolada (a CLI e os testes).
"""

from __future__ import annotations

import re
from typing import Callable

MaskFn = Callable[[str], str]

POLITICAS = ("placeholder", "parcial", "total")
POLITICA_PADRAO = "placeholder"

# Nome legível de cada entidade dentro do placeholder. Sai em português porque
# o documento anonimizado é lido por gente, não por máquina.
ROTULO_ENTIDADE: dict[str, str] = {
    "PERSON": "PESSOA",
    "CPF_BR": "CPF",
    "CNPJ_BR": "CNPJ",
    "RG_BR": "RG",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER_BR": "TELEFONE",
    "PHONE_NUMBER": "TELEFONE",
    "LOCATION": "LOCAL",
    "CEP_BR": "CEP",
    "ENDERECO_BR": "ENDEREÇO",
    "OAB_BR": "OAB",
    "DATE_OF_BIRTH": "NASCIMENTO",
    "NIT_PIS_PASEP": "NIT",
    "NUMERO_PROCESSO_CNJ": "PROCESSO",
    "CONTA_BANCARIA": "CONTA",
}


def mask_person(text: str) -> str:
    """Mostra 1ª letra de cada nome: 'João da Silva' → 'J**** d* S****'"""
    parts = text.split()
    masked = []
    for part in parts:
        if len(part) <= 1:
            masked.append(part)
        else:
            masked.append(part[0] + "*" * (len(part) - 1))
    return " ".join(masked)


def mask_cpf(text: str) -> str:
    """Mostra 3 primeiros + 2 últimos: '123.456.789-09' → '123.***.***-09'"""
    digits = re.sub(r"\D", "", text)
    if len(digits) == 11:
        return f"{digits[:3]}.***.***-{digits[-2:]}"
    return "*" * len(text)


def mask_cnpj(text: str) -> str:
    """Mostra 2 primeiros + 2 últimos: '12.345.678/0001-90' → '12.***.***/****-90'"""
    digits = re.sub(r"\D", "", text)
    if len(digits) == 14:
        return f"{digits[:2]}.***/****-{digits[-2:]}"
    return "*" * len(text)


def mask_rg(text: str) -> str:
    """Tudo mascarado exceto último dígito: '12.345.678-9' → '**.***.***-9'"""
    if "-" in text:
        parts = text.rsplit("-", 1)
        base = re.sub(r"\d", "*", parts[0])
        return f"{base}-{parts[1]}"
    return "*" * (len(text) - 1) + text[-1]


def mask_email(text: str) -> str:
    """Mostra 2 primeiras letras + domínio: 'joao@gmail.com' → 'jo****@gmail.com'"""
    if "@" not in text:
        return "*" * len(text)
    local, domain = text.split("@", 1)
    if len(local) <= 2:
        masked_local = local
    else:
        masked_local = local[:2] + "*" * (len(local) - 2)
    return f"{masked_local}@{domain}"


def mask_phone(text: str) -> str:
    """
    Mostra DDD e dois últimos dígitos, preservando a pontuação do original:
    '(85) 99999-1234' → '(85) *****-**34'

    Mascarar dígito a dígito, em vez de reconstruir o formato, evita dois
    problemas: o span pode não incluir o parêntese de abertura (e reconstruí-lo
    produziria '((85)'), e o comprimento do resultado se mantém igual ao da
    entrada, o que é o que permite aplicar as máscaras em lote sem desalinhar
    o texto.
    """
    digitos = re.sub(r"\D", "", text)
    if len(digitos) < 10:
        return re.sub(r"\d", "*", text)

    total = len(digitos)
    visiveis = {0, 1, total - 2, total - 1}  # DDD e dois últimos

    saida = []
    indice = 0
    for ch in text:
        if ch.isdigit():
            saida.append(ch if indice in visiveis else "*")
            indice += 1
        else:
            saida.append(ch)
    return "".join(saida)


def mask_location(text: str) -> str:
    """Mostra 2 primeiras letras: 'Fortaleza' → 'Fo*******'"""
    if len(text) <= 2:
        return text
    return text[:2] + "*" * (len(text) - 2)


def mask_cep(text: str) -> str:
    """
    Preserva a região, esconde o endereço: '62755-000' → '62***-***'.

    Os dois primeiros dígitos identificam o estado/região, o que costuma ser
    necessário para a leitura processual; o resto localiza o domicílio.
    """
    digits = re.sub(r"\D", "", text)
    if len(digits) == 8:
        return f"{digits[:2]}***-***"
    return "*" * len(text)


def mask_endereco(text: str) -> str:
    """
    Mantém o tipo do logradouro e mascara o resto:
    'Rua Cassiano Correia, 4, Boa Esperança' → 'Rua *********************************'

    O tipo sozinho não identifica ninguém e preserva a legibilidade da frase.
    """
    match = re.match(
        r"\s*(Rua|RUA|R\.|Avenida|AVENIDA|Av\.|AV\.|Travessa|TRAVESSA|Trav\.|"
        r"Alameda|Al\.|Estrada|ESTRADA|Rodovia|Rod\.|Sítio|SÍTIO|Sitio|SITIO|"
        r"Distrito|DISTRITO|Localidade|LOCALIDADE|Conjunto|Conj\.|Praça|PRAÇA|"
        r"Praca|Vila|VILA|Loteamento|Assentamento|Povoado|Fazenda|Quadra)\s+",
        text,
    )
    if match:
        prefixo = match.group(0)
        return prefixo + "*" * (len(text) - len(prefixo))
    return "*" * len(text)


def mask_oab(text: str) -> str:
    """Estado visível, número mascarado: 'OAB/CE 12345' → 'OAB/CE *****'"""
    match = re.match(r"(OAB[/\s]?\w{2}[/\s]?)(.*)", text, re.IGNORECASE)
    if match:
        prefix = match.group(1)
        number = match.group(2)
        return prefix + "*" * len(number)
    return "*" * len(text)


def mask_date_of_birth(text: str) -> str:
    """Mostra só o ano: '15/03/1985' → '**/**/1985'"""
    match = re.match(r"(\d{2})/(\d{2})/(\d{4})", text)
    if match:
        return f"**/**/{match.group(3)}"
    return "*" * len(text)


def mask_nit(text: str) -> str:
    """3 primeiros + último: '123.45678.90-1' → '123.*****.**-*'"""
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 4:
        return f"{digits[:3]}.*****.{digits[-3:-1]}-*"
    return "*" * len(text)


def mask_processo_cnj(text: str) -> str:
    """Ano + ramo visíveis: '0001234-56.2023.8.06.0001' → '*******-**.2023.8.06.****'"""
    match = re.match(
        r"(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})", text
    )
    if match:
        ano = match.group(3)
        justica = match.group(4)
        tribunal = match.group(5)
        return f"*******-**.{ano}.{justica}.{tribunal}.****"
    return "*" * len(text)


def mask_conta_bancaria(text: str) -> str:
    """Tudo mascarado: 'Ag 1234 CC 56789-0' → 'Ag **** CC *****-*'"""
    return re.sub(r"\d", "*", text)


# Mapeamento entidade → função de mask
MASK_FUNCTIONS: dict[str, MaskFn] = {
    "PERSON": mask_person,
    "CPF_BR": mask_cpf,
    "CNPJ_BR": mask_cnpj,
    "RG_BR": mask_rg,
    "EMAIL_ADDRESS": mask_email,
    "PHONE_NUMBER_BR": mask_phone,
    "LOCATION": mask_location,
    "CEP_BR": mask_cep,
    "ENDERECO_BR": mask_endereco,
    "OAB_BR": mask_oab,
    "DATE_OF_BIRTH": mask_date_of_birth,
    "NIT_PIS_PASEP": mask_nit,
    "NUMERO_PROCESSO_CNJ": mask_processo_cnj,
    "CONTA_BANCARIA": mask_conta_bancaria,
}


def apply_mask(entity_type: str, text: str) -> str:
    """Máscara parcial de uma entidade isolada, sem contexto de documento."""
    fn = MASK_FUNCTIONS.get(entity_type)
    if fn is not None:
        return fn(text)
    # Fallback: mascara tudo
    return "*" * len(text)


def _normalizar(texto: str) -> str:
    """Forma comparável de um valor, para que a mesma pessoa receba o mesmo número."""
    import unicodedata

    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(sem_acento.lower().split())


class Mascarador:
    """
    Aplica a política escolhida, mantendo a numeração dos placeholders estável
    dentro de um documento.

    O estado é por documento e por rótulo: o primeiro nome encontrado vira
    `[PESSOA_1]` e toda ocorrência daquele mesmo nome — inclusive escrita com
    outra caixa ou acentuação, que é o que o OCR produz — recebe o mesmo
    número. É isso que mantém o texto legível: dá para acompanhar que
    `[PESSOA_1]` e `[PESSOA_2]` são pessoas diferentes sem saber quem são.
    """

    def __init__(self, politica: str = POLITICA_PADRAO):
        if politica not in POLITICAS:
            raise ValueError(
                f"política de máscara desconhecida: {politica!r} "
                f"(use uma de {', '.join(POLITICAS)})"
            )
        self.politica = politica
        # Duas estruturas, porque são duas perguntas diferentes — e juntá-las
        # numa só foi o defeito.
        #
        # `_numeros` decide o TEXTO, e numera por RÓTULO. O rótulo é a
        # identidade que o leitor e o modelo enxergam; `entity_type` é detalhe
        # de quem detectou. `ROTULO_ENTIDADE` manda `PHONE_NUMBER_BR` e
        # `PHONE_NUMBER` ao mesmo `TELEFONE`, e o motor suporta os dois: numerar
        # por tipo dava `[TELEFONE_1]` a dois telefones diferentes — texto
        # ambíguo, e mapa reverso que substitui o valor errado.
        #
        # O valor é `(indice, primeira_grafia_vista)`, e não só o índice. A chave
        # é `_normalizar(texto)` — sem acento, minúscula — porque é o que faz
        # `JOÃO DA SILVA` e `joao da silva` receberem o mesmo número, o que o OCR
        # torna obrigatório. Mas a chave normalizada não reidrata: devolveria
        # `joao da silva`, um nome errado num documento que parece certo.
        self._numeros: dict[str, dict[str, tuple[int, str]]] = {}
        # `_tipos` conta por `entity_type`, porque é isso que `resumo()` promete
        # e `valores_distintos` atravessa a API (`api_v1.py:152`,
        # `server.py:331`) até a interface. Mudar a forma disso quebraria a tela.
        self._tipos: dict[str, set[str]] = {}

    def mascarar(self, entity_type: str, texto: str) -> str:
        if self.politica == "parcial":
            return apply_mask(entity_type, texto)
        if self.politica == "total":
            return "*" * len(texto)
        return self._placeholder(entity_type, texto)

    def _placeholder(self, entity_type: str, texto: str) -> str:
        rotulo = ROTULO_ENTIDADE.get(entity_type, entity_type)
        chave = _normalizar(texto)

        por_rotulo = self._numeros.setdefault(rotulo, {})
        if chave not in por_rotulo:
            por_rotulo[chave] = (len(por_rotulo) + 1, texto)

        self._tipos.setdefault(entity_type, set()).add(chave)

        indice, _ = por_rotulo[chave]
        return f"[{rotulo}_{indice}]"

    def resumo(self) -> dict[str, int]:
        """Quantos valores distintos foram encontrados por tipo."""
        return {tipo: len(chaves) for tipo, chaves in self._tipos.items()}

    def mapa(self) -> dict[str, str]:
        """
        O de-para `{"[PESSOA_1]": "João da Silva"}`.

        Não há colisão possível aqui, e a garantia é ESTRUTURAL, não conferida:
        `_numeros` é indexado pelo rótulo e numera dentro dele, então duas
        entradas distintas nunca produzem a mesma etiqueta. Uma verificação em
        tempo de execução seria mais fraca — pegaria o erro depois de existir,
        em vez de torná-lo impossível de escrever.

        Vazio nas políticas `parcial` e `total`: elas não passam por
        `_placeholder`, e reidratar `J**** d* S****` é impossível porque a
        informação não está mais no texto. Vazio é a resposta correta, não uma
        lacuna a preencher por aproximação.
        """
        return {
            f"[{rotulo}_{indice}]": original
            for rotulo, valores in self._numeros.items()
            for indice, original in valores.values()
        }
