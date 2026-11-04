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
3. Conferência **independente no CI** (sem conversor Paraná privado): texto bruto de
   `#conteudo_corpo > form[name=listarAtosAnoForm]` (sem controles nem o aviso
   “Este texto não substitui…”) versus Markdown, via `strip_fold` /
   `md_text_all` em `tests/test_licitacoes_locais_pr.py`. O mesmo gate cobre o
   HTML original e o Markdown de prova.
4. Reconversão complementar no CI com `scripts/nucleo_licitacoes.convert_html`
   sobre a mesma região (confere texto jurídico completo; não replica a
   formatação `###`/`**Art.**` do perfil Paraná).
5. Opcional offline: reconversão tipográfica com
   `coletores/leis/scripts/convert.ts` (`Source` id `br-pr-ato-259084`) — ausente
   do CI público.

O PDF do DOE nº 11097 (edição completa) não está versionado; apenas o hash está em `fontes.json`.

## Limites

Cobertura temática parcial. O acervo não certifica vigência. Anexos em arquivo próprio não constam deste ato na fonte. A coincidência do fold HTML↔Markdown não inventa vigência nem mapa completo com a Lei 14.133.
