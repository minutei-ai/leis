# Identidade federal — issues #99, #102, #103, #104

Lote de correção de identidade, colação de cabeçalho divergente, reconciliação de textos trocados e integração de anexos fac-similares.

## Escopo

| Issue | Objeto | Estado neste PR |
| --- | --- | --- |
| #99 | Cinco decretos com texto de outra norma; grupos de hash idêntico | 5 federais recolecionados; 12 pares MG desmembrados; **803 e 40955 recuperados** via JMG (colação visual); 17 órfãos restantes = nota `nao_publicado_integra` + `excluir_denominador_integra`; 8 ex-ressalvas corrigidas; 37349 recolecionado; 35816/35817 ressalva; 13 aliases. Issue aberta pelos 17 blockers de microfilme/IOF |
| #102 | Decreto-Lei 4.014-A/1942 + lote ampliado | 4.014-A colacionado; **45171 / 45353 / 46934** colacionados ato a ato (literais Senado preservados) |
| #103 | Leis 12.985 e 12.988/2014 com corpos reciprocamente trocados | Corpos, ementas e busca Viaduto/Nabuco conferidos com hashes em `fontes.json` |
| #104 | Anexos dos Decretos-Leis 1.873/1981 e 2.111/1984 | Tabelas + fac-símiles; célula **CLASSE A — NS-4 a 6** (jornada 4 h) Câmara **e** Planalto |

## Fontes oficiais usadas

- Câmara dos Deputados — publicação original (HTML) dos cinco decretos, das duas leis e do Decreto-Lei 4.014-A; PDFs de anexo da Câmara para 1.873 (I e II) e 2.111.
- Planalto — PDF `andel1873-81.pdf` (Anexo I + início do Anexo II do DL 1.873; célula CLASSE A 4 h legível); HTML `Del2111.htm` (tabela do anexo do DL 2.111).
- Senado — ficha `norma/529102` (identidade 4.014-A) e publicação `…/publicacao/15820792` (cabeçalho literal `DECRETO-LEI N. 1.014-A`); fichas/publicações 467738/15805509 (45171), 467918/15700630 (45353), 469503/15804419 (46934).
- ALMG — fichas + API `dadosabertos` (`ementa`/`nomes`/`resumo`/`texto`) dos pares MG; capturas em `mg-recoleta/`. Em 05/11/2026 também foram preservadas as 17 rotas oficiais “Texto Original” dos órfãos, com URL, horário e hashes: `mg-recoleta/almg-texto-original-capturas.json`.
- APM/SIAAPM — Guia do Fundo Secretaria do Interior e inventário oficial da Série 12 (captura PDF apenas local, hash e achado registrados em `mg-recoleta/auditoria-almg-orfaos-2026-11-05.md`).

Snapshots HTML em `fontes/*.html.xz`; divergência Senado em `divergencias/`; fac-símiles PNG e recortes CLASSE A em `anexos/`. Hashes em `fontes.json` e `anexos-hashes.json`.

## Decisões de colação

1. **#99 / #103** — Texto integral recolhido da Câmara quando disponível. Pares MG com HTML ALMG atribuído a outra norma: corpo mantido só no caminho cuja ficha bate; órfão recebe nota `corpo_digital_indisponivel` com metadados explícitos de não-publicação/exclusão do denominador íntegra (sem inventar dispositivo). 37349 recolecionado (Zacarias Roque) via API correta; **803** e **40955** recuperados do Diário oficial JMG (edições digitais 1937 e 2000). Em 05/11/2026 as 17 rotas ALMG “Texto Original” foram verificadas e preservadas; os corpos continuam sem correspondência segura à ficha. Inventário público APM da Série 12 cobre documentos legislativos listados até 1934 e manda consulta aos originais; não localiza esses órfãos nem autoriza concluir ausência em outros acervos. Ausência de texto na API ALMG **não** implica indisponibilidade universal.
2. **#102** — Identidade canônica 4.014-A (Câmara). Lote 45171/45353/46934: cabeçalhos divergentes = literais da publicação Senado; Markdown preservado; ver `divergencias-cabecalho-lote.md`.
3. **#104** — Célula CLASSE A (jornada 4 h) = **NS-4 a 6** nos fac-símiles Câmara e Planalto. Edição histórica do DL 2.111 preservada.
4. **Duplicatas restantes** — `duplicatas-excecoes.json` (13 `alias_catalogo` + 1 `mesmo_texto_fonte_com_ressalva`).

## Limites

- Não se afirma vigência atual a partir da presença de arquivo ou HTTP.
- PDFs oficiais não entram no repositório público.
- 17 corpos MG órfãos continuam pendentes de fonte oficial integral conferível. JMG não lista edições digitais nos anos respectivos; rotas ALMG e série digitalmente catalogada do APM não forneceram texto correspondente. A nota não substitui o texto legal nem entra no denominador íntegra; consulta presencial aos originais/microfilmes e edição IOF continuam necessárias.
- Sem merge enquanto houver requisito pendente nas issues abertas deste lote.
