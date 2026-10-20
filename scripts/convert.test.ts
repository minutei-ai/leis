import { expect, test } from "bun:test";
import { load } from "cheerio";
import { createHash } from "node:crypto";
import { gunzipSync } from "node:zlib";
import { Effect, Either, Schema } from "effect";
import { catalog, Metadata } from "./catalog";
import { convert } from "./convert";

for (const source of catalog) {
  test(`reproduz fonte e Markdown: ${source.id}`, async () => {
    const bytes = gunzipSync(
      await Bun.file(`fontes/${source.id}.html.gz`).arrayBuffer(),
    );
    const metadata = Schema.decodeUnknownSync(Schema.parseJson(Metadata))(
      await Bun.file(`fontes/${source.id}.json`).text(),
    );
    const markdown = await Effect.runPromise(
      convert(source, bytes.toString("utf8")),
    );
    const saved = await Bun.file(`federal/${source.id}.md`).text();
    expect(metadata.id).toBe(source.id);
    expect(metadata.fonte).toBe(source.fonte);
    expect(metadata.sha256_fonte).toBe(
      createHash("sha256").update(bytes).digest("hex"),
    );
    expect(metadata.sha256_markdown).toBe(
      createHash("sha256").update(markdown).digest("hex"),
    );
    expect(saved.endsWith(`\n${markdown}\n`)).toBe(true);
    expect(markdown).not.toContain("�");
    expect(markdown).toContain("Art.");
  });
}

test("recusa página de erro servida com status 200", async () => {
  const source = catalog[0];
  if (source === undefined) return;
  const result = await Effect.runPromise(
    convert(source, "<html><body>Acesso negado</body></html>").pipe(
      Effect.either,
    ),
  );
  expect(Either.isLeft(result)).toBe(true);
});

test("preserva revogações, links e tabelas da fonte real", async () => {
  const source = catalog[0];
  if (source === undefined) return;
  const bytes = gunzipSync(
    await Bun.file(`fontes/${source.id}.html.gz`).arrayBuffer(),
  );
  const html = bytes.toString("utf8");
  const annotated = html.replace(
    /<body([^>]*)>/iu,
    '<body$1><p><s>redação anterior</s> <a href="nota.html">nota</a></p><table><thead><tr><th>Campo</th></tr></thead><tbody><tr><td>Valor</td></tr></tbody></table>',
  );
  const markdown = await Effect.runPromise(convert(source, annotated));
  expect(markdown).toContain("~~redação anterior~~");
  expect(markdown).toContain(new URL("nota.html", source.fonte).href);
  expect(markdown).toContain("| Campo |");
  const truncated = `<html><body>${load(html)("body").text().slice(0, 20000)}</body></html>`;
  const result = await Effect.runPromise(
    convert(source, truncated).pipe(Effect.either),
  );
  expect(Either.isLeft(result)).toBe(true);
});
