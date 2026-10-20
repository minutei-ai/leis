import { createHash } from "node:crypto";
import { mkdir, rename } from "node:fs/promises";
import { gzipSync } from "node:zlib";
import { Clock, Effect, Schedule, Schema } from "effect";

const Families = Schema.Struct({
  LEI: Schema.Literal("lei"),
  LCP: Schema.Literal("lei.complementar"),
  LDL: Schema.Literal("lei.delegada"),
  DEL: Schema.Literal("decreto.lei"),
  EMC: Schema.Literal("emenda.constitucional"),
});

export const Family = Schema.keyof(Families);

export const InventoryRecord = Schema.Struct({
  id: Schema.String.pipe(Schema.pattern(/^\d+$/)),
  tipo: Schema.NonEmptyString,
  numero: Schema.optional(Schema.NonEmptyString),
  complemento: Schema.optional(
    Schema.String.pipe(Schema.pattern(/^[a-z]+$/iu)),
  ),
  normaNome: Schema.NonEmptyString,
  dataassinatura: Schema.String.pipe(Schema.pattern(/^\d{2}\/\d{2}\/\d{4}$/)),
  ementa: Schema.optional(Schema.String),
});

export const InventoryResponse = Schema.Struct({
  ListaDocumento: Schema.Struct({
    Metadados: Schema.Struct({
      Versao: Schema.String,
      VersaoServico: Schema.Literal("3"),
    }),
    documentos: Schema.Union(
      Schema.Literal(""),
      Schema.Struct({ documento: Schema.Array(InventoryRecord) }),
    ),
  }),
});

export const Norm = Schema.Struct({
  senadoId: InventoryRecord.fields.id,
  tipo: Family,
  id: Schema.String.pipe(Schema.pattern(/^br-federal-[a-z0-9-]+$/)),
  titulo: Schema.NonEmptyString,
  data: Schema.NonEmptyString,
  numero: Schema.NonEmptyString,
  urn: Schema.String.pipe(
    Schema.pattern(/^urn:lex:br:federal:[a-z.]+:\d{4}-\d{2}-\d{2};[0-9a-z-]+$/),
  ),
  ementa: Schema.String,
});

export const Inventory = Schema.Struct({
  fonte: Schema.String,
  tipo: Family,
  ano: Schema.Int,
  coletado_em: Schema.String,
  normas: Schema.Array(Norm),
  pendencias: Schema.Array(InventoryRecord),
});

const Encoding = Schema.Struct({
  contentUrl: Schema.optional(Schema.NullOr(Schema.String)),
  version: Schema.optional(Schema.String),
  encodingFormat: Schema.optional(Schema.String),
  license: Schema.optional(Schema.String),
});

export const NormResponse = Schema.Struct({
  legislationIdentifier: Norm.fields.urn,
  legislationDate: Schema.String,
  encoding: Schema.optional(Schema.Union(Encoding, Schema.Array(Encoding))),
});

export class SourceFailure extends Schema.TaggedError<SourceFailure>()(
  "SourceFailure",
  {
    url: Schema.String,
    motivo: Schema.String,
    status: Schema.optional(Schema.Int),
  },
) {}

export const request = Effect.fn("senado.request")(
  function* (url: string) {
    yield* Effect.sleep("500 millis");
    const response = yield* Effect.tryPromise(() =>
      fetch(url, {
        headers: {
          "User-Agent": "MinuteiLeis/0.2 (+https://github.com/minutei-ai/leis)",
        },
        signal: AbortSignal.timeout(45000),
      }),
    );
    if (!response.ok)
      return yield* Effect.fail(
        new SourceFailure({
          url,
          motivo: `HTTP ${response.status}`,
          status: response.status,
        }),
      );
    if (
      !response.url.startsWith("https://legis.senado.leg.br/dadosabertos/") &&
      !response.url.startsWith("https://normas.leg.br/api/public/")
    )
      return yield* Effect.fail(
        new SourceFailure({
          url,
          motivo: `Redirecionamento inesperado: ${response.url}`,
        }),
      );
    const bytes = new Uint8Array(
      yield* Effect.tryPromise(() => response.arrayBuffer()),
    );
    if (bytes.length > 25000000)
      return yield* Effect.fail(
        new SourceFailure({ url, motivo: "Resposta excede 25 MB" }),
      );
    return bytes;
  },
  Effect.retry({
    times: 2,
    schedule: Schedule.spaced("3 seconds"),
    while: (error) =>
      error._tag === "SourceFailure" &&
      (error.status === 429 || error.status === 503),
  }),
);

export const inventoryRecords = (response: typeof InventoryResponse.Type) => {
  const documents = response.ListaDocumento.documentos;
  if (documents === "") return [];
  return documents.documento;
};

