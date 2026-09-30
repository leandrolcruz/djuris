/**
 * A moldura por plataforma.
 *
 * O porte para macOS achou aqui o primeiro defeito, e ele era invisível no
 * Windows por construção: `titleBarOverlay` e `setTitleBarOverlay` só existem
 * lá e no Linux. No Mac o método não existe, e o handler de troca de tema
 * morria com `TypeError` a cada clique — no log, sem nada que apontasse para
 * a barra de título.
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  ALTURA_MOLDURA,
  moldurAceitaPintura,
  opcoesDeMoldura,
  recuoDosSemaforos,
} from "../dist-electron/moldura.js";

const CORES = { fundo: "#faf8ff", simbolo: "#131b2e" };

test("no Windows a moldura é sobreposição pintada pelo aplicativo", () => {
  const o = opcoesDeMoldura("win32", CORES);
  assert.equal(o.titleBarStyle, "hidden");
  assert.deepEqual(o.titleBarOverlay, {
    color: "#faf8ff",
    symbolColor: "#131b2e",
    height: ALTURA_MOLDURA,
  });
  assert.equal(o.trafficLightPosition, undefined);
});

test("no Linux vale o mesmo que no Windows", () => {
  assert.deepEqual(opcoesDeMoldura("linux", CORES), opcoesDeMoldura("win32", CORES));
});

test("no macOS não se manda titleBarOverlay, que lá não existe", () => {
  const o = opcoesDeMoldura("darwin", CORES);
  assert.equal(o.titleBarOverlay, undefined);
  // `hidden`, não `hiddenInset`: só com `hidden` a posição dos semáforos é
  // respeitada. Com `hiddenInset` o sistema ignora a nossa e põe os botões
  // onde quiser — foi assim que eles continuaram caindo sobre a marca.
  assert.equal(o.titleBarStyle, "hidden");
});

test("no macOS os semáforos são centrados na faixa, não encostados no topo", () => {
  const { trafficLightPosition } = opcoesDeMoldura("darwin", CORES);
  assert.ok(trafficLightPosition, "sem posição, os botões caem sobre a marca");
  // Centrado: sobra a mesma folga acima e abaixo dos 16px do botão.
  assert.equal(trafficLightPosition.y, (ALTURA_MOLDURA - 16) / 2);
  assert.ok(trafficLightPosition.x > 0);
});

test("só quem tem sobreposição aceita repintura no troca-tema", () => {
  assert.equal(moldurAceitaPintura("win32"), true);
  assert.equal(moldurAceitaPintura("linux"), true);
  // No macOS quem pinta os semáforos é o sistema, que já segue o tema.
  assert.equal(moldurAceitaPintura("darwin"), false);
});

test("o recuo do conteúdo só existe onde os botões ficam à esquerda", () => {
  assert.ok(recuoDosSemaforos("darwin") > 52, "os três botões ocupam ~52px");
  assert.equal(recuoDosSemaforos("win32"), 0);
  assert.equal(recuoDosSemaforos("linux"), 0);
});
