import { load } from "cheerio";
import { createHash } from "node:crypto";
import { rename } from "node:fs/promises";
import { gzipSync } from "node:zlib";
import { Clock, Effect, Schema } from "effect";
import { Source } from "./catalog";

export const BahiaCategory = Schema.Literal("4", "5", "6", "7", "11", "30", "31", "32", "33");
export const BahiaLink = Schema.Struct({
  fonte: Schema.String.pipe(Schema.pattern(/^https:\/\/www\.legislabahia\.ba\.gov\.br\/documentos\/[a-z0-9-]+$/u)),
  titulo: Schema.NonEmptyString,
});
export const BahiaPage = Schema.Struct({
  categoria: BahiaCategory,
  pagina: Schema.Int.pipe(Schema.nonNegative()),
  total: Schema.Int.pipe(Schema.positive()),
  inicio: Schema.Int.pipe(Schema.positive()),
  fim: Schema.Int.pipe(Schema.positive()),
  proxima: Schema.NullOr(Schema.String),
  ultima: Schema.Int.pipe(Schema.nonNegative()),
  normas: Schema.Array(BahiaLink),
});
export const BahiaInventory = Schema.Struct({
  fonte: Schema.String,
  coletado_em: Schema.String,
  sha256_fonte: Schema.String,
  pagina: BahiaPage,
});
export class BahiaFailure extends Schema.TaggedError<BahiaFailure>()("BahiaFailure", {
  fonte: Schema.String,
  motivo: Schema.String,
}) {}

export const bahiaSearch = (category: typeof BahiaCategory.Type, page: number) =>
  `https://www.legislabahia.ba.gov.br/documentos?categoria%5B0%5D=${category}&page=${page}`;

export const parseBahiaPage = Effect.fn("bahia.parsePage")(function* (html: string, category: typeof BahiaCategory.Type, page: number) {
  const $ = load(html);
  const selected = $('select[name="categoria[]"] option[selected]');
  if (selected.length !== 1 || selected.attr("value") !== category)
    return yield* Effect.fail(new BahiaFailure({ fonte: "Bahia pesquisa", motivo: "Categoria devolvida difere da solicitada" }));
  const range = $(".view-header").text().replace(/\s+/gu, " ").trim().match(/^(\d+) - (\d+) de (\d+)$/u);
  if (range === null)
    return yield* Effect.fail(new BahiaFailure({ fonte: "Bahia pesquisa", motivo: "Intervalo e total ausentes; não é catálogo vazio" }));
  const start = Number(range[1]);
  const end = Number(range[2]);
  const total = Number(range[3]);
  const links: Array<typeof BahiaLink.Type> = [];
  for (const row of $("td[headers='view-title-table-column'] b a").toArray()) {
    const href = $(row).attr("href");
    if (href === undefined)
      return yield* Effect.fail(new BahiaFailure({ fonte: "Bahia pesquisa", motivo: "Resultado sem endereço" }));
    links.push(yield* Schema.decodeUnknown(BahiaLink)({ fonte: new URL(href, "https://www.legislabahia.ba.gov.br").href, titulo: $(row).text().replace(/\s+/gu, " ").trim() }));
  }
  if (total > 1000000 || start !== page * 20 + 1 || end !== Math.min(start + 19, total) || links.length !== end - start + 1 || new Set(links.map((link) => link.fonte)).size !== links.length)
    return yield* Effect.fail(new BahiaFailure({ fonte: "Bahia pesquisa", motivo: "Resultados não fecham intervalo ou página solicitada" }));
  const next = $("a[rel=next]").attr("href");
  const last = $("a[rel=last]").attr("href");
  const nextLinks: Array<string> = [];
  const lastPages = [page];
  for (const [kind, href] of [["next", next], ["last", last]]) {
    if (href === undefined) continue;
    const url = new URL(href, "https://www.legislabahia.ba.gov.br/documentos");
    const categories = Array.from(url.searchParams).filter(([key]) => /^categoria\[\d+\]$/u.test(key)).map(([, value]) => value);
    const allowed = Array.from(url.searchParams).every(([key, value]) => key === "page" || /^categoria\[\d+\]$/u.test(key) || (["num", "ementa", "exp", "data[min]", "data[max]"].includes(key) && value === ""));
    const number = Number(url.searchParams.get("page"));
    if (url.origin !== "https://www.legislabahia.ba.gov.br" || url.pathname !== "/documentos" || categories.length !== 1 || categories[0] !== category || !allowed || !Number.isInteger(number) || number < 0)
      return yield* Effect.fail(new BahiaFailure({ fonte: url.href, motivo: "Paginação altera origem ou consulta" }));
    if (kind === "next") {
      if (number !== page + 1)
        return yield* Effect.fail(new BahiaFailure({ fonte: url.href, motivo: "Próxima página fora de sequência" }));
      nextLinks.push(url.href);
    }
    if (kind === "last") lastPages.push(number);
  }
  if ((end < total) !== (nextLinks.length > 0) || (end < total && lastPages.at(-1) !== Math.ceil(total / 20) - 1))
    return yield* Effect.fail(new BahiaFailure({ fonte: "Bahia pesquisa", motivo: "Paginação incompleta para o total declarado" }));
  return BahiaPage.make({ categoria: category, pagina: page, total, inicio: start, fim: end, proxima: nextLinks[0] ?? null, ultima: lastPages.at(-1) ?? page, normas: links });
});

