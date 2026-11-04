# Contrato — matriz do núcleo federal essencial (issue #62)

Este contrato cobre apenas o manifesto
[`matriz-nucleo-federal-essencial.json`](matriz-nucleo-federal-essencial.json)
e as provas em `provas/nucleo-federal-essencial/`. Não redefine os contratos dos
lotes CDC/ECA, CTN/SUS ou benefícios/MDP; aponta para eles.

## Objetivo

Registrar, de forma verificável, a cobertura das seis normas priorizadas na
issue #62 **por área e identidade normativa** (`norma_id` + número + data +
área), com fonte oficial, estado de recuperação e causa da lacuna original.

## Regras

1. **Sem vigência inferida.** `vigencia_certificada` no manifesto é sempre
   `false`. Situação e efeitos ficam nos Markdown/lotes citados.
2. **Identidade ≠ arquivo solto.** O gate exige o `norma_id` canônico e o
   arquivo `federal/<norma_id>.md` com `sha256_markdown` coerente com o
   cabeçalho do lote que o publicou. Contagem de arquivos no `federal/` não
   basta.
3. **Backlog explícito.** Cada entrada em `backlog` traz fonte indicada,
   `estado_recuperacao`, causa da lacuna e lote/PR de publicação.
4. **Diagnóstico factual.** A causa unificada é
   `identificada-nao-coletada` (catálogo Senado presente; Markdown/fonte/falha
   canônica ausentes no coletor). Detalhes permanecem nos diagnósticos por lote.
5. **Fora de `PENDENCIAS.md`.** Ausência de diploma integral não se mistura com
   peça acompanhante pendente de ato já publicado.
6. **Escopo parcial.** `escopo.nao_cataloga` lista o que esta matriz não cobre;
   ausência na matriz não afirma inexistência no ordenamento.
7. **Sem alteração de contagens globais.** Este contrato não autoriza mudança do
   README agregado nem do manifesto de licitações.

## Campos principais do manifesto

| Campo | Significado |
| --- | --- |
| `documentos[]` | Uma entrada por identidade: área, aliases, edição, fonte, hashes, lote, PR, senadoId, causa da lacuna. |
| `backlog[]` | Visão enxuta estado/fonte/lote para rastreio de recuperação. |
| `diagnostico_unificado` | Padrão da lacuna e medidas para não a reproduzir. |
| `lotes[]` | Ponteiros aos três PRs/manifestos que publicaram os textos. |
| `escopo` | `parcial`, com `inclui` e `nao_cataloga` concretos. |

## Verificação

`tests/test_matriz_nucleo_federal_essencial.py` confere: seis identidades,
arquivos presentes, hashes do manifesto alinhados aos cabeçalhos, separação de
`PENDENCIAS.md`, e que o gate não se reduz a “existe algum arquivo com o
número”.

## Integridade

`edicao_integral=true` nos documentos desta matriz espelha o cabeçalho do lote que publicou a norma. Significa reprodução conferida da **fonte principal** daquele lote. Não afirma identidade byte a byte com toda fonte de conferência, nem vigência. Divergências oficiais conhecidas (ex.: CDC Planalto×Câmara) permanecem no manifesto do lote e são apontadas em `integridade.divergencias_conhecidas_no_lote` quando existirem. Hashes e contagens de artigos **não** substituem a leitura das provas.
