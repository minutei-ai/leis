import { load } from "cheerio";
import { createHash } from "node:crypto";
import { mkdir, rename } from "node:fs/promises";
import { gzipSync } from "node:zlib";
import { Clock, Effect, Schema } from "effect";

const months = new Map([
  ["janeiro", "01"], ["fevereiro", "02"], ["março", "03"], ["abril", "04"],
  ["maio", "05"], ["junho", "06"], ["julho", "07"], ["agosto", "08"],
  ["setembro", "09"], ["outubro", "10"], ["novembro", "11"], ["dezembro", "12"],
]);

export const PmspLink = Schema.Struct({
  fonte: Schema.String.pipe(Schema.pattern(/^https:\/\/legislacao\.prefeitura\.sp\.gov\.br\/leis\/[a-z0-9-]+$/u)),
  titulo: Schema.NonEmptyString,
});
export const PmspNorm = Schema.Struct({
  ...PmspLink.fields,
  id: Schema.String.pipe(Schema.pattern(/^br-municipal-3550308-lei-\d{4}-\d{2}-\d{2}-\d+$/u)),
  data: Schema.String,
});
export const PmspPage = Schema.Struct({
  pagina: Schema.Int,
  paginas: Schema.Int,
  total: Schema.Int,
  normas: Schema.Array(PmspNorm),
  pendencias: Schema.Array(PmspLink),
});
export const PmspInventory = Schema.Struct({
  ano_publicacao: Schema.Int,
  fonte: Schema.String,
  metodo: Schema.Literal("POST"),
  consulta: Schema.Record({ key: Schema.String, value: Schema.String }),
  coletado_em: Schema.String,
  total: Schema.Int,
  paginas: Schema.Array(Schema.Struct({ numero: Schema.Int, sha256_fonte: Schema.String })),
  normas: Schema.Array(PmspNorm),
  pendencias: Schema.Array(PmspLink),
});
export class PmspFailure extends Schema.TaggedError<PmspFailure>()("PmspFailure", {
  fonte: Schema.String,
  motivo: Schema.String,
}) {}

export const pmspNorm = Effect.fn("pmsp.norm")(function* (link: typeof PmspLink.Type) {
  if (!new URL(link.fonte).pathname.startsWith("/leis/lei-"))
    return yield* Effect.fail(new PmspFailure({ fonte: link.fonte, motivo: "Resultado não aponta para uma lei" }));
  const match = link.titulo.normalize("NFC").match(/^LEI Nº\s*([\d.]+)\s+de\s+(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})$/iu);
  if (match === null || match[3] === undefined)
    return yield* Effect.fail(new PmspFailure({ fonte: link.fonte, motivo: "Título sem identidade de lei suportada" }));
  const month = months.get(match[3].toLowerCase());
  if (month === undefined || match[1] === undefined || match[2] === undefined)
    return yield* Effect.fail(new PmspFailure({ fonte: link.fonte, motivo: "Mês ou número inválido" }));
  const date = `${match[4]}-${month}-${match[2].padStart(2, "0")}`;
  const decoded = yield* Schema.decodeUnknown(Schema.DateFromString)(date);
  if (decoded.toISOString().slice(0, 10) !== date)
    return yield* Effect.fail(new PmspFailure({ fonte: link.fonte, motivo: "Data inexistente" }));
  return PmspNorm.make({ ...link, data: date, id: `br-municipal-3550308-lei-${date}-${match[1].replaceAll(".", "")}` });
});

export const parsePmspPage = Effect.fn("pmsp.parsePage")(function* (html: string) {
  const $ = load(html);
  const count = $("#number-results").text().replace(/\s+/gu, " ").trim();
  const norms: Array<typeof PmspNorm.Type> = [];
  const pending: Array<typeof PmspLink.Type> = [];
  if (count === "0" && $("#resultados").text().includes("Nenhum resultado encontrado"))
    return PmspPage.make({ pagina: 1, paginas: 1, total: 0, normas: norms, pendencias: pending });
  const range = count.match(/^(\d+) - (\d+) de (\d+)$/u);
  const pagination = $(".pagination span").first().text().trim().match(/^Página (\d+) de (\d+)$/u);
  if ((range === null && !/^\d+$/u.test(count)) || pagination === null)
    return yield* Effect.fail(new PmspFailure({ fonte: "PMSP busca", motivo: "Total ou paginação não reconhecidos" }));
  const counts = { total: Number(count), page: Number(count) };
  if (range !== null) {
    counts.total = Number(range[3]);
    counts.page = Number(range[2]) - Number(range[1]) + 1;
  }
  const total = counts.total;
  if (total >= 10000)
    return yield* Effect.fail(new PmspFailure({ fonte: "PMSP busca", motivo: "Limite de 10.000 resultados atingido; particione o período" }));
  const links = $("#resultados .bx-resultado > a").toArray();
  if (links.length !== counts.page)
    return yield* Effect.fail(new PmspFailure({ fonte: "PMSP busca", motivo: "Quantidade de links difere do intervalo declarado" }));
  for (const element of links) {
    const href = $(element).attr("href");
    if (href === undefined)
      return yield* Effect.fail(new PmspFailure({ fonte: "PMSP busca", motivo: "Resultado sem link" }));
    const link = yield* Schema.decodeUnknown(PmspLink)({ fonte: new URL(href, "https://legislacao.prefeitura.sp.gov.br").href, titulo: $(element).find("h4").text().replace(/\s+/gu, " ").trim() });
    const norm = yield* pmspNorm(link).pipe(Effect.option);
    if (norm._tag === "None") pending.push(link);
    else norms.push(norm.value);
  }
  return PmspPage.make({ pagina: Number(pagination[1]), paginas: Number(pagination[2]), total, normas: norms, pendencias: pending });
});

