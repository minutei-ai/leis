# Contrato de metadados — lote CDC/ECA

Este contrato vale só para o lote independente **CDC** (Lei 8.078/1990) e **ECA**
(Lei 8.069/1990). Os arquivos Markdown começam com cabeçalho `---` de campos planos
e o detalhe fica em [`nucleo-cdc-eca.json`](nucleo-cdc-eca.json).

Não faz parte do núcleo de licitações nem do espaço de metadados da LGPD. O acervo
**não** certifica vigência: `vigencia_certificada` é sempre `false`.

## Campos

Os campos seguem a mesma semântica prática do contrato de licitações (`id`,
`norma_*`, `edicao_*`, `fonte_*`, `capturado_em`, `sha256_*`, `situacao`,
`texto_riscado`, anexos/tabelas/imagens), com acréscimos deste lote:

| Campo | Significado |
| --- | --- |
| `lote` | Sempre `cdc-eca`. |
| `area` | `consumidor` (CDC) ou `infancia-adolescencia` (ECA). |
| `manifesto` | Sempre `metadados/nucleo-cdc-eca.json`. |

`fonte_conferencia` é lista não vazia de URLs `https` da Câmara usadas só para
conferir; não repete `fonte_url`.

## Edição e fontes

- Edição publicada: consolidada/compilada do **Planalto** (URLs da issue #62).
- Conferência: texto atualizado da **Câmara** (HTML LegIn), sem combinar redações.
- Ordinais tipográficos partidos no HTML do Planalto (`3 <u><sup>o</sup></u>`) são
  normalizados para `3º` antes da conversão e da cobertura de texto; isso não reedita
  o dispositivo.
- Texto riscado da fonte vira `~~…~~` no Markdown.

## Provas

`provas/nucleo-cdc-eca/` guarda snapshots `.xz`, `fontes.json`, reconciliações
artigo a artigo e o diagnóstico factual da omissão na coleta. O `verify`
reconverte os snapshots e compara Markdown/provas/manifesto byte a byte (JSON
canônico).

Travas: conjuntos revisados de `apenas_na_conferencia`, `divergencias_de_forma` e
`divergencias_substanciais` são fixos; alteração nova falha o build/verify.
