/**
 * A marca do produto.
 *
 * O símbolo vem do SVG da referência de desenho: um selo cobalto com escudo e
 * o ponto de sigilo. Ele é **desenhado**, não uma imagem — o `logo.png` de
 * antes tinha 12 KB e ficava serrilhado em tela de alta densidade, e um
 * arquivo raster não acompanha tamanho nem cor.
 *
 * As cores do selo são literais de propósito. Marca não muda com tema: o
 * cobalto continua cobalto no escuro, como acontece em qualquer aplicativo que
 * tenha identidade. O que acompanha o tema é a assinatura ao lado, que é
 * texto do aplicativo e não parte do símbolo.
 */

export function Simbolo({ tamanho = 32 }: { tamanho?: number }) {
  return (
    <svg
      width={tamanho}
      height={tamanho}
      viewBox="0 0 40 40"
      fill="none"
      aria-hidden="true"
      focusable="false"
      className="shrink-0"
    >
      <rect x="0" y="0" width="40" height="40" rx="11" fill="#1D4ED8" />
      <path
        d="M20 9L30 13.5V21C30 27 25.8 32.6 20 34C14.2 32.6 10 27 10 21V13.5L20 9Z"
        fill="#FFFFFF"
        fillOpacity="0.16"
        stroke="#FFFFFF"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <circle cx="20" cy="19.5" r="3.2" fill="#60A5FA" />
      <path d="M20 22.8V26.2" stroke="#60A5FA" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}

interface MarcaProps {
  /** Versão do aplicativo, escrita embaixo do nome. */
  versao: string;
  /** No rail estreito só o símbolo aparece. */
  compacta?: boolean;
}

export function Marca({ versao, compacta = false }: MarcaProps) {
  return (
    <div className="flex items-center gap-gutter-sm">
      <Simbolo tamanho={compacta ? 28 : 32} />
      {!compacta && (
        <div className="flex min-w-0 flex-col">
          <span className="font-display text-headline-sm text-primary">Sigilo</span>
          <span className="font-mono text-mono-tag text-on-surface-variant uppercase">
            v{versao} local
          </span>
        </div>
      )}
    </div>
  );
}
