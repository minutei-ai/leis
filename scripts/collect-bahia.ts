import { createHash } from "node:crypto";
import { mkdir, rm } from "node:fs/promises";
import { parseArgs } from "node:util";
import { Cause, Clock, Effect, Exit, Schema } from "effect";
import { Metadata } from "./catalog";
import { convert } from "./convert";
import { intact, saveDocument } from "./document";
import { CollectionFailure, pendingFailures } from "./failures";
import { BahiaFailure, BahiaCategory, BahiaLink, bahiaSearch, bahiaSource, bahiaRequest, bahiaFailureId, bahiaInventoryPath, discoverBahiaPage } from "./bahia";

const args = parseArgs({ options: {
  categories: { type: "string", default: "5,6,11,30,31,32,33,4,7" },
  limit: { type: "string", default: "1000000" },
  pages: { type: "string", default: "100" },
  refresh: { type: "boolean", default: false },
  "skip-failures": { type: "boolean", default: false },
  "only-failures": { type: "boolean", default: false },
  "discover-only": { type: "boolean", default: false },
} });
const categories = Schema.decodeUnknownSync(Schema.Array(BahiaCategory))(args.values.categories.split(","));
const pageLimit = Schema.decodeUnknownSync(Schema.NumberFromString.pipe(Schema.int(), Schema.positive()))(args.values.pages);
const limit = Schema.decodeUnknownSync(Schema.NumberFromString.pipe(Schema.int(), Schema.positive()))(args.values.limit);
Schema.decodeUnknownSync(Schema.Literal(false))(args.values["only-failures"] && args.values["skip-failures"]);
Schema.decodeUnknownSync(Schema.Literal(false))(args.values["only-failures"] && args.values["discover-only"]);
const Failure = Schema.Struct({ ...CollectionFailure.fields, fonte: BahiaLink.fields.fonte });

