# Provas — licitações locais (PR)

Recuperação pontual do Decreto estadual 10.086/2022 (`codAto=259084`) a partir do Sistema Legislação do Paraná.

## Snapshots

| Arquivo | Papel |
| --- | --- |
| `fontes/legislacao-pr-259084-compilado.htm.xz` | Fonte da publicação Markdown (`tipoVisualizacao=compilado`) |
| `fontes/legislacao-pr-259084-original.htm.xz` | Corpo original preservado (não sobrescreve o publicado) |
| `fontes/legislacao-pr-259084-alterado.htm.xz` | Visão “Alterado” com histórico |
| `fontes/legislacao-pr-259084-exibirAto.htm.xz` | Página interativa citada na issue |
| `br-pr-ato-259084-original.md` | Conversão do original só como prova |
| `fontes.json` | URLs, datas, hashes e metadados de captura |

## Reprodução

1. Baixar a impressão compilada:
   `https://www.legislacao.pr.gov.br/legislacao/listarAtosAno.do?action=exibirImpressao&codAto=259084&tipoVisualizacao=compilado`
2. Conferir `sha256_fonte` / `sha256_conteudo` em `fontes.json` (conteúdo com `jsessionid` removido).
3. Converter com o perfil Paraná já existente em `coletores/leis/scripts/convert.ts` (`Source` id `br-pr-ato-259084`).
4. Comparar o Markdown publicado em `estaduais/PR/br-pr-ato-259084.md`.

O PDF do DOE nº 11097 (edição completa) não está versionado; apenas o hash está em `fontes.json`.

## Limites

Cobertura temática parcial. O acervo não certifica vigência. Anexos em arquivo próprio não constam deste ato na fonte.
