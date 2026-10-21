import { expect, test } from "bun:test";
import { gunzipSync } from "node:zlib";
import { Effect, Either, Schema } from "effect";
import { AlmgDocument, almgNormFromRecord, extractAlmgHtml, parseAlmgCsv, projectAlmgRecords } from "./almg";
import { Source } from "./catalog";
import { convert } from "./convert";

const records = await Effect.runPromise(parseAlmgCsv(gunzipSync(await Bun.file("catalogos/almg/2026.fonte.csv.gz").arrayBuffer()).toString("utf8")));

test("CSV oficial preserva campos multilinha e contabiliza todas as famílias", async () => {
  expect(records.length).toBeGreaterThan(0);
  expect(records.some((record) => record.Ementa.includes("\n"))).toBe(true);
  const projection = await Effect.runPromise(projectAlmgRecords(records));
  expect(projection.normas.length + projection.pendencias.length + Object.values(projection.fora_escopo).reduce((sum, count) => sum + count, 0)).toBe(records.length);
  expect(projection.normas.some((norm) => norm.id === "br-mg-lei-2026-01-02-25676")).toBe(true);
});

test("ALMG original é vinculado à identidade e reproduz o texto", async () => {
  const record = records.find((record) => record.Tipo === "LEI" && record.Numero === "25676");
  expect(record).toBeDefined();
  if (record === undefined) return;
  const norm = await Effect.runPromise(almgNormFromRecord(record));
  const bytes = gunzipSync(await Bun.file("scripts/fixtures/almg-original.json.gz").arrayBuffer());
  const response = Schema.decodeUnknownSync(Schema.parseJson(AlmgDocument))(bytes.toString("utf8"));
  const html = await Effect.runPromise(extractAlmgHtml(norm, response));
  const markdown = await Effect.runPromise(convert(Source.make({ id: norm.id, titulo: norm.titulo, data: norm.data, fonte: norm.fonte }), html));
  expect(norm.versao).toBe("publicação original disponibilizada pela ALMG");
  expect(markdown).toContain("Associação de Equoterapia");
  expect(markdown).toContain("Art. 2º");
  expect(markdown).not.toContain("\\n");
  const wrong = await Effect.runPromise(extractAlmgHtml({ ...norm, numero: "25677" }, response).pipe(Effect.either));
  expect(Either.isLeft(wrong)).toBe(true);
});

test("ALMG escolhe o link atualizado e não aceita outra norma como resposta", async () => {
  const record = records.find((record) => record.Tipo === "LEI" && record.Numero === "25698");
  expect(record).toBeDefined();
  if (record === undefined) return;
  const norm = await Effect.runPromise(almgNormFromRecord(record));
  const bytes = gunzipSync(await Bun.file("scripts/fixtures/almg-atualizado.json.gz").arrayBuffer());
  const response = Schema.decodeUnknownSync(Schema.parseJson(AlmgDocument))(bytes.toString("utf8"));
  expect(norm.versao).toBe("texto atualizado disponibilizado pela ALMG");
  expect(await Effect.runPromise(extractAlmgHtml(norm, response))).toContain("Art. 1º");
  const invalidDate = await Effect.runPromise(almgNormFromRecord({ ...record, DataLegislacao: "31/02/2026" }).pipe(Effect.either));
  expect(Either.isLeft(invalidDate)).toBe(true);
});
