# Contrato global de metadados do acervo (BM25)

Versão `1`. Este contrato descreve a identidade tipada e a exportação para
filtros/BM25 de **todo** o acervo Markdown. É o contrato geral pedido pela
issue #70; não substitui os contratos setoriais já publicados:

- [`CONTRATO.md`](CONTRATO.md) — núcleo de licitações
- [`CONTRATO-lgpd.md`](CONTRATO-lgpd.md) — catálogo temático LGPD
- [`CONTRATO-cdc-eca.md`](CONTRATO-cdc-eca.md) — CDC/ECA
- catálogos em [`licitacoes-locais/`](licitacoes-locais/) — amostra temática #57

Um arquivo setorial com cabeçalho próprio **reutiliza** a mesma gramática
(`campo: valor` JSON; `desconhecido` explícito; `vigencia_certificada` sempre
`false`). Este contrato não cria `norma_id` paralelo para a mesma edição.

A ausência de cabeçalho estruturado em um Markdown geral significa
**metadados não registrados**, nunca “vigente” nem “completo”.

## Regras gerais

1. **Desconhecido é explícito.** Estado de conhecimento (`conhecido`,
   `ausente`, `desconhecido`, `conflitante`, `nao-aplicavel`) é distinto do
   valor do campo. `"desconhecido"` não é data ISO; `null` em número legal de
   ato reconhecidamente sem número não é o mesmo que número desconhecido.
2. **O acervo não certifica vigência.** Presença no catálogo, no índice ou no
   export BM25 não implica vigência.
3. **`norma_id` ≠ `edicao_id`.** Edições alternativas/históricas/consolidadas
   da mesma norma não se fundem. Edições em `federal/edicoes/` não incrementam
   a contagem de normas do README.
4. **Número legal é textual**, com `complemento` e forma original preservados.
   `1599` e `1599-A` são identidades distintas; `seq-sf` e IDs de provedor
   (`br-ac-norma-1121`) nunca viram número legal.
5. **Markdown integral.** A exportação de busca entrega o corpo Markdown
   publicado, verificável por hash, sem truncar tabelas, notas, riscos ou
   alertas. Metadados tipados ficam fora do campo de ranking da íntegra.
