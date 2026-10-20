import { Effect, Schema } from "effect";
import { Metadata } from "./catalog";
import { intact } from "./document";
import { Inventory } from "./senado";

await Effect.runPromise(
  Effect.gen(function* () {
    const metadataPaths = yield* Effect.tryPromise(() =>
      Array.fromAsync(new Bun.Glob("fontes/*.json").scan(".")),
    );
    const published = new Set<string>();
    const versions = new Map<string, number>();
    for (const path of metadataPaths.sort()) {
      const metadata = yield* Effect.tryPromise(() =>
        Bun.file(path).text(),
      ).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(Metadata))));
      if (!(yield* intact(metadata.id))) continue;
      published.add(metadata.id);
      versions.set(metadata.versao, (versions.get(metadata.versao) ?? 0) + 1);
    }
    const paths = yield* Effect.tryPromise(() =>
      Array.fromAsync(new Bun.Glob("catalogos/senado/*/*.json").scan(".")),
    );
    const rows: Array<string> = [];
    const indexed = new Set<string>();
    for (const path of paths.sort().reverse()) {
      const inventory = yield* Effect.tryPromise(() =>
        Bun.file(path).text(),
      ).pipe(Effect.flatMap(Schema.decodeUnknown(Schema.parseJson(Inventory))));
      for (const norm of inventory.normas) indexed.add(norm.id);
      const collected = inventory.normas.filter((norm) =>
        published.has(norm.id),
      ).length;
      rows.push(
        `| ${inventory.tipo} | ${inventory.ano} | ${inventory.normas.length} | ${inventory.pendencias.length} | ${collected} | ${inventory.normas.length - collected} |`,
      );
    }
    const missing = Array.from(indexed).filter((id) => !published.has(id));
    const failures = yield* Effect.tryPromise(() =>
      Array.fromAsync(new Bun.Glob("falhas/*.json").scan(".")),
    );
    const report = `# Cobertura do acervo\n\nEste relatório é gerado por \`bun run coverage\` a partir dos catálogos e dos arquivos com hashes íntegros presentes neste commit. Não mede toda a legislação brasileira nem a completude do catálogo oficial.\n\n- Normas publicadas: **${published.size}**.\n- Normas identificadas nos catálogos consultados do Senado: **${indexed.size}**.\n- Dessas, ainda sem Markdown íntegro: **${missing.length}**.\n- Falhas de coleta registradas: **${failures.length}**.\n\n## Versões publicadas\n\n${Array.from(
      versions.keys(),
    )
      .sort()
      .map((version) => `- ${version}: ${versions.get(version)}.`)
      .join(
        "\n",
      )}\n\n## Catálogos consultados\n\nCada catálogo preserva a resposta oficial comprimida, o filtro e a data de coleta. A consulta por tipo/ano não expõe total independente ou paginação; as quantidades abaixo correspondem aos registros efetivamente recebidos. Pendências são identificações que o coletor ainda não consegue representar.\n\n| Tipo | Ano | Identificadas | Pendências de identidade | Publicadas | A coletar |\n| --- | ---: | ---: | ---: | ---: | ---: |\n${rows.join("\n")}\n\n## Lacunas\n\nA descoberta federal está em expansão por anos e famílias. Anos ou tipos ausentes da tabela não foram consultados; não significam ausência de normas. O Senado pode não ter digitalizado ou catalogado todos os atos. Normas estaduais, distritais e municipais ainda não foram coletadas. Anexos e outros documentos vinculados por links não são baixados por este coletor; imagens e links presentes no HTML permanecem no Markdown. Hash e reprodução verificam a transformação, sem certificar vigência ou revisão jurídica integral.\n`;
    yield* Effect.tryPromise(() => Bun.write("COBERTURA.md", report));
    yield* Effect.log(
      `Cobertura: ${published.size} publicadas; ${indexed.size} identificadas; ${missing.length} a coletar`,
    );
  }),
);
