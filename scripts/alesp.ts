import { createHash } from "node:crypto";
import { mkdir, rename } from "node:fs/promises";
import { gzipSync } from "node:zlib";
import { Clock, Effect, Schedule, Schema } from "effect";

export const AlespRecord = Schema.Struct({
  idNorma: Schema.String.pipe(Schema.pattern(/^\d+$/)),
  tipo: Schema.NonEmptyString,
  nuNorma: Schema.String,
  data: Schema.String.pipe(Schema.pattern(/^\d{2}\/\d{2}\/\d{4}$/)),
  nomeNorma: Schema.NonEmptyString,
  idTipo: Schema.String,
  dsEmenta: Schema.String,
});

export const AlespPage = Schema.Struct({
  content: Schema.Array(AlespRecord),
  totalPages: Schema.Int.pipe(Schema.positive()),
  totalElements: Schema.Int.pipe(Schema.nonNegative()),
  number: Schema.Int.pipe(Schema.nonNegative()),
  size: Schema.Int.pipe(Schema.positive()),
  numberOfElements: Schema.Int.pipe(Schema.nonNegative()),
  last: Schema.Boolean,
});

export const AlespInventory = Schema.Struct({
  fonte: Schema.String,
  coletado_em: Schema.String,
  sha256_fonte: Schema.String,
  pagina: AlespPage,
});

export const AlespDetail = Schema.Struct({
  ...AlespRecord.fields,
  urlIntegraOriginal: Schema.NullOr(Schema.String),
  urlIntegraAtualizada: Schema.NullOr(Schema.String),
});

export class AlespFailure extends Schema.TaggedError<AlespFailure>()("AlespFailure", {
  fonte: Schema.String,
  motivo: Schema.String,
  status: Schema.optional(Schema.Int),
}) {}

export const alespRequest = Effect.fn("alesp.request")(function* (url: string) {
  if (!url.startsWith("https://baleg-api-prd.al.sp.gov.br/") && !url.startsWith("https://www.al.sp.gov.br/repositorio/legislacao/"))
    return yield* Effect.fail(new AlespFailure({ fonte: url, motivo: "Origem não autorizada" }));
  yield* Effect.sleep("500 millis");
  const response = yield* Effect.tryPromise(() => fetch(url, {
    signal: AbortSignal.timeout(45000),
    headers: { "User-Agent": "MinuteiLeis/0.4 (+https://github.com/minutei-ai/leis)" },
  }));
  if (response.status !== 200 || new URL(response.url).origin !== new URL(url).origin)
    return yield* Effect.fail(new AlespFailure({ fonte: url, motivo: `Resposta inesperada: ${response.status} ${response.url}`, status: response.status }));
  const bytes = new Uint8Array(yield* Effect.tryPromise(() => response.arrayBuffer()));
  if (bytes.length === 0 || bytes.length > 25000000)
    return yield* Effect.fail(new AlespFailure({ fonte: url, motivo: "Resposta vazia ou maior que 25 MB" }));
  return bytes;
}, Effect.retry({ times: 2, schedule: Schedule.spaced("3 seconds"), while: (error) => error._tag === "AlespFailure" && (error.status === 429 || error.status === 503) }));

export const alespSource = Effect.fn("alesp.source")(function* (record: typeof AlespRecord.Type, detail: typeof AlespDetail.Type) {
  if (detail.idNorma !== record.idNorma || detail.data !== record.data || detail.nuNorma !== record.nuNorma || detail.idTipo !== record.idTipo)
    return yield* Effect.fail(new AlespFailure({ fonte: record.idNorma, motivo: "Identidade do documento difere do catálogo" }));
  const parts = record.data.split("/");
  const date = `${parts[2]}-${parts[1]}-${parts[0]}`;
  const decoded = yield* Schema.decodeUnknown(Schema.DateFromString)(date);
  if (decoded.toISOString().slice(0, 10) !== date)
    return yield* Effect.fail(new AlespFailure({ fonte: record.idNorma, motivo: "Data inexistente" }));
  const id = `br-sp-norma-${record.idNorma}`;
  const updated = detail.urlIntegraAtualizada;
  const original = detail.urlIntegraOriginal;
  const url = updated ?? original;
  if (url === null || !/^https:\/\/www\.al\.sp\.gov\.br\/repositorio\/legislacao\/.+\.html$/u.test(url))
    return yield* Effect.fail(new AlespFailure({ fonte: record.idNorma, motivo: "Fonte sem texto HTML atualizado ou original autorizado" }));
  if (updated !== null)
    return { id, data: date, fonte: url, versao: "texto atualizado disponibilizado pela Alesp" as const };
  return { id, data: date, fonte: url, versao: "publicação original disponibilizada pela Alesp" as const };
});

export const discoverAlespPage = Effect.fn("alesp.discoverPage")(function* (page: number, refresh: boolean) {
  const path = `catalogos/alesp/${String(page).padStart(5, "0")}`;
  const file = Bun.file(`${path}.json`);
  if (!refresh && (yield* Effect.tryPromise(() => file.exists())))
    return yield* Effect.tryPromise(() => file.text()).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(AlespInventory))));
  const url = `https://baleg-api-prd.al.sp.gov.br/normas?page=${page}&size=1000`;
  const bytes = yield* alespRequest(url);
  const response = yield* Schema.decodeUnknown(Schema.parseJson(AlespPage))(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  if (response.number !== page || response.content.length !== response.numberOfElements || response.content.length > response.size || response.last !== (page + 1 === response.totalPages))
    return yield* Effect.fail(new AlespFailure({ fonte: url, motivo: "Paginação inconsistente" }));
  const now = yield* Clock.currentTimeMillis;
  const inventory = AlespInventory.make({ fonte: url, coletado_em: new Date(now).toISOString(), sha256_fonte: createHash("sha256").update(bytes).digest("hex"), pagina: response });
  const json = yield* Schema.encode(Schema.parseJson(AlespInventory, { space: 2 }))(inventory);
  yield* Effect.tryPromise(() => mkdir("catalogos/alesp", { recursive: true }));
  yield* Effect.tryPromise(() => Bun.write(`${path}.fonte.json.gz.tmp`, gzipSync(bytes, { level: 9 })));
  yield* Effect.tryPromise(() => rename(`${path}.fonte.json.gz.tmp`, `${path}.fonte.json.gz`));
  yield* Effect.tryPromise(() => Bun.write(`${path}.json.tmp`, `${json}\n`));
  yield* Effect.tryPromise(() => rename(`${path}.json.tmp`, `${path}.json`));
  yield* Effect.log(`Alesp/${page}: ${response.content.length} registros; ${response.totalElements} no catálogo, ${response.totalPages} páginas`);
  return inventory;
});
