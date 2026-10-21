import { Effect, Schema } from "effect";

export const CollectionFailure = Schema.Struct({
  id: Schema.String,
  coletado_em: Schema.String.pipe(Schema.pattern(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/u)),
  erro: Schema.String,
});

export const oldestFailures = (failures: ReadonlyArray<typeof CollectionFailure.Type>, limit: number) =>
  failures.slice().sort((left, right) => left.coletado_em.localeCompare(right.coletado_em) || left.id.localeCompare(right.id)).slice(0, limit).map((failure) => failure.id);

export const pendingFailures = Effect.fn("leis.pendingFailures")(function* (prefix: string, limit: number) {
  const paths = yield* Effect.tryPromise(() => Array.fromAsync(new Bun.Glob(`falhas/${prefix}*.json`).scan(".")));
  const failures = yield* Effect.forEach(paths, (path) => Effect.tryPromise(() => Bun.file(path).text()).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(CollectionFailure)))));
  return new Set(oldestFailures(failures, limit));
});
