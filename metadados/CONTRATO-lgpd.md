# Contrato de metadados — catálogo temático LGPD

Este contrato vale para as edições da Lei nº 13.709/2018 (LGPD) publicadas com
cabeçalho de metadados e para o manifesto [`lgpd.json`](lgpd.json). É **separado**
do [contrato do núcleo de licitações](CONTRATO.md): o núcleo federal de licitações
não cataloga todo o direito.

Os campos do cabeçalho seguem a mesma gramática do contrato do núcleo (`campo: valor`
JSON; `desconhecido` explícito; `vigencia_certificada` sempre `false`).

## Edições

| Arquivo | Papel |
| --- | --- |
| `federal/br-federal-lei-2018-08-14-13709.md` | Edição **histórica** preservada (corpo anterior à Lei 15.352/2026), com alerta por dispositivo |
| `federal/edicoes/br-federal-lei-2018-08-14-13709-consolidada.md` | Edição **consolidada** integral (Câmara, norma atualizada), conferida com o Planalto |
| `federal/br-federal-lei-2026-02-25-15352.md` | Modificadora **já publicada** — reutilizada/validada, **não** republicada neste catálogo |
| `federal/br-federal-medida-provisoria-2025-09-17-1317.md` | MP 1.317/2025 já publicada (convertida); snapshots oficiais em `provas/lgpd/fontes/` |

Edições em `federal/edicoes/` **não** incrementam a contagem de normas do README.

## Fontes

- Principal da consolidada: Câmara dos Deputados (HTML norma atualizada).
- Conferência: Planalto (`fonte_conferencia` — URL distinta de `fonte_url`).
- Modificadora / MP: snapshots Câmara e Planalto em `provas/lgpd/` para reconversão offline.

## Regras específicas

- **Não renomear mecanicamente** “Autoridade” → “Agência”. Preservar o que cada fonte
  mantém (ex.: art. 5º, XIX continua “autoridade nacional”; arts. transitórios da
  Lei 15.352 ainda mencionam “Autoridade Nacional de Proteção de Dados”).
- A edição histórica propaga **alerta por dispositivo** quando recuperada (art. 5º
  VIII/XIX, títulos do Cap. IX / Seção I, arts. 55-A e 55-C).
- Anexos tabulares da Lei 15.352: presentes no snapshot Planalto; ausentes do
  Markdown já publicado da modificadora — limite explícito em
  `provas/lgpd/validacao-lei-15352.json`.
- Provas devem permitir reconversão offline integral e comparação do corpo
  normativo com o snapshot (não apenas hashes autoconsistentes).
