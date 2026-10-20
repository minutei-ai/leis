import { load } from "cheerio";
import { Effect, Schema } from "effect";
import TurndownService from "turndown";
import { gfm } from "turndown-plugin-gfm";
import { Source } from "./catalog";

export class InvalidDocument extends Schema.TaggedError<InvalidDocument>()("InvalidDocument", {
  fonte: Schema.String,
  motivo: Schema.String,
}) {}

export const convert = Effect.fn("leis.convert")(function* (source: typeof Source.Type, html: string) {
  const $ = load(html);
  const body = $("body");
  const text = body.text().replace(/\s+/gu, " ").normalize("NFC");
  if (body.length !== 1 || text.length < 10000)
    return yield* Effect.fail(new InvalidDocument({ fonte: source.fonte, motivo: "Corpo da norma ausente ou curto" }));
  for (const marker of [source.marcadorInicial, source.marcadorFinal]) {
    if (!text.includes(marker))
      return yield* Effect.fail(new InvalidDocument({ fonte: source.fonte, motivo: `Dispositivo esperado ausente: ${marker}` }));
  }
  body.find("script, style").remove();
  body.find("[href]").each((_, element) => {
    const link = $(element);
    const href = link.attr("href");
    if (href !== undefined) link.attr("href", new URL(href, source.fonte).href);
  });
  const converter = new TurndownService({ headingStyle: "atx", codeBlockStyle: "fenced" });
  converter.use(gfm);
  converter.addRule("linebreak", { filter: "br", replacement: () => "<br>\n" });
  converter.addRule("strikethrough", {
    filter: (node) => ["S", "STRIKE", "DEL"].includes(node.nodeName),
    replacement: (content) => `~~${content}~~`,
  });
  return converter.turndown(body.html() ?? "").replace(/[ \t]+\n/gu, "\n").replace(/\n{3,}/gu, "\n\n").trim();
});