6. **Representação ≠ transcrição.** Fac-símile integral preservado não é texto
   integral pesquisável (#77). Filtros separam as duas dimensões.
7. **Ente emissor ≠ âmbito de aplicação ≠ domicílio de fornecedor.**
   Brasília/DF (`5300108`) e Fernando de Noronha (`2605459`) não são tratados
   como municípios faltantes (#74).

## Identidade

| Campo | Significado |
| --- | --- |
| `norma_id` | Identidade estável da norma (sem tipo de edição). |
| `edicao_id` | Identidade do arquivo/edição (`norma` + tipo + órgão quando couber). |
| `especie` / `especie_rotulo_fonte` | Espécie canônica e rótulo literal da fonte. |
| `numero` | Número legal textual ou `null` (ato sem número). |
| `numero_estado` | `informado` \| `sem-numero` \| `desconhecido`. |
| `complemento` | Sufixo oficial (`A`, etc.) ou `null`; nunca fundir com `reedicao`. |
| `reedicao` | Reedição/série própria do provedor, se houver. |
| `provedor_id` | ID oficial do provedor (Senado, Casa Civil, etc.) em namespace próprio. |
| `provedor_token` | Token local de desambiguação (`seq-sf`, …); não é número legal. |
| `titulo` / `ementa` | Textos para ranking; não substituem a íntegra. |

Exemplos obrigatórios de não-fusão: LC 1/1962 ≠ LC 1/1967; mesmo número em
municípios/órgãos distintos; seis atos distintos em 20/10/1823.

## Ente e órgão

| Campo | Significado |
| --- | --- |
| `esfera` | `federal` \| `estadual` \| `distrital` \| `municipal`. |
| `uf` | Sigla ou `null`/`desconhecido`. |
| `ibge` | Código IBGE municipal quando aplicável; entidades especiais marcadas. |
| `orgao_emissor` | Órgão que expediu o ato. |
| `poder` | Executivo / Legislativo / outro informado. |
| `ambito_aplicacao` | Só quando demonstrado na norma; separado do emissor. |

## Datas e edição

Datas do ato, publicação, republicação, captura e intervalos de efeitos ficam
em campos separados. Ano-only permanece sem dia/mês inventado.

| Campo | Significado |
| --- | --- |
| `edicao_tipo` | `historica` \| `consolidada` \| `original` \| `desconhecida`. |
| `edicao_integral` | `true` \| `false` \| `"desconhecido"`. |
| `representacao` | `texto` \| `fac-simile` \| `mista`. |
| `cobertura_transcricao` | `integral` \| `parcial` \| `ausente` \| `desconhecida`. |
| `cobertura_ocr` | `nao-aplicavel` \| `ausente` \| `parcial` \| `validada` \| `desconhecida`. |
| `situacao` | Só o informado pela fonte; nunca inferido. |
| `vigencia_certificada` | Sempre `false`. |

## Integridade e relações

- `caminho`, `sha256_markdown` (corpo após cabeçalho, ou arquivo inteiro quando
  não há cabeçalho — semântica explícita no export), `sha256_fonte` quando
  houver captura.
- Relações (`alteracao`, `revogacao`, `revogacao-parcial`, `retificacao`,
  `regulamento`, …) trazem origem/destino/dispositivo e
  `escopo_cobertura` (`completo` \| `parcial` \| `desconhecido`).
- Hash da fonte HTML/PDF **não** se confunde com hash do Markdown.

## Exportação BM25

Documento exportado por edição:

1. **Ranking (text):** `titulo`, `ementa`, `markdown_integral`.
2. **Filtros exatos (keyword/typed):** identidades, espécie, ente, número,
   complemento, edição, situação, representação, cobertura de transcrição.
3. **Intervalos:** datas tipadas; `"desconhecido"` não entra como date.
4. **Alertas:** `alerta_cobertura_textual`, `alerta_reproducao_incompleta`,
   `vigencia_certificada=false`.
5. **Proveniência:** `fonte_do_campo` / `campo_fontes` registra a origem de
   cada valor (`caminho-canonico`, `cabecalho-literal`, `frontmatter`,
   `desconhecido-explicito`, …). Ausência de proveniência não autoriza
   inferência.

O consumidor Elasticsearch mapeia text≠keyword; o Markdown integral não vai
para `keyword`. Ver [`provas/cobertura-nacional/bm25-mapeamento.json`](../provas/cobertura-nacional/bm25-mapeamento.json).

## Cabeçalhos no acervo geral

Arquivos fora dos lotes setoriais podem receber o mesmo cabeçalho `---` quando
os campos forem extraídos sem inventar dados. O piloto está em
[`acervo-geral-piloto.json`](acervo-geral-piloto.json): corpo Markdown
preservado byte-a-byte após o frontmatter; `provedor_id` de caminho opaco
nunca vira número legal; `fonte_url`/`edicao_tipo`/`situacao` ficam
`desconhecido` até haver captura registrada.

## Cobertura de campos

Nenhum campo é “coberto” por aparecer em amostra. O relatório em
`provas/cobertura-nacional/cobertura-campos.json` classifica, por lote/fonte,
cada campo como `conhecido`, `ausente`, `desconhecido`, `conflitante` ou
`nao-aplicavel`, a partir dos arquivos publicados e dos contratos setoriais.

## Fontes por jurisdição

O registro em
`provas/cobertura-nacional/registro-fontes-jurisdicao.json` lista fontes
oficiais/coletores já identificados por UF e pelos municípios publicados.
Municípios sem diretório permanecem `nao-investigado` sem inferir ausência
de legislação por falta de pasta ou por erro HTTP (#74).

## Ferramenta

`scripts/cobertura_nacional.py` gera/verifica inventários territoriais,
fac-símiles, export de amostra, registro de fontes e a matriz nacional (#83),
sem rede.
