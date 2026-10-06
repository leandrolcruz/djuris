/**
 * O preload não pode importar módulo do projeto.
 *
 * Ele roda em SANDBOX, onde `require` de arquivo relativo não resolve. A
 * exceção derruba o preload inteiro e `window.electronAPI` simplesmente não
 * existe — e nada disso aparece no terminal. A interface sobe, o cofre fica
 * "indisponível", o backend parece mudo, e não há uma linha de log apontando
 * para o preload.
 *
 * Aconteceu de verdade em 30/09/2026: um `import { recuoDosSemaforos } from
 * "./moldura"` acrescentado ao preload derrubou o bridge inteiro do aplicativo.
 * Passou por typecheck, passou pelas 96 do Node, passou pelo build, e só
 * apareceu quando a interface foi olhada de perto — duas tentativas de
 * conserto DEPOIS, porque o sintoma visível (botões da janela sobre a marca)
 * não tinha relação óbvia com a causa.
 *
 * O que precisa de lógica é calculado no main e chega por
 * `additionalArguments`.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PRELOAD = path.join(RAIZ, "dist-electron", "preload.js");

test("o preload compilado não faz require de módulo do projeto", () => {
  const fonte = readFileSync(PRELOAD, "utf8");
  const locais = [...fonte.matchAll(/require\(["'](\.[^"']*)["']\)/g)].map((m) => m[1]);
  assert.deepEqual(
    locais,
    [],
    `o preload roda em sandbox e não resolve estes require: ${locais.join(", ")}. ` +
      `Calcule no main e passe por additionalArguments.`
  );
});

test("o preload só requer módulos que o sandbox oferece", () => {
  const fonte = readFileSync(PRELOAD, "utf8");
  const todos = [...fonte.matchAll(/require\(["']([^"']+)["']\)/g)].map((m) => m[1]);
  const permitidos = new Set(["electron"]);
  const proibidos = todos.filter((m) => !permitidos.has(m));
  assert.deepEqual(proibidos, [], `fora do que o sandbox oferece: ${proibidos.join(", ")}`);
});

test("o recuo dos semáforos chega por argumento, não por import", () => {
  const fonte = readFileSync(PRELOAD, "utf8");
  assert.match(fonte, /recuo-semaforos/, "o preload precisa ler o argumento que o main injeta");
});

test("o DevTools não abre sozinho — é opt-in por variável", () => {
  /*
   * O inspetor abria SEMPRE em modo dev. Isso era preferência de quem
   * desenvolve até o aplicativo passar a ser aberto por atalho: como não há
   * build empacotado no macOS, o uso normal É o modo dev, e a janela nascia
   * com metade da tela tomada.
   *
   * O teste lê o main COMPILADO e exige que a chamada esteja sob a condição.
   * Sem isso, um `openDevTools` solto volta na primeira refatoração e ninguém
   * percebe até abrir o aplicativo.
   */
  const fonte = readFileSync(path.join(RAIZ, "dist-electron", "main.js"), "utf8");
  const chamadas = [...fonte.matchAll(/openDevTools\s*\(/g)];
  assert.equal(chamadas.length, 1, "esperava uma única chamada a openDevTools");

  const antes = fonte.slice(0, chamadas[0].index);
  const guarda = antes.lastIndexOf("DJURIS_DEVTOOLS");
  assert.ok(guarda !== -1, "openDevTools precisa estar sob DJURIS_DEVTOOLS");
  assert.ok(
    chamadas[0].index - guarda < 200,
    "a guarda tem de ser a condição imediata, não uma menção distante"
  );
});