await Effect.runPromise(Effect.gen(function* () {
  for (const path of ["estaduais/BA", "fontes", "falhas", "falhas-catalogos", "catalogos/bahia"])
    yield* Effect.tryPromise(() => mkdir(path, { recursive: true }));
  const existing = new Map<string, string>();
  const paths = yield* Effect.tryPromise(() => Array.fromAsync(new Bun.Glob("fontes/br-ba-*.json").scan(".")));
  for (const path of paths) {
    const metadata = yield* Effect.tryPromise(() => Bun.file(path).text()).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(Metadata))));
    existing.set(metadata.fonte, metadata.id);
  }
  const retries = new Set<string>();
  if (args.values["only-failures"]) {
    const pending = yield* pendingFailures("bahia-url-", limit);
    for (const id of pending) retries.add(id);
    if (retries.size === 0) return yield* Effect.log("Nenhuma falha baiana pendente");
  }
  const fetched = new Set<string>();
  const seen = new Set<string>();
  const processed = new Set<string>();
  const failures = new Set<string>();
  for (const category of categories) {
    const pages = [bahiaSearch(category, 0)];
    const totals = new Set<number>();
    for (const [page, url] of pages.entries()) {
      if (processed.size >= limit) break;
      const inventoryPath = bahiaInventoryPath(category, page);
      const cached = yield* Effect.tryPromise(() => Bun.file(`${inventoryPath}.json`).exists());
      if (args.values["only-failures"] && !cached) break;
      if (!cached || args.values.refresh) {
        if (fetched.size >= pageLimit) break;
        fetched.add(inventoryPath);
      }
      const catalogId = `bahia-${category}-${String(page).padStart(5, "0")}`;
      const failurePath = `falhas-catalogos/${catalogId}.json`;
      const discovered = yield* discoverBahiaPage(category, page, url, args.values.refresh).pipe(Effect.exit);
      if (Exit.isFailure(discovered)) {
        failures.add(catalogId);
        const now = yield* Clock.currentTimeMillis;
        const failure = CollectionFailure.make({ id: catalogId, coletado_em: new Date(now).toISOString(), erro: Cause.pretty(discovered.cause) });
        const json = yield* Schema.encode(Schema.parseJson(CollectionFailure, { space: 2 }))(failure);
        yield* Effect.tryPromise(() => Bun.write(failurePath, `${json}\n`));
        yield* Effect.logError(failure.erro);
        break;
      }
      yield* Effect.tryPromise(() => rm(failurePath, { force: true }));
      const inventory = discovered.value;
      totals.add(inventory.pagina.total);
      if (totals.size > 1)
        return yield* Effect.fail(new BahiaFailure({ fonte: inventory.fonte, motivo: "Total mudou durante a paginação; atualize os inventários" }));
      if (inventory.pagina.proxima !== null) pages.push(inventory.pagina.proxima);
      if (args.values["discover-only"]) continue;
      for (const link of inventory.pagina.normas) {
        if (processed.size >= limit) break;
        if (seen.has(link.fonte)) continue;
        seen.add(link.fonte);
        const failureId = bahiaFailureId(link.fonte);
        const id = existing.get(link.fonte);
        if (!args.values.refresh && !args.values["only-failures"] && id !== undefined && (yield* intact(id))) continue;
        if (args.values["only-failures"] && !retries.has(failureId)) continue;
        if (args.values["skip-failures"] && (yield* Effect.tryPromise(() => Bun.file(`falhas/${failureId}.json`).exists()))) continue;
        processed.add(link.fonte);
        const result = yield* Effect.gen(function* () {
          const bytes = yield* bahiaRequest(link.fonte);
          const html = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
          const source = yield* bahiaSource(link, html);
          if (id !== undefined && source.id !== id)
            return yield* Effect.fail(new BahiaFailure({ fonte: link.fonte, motivo: `Identidade oficial alterada: ${id} -> ${source.id}` }));
          const markdown = yield* convert(source, html);
          const now = yield* Clock.currentTimeMillis;
          const metadata = Metadata.make({ ...source, versao: "texto compilado disponibilizado pela Casa Civil da Bahia", coletado_em: new Date(now).toISOString(), sha256_fonte: createHash("sha256").update(bytes).digest("hex"), sha256_markdown: createHash("sha256").update(markdown).digest("hex") });
          const priorFile = Bun.file(`fontes/${source.id}.json`);
          if (yield* Effect.tryPromise(() => priorFile.exists())) {
            const prior = yield* Effect.tryPromise(() => priorFile.text()).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(Metadata))));
            if (prior.fonte !== source.fonte)
              return yield* Effect.fail(new BahiaFailure({ fonte: link.fonte, motivo: `Identidade oficial já pertence a outro endereço: ${source.id}` }));
            if (prior.sha256_fonte === metadata.sha256_fonte && prior.sha256_markdown === metadata.sha256_markdown && (yield* intact(source.id))) return;
          }
          yield* saveDocument(metadata, bytes, markdown, undefined);
          existing.set(source.fonte, source.id);
          yield* Effect.log(`Coletado ${source.id}`);
        }).pipe(Effect.exit);
        if (Exit.isSuccess(result)) yield* Effect.tryPromise(() => rm(`falhas/${failureId}.json`, { force: true }));
        if (Exit.isFailure(result)) {
          failures.add(failureId);
          const now = yield* Clock.currentTimeMillis;
          const failure = Failure.make({ id: failureId, fonte: link.fonte, coletado_em: new Date(now).toISOString(), erro: Cause.pretty(result.cause) });
          const json = yield* Schema.encode(Schema.parseJson(Failure, { space: 2 }))(failure);
          yield* Effect.tryPromise(() => Bun.write(`falhas/${failureId}.json`, `${json}\n`));
          yield* Effect.logError(`Falhou ${link.fonte}: ${failure.erro}`);
        }
      }
    }
  }
  yield* Effect.log(`Bahia: ${processed.size} tentativas; ${fetched.size} páginas consultadas; ${failures.size} falhas. Limites de lote não significam esgotamento do catálogo.`);
  if (failures.size > 0) process.exitCode = 1;
}));