export const bahiaSource = Effect.fn("bahia.source")(function* (link: typeof BahiaLink.Type, html: string) {
  const $ = load(html);
  const node = $(".node--type-documento.node--view-mode-full");
  const short = $("link[rel=shortlink]").attr("href");
  const match = short?.match(/^https:\/\/www\.legislabahia\.ba\.gov\.br\/node\/(\d+)$/u);
  const canonical = $("link[rel=canonical]").attr("href");
  const date = node.find(".field--name-field-data-doc time").attr("datetime")?.slice(0, 10);
  const body = node.find(".field--name-body").clone();
  body.find("style,script").remove();
  const titles = body.find(".lei, .lei1, .titulo, .normalanexo, p").toArray().map((element) => {
    const heading = $(element).clone();
    heading.find(".revogado").remove();
    heading.find("a").filter((_, anchor) => $(anchor).text().trim() === "[Download]").remove();
    return heading.text().replace(/\s+/gu, " ").trim();
  });
  const title = titles.find((value) => /^(?:LEI|LC|LD|CONSTITUIÇÃO|EMENDA)\b/iu.test(value));
  const compared = [title ?? "", link.titulo].map((value) => value.toLocaleUpperCase("pt-BR").replace(/^LD /u, "LEI DELEGADA ").replace(/^LC /u, "LEI COMPLEMENTAR ").replace(/^EMENDA À CONSTITUIÇÃO /u, "EMENDA CONSTITUCIONAL ").replace(/N\.?[º°]\s*0*(\d+)/u, "Nº $1").replace(/, DE /u, " DE ").replace(/\s*\[DOWNLOAD\]$/u, "").replace(/\.$/u, ""));
  if (node.length !== 1 || match?.[1] === undefined || node.attr("data-history-node-id") !== match[1])
    return yield* Effect.fail(new BahiaFailure({ fonte: link.fonte, motivo: "Identidade Drupal ausente ou divergente" }));
  if (canonical !== link.fonte || date === undefined)
    return yield* Effect.fail(new BahiaFailure({ fonte: link.fonte, motivo: "Endereço canônico ou data oficial ausente ou divergente" }));
  const parsed = yield* Schema.decodeUnknown(Schema.DateFromString)(date);
  if (parsed.toISOString().slice(0, 10) !== date)
    return yield* Effect.fail(new BahiaFailure({ fonte: link.fonte, motivo: "Data oficial inválida" }));
  const writtenDate = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "long", year: "numeric", timeZone: "UTC" }).format(parsed).toLocaleUpperCase("pt-BR");
  const category = node.find(".field--name-field-categoria-doc .field--item").text().trim();
  const historicalConstitution = category === `Constituição Estadual ${date.slice(0, 4)}`
    && compared[1]?.replace(/ - TEXTO CONSOLIDADO$/u, "") === `CONSTITUIÇÃO DO ESTADO DA BAHIA DE ${writtenDate}`
    && ["CONSTITUIÇÃO", "CONSTITUIÇÃO DO ESTADO DA BAHIA"].includes(compared[0] ?? "")
    && body.text().replace(/\s+/gu, " ").toLocaleUpperCase("pt-BR").includes(writtenDate);
  if (compared[0] !== compared[1] && !historicalConstitution)
    return yield* Effect.fail(new BahiaFailure({ fonte: link.fonte, motivo: `Título do catálogo diverge da íntegra: ${title}` }));
  return Source.make({ ...link, id: `br-ba-norma-${match[1]}`, data: date });
});

