import { expect, test } from "bun:test";
import { gunzipSync } from "node:zlib";
import { Effect, Either } from "effect";
import { parsePmspPage, pmspNorm } from "./pmsp";
import { Source } from "./catalog";
import { convert } from "./convert";

const listing = gunzipSync(await Bun.file("scripts/fixtures/pmsp-2026.html.gz").arrayBuffer()).toString("utf8");

test("PMSP identifica a lei pelo município, data e número, com paginação independente", async () => {
  const page = await Effect.runPromise(parsePmspPage(listing));
  expect(page.pagina).toBe(1);
  expect(page.paginas).toBe(2);
  expect(page.total).toBe(184);
  expect(page.normas.length + page.pendencias.length).toBe(100);
  expect(page.normas[0]?.id).toBe("br-municipal-3550308-lei-2026-10-16-18562");
  expect(page.normas[0]?.data).toBe("2026-10-16");
});

test("PMSP distingue resultado vazio de página inválida ou busca truncada", async () => {
  const empty = gunzipSync(await Bun.file("scripts/fixtures/pmsp-empty.html.gz").arrayBuffer()).toString("utf8");
  expect((await Effect.runPromise(parsePmspPage(empty))).total).toBe(0);
  for (const html of ["<html>Erro</html>", listing.replace("de 184", "de 10000")]) {
    expect(Either.isLeft(await Effect.runPromise(parsePmspPage(html).pipe(Effect.either)))).toBe(true);
  }
  const invalid = await Effect.runPromise(pmspNorm({ fonte: "https://legislacao.prefeitura.sp.gov.br/leis/lei-1", titulo: "LEI Nº 1 de 31 de Fevereiro de 2026" }).pipe(Effect.either));
  expect(Either.isLeft(invalid)).toBe(true);
});

test("PMSP converte só a íntegra legal, sem navegação, compartilhamento ou cookies", async () => {
  const page = await Effect.runPromise(parsePmspPage(listing));
  const norm = page.normas[0];
  expect(norm).toBeDefined();
  if (norm === undefined) return;
  const html = gunzipSync(await Bun.file("scripts/fixtures/pmsp-texto.html.gz").arrayBuffer()).toString("utf8");
  const source = Source.make(norm);
  const markdown = await Effect.runPromise(convert(source, html));
  expect(markdown).toContain("Programa Municipal ‘Sonho Grande’");
  expect(markdown).toContain("Art. 4º");
  expect(markdown).not.toContain("Pesquisa de Satisfação");
  expect(markdown).not.toContain("Detalhes da Norma");
  const wrong = await Effect.runPromise(convert({ ...source, titulo: "Outra lei" }, html).pipe(Effect.either));
  expect(Either.isLeft(wrong)).toBe(true);
});


test("PMSP mantém resultado de outro tipo como pendência em vez de publicá-lo como lei", async () => {
  const page = await Effect.runPromise(parsePmspPage(listing.replace('href="/leis/lei-18562-', 'href="/leis/portaria-legislativo-18562-')));
  expect(page.normas).toHaveLength(99);
  expect(page.pendencias).toHaveLength(1);
  expect(page.pendencias[0]?.fonte).toContain("portaria-legislativo");
});


test("PMSP aceita o total simples de ano com uma única página", async () => {
  const html = gunzipSync(await Bun.file("scripts/fixtures/pmsp-1983.html.gz").arrayBuffer()).toString("utf8");
  const page = await Effect.runPromise(parsePmspPage(html));
  expect(page.total).toBe(97);
  expect(page.paginas).toBe(1);
  expect(page.normas.length + page.pendencias.length).toBe(97);
});
