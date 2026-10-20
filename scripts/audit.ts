import { createHash } from "node:crypto";
import { gunzipSync } from "node:zlib";
import { Effect, Schema } from "effect";
import { Metadata, Source, catalog } from "./catalog";
import { convert, InvalidDocument } from "./convert";
import { intact } from "./document";
import {
  Inventory,
  InventoryResponse,
  Norm,
  inventoryRecords,
  normFromRecord,
} from "./senado";

await Effect.runPromise(
  Effect.gen(function* () {
    const inventoryPaths = yield* Effect.tryPromise(() =>
      Array.fromAsync(new Bun.Glob("catalogos/senado/*/*.json").scan(".")),
    );
    for (const path of inventoryPaths) {
      const inventory = yield* Effect.tryPromise(() =>
        Bun.file(path).text(),
      ).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(Inventory))));
      const bytes = yield* Effect.tryPromise(() =>
        Bun.file(path.replace(/\.json$/u, ".fonte.json.gz")).arrayBuffer(),
      );
      const original = yield* Schema.decodeUnknown(
        Schema.parseJson(InventoryResponse),
      )(gunzipSync(bytes).toString("utf8"));
      const records = inventoryRecords(original);
      const norms: Array<typeof Norm.Type> = [];
      for (const record of records) {
        const norm = yield* normFromRecord(record, inventory.tipo).pipe(
          Effect.option,
        );
        if (norm._tag === "Some") norms.push(norm.value);
      }
      const expected = yield* Schema.encode(
        Schema.parseJson(Schema.Array(Norm)),
      )(norms);
      const stored = yield* Schema.encode(Schema.parseJson(Schema.Array(Norm)))(
        inventory.normas,
      );
      if (
        expected !== stored ||
        records.length !== inventory.normas.length + inventory.pendencias.length
      )
        return yield* Effect.fail(
          new InvalidDocument({
            fonte: path,
            motivo: "Inventário não reproduz a resposta oficial preservada",
          }),
        );
      if (
        inventory.normas.some(
          (norm) => norm.data.slice(0, 4) !== String(inventory.ano),
        )
      )
        return yield* Effect.fail(
          new InvalidDocument({
            fonte: path,
            motivo: "Ano de norma difere do catálogo",
          }),
        );
    }
    const paths = yield* Effect.tryPromise(() =>
      Array.fromAsync(new Bun.Glob("fontes/*.json").scan(".")),
    );
    for (const path of paths.sort()) {
      const metadata = yield* Effect.tryPromise(() =>
        Bun.file(path).text(),
      ).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(Metadata))));
      if (!(yield* intact(metadata.id)))
        return yield* Effect.fail(
          new InvalidDocument({
            fonte: path,
            motivo: "Arquivo ausente ou hash divergente",
          }),
        );
      const bytes = yield* Effect.tryPromise(() =>
        Bun.file(`fontes/${metadata.id}.html.gz`).arrayBuffer(),
      );
      const html = gunzipSync(bytes).toString("utf8");
      const source =
        catalog.find((source) => source.id === metadata.id) ??
        Source.make({
          id: metadata.id,
          titulo: metadata.titulo,
          data: metadata.data,
          fonte: metadata.fonte,
        });
      const markdown = yield* convert(source, html);
      if (
        createHash("sha256").update(markdown).digest("hex") !==
        metadata.sha256_markdown
      )
        return yield* Effect.fail(
          new InvalidDocument({
            fonte: path,
            motivo: "Conversão não reproduz o corpo publicado",
          }),
        );
    }
    yield* Effect.log(
      `Auditoria: ${inventoryPaths.length} catálogos reproduzidos; ${paths.length} normas reproduzidas, com hashes íntegros`,
    );
  }),
);
