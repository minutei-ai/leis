import { Effect, Schema } from "effect";
import { BahiaInventory } from "./bahia";
import { AlmgInventory } from "./almg";
import { AlespInventory } from "./alesp";
import { Metadata } from "./catalog";
import { intact } from "./document";
import { PmspInventory } from "./pmsp";
import { Inventory } from "./senado";

await Effect.runPromise(Effect.gen(function* () {
  const metadataPaths = yield* Effect.tryPromise(() => Array.fromAsync(new Bun.Glob("fontes/*.json").scan(".")));
  const published = new Set<string>();
  const versions = new Map<string, number>();
  for (const path of metadataPaths.sort()) {
    const metadata = yield* Effect.tryPromise(() => Bun.file(path).text()).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(Metadata))));
    if (!(yield* intact(metadata.id))) continue;
    published.add(metadata.id);
    versions.set(metadata.versao, (versions.get(metadata.versao) ?? 0) + 1);
  }
  const paths = yield* Effect.tryPromise(() => Array.fromAsync(new Bun.Glob("catalogos/senado/*/*.json").scan(".")));
  const rows: Array<string> = [];
  const indexed = new Set<string>();
  for (const path of paths.sort().reverse()) {
    const inventory = yield* Effect.tryPromise(() => Bun.file(path).text()).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(Inventory))));
    for (const norm of inventory.normas) indexed.add(norm.id);
    const collected = inventory.normas.filter((norm) => published.has(norm.id)).length;
    rows.push(`| ${inventory.tipo} | ${inventory.ano} | ${inventory.normas.length} | ${inventory.pendencias.length} | ${collected} | ${inventory.normas.length - collected} |`);
  }
  const almgPaths = yield* Effect.tryPromise(() => Array.fromAsync(new Bun.Glob("catalogos/almg/*.json").scan(".")));
  const almgIndexed = new Set<string>();
  const almgRows: Array<string> = [];
  for (const path of almgPaths.sort().reverse()) {
    const inventory = yield* Effect.tryPromise(() => Bun.file(path).text()).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(AlmgInventory))));
    for (const norm of inventory.normas) almgIndexed.add(norm.id);
    const collected = inventory.normas.filter((norm) => published.has(norm.id)).length;
    const excluded = Object.values(inventory.fora_escopo).reduce((sum, count) => sum + count, 0);
    almgRows.push(`| ${inventory.ano} | ${inventory.normas.length} | ${inventory.pendencias.length} | ${excluded} | ${collected} | ${inventory.normas.length - collected} |`);
  }
  const alespPaths = yield* Effect.tryPromise(() => Array.fromAsync(new Bun.Glob("catalogos/alesp/*.json").scan(".")));
  const alespIndexed = new Set<string>();
  const alespPages = new Set<number>();
  const alespTotals = new Set<number>();
  const alespExpectedPages = new Set<number>();
  for (const path of alespPaths.sort()) {
    const inventory = yield* Effect.tryPromise(() => Bun.file(path).text()).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(AlespInventory))));
    for (const record of inventory.pagina.content) alespIndexed.add(`br-sp-norma-${record.idNorma}`);
    alespPages.add(inventory.pagina.number);
    alespTotals.add(inventory.pagina.totalElements);
    alespExpectedPages.add(inventory.pagina.totalPages);
  }
  const alespCollected = Array.from(alespIndexed).filter((id) => published.has(id)).length;
  const pmspPaths = yield* Effect.tryPromise(() => Array.fromAsync(new Bun.Glob("catalogos/pmsp/*.json").scan(".")));
  const pmspIndexed = new Set<string>();
  const pmspRows: Array<string> = [];
  for (const path of pmspPaths.sort().reverse()) {
    const inventory = yield* Effect.tryPromise(() => Bun.file(path).text()).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(PmspInventory))));
    for (const norm of inventory.normas) pmspIndexed.add(norm.id);
    const collected = inventory.normas.filter((norm) => published.has(norm.id)).length;
    pmspRows.push(`| ${inventory.ano_publicacao} | ${inventory.total} | ${inventory.normas.length} | ${inventory.pendencias.length} | ${collected} | ${inventory.normas.length - collected} |`);
  }
  const pmspCollected = Array.from(pmspIndexed).filter((id) => published.has(id)).length;
  const bahiaPaths = yield* Effect.tryPromise(() => Array.fromAsync(new Bun.Glob("catalogos/bahia/*.json").scan(".")));
  const bahiaLinks = new Set<string>();
  const bahiaInventories: Array<typeof BahiaInventory.Type> = [];
  for (const path of bahiaPaths.sort()) {
    const inventory = yield* Effect.tryPromise(() => Bun.file(path).text()).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(BahiaInventory))));
    const page = inventory.pagina;
    for (const link of page.normas) bahiaLinks.add(link.fonte);
    bahiaInventories.push(inventory);
  }
  const bahiaCollected = Array.from(published).filter((id) => id.startsWith("br-ba-")).length;
  const missing = Array.from(indexed).filter((id) => !published.has(id));
  const almgMissing = Array.from(almgIndexed).filter((id) => !published.has(id));
  const failures = yield* Effect.tryPromise(() => Array.fromAsync(new Bun.Glob("falhas/*.json").scan(".")));
  const catalogFailures = yield* Effect.tryPromise(() => Array.fromAsync(new Bun.Glob("falhas-catalogos/*.json").scan(".")));
  const report = [
    "# Cobertura do acervo", "",
    "Este relatório é gerado por `bun run coverage` a partir dos catálogos e dos arquivos com hashes íntegros presentes neste commit. Não mede toda a legislação brasileira nem a completude dos catálogos oficiais.", "",
    `- Normas publicadas: **${published.size}**.`,
    `- Normas identificadas nos catálogos consultados do Senado: **${indexed.size}**.`,
    `- Dessas, ainda sem Markdown íntegro: **${missing.length}**.`,
    `- Normas identificadas nos catálogos consultados da ALMG: **${almgIndexed.size}**.`,
    `- Dessas, ainda sem Markdown íntegro: **${almgMissing.length}**.`,
    `- Normas identificadas nas páginas consultadas da Alesp: **${alespIndexed.size}**; publicadas: **${alespCollected}**.`,
    `- Leis municipais de São Paulo identificadas: **${pmspIndexed.size}**; publicadas: **${pmspCollected}**.`,
    `- Documentos baianos catalogados: **${bahiaLinks.size}**; publicados: **${bahiaCollected}**.`,
    `- Falhas de coleta registradas: **${failures.length}**.`,
    `- Falhas de descoberta de catálogos registradas: **${catalogFailures.length}**.`, "",
    "## Versões publicadas", "",
    ...Array.from(versions.keys()).sort().map((version) => `- ${version}: ${versions.get(version)}.`), "",
    "## Catálogos federais do Senado", "",
    "Cada catálogo preserva a resposta oficial comprimida, o filtro e a data de coleta. A consulta por tipo/ano não expõe total independente ou paginação; as quantidades abaixo correspondem aos registros efetivamente recebidos. Pendências são identificações que o coletor ainda não consegue representar.", "",
    "| Tipo | Ano | Identificadas | Pendências de identificação ou texto | Publicadas | A coletar |",
    "| --- | ---: | ---: | ---: | ---: | ---: |", ...rows, "",
    "## Minas Gerais — ALMG", "",
    "O CSV anual é preservado integralmente. A coleta de textos abrange LEI, LCP, LDL, DEL, DEC, CON e EMC. Outros tipos de ato são contabilizados separadamente, sem serem tratados como leis ausentes ou falhas de download.", "",
    "| Ano | Identificadas | Pendências de identificação ou texto | Outras famílias no CSV | Publicadas | A coletar |",
    "| ---: | ---: | ---: | ---: | ---: | ---: |", ...almgRows, "",
    "## São Paulo — Alesp", "",
    `- Páginas preservadas: **${alespPages.size}**. Totais de páginas informados pela API: ${Array.from(alespExpectedPages).sort((a, b) => a - b).join(", ")}.`,
    `- Totais de registros informados pela API nas respostas: ${Array.from(alespTotals).sort((a, b) => a - b).join(", ")}.`,
    `- Identidades únicas recebidas: **${alespIndexed.size}**; textos publicados: **${alespCollected}**; a coletar: **${alespIndexed.size - alespCollected}**.`, "",
    "A API paginada da Alesp abrange leis e outras famílias de atos. O total oficial é de registros do catálogo, não de arquivos Markdown nem de todas as normas já editadas no estado. Páginas ausentes, mudanças do total durante a coleta, duplicações e ausência de texto impedem equiparar os números à completude estadual. O coletor prefere a íntegra atualizada em HTML e registra falha quando só há PDF ou não há texto disponível.", "",
    "## Município de São Paulo — PMSP (IBGE 3550308)", "",
    "A descoberta consulta apenas o tipo LEI, particionado por ano de publicação. O portal limita buscas a 10.000 resultados; o coletor recusa períodos que atinjam esse teto. Cada página HTML da pesquisa é preservada e seu total, paginação e identidades são reproduzidos pela auditoria. A versão publicada é o texto compilado fornecido pela prefeitura, com redações históricas presentes na fonte; não é certificação de vigência.", "",
    "| Ano de publicação | Total declarado | Identificadas | Pendências | Publicadas | A coletar |",
    "| ---: | ---: | ---: | ---: | ---: | ---: |", ...pmspRows, "",
    "## Bahia — Casa Civil", "",
    "Categorias integradas: leis ordinárias (7), complementares (5), delegadas (6), emendas (4) e constituições de 1989 (11), 1891 (30), 1935 (31), 1947 (32) e 1967 (33). A tabela distingue páginas preservadas do total informado; uma descoberta parcial não significa catálogo esgotado. A identidade publicada usa o node ID oficial do Drupal, conferido no shortlink e no corpo. O texto é a compilação disponibilizada na data da coleta, sem certificação de vigência. Falhas antes de resolver o node ID usam um hash do endereço apenas na fila de retentativas, nunca como identidade de norma.", "",
    "| Categoria oficial | Páginas preservadas | Páginas declaradas | Documentos nas páginas | Total declarado |",
    "| --- | ---: | ---: | ---: | ---: |",
    ...Array.from(new Set(bahiaInventories.map((inventory) => inventory.pagina.categoria))).map((category) => {
      const pages = bahiaInventories.filter((inventory) => inventory.pagina.categoria === category);
      const total = pages[0]?.pagina.total ?? 0;
      return `| ${category} | ${pages.length} | ${Math.ceil(total / 20)} | ${pages.reduce((sum, inventory) => sum + inventory.pagina.normas.length, 0)} | ${total} |`;
    }), "",
    "## Lacunas", "",
    "A descoberta federal está em expansão por anos e famílias. Anos ou tipos ausentes das tabelas não foram consultados; não significam ausência de normas. Os portais podem não ter digitalizado ou catalogado todos os atos. A cobertura estadual inclui fontes de Minas Gerais, São Paulo e Bahia; os demais estados, o Distrito Federal e os demais municípios ainda estão pendentes. Anexos e outros documentos vinculados por links não são baixados por estes coletores; imagens e links presentes no HTML permanecem no Markdown. Hash e reprodução verificam a transformação, sem certificar vigência ou revisão jurídica integral.", "",
  ].join("\n");
  yield* Effect.tryPromise(() => Bun.write("COBERTURA.md", report));
  yield* Effect.log(`Cobertura: ${published.size} publicadas; ${indexed.size} federais e ${almgIndexed.size} mineiras identificadas`);
}));
