import { expect, test } from "bun:test";
import { gunzipSync } from "node:zlib";
import { Effect, Either, Schema } from "effect";
import { Source } from "./catalog";
import { convert } from "./convert";
import {
  Family,
  InventoryResponse,
  inventoryRecords,
  Norm,
  NormResponse,
  normFromRecord,
  selectEncoding,
} from "./senado";

const cdc = Norm.make({
  senadoId: "549954",
  tipo: "LEI",
  id: "br-federal-lei-1990-09-11-8078",
  titulo: "Código de Defesa do Consumidor",
  data: "1990-09-11",
  numero: "8078",
  urn: "urn:lex:br:federal:lei:1990-09-11;8078",
  ementa: "Dispõe sobre a proteção do consumidor",
});

test("catálogo vazio oficial é distinto de payload inválido", async () => {
  const bytes = gunzipSync(
    await Bun.file("scripts/fixtures/senado-empty.json.gz").arrayBuffer(),
  );
  const decoded = Schema.decodeUnknownSync(Schema.parseJson(InventoryResponse))(
    bytes.toString("utf8"),
  );
  expect(inventoryRecords(decoded)).toEqual([]);
  expect(Either.isLeft(Schema.decodeUnknownEither(InventoryResponse)({}))).toBe(
    true,
  );
});

test("identidade vem de tipo, data e número e rejeita datas impossíveis", async () => {
  const record = {
    id: "1",
    tipo: "LEI-n",
    numero: "8078",
    normaNome: "Lei nº 8.078",
    dataassinatura: "11/09/1990",
  };
  const norm = await Effect.runPromise(normFromRecord(record, "LEI"));
  expect(norm.urn).toBe(cdc.urn);
  expect(norm.id).toBe(cdc.id);
  const suffixed = await Effect.runPromise(
    normFromRecord(
      {
        ...record,
        numero: "5422",
        complemento: "A",
        dataassinatura: "25/04/1968",
      },
      "LEI",
    ),
  );
  expect(suffixed.urn).toBe("urn:lex:br:federal:lei:1968-04-25;5422-a");
  expect(suffixed.id).toBe("br-federal-lei-1968-04-25-5422-a");
  for (const invalid of [
    { ...record, dataassinatura: "31/02/1990" },
    { ...record, tipo: "DEL" },
    { ...record, numero: "" },
  ]) {
    const result = await Effect.runPromise(
      normFromRecord(invalid, "LEI").pipe(Effect.either),
    );
    expect(Either.isLeft(result)).toBe(true);
  }
  expect(Either.isLeft(Schema.decodeUnknownEither(Family)("OUTRO"))).toBe(true);
});

test("prefere compilação atual e valida URN antes de baixar HTML", async () => {
  const bytes = gunzipSync(
    await Bun.file("scripts/fixtures/cdc.json.gz").arrayBuffer(),
  );
  const details = Schema.decodeUnknownSync(Schema.parseJson(NormResponse))(
    bytes.toString("utf8"),
  );
  const encoding = await Effect.runPromise(selectEncoding(cdc, details));
  expect(encoding.versao).toBe("compilação atual disponibilizada pelo Senado");
  expect(encoding.fonte).toContain("/api/public/binario/");
  const result = await Effect.runPromise(
    selectEncoding(
      { ...cdc, urn: "urn:lex:br:federal:lei:1990-09-11;8079" },
      details,
    ).pipe(Effect.either),
  );
  expect(Either.isLeft(result)).toBe(true);
  const html = gunzipSync(
    await Bun.file("scripts/fixtures/cdc.html.gz").arrayBuffer(),
  ).toString("utf8");
  const markdown = await Effect.runPromise(
    convert(
      Source.make({
        id: cdc.id,
        titulo: cdc.titulo,
        data: cdc.data,
        fonte: encoding.fonte,
      }),
      html,
    ),
  );
  expect(markdown).toContain("Art. 1º");
  expect(markdown).toContain("Art. 119");
  expect(markdown).toContain("consumidor");
});

test("publicação original é explícita e ausência de texto não vira sucesso", async () => {
  const bytes = gunzipSync(
    await Bun.file("scripts/fixtures/original.json.gz").arrayBuffer(),
  );
  const details = Schema.decodeUnknownSync(Schema.parseJson(NormResponse))(
    bytes.toString("utf8"),
  );
  const original = Norm.make({
    ...cdc,
    senadoId: "44095919",
    id: "br-federal-lei-2026-09-29-15526",
    numero: "15526",
    data: "2026-09-29",
    urn: "urn:lex:br:federal:lei:2026-09-29;15526",
    titulo: "Lei nº 15.526",
  });
  const encoding = await Effect.runPromise(selectEncoding(original, details));
  expect(encoding.versao).toBe(
    "publicação original disponibilizada pelo Senado",
  );
  const missing = await Effect.runPromise(
    selectEncoding(original, { ...details, encoding: undefined }).pipe(
      Effect.either,
    ),
  );
  expect(Either.isLeft(missing)).toBe(true);
});
