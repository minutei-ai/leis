# Identidade federal — issues #99, #102, #103, #104

Lote de correção de identidade, colação de cabeçalho divergente, reconciliação de textos trocados e integração de anexos fac-similares.

## Escopo

| Issue | Objeto | Estado neste PR |
| --- | --- | --- |
| #99 | Cinco decretos com texto de outra norma; 38→34 grupos de hash idêntico | 5 federais recolecionados; 34 grupos auditados um a um (`duplicatas-auditoria.md`). **12 pendências de identidade MG** (ementa ALMG diverge do corpo) — **não fecha** |
| #102 | Decreto-Lei 4.014-A/1942: caminho/catálogo `4014-A` vs cabeçalho Senado `1.014-A` | Caso 4.014-A colacionado; lote ampliado (45171/45353/46934 + amostra) **documentado sem reescrita** — **não fecha** |
| #103 | Leis 12.985 e 12.988/2014 com corpos reciprocamente trocados | Corpos, ementas e busca Viaduto/Nabuco conferidos com hashes em `fontes.json` |
| #104 | Anexos dos Decretos-Leis 1.873/1981 e 2.111/1984 | Tabelas transcritas + fac-símiles; célula **CLASSE A — NS-4 a 6** (jornada 4 h) recuperada por colação visual Câmara **e** Planalto |

## Fontes oficiais usadas

- Câmara dos Deputados — publicação original (HTML) dos cinco decretos, das duas leis e do Decreto-Lei 4.014-A; PDFs de anexo da Câmara para 1.873 (I e II) e 2.111.
- Planalto — PDF `andel1873-81.pdf` (Anexo I + início do Anexo II do DL 1.873; célula CLASSE A 4 h legível); HTML `Del2111.htm` (tabela do anexo do DL 2.111).
- Senado — ficha `norma/529102` (identidade 4.014-A) e publicação `…/publicacao/15820792` (cabeçalho literal `DECRETO-LEI N. 1.014-A`).
- ALMG — ementas das fichas dos pares MG em `duplicatas-excecoes.json` / `duplicatas-auditoria.md`.

Snapshots HTML em `fontes/*.html.xz`; divergência Senado em `divergencias/`; fac-símiles PNG e recortes CLASSE A em `anexos/`. Hashes em `fontes.json` e `anexos-hashes.json`.

## Decisões de colação

1. **#99 / #103** — Texto integral recolhido da Câmara (publicação original / retificação quando a publicação original 404). Epígrafe e ementa passam a coincidir com o caminho. Chrome do portal removido.
2. **#102** — Identidade canônica do acervo: **4.014-A** (Câmara, LexML, ficha Senado, ementa Destacamento de Fernando de Noronha). O Markdown publicado segue a Câmara (`DECRETO-LEI Nº 4.014-A`). A publicação textual do Senado traz literalmente `1.014-A`; isso é **divergência documentada da fonte**, não correção editorial silenciosa. Evidência em `divergencias/` e `NOTA-DIVERGENCIA-4014-A.md`. Lote ampliado em `divergencias-cabecalho-lote.md`.
3. **#104** — Corpo dos decretos-leis limpo; anexos transcritos em Markdown com fac-símiles PNG e URLs/PDF de origem. Célula CLASSE A (jornada 4 h) lida como **NS-4 a 6** nos fac-símiles da Câmara (Anexo II) e do Planalto (`andel1873-81.pdf`); recortes em `anexos/*classe-a-4h*-crop.png`. Edição histórica do DL 2.111 preservada à parte da redação posterior do DL 2.196/1984.
4. **Duplicatas restantes** — ver `duplicatas-excecoes.json` (tipos `alias_catalogo` / `pendencia_identidade` / `mesmo_texto_fonte_com_ressalva`) e `duplicatas-auditoria.md`. O teste falha se surgir grupo novo fora da lista ou se voltar justificativa genérica única.

## Limites

- Não se afirma vigência atual a partir da presença de arquivo ou HTTP.
- PDFs oficiais não entram no repositório público; permanecem como origem dos PNG e dos hashes SHA-256 conferidos com a issue #104.
- Pendências MG de identidade e o lote ampliado #102 **não** são encerrados automaticamente.
- Sem merge enquanto houver requisito pendente nas issues abertas deste lote.
