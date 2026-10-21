import { createHash } from "node:crypto";
import { mkdir, rm } from "node:fs/promises";
import { parseArgs } from "node:util";
import { Cause, Clock, Effect, Exit, Schema } from "effect";
import { AlespDetail, AlespFailure, alespRequest, alespSource, discoverAlespPage } from "./alesp";
import { Metadata, Source } from "./catalog";
import { convert, decodeHtml } from "./convert";
import { intact, saveDocument } from "./document";

const args = parseArgs({ options: {
  limit: { type: "string", default: "1000000" },
  refresh: { type: "boolean", default: false },
  "skip-failures": { type: "boolean", default: false },
  "discover-only": { type: "boolean", default: false },
} });
const limit = Schema.decodeUnknownSync(Schema.NumberFromString.pipe(Schema.int(), Schema.positive()))(args.values.limit);
const Failure = Schema.Struct({ id: Schema.String, fonte: Schema.String, coletado_em: Schema.String, erro: Schema.String });

await Effect.runPromise(Effect.gen(function* () {
  for (const path of ["estaduais/SP", "fontes", "falhas"])
    yield* Effect.tryPromise(() => mkdir(path, { recursive: true }));
  const seen = new Set<string>();
  const processed = new Set<string>();
  const failures = new Set<string>();
  const first = yield* discoverAlespPage(0, args.values.refresh);
  for (const page of Array.from({ length: first.pagina.totalPages }, (_, index) => index)) {
    if (processed.size >= limit) break;
    const inventory = yield* discoverAlespPage(page, args.values.refresh && page !== 0);
    if (inventory.pagina.totalElements !== first.pagina.totalElements || inventory.pagina.totalPages !== first.pagina.totalPages)
      return yield* Effect.fail(new AlespFailure({ fonte: inventory.fonte, motivo: "Catálogo mudou durante a paginação; atualize os inventários" }));
    if (args.values["discover-only"]) continue;
    for (const record of inventory.pagina.content) {
      if (processed.size >= limit) break;
      const id = `br-sp-norma-${record.idNorma}`;
      if (seen.has(id)) continue;
      seen.add(id);
      if (!args.values.refresh && (yield* intact(id))) continue;
      if (args.values["skip-failures"] && (yield* Effect.tryPromise(() => Bun.file(`falhas/${id}.json`).exists()))) continue;
      processed.add(id);
      const result = yield* Effect.gen(function* () {
        const dataUrl = `https://baleg-api-prd.al.sp.gov.br/norma/${record.idNorma}`;
        const data = yield* alespRequest(dataUrl);
        const detail = yield* Schema.decodeUnknown(Schema.parseJson(AlespDetail))(new TextDecoder("utf-8", { fatal: true }).decode(data));
        const selected = yield* alespSource(record, detail);
        const source = Source.make({ id, titulo: record.nomeNorma, data: selected.data, fonte: selected.fonte });
        const bytes = yield* alespRequest(source.fonte);
        const markdown = yield* convert(source, decodeHtml(source, bytes));
        const now = yield* Clock.currentTimeMillis;
        const metadata = Metadata.make({ ...source, versao: selected.versao, dados: dataUrl, coletado_em: new Date(now).toISOString(), sha256_fonte: createHash("sha256").update(bytes).digest("hex"), sha256_markdown: createHash("sha256").update(markdown).digest("hex"), sha256_dados: createHash("sha256").update(data).digest("hex") });
        const priorFile = Bun.file(`fontes/${id}.json`);
        if (yield* Effect.tryPromise(() => priorFile.exists())) {
          const prior = yield* Effect.tryPromise(() => priorFile.text()).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(Metadata))));
          if (prior.sha256_fonte === metadata.sha256_fonte && prior.sha256_dados === metadata.sha256_dados && prior.sha256_markdown === metadata.sha256_markdown && prior.versao === metadata.versao && (yield* intact(id))) {
            yield* Effect.log(`Sem alteração: ${id}`);
            return;
          }
        }
        yield* saveDocument(metadata, bytes, markdown, data);
        yield* Effect.log(`Coletado ${id}: ${metadata.versao}`);
      }).pipe(Effect.exit);
      if (Exit.isSuccess(result))
        yield* Effect.tryPromise(() => rm(`falhas/${id}.json`, { force: true }));
      if (Exit.isFailure(result)) {
        failures.add(id);
        const now = yield* Clock.currentTimeMillis;
        const failure = Failure.make({ id, fonte: `https://baleg-api-prd.al.sp.gov.br/norma/${record.idNorma}`, coletado_em: new Date(now).toISOString(), erro: Cause.pretty(result.cause) });
        const json = yield* Schema.encode(Schema.parseJson(Failure, { space: 2 }))(failure);
        yield* Effect.tryPromise(() => Bun.write(`falhas/${id}.json`, `${json}\n`));
        yield* Effect.logError(`Falhou ${id}: ${failure.erro}`);
      }
    }
  }
  yield* Effect.log(`Alesp: ${processed.size} tentativas; ${failures.size} falhas`);
  if (failures.size > 0) process.exitCode = 1;
}));