export const pmspRequest = Effect.fn("pmsp.request")(function* (url: string, init: RequestInit) {
  if (!url.startsWith("https://legislacao.prefeitura.sp.gov.br/"))
    return yield* Effect.fail(new PmspFailure({ fonte: url, motivo: "Origem não autorizada" }));
  yield* Effect.sleep("500 millis");
  const response = yield* Effect.tryPromise(() => fetch(url, { ...init, signal: AbortSignal.timeout(45000) }));
  if (response.status !== 200 || !response.url.startsWith("https://legislacao.prefeitura.sp.gov.br/"))
    return yield* Effect.fail(new PmspFailure({ fonte: url, motivo: `Resposta inesperada: ${response.status} ${response.url}` }));
  return response;
});

export const discoverPmspYear = Effect.fn("pmsp.discoverYear")(function* (year: number, refresh: boolean) {
  const path = `catalogos/pmsp/${year}`;
  const file = Bun.file(`${path}.json`);
  if (!refresh && (yield* Effect.tryPromise(() => file.exists())))
    return yield* Effect.tryPromise(() => file.text()).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(PmspInventory))));
  const query = { "ano-inicial": `01/01/${year}`, "ano-final": `31/12/${year}`, "tipo[]": "LEI", limite: "100" };
  const headers = new Headers({ "User-Agent": "MinuteiLeis/0.4 (+https://github.com/minutei-ai/leis)" });
  const url = "https://legislacao.prefeitura.sp.gov.br/busca";
  const response = yield* pmspRequest(url, { method: "POST", body: new URLSearchParams(query), headers });
  const firstBytes = new Uint8Array(yield* Effect.tryPromise(() => response.arrayBuffer()));
  const first = yield* parsePmspPage(new TextDecoder("utf-8", { fatal: true }).decode(firstBytes));
  const norms = new Map<string, typeof PmspNorm.Type>();
  const pending: Array<typeof PmspLink.Type> = [];
  const pages: Array<typeof PmspInventory.Type.paginas[number]> = [];
  yield* Effect.tryPromise(() => mkdir(path, { recursive: true }));
  for (const index of Array.from({ length: first.paginas }, (_, index) => index)) {
    const page = index + 1;
    const bytes = yield* Effect.gen(function* () {
      if (page === 1) return firstBytes;
      const next = yield* pmspRequest(`${url}/pg/${page}`, { method: "POST", body: new URLSearchParams(query), headers });
      return new Uint8Array(yield* Effect.tryPromise(() => next.arrayBuffer()));
    });
    if (bytes.length === 0 || bytes.length > 25000000)
      return yield* Effect.fail(new PmspFailure({ fonte: url, motivo: "Página vazia ou maior que 25 MB" }));
    const parsed = yield* parsePmspPage(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    if (parsed.pagina !== page || parsed.paginas !== first.paginas || parsed.total !== first.total)
      return yield* Effect.fail(new PmspFailure({ fonte: url, motivo: "Consulta mudou durante a paginação" }));
    for (const norm of parsed.normas) norms.set(norm.id, norm);
    pending.push(...parsed.pendencias);
    pages.push({ numero: page, sha256_fonte: createHash("sha256").update(bytes).digest("hex") });
    yield* Effect.tryPromise(() => Bun.write(`${path}/${page}.html.gz.tmp`, gzipSync(bytes, { level: 9 })));
    yield* Effect.tryPromise(() => rename(`${path}/${page}.html.gz.tmp`, `${path}/${page}.html.gz`));
  }
  if (norms.size + pending.length !== first.total)
    return yield* Effect.fail(new PmspFailure({ fonte: url, motivo: "Identidades recebidas não fecham o total declarado" }));
  const now = yield* Clock.currentTimeMillis;
  const inventory = PmspInventory.make({ ano_publicacao: year, fonte: url, metodo: "POST", consulta: query, coletado_em: new Date(now).toISOString(), total: first.total, paginas: pages, normas: Array.from(norms.values()), pendencias: pending });
  const json = yield* Schema.encode(Schema.parseJson(PmspInventory, { space: 2 }))(inventory);
  yield* Effect.tryPromise(() => Bun.write(`${path}.json.tmp`, `${json}\n`));
  yield* Effect.tryPromise(() => rename(`${path}.json.tmp`, `${path}.json`));
  yield* Effect.log(`PMSP/${year}: ${norms.size} leis, ${pending.length} pendências, ${pages.length} páginas`);
  return inventory;
});
