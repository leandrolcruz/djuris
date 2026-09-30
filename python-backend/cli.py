#!/usr/bin/env python3
"""
CLI de anonimização de dados pessoais em documentos judiciais brasileiros.

    tecjustica-sigilo <arquivo>...                 # forma clássica, preservada
    tecjustica-sigilo anonimizar <arquivo>...      # idem, explícito
    tecjustica-sigilo ler <arquivo>...             # extrai texto + OCR
    tecjustica-sigilo ocr <imagem>
    tecjustica-sigilo status                       # app no ar? porta, motor, OCR
    tecjustica-sigilo conectar                     # pareia esta CLI com o app
    tecjustica-sigilo mcp                          # servidor MCP em stdio

## O que mudou, e por quê

A versão anterior lia a entrada com `Path(path).read_text(encoding="utf-8")` e
nunca importava `documentos`. Consequência: `tecjustica-sigilo autos.pdf`
terminava em `UnicodeDecodeError`. O recurso mais caro do produto — ler PDF e
imagem com OCR — era inalcançável fora da interface gráfica.

Agora a CLI lê documento de verdade, e é **cliente fino**: com o aplicativo
aberto, delega por HTTP para o motor já quente; fechado, sobe em processo
avisando o custo. Ver `cliente_local.py`.

Códigos de saída:
    0 = sucesso
    1 = erro de entrada/saída
    2 = motor falhou
    3 = precisa parear (rode `tecjustica-sigilo conectar`)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import cliente_local as local
from mask_config import POLITICA_PADRAO, POLITICAS

# Extensões que o renderer também trata como "texto puro": dá para ler aqui
# mesmo, sem passar pelo extrator de documentos.
EXTENSOES_TEXTO = {".txt", ".md", ".rtf", ""}


def _e_texto_puro(caminho: str) -> bool:
    return Path(caminho).suffix.lower() in EXTENSOES_TEXTO


def _entidades(bruto: str | None) -> list[str]:
    if not bruto:
        return []
    return [e.strip() for e in bruto.split(",") if e.strip()]


def _mesmo_arquivo(a: Path, b: Path) -> bool:
    """
    Os dois caminhos apontam para o mesmo arquivo?

    `samefile` é o único jeito honesto quando os dois existem: resolve link
    simbólico, junction do Windows e maiúsculas/minúsculas de um jeito que
    comparar strings não resolve — `AUTOS.PDF` e `autos.pdf` são o mesmo arquivo
    no NTFS e strings diferentes. Quando o destino ainda não existe, sobra
    comparar os caminhos resolvidos.
    """
    try:
        if a.exists() and b.exists():
            return a.samefile(b)
    except OSError:
        pass
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def _escrever(destino: str | None, conteudo: str) -> None:
    if destino is None or destino == "-":
        sys.stdout.write(conteudo)
        if not conteudo.endswith("\n"):
            sys.stdout.write("\n")
        return
    # `newline="\n"` explícito: no Windows o modo texto trocaria `\n` por
    # `\r\n`, mudando os bytes de um arquivo que pode ser conferido por hash.
    with open(destino, "w", encoding="utf-8", newline="\n") as f:
        f.write(conteudo)


# ---------------------------------------------------------------------------
# Resolução de backend
# ---------------------------------------------------------------------------


def _resolver(args) -> tuple[str, object]:
    """
    Decide por onde o trabalho vai: `("remoto", sessao)` ou `("local", None)`.

    Sai por `SystemExit` quando o usuário pediu explicitamente um modo que não
    está disponível — falhar rápido é melhor que silenciosamente fazer a coisa
    cara sem avisar.
    """
    if args.offline:
        return "local", None

    sessao = local.app_no_ar()
    if sessao is not None:
        return "remoto", sessao

    if args.remoto:
        print(
            "erro: o aplicativo não está aberto e --remoto foi pedido.\n"
            "Abra o TecJustiça Sigilo, ou rode sem --remoto para carregar o\n"
            "motor neste processo (mais lento).",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return "local", None


def _token_do_cliente() -> str | None:
    return local.ler_credencial()


def _exigir_credencial() -> str:
    token = _token_do_cliente()
    if not token:
        print(
            "erro: esta CLI ainda não foi autorizada pelo aplicativo.\n"
            "Rode `tecjustica-sigilo conectar` e aprove na janela do programa.",
            file=sys.stderr,
        )
        raise SystemExit(3)
    return token


# ---------------------------------------------------------------------------
# Subcomandos
# ---------------------------------------------------------------------------


def cmd_status(args) -> int:
    sessao = local.app_no_ar()

    if sessao is None:
        print("aplicativo: fechado")
        print("modo: offline (o motor sobe a cada comando)")
        print(
            "credencial: "
            + ("guardada" if _token_do_cliente() else "não pareada")
        )
        return 0

    _, info = local.pedir(sessao.base, "/v1/info")
    motor = info.get("motor", {})
    ocr = info.get("ocr", {})

    print(f"aplicativo: aberto (pid {sessao.pid}, porta {sessao.porta})")
    print(f"motor: {'pronto' if motor.get('pronto') else 'carregando'}")
    print(f"modo NLP: {motor.get('modo_nlp')}")
    if motor.get("motivo_fallback"):
        # Degradação silenciosa é o que mais custa aqui: o modo leve encontra
        # menos nomes e locais, e o documento sai com a mesma cara.
        print(
            f"  ATENÇÃO: pedido {motor.get('modo_solicitado')}, "
            f"subiu {motor.get('modo_nlp')} — {motor.get('motivo_fallback')}"
        )
    print(f"OCR: {ocr.get('motor')} ({'offline' if ocr.get('offline') else 'baixaria modelos'})")
    print(
        "credencial: " + ("guardada" if _token_do_cliente() else "não pareada")
    )
    return 0


def cmd_conectar(args) -> int:
    sessao = local.app_no_ar()
    if sessao is None:
        print(
            "erro: o aplicativo precisa estar aberto para autorizar esta CLI.",
            file=sys.stderr,
        )
        return 1

    escopos = ["anonimizar", "ocr", "documento"]
    status, resposta = local.pedir(
        sessao.base,
        "/v1/parear",
        metodo="POST",
        corpo={"nome": "Linha de comando", "escopos": escopos},
    )
    if status != 202:
        print(f"erro ao pedir pareamento: {resposta.get('detail')}", file=sys.stderr)
        return 1

    print()
    print("  Confira este código na janela do TecJustiça Sigilo:")
    print()
    print(f"        {resposta['codigo']}")
    print()
    print("  Aguardando aprovação…", flush=True)

    pedido = resposta["pedido"]
    limite = time.time() + resposta.get("expira_em", 180)

    while time.time() < limite:
        status, corpo = local.pedir(sessao.base, f"/v1/parear/{pedido}")
        if status == 200:
            caminho = local.gravar_credencial(corpo["token"])
            print(f"  Autorizada. Credencial guardada em {caminho}")
            return 0
        if status == 403:
            print("  Recusado pelo aplicativo.", file=sys.stderr)
            return 1
        if status == 404:
            print("  O pedido expirou. Rode o comando de novo.", file=sys.stderr)
            return 1
        time.sleep(1)

    print("  Tempo esgotado sem aprovação.", file=sys.stderr)
    return 1


def _ler_documento_remoto(sessao, caminho: Path, token: str) -> dict:
    """O envio mora em `cliente_local` porque o MCP precisa exatamente dele."""
    return local.enviar_documento(sessao, caminho, token)


def _texto_de(caminho: Path, modo: str, sessao, token: str | None, motor) -> dict:
    """
    O texto de um arquivo, venha ele de onde vier.

    Texto puro é lido aqui mesmo. Documento (PDF, DOCX, imagem) vai para o
    extrator — remoto ou local — que faz OCR quando a página é digitalizada.
    """
    if _e_texto_puro(str(caminho)):
        try:
            return {"texto": caminho.read_text(encoding="utf-8")}
        except UnicodeDecodeError:
            # RTF do Windows costuma vir em cp1252; decodificar errado
            # corromperia justamente os nomes próprios a detectar.
            return {"texto": caminho.read_text(encoding="cp1252")}

    if modo == "remoto":
        return _ler_documento_remoto(sessao, caminho, token or "")

    import documentos

    extraido = documentos.extrair(str(caminho))
    return {
        "texto": extraido.como_markdown(),
        "ocr": {
            "houve_ocr": extraido.houve_ocr,
            "paginas_ocr": extraido.paginas_ocr,
            "paginas_com_erro": extraido.paginas_com_erro,
            "total_paginas": extraido.total_paginas,
        },
    }


def _avisar_paginas_perdidas(info_ocr: dict | None, nome: str) -> None:
    """
    Páginas que precisavam de OCR e não voltaram.

    Não pode ser silencioso nem em script: o texto delas não está no resultado,
    e o que não está no resultado não foi anonimizado nem revisado. Vai para o
    stderr para não sujar um pipe.
    """
    if not info_ocr:
        return
    perdidas = info_ocr.get("paginas_com_erro") or 0
    if perdidas:
        print(
            f"ATENÇÃO: {perdidas} página(s) de {nome} não foram lidas. "
            "O texto delas não está na saída.",
            file=sys.stderr,
        )


def cmd_anonimizar(args) -> int:
    # Validação de argumentos primeiro, antes de resolver backend, exigir
    # credencial ou carregar motor: o que está errado na linha de comando
    # continua errado depois de tudo isso, e falhar cedo poupa a pessoa de
    # parear ou esperar minutos para então ouvir que a opção não valia.
    if len(args.files) > 1 and not (args.in_place or args.output_dir):
        print(
            "erro: com mais de um arquivo, use --in-place ou --output-dir.",
            file=sys.stderr,
        )
        return 1

    # `--in-place` só vale para texto, e a recusa é deliberada.
    #
    # A opção era inofensiva quando a CLI só lia `.txt`. Ao passar a ler PDF,
    # DOCX e imagem, virou destrutiva: gravaria o markdown anonimizado **por
    # cima** dos autos originais, produzindo um arquivo que nenhum leitor abre e
    # destruindo o documento de onde ele veio. Não há desfazer.
    #
    # É a mesma regra de `lib/nomeDeSaida.ts`: a saída é texto, nunca o formato
    # de entrada — a extensão descreve o que o arquivo **é**.
    if args.in_place:
        binarios = [f for f in args.files if not _e_texto_puro(f)]
        if binarios:
            nomes = ", ".join(Path(f).name for f in binarios)
            print(f"erro: --in-place recusado para {nomes}.", file=sys.stderr)
            print(
                "A saída da anonimização é texto, e gravá-la por cima de um "
                "documento binário destruiria o original.",
                file=sys.stderr,
            )
            print("Use --output-dir, ou -o com outro nome de arquivo.", file=sys.stderr)
            return 1

    # `-o` apontando para a própria entrada é `--in-place` por outro nome.
    #
    # A mensagem acima chegava a **sugerir** `-o`, que era a porta dos fundos
    # exata: `anonimizar autos.pdf -o autos.pdf` lia o PDF e depois o abria em
    # modo `"w"`, truncando os autos originais e gravando markdown por cima.
    # A recusa não pode depender do nome da opção — tem de olhar para o arquivo
    # que vai ser aberto para escrita.
    if args.output and args.output != "-":
        destino = Path(args.output)
        colisoes = [
            f for f in args.files
            if _mesmo_arquivo(destino, Path(f)) and not _e_texto_puro(f)
        ]
        if colisoes:
            nomes = ", ".join(Path(f).name for f in colisoes)
            print(f"erro: -o recusado — gravaria por cima de {nomes}.", file=sys.stderr)
            print(
                "A saída da anonimização é texto, e gravá-la por cima de um "
                "documento binário destruiria o original.",
                file=sys.stderr,
            )
            return 1

    # As políticas `parcial` e `total` não passam pelo `_placeholder`, então não
    # produzem mapa nenhum. Aceitar `--autos` com elas gravaria um mapa vazio e
    # prometeria uma reidratação que nunca funcionaria — e o sintoma apareceria
    # só depois, com o documento já enviado.
    if args.autos and args.mascara != "placeholder":
        print(
            f"erro: --autos exige -m placeholder (recebi {args.mascara!r}).",
            file=sys.stderr,
        )
        print(
            "Máscara parcial e cobertura total não deixam o que reidratar: "
            "o valor não está mais no texto.",
            file=sys.stderr,
        )
        return 1

    # O nome dos autos é validado AQUI, junto das outras checagens de linha de
    # comando, e não no fim: ele vira nome de arquivo, e descobrir que é
    # inválido depois de minutos de OCR seria descobrir tarde. A régua é do
    # `mapa_reverso`, para não haver duas.
    if args.autos:
        import mapa_reverso as _mr
        try:
            _mr._caminho(args.autos)
        except ValueError as erro:
            print(f"erro: {erro}", file=sys.stderr)
            return 1

    modo, sessao = _resolver(args)
    entidades = _entidades(args.entities)
    token = _exigir_credencial() if modo == "remoto" else None

    mascarador = None
    if args.autos:
        if modo == "remoto":
            print(
                "erro: --autos ainda só funciona no modo local.\n"
                "Rode com --offline (o motor carrega neste processo).",
                file=sys.stderr,
            )
            return 1

        import mapa_reverso
        from mask_config import Mascarador

        # O Mascarador nasce e morre AQUI, no escopo desta função, e `args.autos`
        # é lido uma vez. É isso que impede que ele atravesse duas invocações e
        # misture pessoas de autos DIFERENTES num espaço de numeração comum — o
        # que produziria um texto internamente coerente e factualmente falso, do
        # tipo que ninguém revisa porque parece certo. A vida curta é a garantia:
        # movê-lo para um cache de processo, ou para fora desta função, a desfaz
        # sem que nada acuse.
        mascarador = Mascarador(args.mascara)

        # E a semeadura é o que faz `--autos` valer ENTRE invocações, não só
        # dentro de uma. Sem ela, esta chamada numeraria do `[PESSOA_1]` outra
        # vez e a gravação recusaria por `EtiquetaConflitante` — porque a peça de
        # segunda-feira já gastou aquele número com outra pessoa.
        # Ler o mapa aqui, ANTES de qualquer trabalho caro, tem duas funções: dá
        # a semente da numeração e valida que a chave abre o que está gravado.
        # Descobrir que o mapa não decifra depois de minutos de OCR seria
        # descobrir tarde — e com os arquivos já escritos.
        try:
            gravado = mapa_reverso.ler(args.autos)
        except mapa_reverso.CifragemIndisponivel as erro:
            print(f"erro: {erro}", file=sys.stderr)
            return 1
        except mapa_reverso.MapaIlegivel as erro:
            print(f"ALARME: {erro}", file=sys.stderr)
            print(
                "Não anonimizei nada. Seguir criaria um segundo mapa para os "
                "mesmos autos, e você ficaria com duas numerações incompatíveis "
                "sem saber qual explica qual peça.",
                file=sys.stderr,
            )
            return 1
        if gravado:
            mascarador.semear(gravado)
            print(
                f"autos {args.autos}: continuando a numeração de "
                f"{len(gravado)} pseudônimo(s) já gravado(s).",
                file=sys.stderr,
            )

    # stdin quando não há arquivo: mantém `cat x.txt | tecjustica-sigilo`.
    if not args.files:
        texto = sys.stdin.read()
        resultado = _anonimizar_texto(
            texto, entidades, args.mascara, modo, sessao, token, args,
            mascarador=mascarador,
        )
        _escrever(args.output, _formatar(resultado, args.format))
        return _gravar_mapa(args, mascarador)

    contexto = local.MotorLocal(quieto=args.quiet) if modo == "local" else _NoOp()
    with contexto as ctx:
        motor = getattr(ctx, "engine", None)

        for bruto in args.files:
            caminho = Path(bruto)
            if not caminho.exists():
                print(f"erro: {caminho} não existe", file=sys.stderr)
                return 1

            lido = _texto_de(caminho, modo, sessao, token, motor)
            _avisar_paginas_perdidas(lido.get("ocr"), caminho.name)

            # O extrator remoto já devolve o texto anonimizado quando pedido;
            # evita uma segunda viagem com o documento inteiro.
            if "texto_anonimizado" in lido:
                resultado = {
                    "anonymized_text": lido["texto_anonimizado"],
                    "entities_found": lido.get("ocorrencias", []),
                }
            else:
                resultado = _anonimizar_texto(
                    lido["texto"], entidades, args.mascara, modo, sessao, token, args,
                    motor, mascarador=mascarador,
                )

            saida = _formatar(resultado, args.format)

            if args.in_place:
                destino = str(caminho)
            elif args.output_dir:
                pasta = Path(args.output_dir)
                pasta.mkdir(parents=True, exist_ok=True)
                # A saída é **texto**, nunca o formato de entrada: gravar
                # markdown num `.pdf` produz um arquivo que nenhum leitor abre.
                destino = str(pasta / f"{caminho.stem}_anonimizado.md")
            elif len(args.files) == 1:
                destino = args.output
            else:
                destino = str(caminho.with_name(f"{caminho.stem}_anonimizado.md"))

            _escrever(destino, saida)
            if destino and destino != "-":
                print(f"{caminho} -> {destino}", file=sys.stderr)

    return _gravar_mapa(args, mascarador)


def _gravar_mapa(args, mascarador) -> int:
    """
    Fecha o `--autos`: grava o de-para cifrado e devolve o código de saída.

    Existe como função porque `cmd_anonimizar` tem DOIS caminhos de sucesso — o
    stdin e o laço de arquivos —, e a Task 7 já mostrou o que acontece quando
    uma saída do motor passa por dois pontos que ninguém revisou junto: a
    segunda fica para trás. Uma cópia deste bloco em cada `return` seria a mesma
    armadilha com outra roupa.

    Devolve 0 quando não há `--autos`: não gravar mapa nenhum é o caminho
    normal, não uma falha.
    """
    if mascarador is None:
        return 0

    import mapa_reverso

    # Esta gravação acontece DEPOIS de os arquivos anonimizados estarem no
    # disco, e não há como ser antes: o mapa só está completo quando a última
    # peça foi lida. Então a falha aqui tem um efeito específico e precisa ser
    # dita com essas palavras — os arquivos existem, parecem certos, e não há
    # como reidratá-los. Um traceback deixaria a pessoa achando que o problema
    # foi na anonimização.
    try:
        destino_mapa = mapa_reverso.gravar(args.autos, mascarador.mapa())
    except (
        mapa_reverso.EtiquetaConflitante,
        mapa_reverso.CifragemIndisponivel,
        mapa_reverso.MapaIlegivel,
        OSError,
    ) as erro:
        print(f"erro ao gravar o mapa dos autos {args.autos}: {erro}", file=sys.stderr)
        print(
            "ATENÇÃO: a anonimização foi concluída e os arquivos de saída "
            "estão gravados, mas SEM mapa não há como reidratá-los depois. "
            "Resolva o que impediu a gravação e rode de novo sobre os mesmos "
            "arquivos — a anonimização é determinística, então a segunda "
            "passada produz os mesmos rótulos.",
            file=sys.stderr,
        )
        return 1

    # Só o caminho no stderr. O mapa é o de-para para o dado real: mesmo o
    # tamanho dele já diz quantas pessoas há no processo.
    print(f"mapa dos autos {args.autos} -> {destino_mapa}", file=sys.stderr)
    return 0


def _anonimizar_texto(
    texto, entidades, politica, modo, sessao, token, args, motor=None, mascarador=None
) -> dict:
    if modo == "remoto":
        status, corpo = local.pedir(
            sessao.base,
            "/v1/anonimizar",
            metodo="POST",
            corpo={"texto": texto, "entidades": entidades, "politica": politica},
            token=token,
            timeout=local.TIMEOUT_LONGO_S,
        )
        if status != 200:
            raise SystemExit(f"erro do aplicativo: {corpo.get('detail')}")
        return {
            "anonymized_text": corpo["texto_anonimizado"],
            "entities_found": corpo["ocorrencias"],
        }

    if motor is None:
        with local.MotorLocal(quieto=args.quiet) as ctx:
            return ctx.engine.anonymize(
                text=texto, entities=entidades, politica_mascara=politica,
                mascarador=mascarador,
            )
    return motor.anonymize(
        text=texto, entities=entidades, politica_mascara=politica,
        mascarador=mascarador,
    )


# O contrato público do `-f json`, declarado. Campo que não está aqui não sai —
# e é essa a direção certa do filtro.
#
# A versão anterior negava `mapa_reverso` por nome, o que conserta o campo
# conhecido e falha aberto no próximo: a Task 7 acrescentou uma chave ao retorno
# do motor e ela escapou por duas saídas que ninguém tinha revisado. Com lista
# de permissão, o campo novo fica de fora até que alguém decida que é público —
# que é a decisão que deve ser explícita.
#
# É o padrão que este repositório já usa em dois dos quatro pontos de saída: o
# `response_model` do Pydantic na rota `/anonymize` (`server.py`) e o dicionário
# montado campo a campo no `mcp_server.py`. Os dois são lista de permissão
# estrutural — campo novo no motor não sai por eles sem alguém escrever o nome.
#
# `entities_found` SAI, e com o texto real dentro: é o contrato documentado do
# `-f json` ("json = com a lista de ocorrências"), e a lista existe para auditar
# o que foi mascarado. Quem não quer o valor real na saída usa o formato `text`.
CAMPOS_PUBLICOS_JSON = (
    "anonymized_text",
    "entities_found",
    "politica_mascara",
    "valores_distintos",
)


def _formatar(resultado: dict, formato: str) -> str:
    if formato == "json":
        publico = {c: resultado[c] for c in CAMPOS_PUBLICOS_JSON if c in resultado}
        return json.dumps(publico, ensure_ascii=False, indent=2)
    return resultado["anonymized_text"]


def cmd_ler(args) -> int:
    """Extrai o texto sem anonimizar. Útil para conferir o que o OCR viu."""
    modo, sessao = _resolver(args)
    token = _exigir_credencial() if modo == "remoto" else None

    contexto = local.MotorLocal(quieto=args.quiet) if modo == "local" else _NoOp()
    with contexto as ctx:
        partes = []
        for bruto in args.files:
            caminho = Path(bruto)
            if not caminho.exists():
                print(f"erro: {caminho} não existe", file=sys.stderr)
                return 1
            lido = _texto_de(caminho, modo, sessao, token, getattr(ctx, "engine", None))
            _avisar_paginas_perdidas(lido.get("ocr"), caminho.name)
            partes.append(lido["texto"])

    _escrever(args.output, "\n\n".join(partes))
    return 0


def cmd_reidratar(args) -> int:
    """
    Desfaz a máscara num texto que voltou de fora, usando o mapa dos autos.

    Não fala com o motor e não carrega modelo: é substituição de rótulo por
    valor a partir de um mapa já gravado. Roda em milissegundos, e roda com o
    SSD montado e nada mais.

    Por que isto NÃO é ferramenta de MCP: chamada por um agente, ela devolve os
    nomes reais ao contexto dele — que é a nuvem — e desfaz o que o programa
    existe para fazer. `mcp_server.py` segue com quatro ferramentas, e o
    `smoke-backend.sh` confere esse número.
    """
    import mapa_reverso

    try:
        mapa = mapa_reverso.ler(args.autos)
    except (ValueError, mapa_reverso.CifragemIndisponivel) as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1
    except mapa_reverso.MapaIlegivel as erro:
        # Ramo próprio, e não junto dos outros, porque a reação é outra: aqui o
        # mapa EXISTE. Tratar isto como "não tenho mapa" devolveria o texto com
        # os rótulos em claro e deixaria quem lê concluir que o prazo venceu.
        print(f"ALARME: {erro}", file=sys.stderr)
        print(
            "Nada foi reidratado. Se você recriou a chave de propósito, os mapas "
            "gravados antes dela são perda esperada. Se não recriou, alguém "
            "mexeu na chave.",
            file=sys.stderr,
        )
        return 1

    if not mapa:
        print(
            f"erro: não há mapa para os autos {args.autos!r}.",
            file=sys.stderr,
        )
        print(
            "Ou o nome está errado, ou o prazo de guarda venceu e o mapa foi "
            "apagado (padrão: 7 dias; veja PRESIDIO_MAPA_PRAZO_DIAS).",
            file=sys.stderr,
        )
        return 1

    if args.files:
        # `reidratar` recebe a RESPOSTA que voltou de um modelo, que é texto.
        # Recusar binário aqui, e não deixar o `read_text` explodir, porque o
        # engano natural é passar o PDF dos autos — o `anonimizar` aceita PDF, e
        # nada na linha de comando sugere que este subcomando não aceita. Um
        # `UnicodeDecodeError` cru mandaria a pessoa procurar defeito de
        # codificação num arquivo que simplesmente não é para entrar aqui.
        binarios = [f for f in args.files if not _e_texto_puro(f)]
        if binarios:
            nomes = ", ".join(Path(f).name for f in binarios)
            print(f"erro: reidratar recusa {nomes} — não é texto.", file=sys.stderr)
            print(
                "Este subcomando reidrata a RESPOSTA que voltou do modelo, que é "
                "texto. Para ler um documento, use `ler` ou `anonimizar`.",
                file=sys.stderr,
            )
            return 1

        partes = []
        for bruto in args.files:
            caminho = Path(bruto)
            if not caminho.exists():
                print(f"erro: {caminho} não existe", file=sys.stderr)
                return 1
            try:
                partes.append(caminho.read_text(encoding="utf-8"))
            except UnicodeDecodeError:
                # Extensão de texto com bytes que não são UTF-8 (um `.txt` salvo
                # em latin-1, que sai de sistema judicial antigo). A régua acima
                # olha a extensão e não o conteúdo, então este ramo existe.
                print(
                    f"erro: {caminho} não é UTF-8. Converta antes "
                    f"(`iconv -f latin1 -t utf8`).",
                    file=sys.stderr,
                )
                return 1
        texto = "\n\n".join(partes)
    else:
        texto = sys.stdin.read()

    saida = mapa_reverso.reidratar(texto, mapa)

    # Rótulo que sobrou é informação, não ruído: significa que o texto fala de
    # alguém que este mapa não conhece — autos trocados, ou peça anonimizada
    # noutra sessão. Silenciar entregaria um documento com lacuna invisível.
    #
    # `finditer` e `group(0)`, e não `findall`: desde a Task 10b a expressão tem
    # dois grupos de captura (o rótulo e o índice, que o `semear` precisa ler),
    # e `findall` com grupos devolve as TUPLAS, não a etiqueta inteira. O aviso
    # sairia como `('PESSOA', '7')` — ou nem sairia, porque o `join` recusa
    # tupla. Um `findall` aqui é a mesma classe de defeito que esta rodada vem
    # fechando: código que continua parecendo certo depois de o contrato mudar.
    sobraram = sorted({m.group(0) for m in mapa_reverso.RE_ROTULO.finditer(saida)})
    if sobraram:
        print(
            f"aviso: {len(sobraram)} rótulo(s) sem entrada no mapa, deixados "
            f"como estão: {', '.join(sobraram)}",
            file=sys.stderr,
        )

    _escrever(args.output, saida)
    return 0


def cmd_ocr(args) -> int:
    modo, sessao = _resolver(args)
    caminho = Path(args.imagem)
    if not caminho.exists():
        print(f"erro: {caminho} não existe", file=sys.stderr)
        return 1

    if modo == "remoto":
        token = _exigir_credencial()
        import mimetypes
        import urllib.request
        import uuid

        limite = f"----tecjustica{uuid.uuid4().hex}"
        tipo = mimetypes.guess_type(caminho.name)[0] or "image/png"
        corpo = bytearray()
        corpo += f"--{limite}\r\n".encode()
        corpo += (
            f'Content-Disposition: form-data; name="file"; filename="{caminho.name}"\r\n'
        ).encode()
        corpo += f"Content-Type: {tipo}\r\n\r\n".encode()
        corpo += caminho.read_bytes()
        corpo += f"\r\n--{limite}--\r\n".encode()

        requisicao = urllib.request.Request(
            f"{sessao.base}/v1/ocr",
            data=bytes(corpo),
            headers={
                "Content-Type": f"multipart/form-data; boundary={limite}",
                "X-Presidio-Token": token,
            },
            method="POST",
        )
        with urllib.request.urlopen(requisicao, timeout=local.TIMEOUT_LONGO_S) as r:
            resultados = json.loads(r.read().decode("utf-8"))["results"]
    else:
        import ocr_engine

        resultados = ocr_engine.reconhecer(caminho.read_bytes())

    if args.format == "json":
        _escrever(args.output, json.dumps(resultados, ensure_ascii=False, indent=2))
    else:
        _escrever(args.output, "\n".join(r["text"] for r in resultados))
    return 0


def cmd_mcp(args) -> int:
    import mcp_server

    return mcp_server.executar()


class _NoOp:
    """Contexto vazio, para o modo remoto não precisar de um `if` no `with`."""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


# ---------------------------------------------------------------------------
# Linha de comando
# ---------------------------------------------------------------------------


def construir_parser() -> argparse.ArgumentParser:
    pai = argparse.ArgumentParser(add_help=False)
    pai.add_argument("-o", "--output", help="Arquivo de saída (padrão: stdout).")
    pai.add_argument(
        "-f", "--format", choices=["text", "json"], default="text",
        help="text = só o conteúdo; json = com a lista de ocorrências.",
    )
    pai.add_argument(
        "--offline", action="store_true",
        help="Carrega o motor neste processo, mesmo com o aplicativo aberto.",
    )
    pai.add_argument(
        "--remoto", action="store_true",
        help="Exige o aplicativo aberto; falha em vez de carregar o motor.",
    )
    pai.add_argument("-q", "--quiet", action="store_true",
                     help="Suprime as mensagens de progresso no stderr.")

    anonimizacao = argparse.ArgumentParser(add_help=False)
    anonimizacao.add_argument(
        "-e", "--entities",
        help="Entidades a mascarar, separadas por vírgula. Padrão: todas.",
    )
    anonimizacao.add_argument(
        "-m", "--mascara", choices=POLITICAS, default=POLITICA_PADRAO,
        help=(
            "placeholder = [PESSOA_1] (nada permanece); "
            "parcial = J**** d* S**** (mantém iniciais); "
            "total = ************* (esconde até o formato)"
        ),
    )
    anonimizacao.add_argument("--output-dir", help="Pasta de saída (lote).")
    anonimizacao.add_argument(
        "--in-place", action="store_true",
        help="Sobrescreve os arquivos de entrada.",
    )
    anonimizacao.add_argument(
        "--nlp-mode", choices=["transformer", "spacy"],
        help="Sobrescreve PRESIDIO_NLP_MODE nesta execução (só no modo offline).",
    )
    anonimizacao.add_argument(
        "--autos", metavar="ID",
        help=(
            "Dá a estas peças um espaço de pseudônimos comum e grava o mapa "
            "cifrado, para depois usar em `reidratar`. Sem isto, cada arquivo "
            "numera do zero e o mapa é descartado."
        ),
    )

    parser = argparse.ArgumentParser(
        prog="tecjustica-sigilo",
        description=(
            "Anonimiza dados pessoais (CPF, CNPJ, RG, nomes, processos CNJ) "
            "em documentos judiciais brasileiros. Roda inteiramente nesta máquina."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="comando")

    p = sub.add_parser("anonimizar", parents=[pai, anonimizacao],
                       help="Mascara os dados pessoais de um ou mais arquivos.")
    p.add_argument("files", nargs="*", help="Arquivos. Sem argumento, lê de stdin.")
    p.set_defaults(func=cmd_anonimizar)

    p = sub.add_parser("ler", parents=[pai],
                       help="Extrai o texto (com OCR quando preciso), sem anonimizar.")
    p.add_argument("files", nargs="+")
    p.set_defaults(func=cmd_ler)

    p = sub.add_parser(
        "reidratar", parents=[pai],
        help="Devolve os nomes reais a um texto que voltou mascarado de fora.",
    )
    p.add_argument(
        "files", nargs="*",
        help="Arquivos de texto. Sem argumento, lê de stdin.",
    )
    p.add_argument(
        "--autos", required=True, metavar="ID",
        help="Os autos cujo mapa usar (o mesmo ID passado no `anonimizar`).",
    )
    p.set_defaults(func=cmd_reidratar)

    p = sub.add_parser("ocr", parents=[pai], help="Reconhece o texto de uma imagem.")
    p.add_argument("imagem")
    p.set_defaults(func=cmd_ocr)

    p = sub.add_parser("status", help="Mostra se o aplicativo está no ar e como.")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("conectar", help="Autoriza esta CLI junto ao aplicativo.")
    p.set_defaults(func=cmd_conectar)

    p = sub.add_parser("mcp", help="Servidor MCP em stdio, para agentes.")
    p.set_defaults(func=cmd_mcp)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Forma clássica preservada: `tecjustica-sigilo arquivo.txt -o saida.txt`
    # continua valendo. Sem isto, quem já usa a CLI em script veria o comando
    # quebrar da noite para o dia — e o custo de manter é uma linha.
    comandos = {"anonimizar", "ler", "ocr", "status", "conectar", "mcp", "reidratar"}
    if not argv or (argv[0] not in comandos and not argv[0].startswith("-")):
        argv = ["anonimizar", *argv]
    elif argv and argv[0].startswith("-") and argv[0] not in {"-h", "--help"}:
        argv = ["anonimizar", *argv]

    args = construir_parser().parse_args(argv)

    if getattr(args, "nlp_mode", None):
        os.environ["PRESIDIO_NLP_MODE"] = args.nlp_mode

    funcao = getattr(args, "func", None)
    if funcao is None:
        construir_parser().print_help()
        return 1

    try:
        return funcao(args)
    except SystemExit as saida:
        if isinstance(saida.code, str):
            print(saida.code, file=sys.stderr)
            return 2
        return saida.code or 0
    except FileNotFoundError as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrompido", file=sys.stderr)
        return 130
    except Exception as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
