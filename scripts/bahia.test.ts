import { expect, test } from "bun:test";
import { mkdtemp, rm, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { gunzipSync } from "node:zlib";
import { Effect, Either } from "effect";
import { bahiaSource, parseBahiaPage } from "./bahia";
import { convert } from "./convert";

const listing = gunzipSync(await Bun.file("scripts/fixtures/bahia-lista.html.gz").arrayBuffer()).toString("utf8");
const html = gunzipSync(await Bun.file("scripts/fixtures/bahia-texto.html.gz").arrayBuffer()).toString("utf8");

test("Bahia reproduz total e links nativos de paginação por categoria", async () => {
  const page = await Effect.runPromise(parseBahiaPage(listing, "5", 0));
  expect(page.total).toBe(60);
  expect(page.normas).toHaveLength(20);
  expect(page.proxima).toContain("page=1");
  expect(page.ultima).toBe(2);
});

test("Bahia rejeita página truncada, filtro divergente e resposta sem catálogo", async () => {
  for (const content of ["<html>Verificação de segurança</html>", listing.replace("1 - 20 de 60", "1 - 19 de 60"), listing.replaceAll("categoria%5B5%5D=5", "categoria%5B5%5D=7")])
    expect(Either.isLeft(await Effect.runPromise(parseBahiaPage(content, "5", 0).pipe(Effect.either)))).toBe(true);
});

test("Bahia confere identidade imutável e converte a íntegra sem navegação", async () => {
  const page = await Effect.runPromise(parseBahiaPage(listing, "5", 0));
  const link = page.normas[0];
  expect(link).toBeDefined();
  if (link === undefined) return;
  const source = await Effect.runPromise(bahiaSource(link, html));
  expect(source.id).toBe("br-ba-norma-149152");
  expect(source.data).toBe("2026-08-17");
  const markdown = await Effect.runPromise(convert(source, html));
  expect(markdown).toContain("Art. 1º");
  expect(markdown).toContain("Art. 6º");
  expect(markdown).not.toContain("Pesquisa Avançada");
  expect(markdown).not.toContain("Font Definitions");
  for (const content of [html.replaceAll("node/149152", "node/1"), html.replaceAll("2026-08-17T", "2026-02-31T")])
    expect(Either.isLeft(await Effect.runPromise(bahiaSource(link, content).pipe(Effect.either)))).toBe(true);
  expect(Either.isLeft(await Effect.runPromise(bahiaSource({ ...link, titulo: "Outra lei" }, html).pipe(Effect.either)))).toBe(true);
});

test("Bahia reconhece o layout histórico com título em div e preserva referências", async () => {
  const old = gunzipSync(await Bun.file("scripts/fixtures/bahia-historico.html.gz").arrayBuffer()).toString("utf8");
  const source = await Effect.runPromise(bahiaSource({ fonte: "https://www.legislabahia.ba.gov.br/documentos/lei-complementar-no-42-de-09-de-julho-de-2015", titulo: "LEI COMPLEMENTAR Nº 42 DE 09 DE JULHO DE 2015" }, old));
  expect(source.id).toBe("br-ba-norma-129546");
  const markdown = await Effect.runPromise(convert(source, old));
  expect(markdown).toContain("FUNPREV");
  expect(markdown).toContain("Ver também");
  expect(markdown).not.toContain("Pesquisa Avançada");
});

test("Bahia suporta lei delegada histórica e ignora parágrafo vazio antes do título", async () => {
  const old = gunzipSync(await Bun.file("scripts/fixtures/bahia-delegada.html.gz").arrayBuffer()).toString("utf8");
  const link = { fonte: "https://www.legislabahia.ba.gov.br/documentos/ld-no-70-de-03-de-junho-de-1983", titulo: "LD Nº 70 DE 03 DE JUNHO DE 1983" };
  const source = await Effect.runPromise(bahiaSource(link, old));
  expect(source.data).toBe("1983-06-03");
  const markdown = await Effect.runPromise(convert(source, old));
  expect(markdown).toContain("Departamento de Edificações Públicas");
  const withAnchor = old.replace('<div class="lei1">', '<p><a id="titulo"></a></p><div class="lei1">');
  expect((await Effect.runPromise(bahiaSource(link, withAnchor))).id).toBe(source.id);
});

test("Bahia compara cabeçalho histórico sem remover a revogação do texto publicado", async () => {
  const old = gunzipSync(await Bun.file("scripts/fixtures/bahia-revogada.html.gz").arrayBuffer()).toString("utf8");
  const link = { fonte: "https://www.legislabahia.ba.gov.br/documentos/lei-complementar-no-13-de-30-de-dezembro-de-1997", titulo: "LC Nº 013 DE 30 DE DEZEMBRO DE 1997" };
  const source = await Effect.runPromise(bahiaSource(link, old));
  const markdown = await Effect.runPromise(convert(source, old));
  expect(markdown).toContain("Revogado pela");
  expect(markdown).toContain("revogado");
  expect(markdown).toContain("Art. 1º");
  expect(Either.isLeft(await Effect.runPromise(bahiaSource({ ...link, titulo: "LC Nº 14 DE 30 DE DEZEMBRO DE 1997" }, old).pipe(Effect.either)))).toBe(true);
});


test("Bahia retoma a descoberta paginada respeitando o orçamento de novas consultas", async () => {
  const directory = await mkdtemp(join(tmpdir(), "leis-bahia-"));
  await symlink(join(import.meta.dir, "../node_modules"), join(directory, "node_modules"), "dir");
  const fixtures = ["bahia-lista.html.gz", "bahia-lista-1.html.gz", "bahia-lista-2.html.gz"].map((file) => join(import.meta.dir, "fixtures", file));
  for (const expected of [0, 1, 2]) {
    const program = `import { gunzipSync } from "node:zlib";
const fixtures = ${JSON.stringify(fixtures)};
globalThis.fetch = async (input) => {
  const url = new URL(input);
  const page = Number(url.searchParams.get("page"));
  console.log("Consulta:" + page);
  const response = new Response(gunzipSync(await Bun.file(fixtures[page]).arrayBuffer()), { headers: { "content-type": "text/html" } });
  Object.defineProperty(response, "url", { value: url.href });
  return response;
};
await import(${JSON.stringify(join(import.meta.dir, "collect-bahia.ts"))});
`;
    await Bun.write(join(directory, "collect.ts"), program);
    const child = Bun.spawn(["bun", "collect.ts", "--categories", "5", "--discover-only", "--pages", "1"], { cwd: directory, stdout: "pipe", stderr: "pipe" });
    expect({ code: await child.exited, stderr: await new Response(child.stderr).text() }).toEqual({ code: 0, stderr: "" });
    const output = await new Response(child.stdout).text();
    expect(output.match(/Consulta:\d+/gu)).toEqual([`Consulta:${expected}`]);
    const inventory = await Bun.file(join(directory, `catalogos/bahia/5-${String(expected).padStart(5, "0")}.json`)).json();
    expect(inventory.pagina.pagina).toBe(expected);
    expect(inventory.pagina.total).toBe(60);
  }
  await rm(directory, { recursive: true });
});

test("Bahia confere emenda com abreviatura e pontuação oficiais distintas", async () => {
  const html = gunzipSync(await Bun.file("scripts/fixtures/bahia-emenda.html.gz").arrayBuffer()).toString("utf8");
  const source = await Effect.runPromise(bahiaSource({ fonte: "https://www.legislabahia.ba.gov.br/documentos/emenda-constituicao-no-33-de-19-de-marco-de-2024", titulo: "EMENDA À CONSTITUIÇÃO Nº 33 DE 19 DE MARÇO DE 2024" }, html));
  expect(source.data).toBe("2024-03-19");
  expect(await Effect.runPromise(convert(source, html))).toContain("Art. 1º");
});
