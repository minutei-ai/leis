import { load } from "cheerio";
import { Effect, Schema } from "effect";
import TurndownService from "turndown";
import { gfm } from "turndown-plugin-gfm";
import { Source } from "./catalog";

export class InvalidDocument extends Schema.TaggedError<InvalidDocument>()(
  "InvalidDocument",
  {
    fonte: Schema.String,
    motivo: Schema.String,
  },
) {}

export const decodeHtml = (source: typeof Source.Type, bytes: Uint8Array) => {
  if (source.fonte.startsWith("https://www.al.sp.gov.br/repositorio/legislacao/"))
    return new TextDecoder("windows-1252", { fatal: true }).decode(bytes);
  return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
};

export const convert = Effect.fn("leis.convert")(function* (
  source: typeof Source.Type,
  html: string,
) {
  const $ = load(html);
  if (source.fonte.startsWith("https://legislacao.prefeitura.sp.gov.br/leis/")) {
    const content = $(".bx-retornaLei .customStyle:not(.bx-ementa)");
    const title = $(".bx-leis > h4").text().replace(/\s+/gu, " ").trim();
    if (content.length !== 1 || !source.id.startsWith("br-municipal-3550308-") || title.toLocaleLowerCase("pt-BR") !== source.titulo.toLocaleLowerCase("pt-BR"))
      return yield* Effect.fail(new InvalidDocument({ fonte: source.fonte, motivo: "Conteúdo compilado municipal ausente" }));
    $("body").html(content.html() ?? "");
  }
  if (source.id.startsWith("br-ba-")) {
    const content = $(".node--type-documento.node--view-mode-full .field--name-body");
    if (content.length !== 1)
      return yield* Effect.fail(new InvalidDocument({ fonte: source.fonte, motivo: "Corpo da norma baiana ausente" }));
    $("body").html(content.html() ?? "");
  }
  const body = $("body");
  body.find("script, style").remove();
  const text = body.text().replace(/\s+/gu, " ").normalize("NFC");
  if (body.length !== 1 || text.length < 100)
    return yield* Effect.fail(
      new InvalidDocument({
        fonte: source.fonte,
        motivo: "Corpo da norma ausente ou curto",
      }),
    );
  for (const marker of [source.marcadorInicial, source.marcadorFinal]) {
    if (marker !== undefined && !text.includes(marker))
      return yield* Effect.fail(
        new InvalidDocument({
          fonte: source.fonte,
          motivo: `Dispositivo esperado ausente: ${marker}`,
        }),
      );
  }
  if (!/Art(?:igo|\.)?\s*1[º°o.\s]/iu.test(text))
    return yield* Effect.fail(
      new InvalidDocument({
        fonte: source.fonte,
        motivo: "Artigo inicial ausente",
      }),
    );
  body.find('[style*="line-through"]').each((_, element) => {
    $(element).wrapInner("<del></del>");
  });
  body.find("[href]").each((_, element) => {
    const link = $(element);
    const href = link.attr("href");
    if (href !== undefined) link.attr("href", new URL(href, source.fonte).href);
  });
  const converter = new TurndownService({
    headingStyle: "atx",
    codeBlockStyle: "fenced",
  });
  converter.use(gfm);
  converter.addRule("linebreak", { filter: "br", replacement: () => "<br>\n" });
  converter.addRule("strikethrough", {
    filter: (node) => ["S", "STRIKE", "DEL"].includes(node.nodeName),
    replacement: (content) => `~~${content}~~`,
  });
  return converter
    .turndown(body.html() ?? "")
    .replace(/[ \t]+\n/gu, "\n")
    .replace(/\n{3,}/gu, "\n\n")
    .trim();
});
