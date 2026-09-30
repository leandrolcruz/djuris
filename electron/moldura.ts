/**
 * A moldura da janela, decidida por plataforma.
 *
 * O aplicativo esconde a barra de título do sistema e desenha a própria — é o
 * que separa "programa" de "página dentro de uma moldura". Só que esconder a
 * barra significa coisas diferentes em cada sistema, e o código nasceu
 * sabendo de um só:
 *
 * - **Windows e Linux** têm `titleBarOverlay`: os botões da janela viram uma
 *   sobreposição cuja cor o aplicativo escolhe, e que acompanha o tema.
 * - **macOS não tem.** `setTitleBarOverlay` nem existe lá, e chamá-lo derruba
 *   o handler com `TypeError` — que foi o primeiro erro a aparecer no porte,
 *   a cada troca de tema. Os botões são os três semáforos, o sistema é quem
 *   os pinta, e o que o aplicativo controla é **onde** eles ficam.
 *
 * E ficam onde a barra lateral põe a marca: canto superior esquerdo. Sem
 * posicioná-los, os semáforos caem em cima do logotipo. `hiddenInset` já os
 * afasta um pouco; `trafficLightPosition` os centra na faixa de
 * `ALTURA_MOLDURA`, e `RECUO_SEMAFOROS` diz ao renderer quanto reservar à
 * esquerda para eles.
 */

/** Altura da faixa que o aplicativo usa como barra de título. */
export const ALTURA_MOLDURA = 64;

/**
 * Quanto o conteúdo precisa recuar à esquerda para não ficar sob os semáforos.
 *
 * Os três botões do macOS ocupam ~52px mais a margem esquerda; 78 dá folga sem
 * abrir um vão visível. Zero em toda outra plataforma, onde os botões ficam à
 * direita.
 */
export const RECUO_SEMAFOROS = 78;

export type CoresDaMoldura = { fundo: string; simbolo: string };

export type OpcoesDeMoldura = {
  titleBarStyle: "hidden" | "hiddenInset";
  titleBarOverlay?: { color: string; symbolColor: string; height: number };
  trafficLightPosition?: { x: number; y: number };
};

/** As opções de `BrowserWindow` que desenham a moldura nesta plataforma. */
export function opcoesDeMoldura(
  plataforma: NodeJS.Platform,
  cores: CoresDaMoldura
): OpcoesDeMoldura {
  if (plataforma === "darwin") {
    return {
      // `hidden`, e NÃO `hiddenInset`: a posição dos semáforos só é respeitada
      // com `hidden`. Com `hiddenInset` o sistema aplica o recuo dele e ignora
      // a nossa `trafficLightPosition` — foi a primeira tentativa, e os botões
      // continuaram caindo sobre a marca. Com `hidden` a posição é nossa, e
      // determinística: os três ocupam de x até x+52.
      titleBarStyle: "hidden",
      // Centrado na faixa: os semáforos têm 16px de altura, então metade da
      // diferença os alinha com o texto da marca em vez de encostá-los no topo.
      trafficLightPosition: { x: 18, y: (ALTURA_MOLDURA - 16) / 2 },
    };
  }
  return {
    titleBarStyle: "hidden",
    titleBarOverlay: {
      color: cores.fundo,
      symbolColor: cores.simbolo,
      height: ALTURA_MOLDURA,
    },
  };
}

/**
 * Se vale repintar a moldura quando o tema troca.
 *
 * No macOS não vale, e não é limitação: quem pinta os semáforos é o sistema, e
 * ele já os ajusta ao tema claro ou escuro sozinho. A pergunta existe para que
 * o handler NÃO chame um método que não existe — o `TypeError` aparecia no log
 * a cada troca de tema e não dizia nada sobre a causa.
 */
export function moldurAceitaPintura(plataforma: NodeJS.Platform): boolean {
  return plataforma !== "darwin";
}

/** Recuo à esquerda que o conteúdo precisa, em pixels. */
export function recuoDosSemaforos(plataforma: NodeJS.Platform): number {
  return plataforma === "darwin" ? RECUO_SEMAFOROS : 0;
}
