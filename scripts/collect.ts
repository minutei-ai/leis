import { mkdir } from "node:fs/promises";
import { createHash } from "node:crypto";
import { Clock, Effect, Schema } from "effect";
import { catalog, Metadata } from "./catalog";
import { convert, InvalidDocument } from "./convert";
import { saveDocument } from "./document";

const program = Effect.gen(function* () {
  yield* Effect.tryPromise(() => mkdir("federal", { recursive: true }));
  yield* Effect.tryPromise(() => mkdir("fontes", { recursive: true }));
  for (const source of catalog) {
    const response = yield* Effect.tryPromise(() =>
      fetch(source.fonte, {
        headers: {
          "User-Agent": "MinuteiLeis/0.1 (+https://github.com/minutei-ai/leis)",
          Accept: "text/html",
        },
        signal: AbortSignal.timeout(30000),
      }),
    );
    if (
      !response.ok ||
      !response.url.startsWith("https://www2.camara.leg.br/legin/") ||
      !response.headers.get("content-type")?.includes("text/html")
    )
      return yield* Effect.fail(
        new InvalidDocument({
          fonte: source.fonte,
          motivo: `Resposta inesperada: ${response.status} ${response.url}`,
        }),
      );
    const bytes = new Uint8Array(
      yield* Effect.tryPromise(() => response.arrayBuffer()),
    );
    const markdown = yield* convert(
      source,
      new TextDecoder("utf-8", { fatal: true }).decode(bytes),
    );
    const hash = createHash("sha256").update(bytes).digest("hex");
    const bodyHash = createHash("sha256").update(markdown).digest("hex");
    const metadataPath = `fontes/${source.id}.json`;
    const previous = Bun.file(metadataPath);
    if (yield* Effect.tryPromise(() => previous.exists())) {
      const metadata = yield* Effect.tryPromise(() => previous.text()).pipe(
        Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(Metadata))),
      );
      const document = Bun.file(`federal/${source.id}.md`);
      if (
        metadata.sha256_fonte === hash &&
        metadata.sha256_markdown === bodyHash &&
        (yield* Effect.tryPromise(() => document.exists()))
      ) {
        const saved = yield* Effect.tryPromise(() => document.text());
        if (saved.endsWith(`\n${markdown}\n`)) {
          yield* Effect.log(`Sem alteração: ${source.id}`);
          yield* Effect.sleep("1 second");
          continue;
        }
      }
    }
    const now = yield* Clock.currentTimeMillis;
    const metadata = Metadata.make({
      id: source.id,
      titulo: source.titulo,
      data: source.data,
      fonte: source.fonte,
      versao: "texto atualizado pela Câmara na data de coleta",
      coletado_em: new Date(now).toISOString(),
      sha256_fonte: hash,
      sha256_markdown: bodyHash,
    });
    yield* saveDocument(metadata, bytes, markdown, undefined);
    yield* Effect.log(`Coletado: ${source.id} (${markdown.length} caracteres)`);
    yield* Effect.sleep("1 second");
  }
});

await Effect.runPromise(program);