export const normFromRecord = Effect.fn("senado.normFromRecord")(function* (
  record: typeof InventoryRecord.Type,
  family: typeof Family.Type,
) {
  if (record.tipo !== family && !record.tipo.startsWith(`${family}-`))
    return yield* Effect.fail(
      new SourceFailure({
        url: `https://legis.senado.leg.br/dadosabertos/legislacao/${record.id}.json`,
        motivo: "Tipo da norma difere da consulta",
      }),
    );
  if (record.numero === undefined || !/^\d+[a-z-]*$/iu.test(record.numero))
    return yield* Effect.fail(
      new SourceFailure({
        url: `https://legis.senado.leg.br/dadosabertos/legislacao/${record.id}.json`,
        motivo: "Identificação sem número suportado",
      }),
    );
  const parts = record.dataassinatura.split("/");
  const date = `${parts[2]}-${parts[1]}-${parts[0]}`;
  const decodedDate = yield* Schema.decodeUnknown(Schema.DateFromString)(date);
  if (decodedDate.toISOString().slice(0, 10) !== date)
    return yield* Effect.fail(
      new SourceFailure({
        url: record.id,
        motivo: "Data inexistente no calendário",
      }),
    );
  const normType = Families.fields[family].literals[0];
  const number = [record.numero, record.complemento]
    .filter((part) => part !== undefined)
    .join("-")
    .toLowerCase();
  return Norm.make({
    senadoId: record.id,
    tipo: family,
    id: `br-federal-${normType.replaceAll(".", "-")}-${date}-${number}`,
    titulo: record.normaNome,
    data: date,
    numero: number,
    urn: `urn:lex:br:federal:${normType}:${date};${number}`,
    ementa: record.ementa ?? "",
  });
});

export const selectEncoding = Effect.fn("senado.selectEncoding")(function* (
  norm: typeof Norm.Type,
  response: typeof NormResponse.Type,
) {
  const url = `https://normas.leg.br/?urn=${norm.urn}`;
  if (
    response.legislationIdentifier !== norm.urn ||
    response.legislationDate !== norm.data
  )
    return yield* Effect.fail(
      new SourceFailure({
        url,
        motivo: "Identidade da resposta difere do catálogo",
      }),
    );
  const encoding = response.encoding;
  if (encoding === undefined)
    return yield* Effect.fail(
      new SourceFailure({ url, motivo: "Fonte sem arquivo de texto" }),
    );
  const encodings = Array.of(encoding).flat();
  const candidates = encodings.filter(
    (item) =>
      item.encodingFormat?.endsWith("/text/html") === true &&
      item.contentUrl !== undefined &&
      item.contentUrl !== null,
  );
  const chosen =
    candidates.find((item) => item.version === "Current") ??
    candidates.find((item) => item.version === "Original");
  if (chosen?.contentUrl === undefined || chosen.contentUrl === null)
    return yield* Effect.fail(
      new SourceFailure({
        url,
        motivo: "Fonte sem versão Current ou Original em HTML",
      }),
    );
  const sourceUrl = chosen.contentUrl.replace(
    "/api/binario/",
    "/api/public/binario/",
  );
  if (
    !/^https:\/\/normas\.leg\.br\/api\/public\/binario\/[a-f0-9-]+\/texto$/u.test(
      sourceUrl,
    )
  )
    return yield* Effect.fail(
      new SourceFailure({
        url,
        motivo: `Arquivo fora da origem esperada: ${sourceUrl}`,
      }),
    );
  if (chosen.version === "Current")
    return {
      fonte: sourceUrl,
      versao: "compilação atual disponibilizada pelo Senado" as const,
      licenca_fonte: chosen.license,
    };
  return {
    fonte: sourceUrl,
    versao: "publicação original disponibilizada pelo Senado" as const,
    licenca_fonte: chosen.license,
  };
});

export const discoverYear = Effect.fn("senado.discoverYear")(function* (
  family: typeof Family.Type,
  year: number,
  refresh: boolean,
) {
  const path = `catalogos/senado/${family}/${year}`;
  const existing = Bun.file(`${path}.json`);
  if (!refresh && (yield* Effect.tryPromise(() => existing.exists())))
    return yield* Effect.tryPromise(() => existing.text()).pipe(
      Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(Inventory))),
    );
  const url = `https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?tipo=${family}&ano=${year}`;
  const bytes = yield* request(url);
  const response = yield* Schema.decodeUnknown(
    Schema.parseJson(InventoryResponse),
  )(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  const records = inventoryRecords(response);
  const norms: Array<typeof Norm.Type> = [];
  const pending: Array<typeof InventoryRecord.Type> = [];
  for (const record of records) {
    const norm = yield* normFromRecord(record, family).pipe(Effect.option);
    if (norm._tag === "None") pending.push(record);
    else norms.push(norm.value);
  }
  const ids = new Set(norms.map((norm) => norm.id));
  if (ids.size !== norms.length)
    return yield* Effect.fail(
      new SourceFailure({ url, motivo: "Identidades duplicadas no catálogo" }),
    );
  const now = yield* Clock.currentTimeMillis;
  const inventory = Inventory.make({
    fonte: url,
    tipo: family,
    ano: year,
    coletado_em: new Date(now).toISOString(),
    normas: norms,
    pendencias: pending,
  });
  const json = yield* Schema.encode(Schema.parseJson(Inventory, { space: 2 }))(
    inventory,
  );
  yield* Effect.tryPromise(() =>
    mkdir(`catalogos/senado/${family}`, { recursive: true }),
  );
  yield* Effect.tryPromise(() =>
    Bun.write(`${path}.fonte.json.gz.tmp`, gzipSync(bytes, { level: 9 })),
  );
  yield* Effect.tryPromise(() =>
    rename(`${path}.fonte.json.gz.tmp`, `${path}.fonte.json.gz`),
  );
  yield* Effect.tryPromise(() => Bun.write(`${path}.json.tmp`, `${json}\n`));
  yield* Effect.tryPromise(() => rename(`${path}.json.tmp`, `${path}.json`));
  yield* Effect.log(
    `Catálogo ${family}/${year}: ${norms.length} normas, ${pending.length} pendências, SHA-256 ${createHash("sha256").update(bytes).digest("hex")}`,
  );
  return inventory;
});
