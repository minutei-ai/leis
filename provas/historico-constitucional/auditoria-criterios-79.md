# Auditoria integral — issue #79 (head PR 114)

Critérios de aceite da issue, com evidência no acervo publicado. Não certifica vigência. Não reduz o objetivo a amostras: as amostras abaixo ilustram riscos; o status cobre o lote inteiro (8 identidades).

## Inventário publicado (8/8 do lote inicial)

| id | série | edição | vínculo explícito | anexos_no_corpo | imagens_omitidas | cobertura blocos |
| --- | --- | --- | --- | ---: | ---: | --- |
| `br-federal-constituicao-1824-03-25` | constituicao-1824 | historica-camara | — | 0 | 0 | sim |
| `br-federal-constituicao-1891-02-24` | constituicao-1891 | historica-camara | — | 0 | 0 | sim |
| `br-federal-constituicao-1934-07-16` | constituicao-1934 | historica-camara | — | 0 | 0 | sim |
| `br-federal-constituicao-1937-11-10` | constituicao-1937 | historica-camara | — | 0 | 0 | sim |
| `br-federal-constituicao-1946-09-18` | constituicao-1946 | historica-camara | — | 0 | 0 | sim |
| `br-federal-constituicao-1946-09-18-adct` | constituicao-1946 | historica-camara | `peca_de` → Constituição 1946 | 0 | 0 | sim |
| `br-federal-constituicao-1967-01-24` | constituicao-1967 | historica-camara | — | 0 | 0 | sim |
| `br-federal-emenda-constitucional-1969-10-17-1` | constituicao-1967 | historica-senado | `texto_base_relacionado` → Constituição 1967 | 0 | 0 | sim |

Fontes e hashes: `catalogo-lote.json`, `matriz-lote.json`, `fontes.json`, snapshots em `fontes/`.

## Critérios da issue — status

1. **Catalogar e recuperar os sete atos e peças (1824–1967, ADCT 1946, EC 1/1969), distinguindo publicação original, retificações e consolidações históricas.**  
   **Comprovado (parcial):** 8 identidades publicadas como edição histórica de publicação original (Câmara `div.texto` para constituições/ADCT; Senado/normas.leg.br para EC 1/1969).  
   **Pendente:** inventário/publicação de retificações e de consolidações históricas alternativas como edições distintas (`edicao_relacionada: nenhuma` em todos). Consolidações modernas sob rótulo de original permanecem proibidas e não foram feitas.

2. **Preservar ADCTs, disposições autônomas, notas, anexos e elementos normativos não textuais, com fonte/captura/hashes e transcrição conferida.**  
   **Comprovado (parcial):** ADCT 1946 em arquivo próprio com `peca_de` e série `constituicao-1946`; cobertura de blocos true; hashes de fonte/markdown no manifesto.  
   **Pendente / risco:** `anexos_no_corpo: 0` e `imagens_omitidas: 0` nestas capturas HTML **não garantem** ausência de anexos/fac-símiles em outras edições ou em PDF oficial. Elementos não textuais além do HTML capturado não foram inventariados. Prova privada da EC 1969 citada em `limites.json` permanece fora do repo público.

3. **Representar séries constitucionais e vínculos das emendas com o texto-base; EC 1/1969 sem colidir com EC 1/1992 nem outras EC 1 históricas.**  
   **Comprovado:** `serie_historica` em todos; EC 1/1969 com id datado `…-1969-10-17-1`, série `constituicao-1967`, nota explícita de distinção frente a EC 1/1992; `texto_base_relacionado` aponta para `br-federal-constituicao-1967-01-24`.  
   **Pendente:** reconciliação ampla das demais emendas já publicadas no acervo com seus textos-base históricos (fora do lote inicial de 8).

4. **Metadados para recuperação histórica e filtro de edição/série (#70); não devolver como Constituição atual por ausência de filtro.**  
   **Comprovado (parcial):** cabeçalhos com `edicao_tipo: historica`, `vigencia_certificada: false`, `serie_historica` e notas de edição.  
   **Pendente:** integração efetiva dos filtros #70 e do rastreador #83 (declarado em limites).

5. **Reconciliar emendas já publicadas com textos-base, sem duplicar atos e sem presumir que o lote esgota alterações constitucionais históricas.**  
   **Pendente:** `limites.json` / manifesto do script registram que emendas às séries 1891–1967 (exceto EC 1/1969 deste lote) não foram inventariadas neste PR.

6. **Registrar o que permanece não inventariado (emendas de séries anteriores, leis constitucionais e atos com conteúdo constitucional).**  
   **Comprovado (registro):** limites apontam #90 para LCT/AIT/ACP e deixam emendas históricas remanescentes explícitas.

## Amostras de risco (não substituem o lote)

- **1946 data/URL:** catálogo Câmara contém `18-julho` na URL; id e ADCT usam `1946-09-18` (promulgação). Divergência preservada nas notas — ver `catalogo-lote.json`.
- **1934 data Câmara×Senado:** Câmara 16/07/1934 vs URN Senado 14/07/1934; arquivo segue Câmara.
- **EC 1/1969 vs EC 1/1992:** identidades e séries distintas no acervo; risco residual se consumidor ignorar `serie_historica` / data no id (#70).
- **ADCT vs texto principal 1946:** peça separada (`peca_de`); risco de omissão se cliente listar só `norma_tipo: constituicao` sem `constituicao-adct`.
- **Anexos/edições:** publicação de 8 Markdown com cobertura de blocos **não** garante anexos de outras fontes nem edições consolidadas históricas.

## Bloqueios reais para fechar a issue

- Filtros #70 / rastreador #83.
- Inventário das emendas das séries anteriores (exceto EC 1/1969 já publicada).
- Edições alternativas (retificações/consolidações históricas) com `edicao_id` distintos quando existirem nas fontes.
- Garantia de anexos/fac-símiles além do HTML `div.texto` / binário Senado capturado — exige colação por fonte/edição, não inferência por HTTP ou por `anexos_no_corpo: 0`.
