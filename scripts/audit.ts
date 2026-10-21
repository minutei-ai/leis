import { createHash } from "node:crypto";
import { gunzipSync } from "node:zlib";
import { Effect, Schema } from "effect";
import { Metadata, Source, catalog } from "./catalog";
import { convert, InvalidDocument } from "./convert";
import { intact } from "./document";
import { AlmgInventory, AlmgDocument, AlmgNorm, parseAlmgCsv, projectAlmgRecords, extractAlmgHtml } from "./almg";
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
    const almgPaths = yield* Effect.tryPromise(() => Array.fromAsync(new Bun.Glob("catalogos/almg/*.json").scan(".")));
    const almgNorms = new Map<string, typeof AlmgNorm.Type>();
    for (const path of almgPaths) {
      const inventory = yield* Effect.tryPromise(() => Bun.file(path).text()).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(AlmgInventory))));
      const sourceBytes = yield* Effect.tryPromise(() => Bun.file(path.replace(/\.json$/u, ".fonte.csv.gz")).arrayBuffer());
      const raw = gunzipSync(sourceBytes);
      if (createHash("sha256").update(raw).digest("hex") !== inventory.sha256_fonte)
        return yield* Effect.fail(new InvalidDocument({ fonte: path, motivo: "Hash do catálogo ALMG diverge da fonte preservada" }));
      const records = yield* parseAlmgCsv(raw.toString("utf8"));
      const projected = yield* projectAlmgRecords(records);
      const projectionSchema = Schema.parseJson(AlmgInventory.pipe(Schema.pick("normas", "pendencias", "fora_escopo")));
      const expected = yield* Schema.encode(projectionSchema)(projected);
      const stored = yield* Schema.encode(projectionSchema)(inventory);
      if (expected !== stored || inventory.normas.some((norm) => norm.ano !== inventory.ano))
        return yield* Effect.fail(new InvalidDocument({ fonte: path, motivo: "Catálogo ALMG não reproduz a fonte preservada" }));
      for (const norm of inventory.normas) almgNorms.set(norm.id, norm);
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
      if (metadata.id.startsWith("br-mg-")) {
        const norm = almgNorms.get(metadata.id);
        if (norm === undefined || norm.fonte !== metadata.fonte || norm.versao !== metadata.versao)
          return yield* Effect.fail(new InvalidDocument({ fonte: path, motivo: "Norma ALMG sem catálogo ou com versão divergente" }));
        const data = yield* Effect.tryPromise(() => Bun.file(`fontes/${metadata.id}.dados.json.gz`).arrayBuffer());
        const decoded = yield* Schema.decodeUnknown(Schema.parseJson(AlmgDocument))(gunzipSync(data).toString("utf8"));
        const extracted = yield* extractAlmgHtml(norm, decoded);
        if (extracted !== html)
          return yield* Effect.fail(new InvalidDocument({ fonte: path, motivo: "HTML ALMG não corresponde ao JSON original" }));
      }
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
      `Auditoria: ${inventoryPaths.length + almgPaths.length} catálogos reproduzidos; ${paths.length} normas reproduzidas, com hashes íntegros`,
    );
  }),
);
