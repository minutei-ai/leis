import { createHash } from "node:crypto";
import { rename } from "node:fs/promises";
import { gunzipSync, gzipSync } from "node:zlib";
import { Effect, Schema } from "effect";
import { Metadata } from "./catalog";

const markdownPath = (id: string) => {
  if (id.startsWith("br-municipal-3550308-")) return `municipais/3550308/${id}.md`;
  if (id.startsWith("br-federal-")) return `federal/${id}.md`;
  return `estaduais/${id.slice(3, 5).toUpperCase()}/${id}.md`;
};

const renderDocument = (metadata: typeof Metadata.Type, markdown: string) => {
  const frontmatter = Object.entries(metadata)
    .filter(([, value]) => value !== undefined)
    .map(([key, value]) => `${key}: ${JSON.stringify(value)}`)
    .join("\n");
  return `---\n${frontmatter}\n---\n\n# ${metadata.titulo}\n\n${markdown}\n`;
};

export const intact = Effect.fn("leis.intact")(
  function* (id: string) {
    const metadataFile = Bun.file(`fontes/${id}.json`);
    if (!(yield* Effect.tryPromise(() => metadataFile.exists()))) return false;
    const metadata = yield* Effect.tryPromise(() => metadataFile.text()).pipe(
      Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(Metadata))),
    );
    const documentFile = Bun.file(markdownPath(id));
    const htmlFile = Bun.file(`fontes/${id}.html.gz`);
    const files = [documentFile, htmlFile];
    for (const file of files)
      if (!(yield* Effect.tryPromise(() => file.exists()))) return false;
    const markdown = yield* Effect.tryPromise(() => documentFile.text());
    const match = markdown.match(
      /^---\n[\s\S]+?\n---\n\n# [^\n]+\n\n([\s\S]*)\n$/u,
    );
    if (match?.[1] === undefined || metadata.id !== id) return false;
    if (markdown !== renderDocument(metadata, match[1])) return false;
    const bytes = yield* Effect.tryPromise(() => htmlFile.arrayBuffer());
    const html = yield* Effect.try(() => gunzipSync(bytes));
    if (
      createHash("sha256").update(html).digest("hex") !== metadata.sha256_fonte
    )
      return false;
    if (
      createHash("sha256").update(match[1]).digest("hex") !==
      metadata.sha256_markdown
    )
      return false;
    if (metadata.sha256_dados !== undefined) {
      const dataFile = Bun.file(`fontes/${id}.dados.json.gz`);
      if (!(yield* Effect.tryPromise(() => dataFile.exists()))) return false;
      const dataBytes = yield* Effect.tryPromise(() => dataFile.arrayBuffer());
      const data = yield* Effect.try(() => gunzipSync(dataBytes));
      if (
        createHash("sha256").update(data).digest("hex") !==
        metadata.sha256_dados
      )
        return false;
    }
    return true;
  },
  Effect.catchAll((error) =>
    Effect.logWarning("Arquivo incompleto ou inválido", error).pipe(
      Effect.as(false),
    ),
  ),
);

export const saveDocument = Effect.fn("leis.saveDocument")(function* (
  metadata: typeof Metadata.Type,
  bytes: Uint8Array,
  markdown: string,
  data: Uint8Array | undefined,
) {
  const json = yield* Schema.encode(Schema.parseJson(Metadata, { space: 2 }))(
    metadata,
  );
  const files = [];
  if (data !== undefined)
    files.push({
      path: `fontes/${metadata.id}.dados.json.gz`,
      data: gzipSync(data, { level: 9 }),
    });
  files.push({
    path: `fontes/${metadata.id}.html.gz`,
    data: gzipSync(bytes, { level: 9 }),
  });
  files.push({
    path: markdownPath(metadata.id),
    data: renderDocument(metadata, markdown),
  });
  files.push({ path: `fontes/${metadata.id}.json`, data: `${json}\n` });
  for (const file of files) {
    yield* Effect.tryPromise(() => Bun.write(`${file.path}.tmp`, file.data));
    yield* Effect.tryPromise(() => rename(`${file.path}.tmp`, file.path));
  }
});
