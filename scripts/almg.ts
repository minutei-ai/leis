import { createHash } from "node:crypto";
import { mkdir, rename } from "node:fs/promises";
import { gzipSync } from "node:zlib";
import { parse } from "csv-parse/sync";
import { Clock, Effect, Schedule, Schema } from "effect";

const Kinds = Schema.Struct({
  LEI: Schema.Literal("lei"),
  LCP: Schema.Literal("lei-complementar"),
  LDL: Schema.Literal("lei-delegada"),
  DEL: Schema.Literal("decreto-lei"),
  DEC: Schema.Literal("decreto"),
  CON: Schema.Literal("constituicao"),
  EMC: Schema.Literal("emenda-constitucional"),
});
const Kind = Schema.keyof(Kinds);

export const AlmgRecord = Schema.Struct({
  Tipo: Schema.NonEmptyString,
  Numero: Schema.String,
  Ano: Schema.String,
  Complemento: Schema.String,
  DataLegislacao: Schema.String,
  Ementa: Schema.String,
  LinkTextoOriginal: Schema.String,
  LinkTextoAtualizado: Schema.String,
});

export const AlmgNorm = Schema.Struct({
  id: Schema.String.pipe(Schema.pattern(/^br-mg-[a-z0-9-]+$/)),
  tipo: Kind,
  numero: Schema.String.pipe(Schema.pattern(/^\d+$/)),
  complemento: Schema.String,
  ano: Schema.Int,
  data: Schema.String,
  titulo: Schema.String,
  fonte: Schema.String.pipe(Schema.pattern(/^https:\/\/dadosabertos\.almg\.gov\.br\/api\/v2\/legislacao\/mineira\//)),
  versao: Schema.Literal("texto atualizado disponibilizado pela ALMG", "publicação original disponibilizada pela ALMG"),
});

export const AlmgInventory = Schema.Struct({
  fonte: Schema.String,
  ano: Schema.Int,
  coletado_em: Schema.String,
  sha256_fonte: Schema.String,
  normas: Schema.Array(AlmgNorm),
  pendencias: Schema.Array(AlmgRecord),
  fora_escopo: Schema.Record({ key: Schema.String, value: Schema.Int }),
});

export const AlmgDocument = Schema.Struct({
  listaNormaDocumento: Schema.Array(Schema.Struct({
    siglaTipoNorma: Schema.String,
    numero: Schema.Int,
    ano: Schema.Int,
    codTipoDocumento: Schema.Int,
    conteudo: Schema.NonEmptyString,
  })),
});

export class AlmgFailure extends Schema.TaggedError<AlmgFailure>()("AlmgFailure", {
  fonte: Schema.String,
  motivo: Schema.String,
  status: Schema.optional(Schema.Int),
}) {}

export const almgRequest = Effect.fn("almg.request")(function* (url: string, accept: string) {
  if (!url.startsWith("https://dadosabertos.almg.gov.br/"))
    return yield* Effect.fail(new AlmgFailure({ fonte: url, motivo: "Origem não autorizada" }));
  yield* Effect.sleep("500 millis");
  const response = yield* Effect.tryPromise(() => fetch(url, { signal: AbortSignal.timeout(45000), headers: { "User-Agent": "MinuteiLeis/0.3 (+https://github.com/minutei-ai/leis)", Accept: accept } }));
  if (response.status !== 200 || !response.url.startsWith("https://dadosabertos.almg.gov.br/"))
    return yield* Effect.fail(new AlmgFailure({ fonte: url, motivo: `Resposta inesperada: ${response.status} ${response.url}`, status: response.status }));
  const bytes = new Uint8Array(yield* Effect.tryPromise(() => response.arrayBuffer()));
  if (bytes.length === 0 || bytes.length > 25000000)
    return yield* Effect.fail(new AlmgFailure({ fonte: url, motivo: "Resposta vazia ou maior que 25 MB" }));
  return bytes;
}, Effect.retry({ times: 2, schedule: Schedule.spaced("3 seconds"), while: (error) => error._tag === "AlmgFailure" && (error.status === 429 || error.status === 503) }));

export const parseAlmgCsv = Effect.fn("almg.parseCsv")(function* (csv: string) {
  const rows: unknown = yield* Effect.try(() => parse(csv, { columns: true, bom: true, skip_empty_lines: true }));
  return yield* Schema.decodeUnknown(Schema.Array(AlmgRecord))(rows);
});

export const almgNormFromRecord = Effect.fn("almg.normFromRecord")(function* (record: typeof AlmgRecord.Type) {
  const kind = yield* Schema.decodeUnknown(Kind)(record.Tipo);
  const year = yield* Schema.decodeUnknown(Schema.NumberFromString.pipe(Schema.int()))(record.Ano);
  yield* Schema.decodeUnknown(Schema.String.pipe(Schema.pattern(/^\d+$/)))(record.Numero);
  yield* Schema.decodeUnknown(Schema.String.pipe(Schema.pattern(/^[a-z]*$/iu)))(record.Complemento);
  const parts = record.DataLegislacao.match(/^(\d{2})\/(\d{2})\/(\d{4})$/u);
  if (parts === null)
    return yield* Effect.fail(new AlmgFailure({ fonte: record.LinkTextoOriginal, motivo: "Data ausente ou inválida" }));
  const date = `${parts[3]}-${parts[2]}-${parts[1]}`;
  const decoded = yield* Schema.decodeUnknown(Schema.DateFromString)(date);
  if (decoded.toISOString().slice(0, 10) !== date || date.slice(0, 4) !== record.Ano)
    return yield* Effect.fail(new AlmgFailure({ fonte: record.LinkTextoOriginal, motivo: "Data difere do ano ou não existe no calendário" }));
  const number = [record.Numero, record.Complemento].filter((part) => part.length > 0).join("-");
  const base = { id: `br-mg-${Kinds.fields[kind].literals[0]}-${date}-${number.toLowerCase()}`, tipo: kind, numero: record.Numero, complemento: record.Complemento, ano: year, data: date, titulo: `${record.Tipo} nº ${number}, de ${record.DataLegislacao}` };
  if (record.LinkTextoAtualizado.length > 0)
    return yield* Schema.decodeUnknown(AlmgNorm)({ ...base, fonte: record.LinkTextoAtualizado, versao: "texto atualizado disponibilizado pela ALMG" });
  return yield* Schema.decodeUnknown(AlmgNorm)({ ...base, fonte: record.LinkTextoOriginal, versao: "publicação original disponibilizada pela ALMG" });
});

export const projectAlmgRecords = Effect.fn("almg.projectRecords")(function* (records: ReadonlyArray<typeof AlmgRecord.Type>) {
  const norms = new Map<string, typeof AlmgNorm.Type>();
  const pending: Array<typeof AlmgRecord.Type> = [];
  const excluded = new Map<string, number>();
  for (const record of records) {
    if (!Schema.is(Kind)(record.Tipo)) {
      excluded.set(record.Tipo, (excluded.get(record.Tipo) ?? 0) + 1);
      continue;
    }
    const norm = yield* almgNormFromRecord(record).pipe(Effect.option);
    if (norm._tag === "None") pending.push(record);
    else {
      const prior = norms.get(norm.value.id);
      if (prior !== undefined) {
        const encode = Schema.encodeSync(Schema.parseJson(AlmgNorm));
        if (encode(prior) !== encode(norm.value))
          return yield* Effect.fail(new AlmgFailure({ fonte: norm.value.fonte, motivo: "Identidade duplicada com dados conflitantes no catálogo" }));
        pending.push(record);
      } else norms.set(norm.value.id, norm.value);
    }
  }
  return { normas: Array.from(norms.values()), pendencias: pending, fora_escopo: Object.fromEntries(excluded) };
});

export const discoverAlmgYear = Effect.fn("almg.discoverYear")(function* (year: number, refresh: boolean) {
  const path = `catalogos/almg/${year}`;
  const file = Bun.file(`${path}.json`);
  if (!refresh && (yield* Effect.tryPromise(() => file.exists())))
    return yield* Effect.tryPromise(() => file.text()).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(AlmgInventory))));
  const url = `https://dadosabertos.almg.gov.br/arquivo/legislacao-mineira/download?ano=${year}`;
  const bytes = yield* almgRequest(url, "*/*");
  const rows = yield* parseAlmgCsv(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  const projection = yield* projectAlmgRecords(rows);
  const now = yield* Clock.currentTimeMillis;
  const inventory = AlmgInventory.make({ fonte: url, ano: year, coletado_em: new Date(now).toISOString(), sha256_fonte: createHash("sha256").update(bytes).digest("hex"), ...projection });
  const json = yield* Schema.encode(Schema.parseJson(AlmgInventory, { space: 2 }))(inventory);
  yield* Effect.tryPromise(() => mkdir("catalogos/almg", { recursive: true }));
  yield* Effect.tryPromise(() => Bun.write(`${path}.fonte.csv.gz.tmp`, gzipSync(bytes, { level: 9 })));
  yield* Effect.tryPromise(() => rename(`${path}.fonte.csv.gz.tmp`, `${path}.fonte.csv.gz`));
  yield* Effect.tryPromise(() => Bun.write(`${path}.json.tmp`, `${json}\n`));
  yield* Effect.tryPromise(() => rename(`${path}.json.tmp`, `${path}.json`));
  yield* Effect.log(`ALMG/${year}: ${inventory.normas.length} normas, ${inventory.pendencias.length} pendências`);
  return inventory;
});

export const extractAlmgHtml = Effect.fn("almg.extractHtml")(function* (norm: typeof AlmgNorm.Type, response: typeof AlmgDocument.Type) {
  const type = yield* Schema.decodeUnknown(Schema.NumberFromString.pipe(Schema.int()))(new URL(norm.fonte).searchParams.get("tipoDoc"));
  const documents = response.listaNormaDocumento.filter((document) => document.siglaTipoNorma === norm.tipo && document.numero === Number(norm.numero) && document.ano === norm.ano && document.codTipoDocumento === type);
  if (documents.length !== 1 || documents[0] === undefined)
    return yield* Effect.fail(new AlmgFailure({ fonte: norm.fonte, motivo: "Resposta sem documento único com a identidade solicitada" }));
  return documents[0].conteudo.replace(/>\\n(?=<)/gu, ">\n");
});
