import { createHash } from "node:crypto";
import { mkdir, rm } from "node:fs/promises";
import { parseArgs } from "node:util";
import { Cause, Clock, Effect, Exit, Schema } from "effect";
import { AlmgDocument, discoverAlmgYear, extractAlmgHtml, almgRequest } from "./almg";
import { Metadata, Source } from "./catalog";
import { convert } from "./convert";
import { intact, saveDocument } from "./document";

const args = parseArgs({ options: {
  from: { type: "string", default: "1947" },
  to: { type: "string", default: String(new Date().getUTCFullYear()) },
  limit: { type: "string", default: "1000000" },
  refresh: { type: "boolean", default: false },
  "discover-only": { type: "boolean", default: false },
} });
const first = Schema.decodeUnknownSync(Schema.NumberFromString.pipe(Schema.int(), Schema.between(1800, 2100)))(args.values.from);
const last = Schema.decodeUnknownSync(Schema.NumberFromString.pipe(Schema.int(), Schema.between(first, 2100)))(args.values.to);
const limit = Schema.decodeUnknownSync(Schema.NumberFromString.pipe(Schema.int(), Schema.positive()))(args.values.limit);
const Failure = Schema.Struct({ id: Schema.String, fonte: Schema.String, coletado_em: Schema.String, erro: Schema.String });

await Effect.runPromise(Effect.gen(function* () {
  for (const path of ["estaduais/MG", "fontes", "falhas"])
    yield* Effect.tryPromise(() => mkdir(path, { recursive: true }));
  const processed = new Set<string>();
  const failures = new Set<string>();
  for (const offset of Array.from({ length: last - first + 1 }, (_, index) => index)) {
    if (processed.size >= limit) break;
    const inventory = yield* discoverAlmgYear(last - offset, args.values.refresh);
    if (args.values["discover-only"]) continue;
    for (const norm of inventory.normas) {
      if (processed.size >= limit) break;
      if (!args.values.refresh && (yield* intact(norm.id))) continue;
      processed.add(norm.id);
      const result = yield* Effect.gen(function* () {
        const data = yield* almgRequest(norm.fonte, "application/json");
        const response = yield* Schema.decodeUnknown(Schema.parseJson(AlmgDocument))(new TextDecoder("utf-8", { fatal: true }).decode(data));
        const html = yield* extractAlmgHtml(norm, response);
        const source = Source.make({ id: norm.id, titulo: norm.titulo, data: norm.data, fonte: norm.fonte });
        const markdown = yield* convert(source, html);
        const bytes = new TextEncoder().encode(html);
        const now = yield* Clock.currentTimeMillis;
        const metadata = Metadata.make({ id: norm.id, titulo: norm.titulo, data: norm.data, fonte: norm.fonte, versao: norm.versao, dados: norm.fonte, coletado_em: new Date(now).toISOString(), sha256_fonte: createHash("sha256").update(bytes).digest("hex"), sha256_markdown: createHash("sha256").update(markdown).digest("hex"), sha256_dados: createHash("sha256").update(data).digest("hex") });
        const priorFile = Bun.file(`fontes/${norm.id}.json`);
        if (yield* Effect.tryPromise(() => priorFile.exists())) {
          const priorResult = Schema.decodeUnknownOption(Schema.parseJson(Metadata))(yield* Effect.tryPromise(() => priorFile.text()));
          if (priorResult._tag === "Some") {
            const prior = priorResult.value;
            if (prior.sha256_fonte === metadata.sha256_fonte && prior.sha256_dados === metadata.sha256_dados && prior.sha256_markdown === metadata.sha256_markdown && prior.versao === metadata.versao && (yield* intact(norm.id))) {
              yield* Effect.log(`Sem alteração: ${norm.id}`);
              return;
            }
          }
        }
        yield* saveDocument(metadata, bytes, markdown, data);
        yield* Effect.log(`Coletado ${norm.id}: ${norm.versao}`);
      }).pipe(Effect.exit);
      if (Exit.isSuccess(result))
        yield* Effect.tryPromise(() => rm(`falhas/${norm.id}.json`, { force: true }));
      if (Exit.isFailure(result)) {
        failures.add(norm.id);
        const now = yield* Clock.currentTimeMillis;
        const record = Failure.make({ id: norm.id, fonte: norm.fonte, coletado_em: new Date(now).toISOString(), erro: Cause.pretty(result.cause) });
        const json = yield* Schema.encode(Schema.parseJson(Failure, { space: 2 }))(record);
        yield* Effect.tryPromise(() => Bun.write(`falhas/${norm.id}.json`, `${json}\n`));
        yield* Effect.logError(`Falhou ${norm.id}: ${record.erro}`);
      }
    }
  }
  yield* Effect.log(`ALMG: ${processed.size} tentativas; ${failures.size} falhas`);
  if (failures.size > 0) process.exitCode = 1;
}));
