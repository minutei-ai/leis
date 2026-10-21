import { mkdir, rm } from "node:fs/promises";
import { parseArgs } from "node:util";
import { Cause, Clock, Effect, Exit, Schema } from "effect";
import { discoverYear, Families, Family, SourceFailure } from "./senado";

const args = parseArgs({ options: {
  from: { type: "string", default: "1822" },
  to: { type: "string", default: String(new Date().getUTCFullYear()) },
  type: { type: "string" },
  all: { type: "boolean", default: false },
  refresh: { type: "boolean", default: false },
} });
const first = Schema.decodeUnknownSync(Schema.NumberFromString.pipe(Schema.int(), Schema.between(1800, 2100)))(args.values.from);
const last = Schema.decodeUnknownSync(Schema.NumberFromString.pipe(Schema.int(), Schema.between(first, 2100)))(args.values.to);
const families: Array<typeof Family.Type> = [];
if (args.values.all) families.push(...Schema.decodeUnknownSync(Schema.Array(Family))(Object.keys(Families.fields)));
else families.push(Schema.decodeUnknownSync(Family)(args.values.type ?? "LEI"));
const Failure = Schema.Struct({ fonte: Schema.String, tipo: Family, ano: Schema.Int, coletado_em: Schema.String, erro: Schema.String });

await Effect.runPromise(Effect.gen(function* () {
  if (args.values.all && args.values.type !== undefined)
    return yield* Effect.fail(new SourceFailure({ url: "discover", motivo: "Use --all ou --type, sem combinar os dois" }));
  yield* Effect.tryPromise(() => mkdir("falhas-catalogos", { recursive: true }));
  const failures = new Set<string>();
  for (const family of families) {
    for (const offset of Array.from({ length: last - first + 1 }, (_, index) => index)) {
      const year = last - offset;
      const path = `falhas-catalogos/senado-${family}-${year}.json`;
      const result = yield* discoverYear(family, year, args.values.refresh).pipe(Effect.exit);
      if (Exit.isSuccess(result))
        yield* Effect.tryPromise(() => rm(path, { force: true }));
      if (Exit.isFailure(result)) {
        failures.add(path);
        const now = yield* Clock.currentTimeMillis;
        const record = Failure.make({ fonte: `https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?tipo=${family}&ano=${year}`, tipo: family, ano: year, coletado_em: new Date(now).toISOString(), erro: Cause.pretty(result.cause) });
        const json = yield* Schema.encode(Schema.parseJson(Failure, { space: 2 }))(record);
        yield* Effect.tryPromise(() => Bun.write(path, `${json}\n`));
        yield* Effect.logError(`Falhou catálogo ${family}/${year}: ${record.erro}`);
      }
    }
  }
  yield* Effect.log(`Descoberta: ${families.length} famílias; ${failures.size} falhas de catálogo`);
  if (failures.size > 0) process.exitCode = 1;
}));
