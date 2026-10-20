import { parseArgs } from "node:util";
import { Effect, Schema } from "effect";
import { discoverYear, Family } from "./senado";

const args = parseArgs({
  options: {
    from: { type: "string", default: "1822" },
    to: { type: "string", default: String(new Date().getUTCFullYear()) },
    type: { type: "string", default: "LEI" },
    refresh: { type: "boolean", default: false },
  },
});
const first = Schema.decodeUnknownSync(
  Schema.NumberFromString.pipe(Schema.int(), Schema.between(1800, 2100)),
)(args.values.from);
const last = Schema.decodeUnknownSync(
  Schema.NumberFromString.pipe(Schema.int(), Schema.between(first, 2100)),
)(args.values.to);
const family = Schema.decodeUnknownSync(Family)(args.values.type);
await Effect.runPromise(
  Effect.gen(function* () {
    for (const offset of Array.from(
      { length: last - first + 1 },
      (_, index) => index,
    ))
      yield* discoverYear(family, last - offset, args.values.refresh);
  }),
);
