import { Effect, Schema } from "effect";
import { AlmgInventory } from "./almg";
import { Metadata } from "./catalog";
import { intact } from "./document";
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
  const missing = Array.from(indexed).filter((id) => !published.has(id));
  const almgMissing = Array.from(almgIndexed).filter((id) => !published.has(id));
  const failures = yield* Effect.tryPromise(() => Array.fromAsync(new Bun.Glob("falhas/*.json").scan(".")));
  const report = [
    "# Cobertura do acervo", "",
    "Este relatório é gerado por `bun run coverage` a partir dos catálogos e dos arquivos com hashes íntegros presentes neste commit. Não mede toda a legislação brasileira nem a completude dos catálogos oficiais.", "",
    `- Normas publicadas: **${published.size}**.`,
    `- Normas identificadas nos catálogos consultados do Senado: **${indexed.size}**.`,
    `- Dessas, ainda sem Markdown íntegro: **${missing.length}**.`,
    `- Normas identificadas nos catálogos consultados da ALMG: **${almgIndexed.size}**.`,
    `- Dessas, ainda sem Markdown íntegro: **${almgMissing.length}**.`,
    `- Falhas de coleta registradas: **${failures.length}**.`, "",
    "## Versões publicadas", "",
    ...Array.from(versions.keys()).sort().map((version) => `- ${version}: ${versions.get(version)}.`), "",
    "## Catálogos federais do Senado", "",
    "Cada catálogo preserva a resposta oficial comprimida, o filtro e a data de coleta. A consulta por tipo/ano não expõe total independente ou paginação; as quantidades abaixo correspondem aos registros efetivamente recebidos. Pendências são identificações que o coletor ainda não consegue representar.", "",
    "| Tipo | Ano | Identificadas | Pendências de identidade | Publicadas | A coletar |",
    "| --- | ---: | ---: | ---: | ---: | ---: |", ...rows, "",
    "## Minas Gerais — ALMG", "",
    "O CSV anual é preservado integralmente. A coleta de textos abrange LEI, LCP, LDL, DEL, DEC, CON e EMC. Outros tipos de ato são contabilizados separadamente, sem serem tratados como leis ausentes ou falhas de download.", "",
    "| Ano | Identificadas | Pendências de identidade | Outras famílias no CSV | Publicadas | A coletar |",
    "| ---: | ---: | ---: | ---: | ---: | ---: |", ...almgRows, "",
    "## Lacunas", "",
    "A descoberta federal está em expansão por anos e famílias. Anos ou tipos ausentes das tabelas não foram consultados; não significam ausência de normas. Os portais podem não ter digitalizado ou catalogado todos os atos. A cobertura estadual começou por Minas Gerais; os demais estados, o Distrito Federal e os municípios ainda estão pendentes. Anexos e outros documentos vinculados por links não são baixados por estes coletores; imagens e links presentes no HTML permanecem no Markdown. Hash e reprodução verificam a transformação, sem certificar vigência ou revisão jurídica integral.", "",
  ].join("\n");
  yield* Effect.tryPromise(() => Bun.write("COBERTURA.md", report));
  yield* Effect.log(`Cobertura: ${published.size} publicadas; ${indexed.size} federais e ${almgIndexed.size} mineiras identificadas`);
}));
