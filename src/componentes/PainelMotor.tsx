import { Botao, Icone } from "../ui";

/**
 * Carregamento e falha do motor, agora como **conteúdo** da casca.
 *
 * Antes eram dois `return` antecipados no `App`, colocados acima da barra
 * lateral: sequestravam a janela inteira e deixavam o aplicativo sem navegação
 * durante um carregamento que chega a 180 s na primeira execução com BERT.
 * Aqui eles ocupam só a área à direita do trilho, que continua montado — dá
 * para ir aos Ajustes ou às Conexões enquanto o motor sobe.
 */

export function MotorCarregando({ modoNlp }: { modoNlp: string }) {
  return (
    <div className="flex flex-1 items-center justify-center bg-background px-gutter-xl">
      <div className="animate-fade-in text-center">
        {/* Sem rotação: um cadeado girando sugere um relógio, não um
            carregamento. Quem indica progresso é a barra abaixo. */}
        <span className="mx-auto grid size-16 place-items-center rounded-xl bg-surface-container text-primary shadow-sm">
          <Icone nome="neurology" tamanho={34} />
        </span>
        <h2 className="mt-gutter-md font-display text-headline-lg text-on-surface">
          Carregando o motor de anonimização
        </h2>
        <p className="mx-auto mt-2 max-w-sm font-body text-body-md text-on-surface-variant">
          {modoNlp === "transformer"
            ? "Iniciando o modelo BERT jurídico. A primeira execução pode levar alguns minutos."
            : "O modelo de linguagem está sendo iniciado."}
        </p>
        <div
          role="progressbar"
          aria-label="Carregando o motor"
          className="mx-auto mt-gutter-lg h-1.5 w-56 overflow-hidden rounded-full bg-surface-container-high"
        >
          <div className="h-full w-1/2 animate-pulse-soft rounded-full bg-primary" />
        </div>
        <p className="mt-gutter-md font-body text-body-sm text-outline">
          O trilho à esquerda continua disponível — dá para ir aos Ajustes ou às
          Conexões enquanto ele sobe.
        </p>
      </div>
    </div>
  );
}

export function MotorComFalha({ aoTentarDeNovo }: { aoTentarDeNovo: () => void }) {
  return (
    <div className="flex flex-1 items-center justify-center bg-background px-gutter-xl">
      <div className="animate-fade-in text-center" role="alert">
        <span className="mx-auto grid size-16 place-items-center rounded-xl bg-error-container/60 text-error shadow-sm">
          <Icone nome="error" tamanho={34} />
        </span>
        <h2 className="mt-gutter-md font-display text-headline-lg text-error">
          O motor de anonimização não respondeu
        </h2>
        <p className="mx-auto mt-2 max-w-sm font-body text-body-md text-on-surface-variant">
          Ele roda como um programa local junto com o aplicativo. Tentar de novo
          costuma resolver; se persistir, feche e abra o aplicativo.
        </p>
        <Botao tipo="primario" icone="refresh" onClick={aoTentarDeNovo} className="mt-gutter-lg">
          Tentar de novo
        </Botao>
      </div>
    </div>
  );
}
