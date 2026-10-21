import { createHash } from "node:crypto";
import { gunzipSync } from "node:zlib";
import { Effect, Schema } from "effect";
import { Metadata, Source, catalog } from "./catalog";
import { convert, decodeHtml, InvalidDocument } from "./convert";
import { intact } from "./document";
import { PmspInventory, PmspNorm, parsePmspPage } from "./pmsp";
import { AlespInventory, AlespPage, AlespRecord, AlespDetail, alespSource } from "./alesp";
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
    const alespPaths = yield* Effect.tryPromise(() => Array.fromAsync(new Bun.Glob("catalogos/alesp/*.json").scan(".")));
    const alespNorms = new Map<string, typeof AlespRecord.Type>();
    for (const path of alespPaths) {
      const inventory = yield* Effect.tryPromise(() => Bun.file(path).text()).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(AlespInventory))));
      const raw = gunzipSync(yield* Effect.tryPromise(() => Bun.file(path.replace(/\.json$/u, ".fonte.json.gz")).arrayBuffer()));
      const original = yield* Schema.decodeUnknown(Schema.parseJson(AlespPage))(raw.toString("utf8"));
      const encode = Schema.encodeSync(Schema.parseJson(AlespPage));
      if (createHash("sha256").update(raw).digest("hex") !== inventory.sha256_fonte || encode(original) !== encode(inventory.pagina) || original.content.length !== original.numberOfElements)
        return yield* Effect.fail(new InvalidDocument({ fonte: path, motivo: "Catálogo Alesp não reproduz a fonte preservada" }));
      for (const record of original.content) alespNorms.set(`br-sp-norma-${record.idNorma}`, record);
    }
    const pmspPaths = yield* Effect.tryPromise(() => Array.fromAsync(new Bun.Glob("catalogos/pmsp/*.json").scan(".")));
    const pmspNorms = new Map<string, typeof PmspNorm.Type>();
    for (const path of pmspPaths) {
      const inventory = yield* Effect.tryPromise(() => Bun.file(path).text()).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(PmspInventory))));
      const norms: Array<typeof PmspNorm.Type> = [];
      const pending: Array<typeof PmspInventory.Type.pendencias[number]> = [];
      for (const [index, page] of inventory.paginas.entries()) {
        const bytes = gunzipSync(yield* Effect.tryPromise(() => Bun.file(`catalogos/pmsp/${inventory.ano_publicacao}/${page.numero}.html.gz`).arrayBuffer()));
        const parsed = yield* parsePmspPage(bytes.toString("utf8"));
        if (page.numero !== index + 1 || createHash("sha256").update(bytes).digest("hex") !== page.sha256_fonte || parsed.pagina !== page.numero || parsed.paginas !== inventory.paginas.length || parsed.total !== inventory.total)
          return yield* Effect.fail(new InvalidDocument({ fonte: path, motivo: "Página municipal não reproduz hash, total ou paginação" }));
        norms.push(...parsed.normas);
        pending.push(...parsed.pendencias);
      }
      const projection = Schema.parseJson(PmspInventory.pipe(Schema.pick("normas", "pendencias")));
      const expected = yield* Schema.encode(projection)({ normas: norms, pendencias: pending });
      const stored = yield* Schema.encode(projection)(inventory);
      if (expected !== stored || norms.length + pending.length !== inventory.total)
        return yield* Effect.fail(new InvalidDocument({ fonte: path, motivo: "Inventário municipal não reproduz as páginas oficiais" }));
      for (const norm of norms) pmspNorms.set(norm.id, norm);
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
      const source =
        catalog.find((source) => source.id === metadata.id) ??
        Source.make({
          id: metadata.id,
          titulo: metadata.titulo,
          data: metadata.data,
          fonte: metadata.fonte,
        });
      const html = decodeHtml(source, gunzipSync(bytes));
      if (metadata.id.startsWith("br-municipal-3550308-")) {
        const norm = pmspNorms.get(metadata.id);
        if (norm === undefined || norm.fonte !== metadata.fonte || norm.data !== metadata.data || norm.titulo !== metadata.titulo)
          return yield* Effect.fail(new InvalidDocument({ fonte: path, motivo: "Texto municipal sem catálogo ou com identidade divergente" }));
      }
      if (metadata.id.startsWith("br-sp-")) {
        const record = alespNorms.get(metadata.id);
        if (record === undefined)
          return yield* Effect.fail(new InvalidDocument({ fonte: path, motivo: "Norma Alesp sem catálogo" }));
        const data = gunzipSync(yield* Effect.tryPromise(() => Bun.file(`fontes/${metadata.id}.dados.json.gz`).arrayBuffer()));
        const detail = yield* Schema.decodeUnknown(Schema.parseJson(AlespDetail))(data.toString("utf8"));
        const selected = yield* alespSource(record, detail);
        if (selected.fonte !== metadata.fonte || selected.versao !== metadata.versao || selected.data !== metadata.data)
          return yield* Effect.fail(new InvalidDocument({ fonte: path, motivo: "Texto ou versão Alesp difere dos metadados preservados" }));
      }

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
      `Auditoria: ${inventoryPaths.length + almgPaths.length + alespPaths.length + pmspPaths.length} catálogos reproduzidos; ${paths.length} normas reproduzidas, com hashes íntegros`,
    );
  }),
);