export const bahiaFailureId = (url: string) => `bahia-url-${createHash("sha256").update(url).digest("hex")}`;

export const bahiaRequest = Effect.fn("bahia.request")(function* (url: string) {
  const target = new URL(url);
  if (target.origin !== "https://www.legislabahia.ba.gov.br" || !target.pathname.startsWith("/documentos"))
    return yield* Effect.fail(new BahiaFailure({ fonte: url, motivo: "Origem ou caminho não autorizado" }));
  yield* Effect.sleep("500 millis");
  const response = yield* Effect.tryPromise(() => fetch(url, { headers: { "User-Agent": "MinuteiLeis/0.5 (+https://github.com/minutei-ai/leis)" }, signal: AbortSignal.timeout(45000) }));
  if (response.status !== 200 || new URL(response.url).origin !== target.origin || !response.headers.get("content-type")?.includes("text/html"))
    return yield* Effect.fail(new BahiaFailure({ fonte: url, motivo: `Resposta inesperada: ${response.status} ${response.url}` }));
  const bytes = new Uint8Array(yield* Effect.tryPromise(() => response.arrayBuffer()));
  if (bytes.length === 0 || bytes.length > 25000000)
    return yield* Effect.fail(new BahiaFailure({ fonte: url, motivo: "Página vazia ou maior que 25 MB" }));
  return bytes;
});

export const bahiaInventoryPath = (category: typeof BahiaCategory.Type, page: number) =>
  `catalogos/bahia/${category}-${String(page).padStart(5, "0")}`;

export const discoverBahiaPage = Effect.fn("bahia.discoverPage")(function* (category: typeof BahiaCategory.Type, page: number, url: string, refresh: boolean) {
  const path = bahiaInventoryPath(category, page);
  if (!refresh && (yield* Effect.tryPromise(() => Bun.file(`${path}.json`).exists())))
    return yield* Effect.tryPromise(() => Bun.file(`${path}.json`).text()).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(BahiaInventory))));
  const bytes = yield* bahiaRequest(url);
  const parsed = yield* parseBahiaPage(new TextDecoder("utf-8", { fatal: true }).decode(bytes), category, page);
  const now = yield* Clock.currentTimeMillis;
  const inventory = BahiaInventory.make({ fonte: url, coletado_em: new Date(now).toISOString(), sha256_fonte: createHash("sha256").update(bytes).digest("hex"), pagina: parsed });
  yield* Effect.tryPromise(() => Bun.write(`${path}.html.gz.tmp`, gzipSync(bytes, { level: 9 })));
  yield* Effect.tryPromise(() => rename(`${path}.html.gz.tmp`, `${path}.html.gz`));
  const json = yield* Schema.encode(Schema.parseJson(BahiaInventory, { space: 2 }))(inventory);
  yield* Effect.tryPromise(() => Bun.write(`${path}.json.tmp`, `${json}\n`));
  yield* Effect.tryPromise(() => rename(`${path}.json.tmp`, `${path}.json`));
  yield* Effect.log(`Bahia/${category}/${page}: ${parsed.normas.length} resultados de ${parsed.total}`);
  return inventory;
});
