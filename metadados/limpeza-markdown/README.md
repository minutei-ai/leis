# Limpeza de Markdown do acervo geral

Lote das issues [#87](https://github.com/minutei-ai/leis/issues/87),
[#98](https://github.com/minutei-ai/leis/issues/98) e
[#100](https://github.com/minutei-ai/leis/issues/100).

O script `scripts/limpeza_markdown.py` remove do corpo pesquisável:

| Família | Tratamento | Artefato |
| --- | --- | --- |
| Marcador interno `###ESPÉCIE-…@@@` | Removido do `.md`; identificador guardado | `marcadores-origem.jsonl` |
| HTML de apresentação (`strong`, `em`, `br`, `font`, `span`, `p`, …) | Convertido para Markdown | — |
| Tabelas com `rowspan`/`colspan` | Permanecem como `<table>` simples (CONTRATO) | — |
| Imagens `data:image` | Extraídas para `assets/md-inline/{sha256}.{ext}` ou omitidas se brasão/logo de cabeçalho | `imagens.jsonl` |
| Chrome de portal (Câmara, ALESP, MG, SP capital, D.O./DOU/Suplemento/DPL/DOE) | Removido do corpo pesquisável; avisos «não substitui…» migram para `<!-- nota-edicao -->` | `portais-removidos.json` |

## Allowlists

### Edições posteriores preservadas na integração

Este lote de limpeza não conclui as issues #87, #98 e #100. Na integração,
823 edições publicadas ou corrigidas depois da preparação do lote foram
preservadas literalmente. Seus geradores e provas precisam de revalidação
antes de alterar a representação Markdown; aplicar a versão antiga limpa
apagaria metadados, correções de identidade ou anexos mais recentes.

`edicoes-posteriores-preservadas.json` fixa o hash de cada edição adiada.
O cleaner recusa mudanças nesses arquivos sem nova revisão. Os gates verificam
a limpeza do lote anterior e, separadamente, os hashes e a preservação dessas
edições. Portanto, o resultado dos gates não significa que todo o acervo atual
está limpo. As pendências permanecem nas issues existentes.

`ALLOWLIST_DATA_IMAGE` e `ALLOWLIST_PORTAL_CAMARA` estão **vazias**. Os geradores
do núcleo de licitações, LGPD e benefícios/MDP omitem brasão e chrome CEDI na
conversão; corpos com `sha256_corpo_preservado` foram limpos com o texto jurídico
intactó e hashes regenerados (proveniência do brasão em `imagens.jsonl`).

Follow-ups (fora do Markdown publicado / coletores privados):

- Coletores ALESP / MG / SP capital / DO fora do repo público: não reintroduzir
  links de portal, “Data da última atualização” nem avisos “não substitui o
  publicado…” no `_source` (proveniência agregada aqui; contrato por norma na #70).
- Mudanças em coletores privados devem permanecer explícitas e reversíveis; este
  PR não publica credenciais nem scripts privados.

## Convenção SP capital / Rio Verde (nota para #70)

Em parte dos municipais de São Paulo (capital) e de Rio Verde, a data no nome do
arquivo reflete a data de **publicação** no diário, não necessariamente a data
do ato. Esta limpeza não altera nomes de arquivo; a catalogação geral da #70
deve registrar essa convenção.

## Reprodução

```sh
python3 scripts/limpeza_markdown.py --dry-run
python3 scripts/limpeza_markdown.py --apply
python3 -m unittest tests.test_limpeza_markdown
```

Este diretório **não** substitui o contrato geral de metadados da #70: só
preserva o que a limpeza removeu do `_source` Markdown.
