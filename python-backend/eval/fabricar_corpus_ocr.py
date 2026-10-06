"""
Fabrica um corpus de OCR a partir de um PDF nativo.

**Por que isto existe.** Dois testes da suíte (`test_deteccao_ocr.py`) dependem
de `PRESIDIO_CORPUS_OCR` apontando para uma pasta com PDF **sem camada de
texto**, e sem ela eles são PULADOS — que em log corrido passa por aprovado. O
corpus original (22 PDFs reais, 125 MB) nunca saiu da máquina de origem.

Varri o acervo desta máquina atrás de substituto e não achei: 40 PDFs testados
entre o gabinete, o Drive e Downloads, incluindo os processos FÍSICOS
digitalizados — todos já vêm OCRizados, porque o Projudi gera PDF nativo e o
fluxo do escritório reconhece o resto. Ausência de material, não descuido.

**O que este script fabrica, e o que isso prova.** Ele rasteriza páginas de um
PDF nativo: a imagem resultante não tem camada de texto, que é a condição que o
teste exige. Gera dois arquivos:

- `escaneado-sintetico`: rasterização limpa, 200 dpi;
- `escaneado-degradado`: 150 dpi mais o que uma digitalização de verdade faz —
  papel torto, foco mole, sujeira de sensor e contraste baixo.

Medido em 06/10/2026, palavras recuperadas contra o texto do PDF original:

    escaneado-sintetico    94,7%
    escaneado-degradado    77,0%

**O limite, dito com todas as letras:** isto é um PISO, não prova de robustez.
Rasterização não reproduz o pior de uma digitalização real — papel amarelado,
carimbo por cima, fotocópia de fotocópia, datilografado. O número que importa
para o produto continua sendo o do corpus real, e ele não está aqui.

Uso:
    python -m eval.fabricar_corpus_ocr <pdf-nativo> <pasta-destino> [n-páginas]
"""

from __future__ import annotations

import random
import sys
from pathlib import Path


def _paginas(origem: Path, quantas: int, dpi: int):
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(origem))
    for i in range(min(quantas, len(doc))):
        yield doc[i].render(scale=dpi / 72).to_pil()


def limpo(origem: Path, destino: Path, quantas: int = 3) -> Path:
    saida = destino / "escaneado-sintetico-3pag.pdf"
    imgs = [p.convert("RGB") for p in _paginas(origem, quantas, 200)]
    imgs[0].save(saida, save_all=True, append_images=imgs[1:], resolution=200)
    return saida


def degradado(origem: Path, destino: Path, quantas: int = 3, semente: int = 42) -> Path:
    from PIL import ImageFilter

    rnd = random.Random(semente)  # semente fixa: o corpus é o mesmo em toda máquina
    saida = destino / "escaneado-degradado-3pag.pdf"
    imgs = []
    for img in _paginas(origem, quantas, 150):
        img = img.convert("L")
        img = img.rotate(rnd.uniform(-0.8, 0.8), expand=False, fillcolor=255)
        img = img.filter(ImageFilter.GaussianBlur(0.6))
        px = img.load()
        for _ in range(img.width * img.height // 400):
            x, y = rnd.randrange(img.width), rnd.randrange(img.height)
            px[x, y] = rnd.choice((0, 255))
        img = img.point(lambda v: min(255, int(v * 0.88) + 28))
        imgs.append(img.convert("RGB"))
    imgs[0].save(saida, save_all=True, append_images=imgs[1:], resolution=150)
    return saida


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    origem, destino = Path(sys.argv[1]), Path(sys.argv[2])
    quantas = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    destino.mkdir(parents=True, exist_ok=True)

    for caminho in (limpo(origem, destino, quantas), degradado(origem, destino, quantas)):
        print(f"{caminho.name}: {caminho.stat().st_size // 1024} KB")

    print(f"\nAponte PRESIDIO_CORPUS_OCR para {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
