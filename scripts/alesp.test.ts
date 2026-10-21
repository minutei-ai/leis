import { expect, test } from "bun:test";
import { gunzipSync } from "node:zlib";
import { Effect, Either, Schema } from "effect";
import { AlespDetail, AlespPage, alespSource } from "./alesp";
import { Source } from "./catalog";
import { convert, decodeHtml } from "./convert";

const detail = Schema.decodeUnknownSync(Schema.parseJson(AlespDetail))(gunzipSync(await Bun.file("scripts/fixtures/alesp-detail.json.gz").arrayBuffer()).toString("utf8"));

test("Alesp preserva o total independente e o número da página", async () => {
  const page = Schema.decodeUnknownSync(Schema.parseJson(AlespPage))(gunzipSync(await Bun.file("scripts/fixtures/alesp-page.json.gz").arrayBuffer()).toString("utf8"));
  expect(page.content).toHaveLength(2);
  expect(page.totalElements).toBeGreaterThan(page.content.length);
  expect(page.number).toBe(0);
});

test("Alesp valida identidade, prefere versão atualizada e recusa PDF como HTML", async () => {
  const selected = await Effect.runPromise(alespSource(detail, detail));
  expect(selected.id).toBe("br-sp-norma-197700");
  expect(selected.data).toBe("2021-03-31");
  expect(selected.versao).toBe("publicação original disponibilizada pela Alesp");
  const updated = await Effect.runPromise(alespSource(detail, { ...detail, urlIntegraAtualizada: detail.urlIntegraOriginal }));
  expect(updated.versao).toBe("texto atualizado disponibilizado pela Alesp");
  for (const invalid of [{ ...detail, idNorma: "1" }, { ...detail, urlIntegraOriginal: "https://www.al.sp.gov.br/repositorio/legislacao/texto.pdf" }, { ...detail, urlIntegraOriginal: "https://example.com/texto.html" }]) {
    const result = await Effect.runPromise(alespSource(detail, invalid).pipe(Effect.either));
    expect(Either.isLeft(result)).toBe(true);
  }
});

test("Alesp converte Artigo por extenso e preserva acentos da fonte Windows-1252", async () => {
  const selected = await Effect.runPromise(alespSource(detail, detail));
  const source = Source.make({ id: selected.id, titulo: detail.nomeNorma, data: selected.data, fonte: selected.fonte });
  const raw = gunzipSync(await Bun.file("scripts/fixtures/alesp-texto.html.gz").arrayBuffer());
  const text = await Effect.runPromise(convert(source, decodeHtml(source, raw)));
  expect(text).toContain("Hospital Veterinário");
  expect(text).toContain("Artigo 1º");
  expect(text).toContain("Ribeirão Preto");
  expect(text).not.toContain("�");
});
