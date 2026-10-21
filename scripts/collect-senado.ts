import { createHash } from "node:crypto";
import { mkdir, rm } from "node:fs/promises";
import { parseArgs } from "node:util";
import { Clock, Cause, Effect, Exit, Schema } from "effect";
import { Metadata, Source, catalog } from "./catalog";
import { convert } from "./convert";
import { intact, saveDocument } from "./document";
import { CollectionFailure, pendingFailures } from "./failures";
import { Inventory, NormResponse, request, selectEncoding } from "./senado";

const args = parseArgs({
  options: {
    limit: { type: "string", default: "1000000" },
    refresh: { type: "boolean", default: false },
  "skip-failures": { type: "boolean", default: false },
  "only-failures": { type: "boolean", default: false },
  },
});
const limit = Schema.decodeUnknownSync(
  Schema.NumberFromString.pipe(Schema.int(), Schema.positive()),
)(args.values.limit);
Schema.decodeUnknownSync(Schema.Literal(false))(args.values["only-failures"] && args.values["skip-failures"]);
const Failure = Schema.Struct({
  ...CollectionFailure.fields,
  urn: Schema.String,
});

await Effect.runPromise(
  Effect.gen(function* () {
    for (const directory of ["federal", "fontes", "falhas"])
      yield* Effect.tryPromise(() => mkdir(directory, { recursive: true }));
    const paths = yield* Effect.tryPromise(() =>
      Array.fromAsync(new Bun.Glob("catalogos/senado/*/*.json").scan(".")),
    );
    const retries = new Set<string>();
    if (args.values["only-failures"]) {
      const pending = yield* pendingFailures("br-federal-", limit);
      for (const id of pending) retries.add(id);
    }
    if (args.values["only-failures"] && retries.size === 0) return yield* Effect.log("Nenhuma falha pendente");
    const seen = new Set(catalog.map((source) => source.id));
    const processed = new Set<string>();
    const failures: Array<string> = [];
    for (const path of paths.sort().reverse()) {
      if (processed.size >= limit) break;
      const inventory = yield* Effect.tryPromise(() =>
        Bun.file(path).text(),
      ).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(Inventory))));
      for (const norm of inventory.normas) {
        if (seen.has(norm.id)) continue;
        seen.add(norm.id);
        if (!args.values.refresh && !args.values["only-failures"] && (yield* intact(norm.id))) continue;
        if (processed.size >= limit) break;
        if (args.values["only-failures"] && !retries.has(norm.id)) continue;
      if (args.values["skip-failures"] && (yield* Effect.tryPromise(() => Bun.file(`falhas/${norm.id}.json`).exists()))) continue;
        processed.add(norm.id);
        const result = yield* Effect.gen(function* () {
          const dataUrl = `https://normas.leg.br/api/public/normas?urn=${encodeURIComponent(norm.urn)}&tipo_documento=maior-detalhe`;
          const data = yield* request(dataUrl);
          const details = yield* Schema.decodeUnknown(
            Schema.parseJson(NormResponse),
          )(new TextDecoder("utf-8", { fatal: true }).decode(data));
          const encoding = yield* selectEncoding(norm, details);
          const bytes = yield* request(encoding.fonte);
          const source = Source.make({
            id: norm.id,
            titulo: norm.titulo,
            data: norm.data,
            fonte: encoding.fonte,
          });
          const markdown = yield* convert(
            source,
            new TextDecoder("utf-8", { fatal: true }).decode(bytes),
          );
          const now = yield* Clock.currentTimeMillis;
          const metadata = Metadata.make({
            id: source.id,
            titulo: source.titulo,
            data: source.data,
            fonte: source.fonte,
            versao: encoding.versao,
            urn: norm.urn,
            dados: dataUrl,
            licenca_fonte: encoding.licenca_fonte,
            coletado_em: new Date(now).toISOString(),
            sha256_fonte: createHash("sha256").update(bytes).digest("hex"),
            sha256_markdown: createHash("sha256")
              .update(markdown)
              .digest("hex"),
            sha256_dados: createHash("sha256").update(data).digest("hex"),
          });
          const priorFile = Bun.file(`fontes/${norm.id}.json`);
          if (yield* Effect.tryPromise(() => priorFile.exists())) {
            const priorResult = Schema.decodeUnknownOption(
              Schema.parseJson(Metadata),
            )(yield* Effect.tryPromise(() => priorFile.text()));
            if (priorResult._tag === "Some") {
              const prior = priorResult.value;
              if (
                prior.sha256_fonte === metadata.sha256_fonte &&
                prior.sha256_markdown === metadata.sha256_markdown &&
                prior.sha256_dados === metadata.sha256_dados &&
                prior.fonte === metadata.fonte &&
                prior.versao === metadata.versao &&
                (yield* intact(norm.id))
              ) {
                yield* Effect.log(`Sem alteração: ${norm.id}`);
                return;
              }
            }
          }
          yield* saveDocument(metadata, bytes, markdown, data);
          yield* Effect.log(`Coletado ${norm.id}: ${encoding.versao}`);
        }).pipe(Effect.exit);
        if (Exit.isSuccess(result))
          yield* Effect.tryPromise(() =>
            rm(`falhas/${norm.id}.json`, { force: true }),
          );
        if (Exit.isFailure(result)) {
          failures.push(norm.id);
          const now = yield* Clock.currentTimeMillis;
          const failure = Failure.make({
            id: norm.id,
            urn: norm.urn,
            coletado_em: new Date(now).toISOString(),
            erro: Cause.pretty(result.cause),
          });
          const json = yield* Schema.encode(
            Schema.parseJson(Failure, { space: 2 }),
          )(failure);
          yield* Effect.tryPromise(() =>
            Bun.write(`falhas/${norm.id}.json`, `${json}\n`),
          );
          yield* Effect.logError(`Falhou ${norm.id}: ${failure.erro}`);
        }
      }
    }
    yield* Effect.log(
      `Tentativas: ${processed.size}; falhas: ${failures.length}`,
    );
    if (failures.length > 0) process.exitCode = 1;
  }),
);
