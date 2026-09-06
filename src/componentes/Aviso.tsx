import { useEffect, useState } from "react";
import { Icone } from "../ui";

/**
 * Aviso flutuante — uma frase, canto inferior direito, some sozinho.
 *
 * Cartão sobre a mesa, com o ícone do sistema e a cor só no ícone: um aviso de
 * sucesso inteiro em verde grita mais do que a notícia merece.
 *
 * Mensagens longas (as que trazem caminho de arquivo) ficam mais tempo na tela.
 */

interface AvisoProps {
  mensagem: string;
  tipo?: "sucesso" | "erro";
  aoFechar: () => void;
  duracaoMs?: number;
}

export function Aviso({ mensagem, tipo = "sucesso", aoFechar, duracaoMs }: AvisoProps) {
  const [visivel, setVisivel] = useState(false);
  const duracao = duracaoMs ?? (mensagem.length > 40 ? 5000 : 3000);

  useEffect(() => {
    requestAnimationFrame(() => setVisivel(true));
    const timer = setTimeout(() => {
      setVisivel(false);
      setTimeout(aoFechar, 200);
    }, duracao);
    return () => clearTimeout(timer);
  }, [duracao, aoFechar]);

  const sucesso = tipo === "sucesso";

  return (
    <div
      role={sucesso ? "status" : "alert"}
      /* z-200: acima de popover (z-100) e de qualquer painel. Um aviso que
         some atrás de outra coisa não é aviso. */
      className={[
        "fixed right-gutter-lg bottom-gutter-lg z-200 flex max-w-md items-start gap-gutter-sm",
        "rounded-lg bg-surface-container-lowest px-gutter-md py-gutter-sm shadow-lg",
        "transition-[opacity,transform] duration-200",
        visivel ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0",
      ].join(" ")}
    >
      <span className={sucesso ? "mt-0.5 text-secondary" : "mt-0.5 text-error"}>
        <Icone nome={sucesso ? "check_circle" : "error"} tamanho={18} preenchido />
      </span>
      <span className="font-body text-body-md leading-snug text-on-surface">{mensagem}</span>
    </div>
  );
}
