# Identidade federal — issues #99, #102, #103, #104

Lote de correção de identidade, colação de cabeçalho divergente, reconciliação de textos trocados e integração de anexos fac-similares.

## Escopo

| Issue | Objeto |
| --- | --- |
| #99 | Cinco decretos com texto de outra norma; 38→34 grupos de hash idêntico (4 federais resolvidos; 34 estaduais/municipais justificados) |
| #102 | Decreto-Lei 4.014-A/1942: caminho e catálogo `4014-A` vs cabeçalho Senado `1.014-A` |
| #103 | Leis 12.985 e 12.988/2014 com corpos reciprocamente trocados |
| #104 | Anexos dos Decretos-Leis 1.873/1981 e 2.111/1984 (tabelas só em PDF escaneado) |

## Fontes oficiais usadas

- Câmara dos Deputados — publicação original (HTML) dos cinco decretos, das duas leis e do Decreto-Lei 4.014-A; PDFs de anexo da Câmara para 1.873 (I e II) e 2.111.
- Planalto — PDF `andel1873-81.pdf` (Anexo I + início do Anexo II do DL 1.873); HTML `Del2111.htm` (tabela do anexo do DL 2.111).
- Senado — ficha `norma/529102` (identidade 4.014-A) e publicação `…/publicacao/15820792` (cabeçalho literal `DECRETO-LEI N. 1.014-A`).

Snapshots HTML em `fontes/*.html.xz`; divergência Senado em `divergencias/`; fac-símiles PNG em `anexos/`. Hashes em `fontes.json` e `anexos-hashes.json`.

## Decisões de colação

1. **#99 / #103** — Texto integral recolhido da Câmara (publicação original / retificação quando a publicação original 404). Epígrafe e ementa passam a coincidir com o caminho. Chrome do portal removido.
2. **#102** — Identidade canônica do acervo: **4.014-A** (Câmara, LexML, ficha Senado, ementa Destacamento de Fernando de Noronha). O Markdown publicado segue a Câmara (`DECRETO-LEI Nº 4.014-A`). A publicação textual do Senado traz literalmente `1.014-A`; isso é **divergência documentada da fonte**, não correção editorial silenciosa. Evidência em `divergencias/` e `NOTA-DIVERGENCIA-4014-A.md`.
3. **#104** — Corpo dos decretos-leis limpo; anexos transcritos em Markdown com fac-símiles PNG e URLs/PDF de origem. Edição histórica do DL 2.111 preservada à parte da redação posterior do DL 2.196/1984.
4. **Duplicatas restantes** — 34 grupos SHA-1 idênticos em BA/GO/MG/MS/RJ/município 5218805: mesmo texto sob IDs de catálogo distintos. Justificados em `duplicatas-excecoes.json`; o teste `tests/test_identidade_federal_99_102_103_104.py` falha se surgir grupo novo fora da lista ou se as identidades federais deste lote voltarem a divergir.

## Limites

- Não se afirma vigência atual a partir da presença de arquivo ou HTTP.
- PDFs oficiais não entram no repositório público; permanecem como origem dos PNG e dos hashes SHA-256 conferidos com a issue #104.
- No Anexo II do DL 1.873, o limite superior da CLASSE A (jornada de 4 horas) está parcialmente ilegível no fac-símile; a transcrição marca a lacuna e remete ao PNG.
- Os 34 grupos estaduais/municipais não foram recolecionados neste lote; a justificação é de identidade de bytes + catálogo, não de reescrita.
