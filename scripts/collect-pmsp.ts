import { createHash } from "node:crypto";
import { mkdir, rm } from "node:fs/promises";
import { parseArgs } from "node:util";
import { Cause, Clock, Effect, Exit, Schema } from "effect";
import { Metadata, Source } from "./catalog";
import { convert } from "./convert";
import { intact, saveDocument } from "./document";
import { discoverPmspYear, PmspFailure, pmspRequest } from "./pmsp";

const args = parseArgs({ options: {
  from: { type: "string", default: "1800" },
  to: { type: "string", default: String(new Date().getUTCFullYear()) },
  limit: { type: "string", default: "1000000" },
  refresh: { type: "boolean", default: false },
  "skip-failures": { type: "boolean", default: false },
  "discover-only": { type: "boolean", default: false },
} });
const first = Schema.decodeUnknownSync(Schema.NumberFromString.pipe(Schema.int(), Schema.between(1800, 2100)))(args.values.from);
const last = Schema.decodeUnknownSync(Schema.NumberFromString.pipe(Schema.int(), Schema.between(first, 2100)))(args.values.to);
const limit = Schema.decodeUnknownSync(Schema.NumberFromString.pipe(Schema.int(), Schema.positive()))(args.values.limit);
const Failure = Schema.Struct({ id: Schema.String, fonte: Schema.String, coletado_em: Schema.String, erro: Schema.String });

await Effect.runPromise(Effect.gen(function* () {
  for (const path of ["municipais/3550308", "fontes", "falhas", "falhas-catalogos"])
    yield* Effect.tryPromise(() => mkdir(path, { recursive: true }));
  const seen = new Set<string>();
  const processed = new Set<string>();
  const failures = new Set<string>();
  for (const offset of Array.from({ length: last - first + 1 }, (_, index) => index)) {
    if (processed.size >= limit) break;
    const catalogId = "pmsp-" + String(last - offset);
    const catalogPath = `falhas-catalogos/${catalogId}.json`;
    const discovered = yield* discoverPmspYear(last - offset, args.values.refresh).pipe(Effect.exit);
    if (Exit.isFailure(discovered)) {
      failures.add(catalogId);
      const now = yield* Clock.currentTimeMillis;
      const failure = Failure.make({ id: catalogId, fonte: "pmsp", coletado_em: new Date(now).toISOString(), erro: Cause.pretty(discovered.cause) });
      const json = yield* Schema.encode(Schema.parseJson(Failure, { space: 2 }))(failure);
      yield* Effect.tryPromise(() => Bun.write(catalogPath, `${json}\n`));
      yield* Effect.logError(`Falhou catálogo ${catalogId}: ${failure.erro}`);
      continue;
    }
    yield* Effect.tryPromise(() => rm(catalogPath, { force: true }));
    const inventory = discovered.value;
    if (args.values["discover-only"]) continue;
    for (const norm of inventory.normas) {
      if (processed.size >= limit) break;
      if (seen.has(norm.id)) continue;
      seen.add(norm.id);
      if (!args.values.refresh && (yield* intact(norm.id))) continue;
      if (args.values["skip-failures"] && (yield* Effect.tryPromise(() => Bun.file(`falhas/${norm.id}.json`).exists()))) continue;
      processed.add(norm.id);
      const result = yield* Effect.gen(function* () {
        const response = yield* pmspRequest(norm.fonte, { headers: { "User-Agent": "MinuteiLeis/0.4 (+https://github.com/minutei-ai/leis)" } });
        const bytes = new Uint8Array(yield* Effect.tryPromise(() => response.arrayBuffer()));
        if (bytes.length === 0 || bytes.length > 25000000)
          return yield* Effect.fail(new PmspFailure({ fonte: norm.fonte, motivo: "Texto vazio ou maior que 25 MB" }));
        const source = Source.make({ id: norm.id, titulo: norm.titulo, data: norm.data, fonte: norm.fonte });
        const markdown = yield* convert(source, new TextDecoder("utf-8", { fatal: true }).decode(bytes));
        const now = yield* Clock.currentTimeMillis;
        const metadata = Metadata.make({ ...source, versao: "texto compilado disponibilizado pela Prefeitura de São Paulo", coletado_em: new Date(now).toISOString(), sha256_fonte: createHash("sha256").update(bytes).digest("hex"), sha256_markdown: createHash("sha256").update(markdown).digest("hex") });
        const priorFile = Bun.file(`fontes/${norm.id}.json`);
        if (yield* Effect.tryPromise(() => priorFile.exists())) {
          const prior = yield* Effect.tryPromise(() => priorFile.text()).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(Metadata))));
          if (prior.sha256_fonte === metadata.sha256_fonte && prior.sha256_markdown === metadata.sha256_markdown && (yield* intact(norm.id))) {
            yield* Effect.log(`Sem alteração: ${norm.id}`);
            return;
          }
        }
        yield* saveDocument(metadata, bytes, markdown, undefined);
        yield* Effect.log(`Coletado ${norm.id}`);
      }).pipe(Effect.exit);
      if (Exit.isSuccess(result))
        yield* Effect.tryPromise(() => rm(`falhas/${norm.id}.json`, { force: true }));
      if (Exit.isFailure(result)) {
        failures.add(norm.id);
        const now = yield* Clock.currentTimeMillis;
        const failure = Failure.make({ id: norm.id, fonte: norm.fonte, coletado_em: new Date(now).toISOString(), erro: Cause.pretty(result.cause) });
        const json = yield* Schema.encode(Schema.parseJson(Failure, { space: 2 }))(failure);
        yield* Effect.tryPromise(() => Bun.write(`falhas/${norm.id}.json`, `${json}\n`));
        yield* Effect.logError(`Falhou ${norm.id}: ${failure.erro}`);
      }
    }
  }
  yield* Effect.log(`PMSP: ${processed.size} tentativas; ${failures.size} falhas`);
  if (failures.size > 0) process.exitCode = 1;
}));
