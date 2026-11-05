# Auditoria integral — issue #90 (head PR 114)

Critérios da issue sobre LCT (21), AIT (17) e ACP (105). Status sobre o lote completo (143), com amostras de risco. Não certifica vigência. Catálogo ≠ íntegra.

## Inventário vs catálogo Senado

| espécie | catálogo | presentes no acervo | ausentes | revisão | SHA captura vs SHA da issue |
| --- | ---: | ---: | ---: | ---: | --- |
| LCT | 21 | 21 | 0 | 0 | diverge (`sha256_bate_com_issue: false`) |
| AIT | 17 | 17 | 0 | 0 | diverge |
| ACP | 105 | 105 | 0 | 0 | diverge |

Fonte de texto: `legis.senado.leg.br/norma/{id}/publicacao/{pub}` (canal `senado-sigen`). `normas.leg.br` não indexa a maioria destas espécies. Manifesto: `matriz-publicacao.json` (143 publicados, 0 retidos). Reconcile: `matriz-lote.json` / `limites.json`.

SHA do catálogo: o campo `sha256` embutido é o da resposta bruta na captura; o arquivo JSON versionado tem hash de serialização distinto; nenhum dos dois coincide com o SHA citado no corpo da issue. Divergência preservada — sem enfraquecer a conferência.

## Critérios — status

1. **Reconciliar por espécie, série histórica, autoridade, número/complemento e data, preservando ID/aliases oficiais.**  
   **Comprovado:** 143 ids canônicos `br-federal-{lei-constitucional|ato-institucional|ato-complementar}-{data}-{numero}`; `serie_historica` própria por espécie; `senado_id` e URN LexML no front matter; espécies não colidem com lei complementar nem com EMC da CF/1988.

2. **Recuperar a íntegra e peças acompanhantes em fonte oficial (disposições autônomas/transitórias, notas, retificações, imagens normativas).**  
   **Comprovado (parcial):** HTML Sigen capturado + Markdown publicado para 143/143; snapshots `.html.xz` com `sha256_fonte`.  
   **Não garantido:** anexos/retificações/imagens normativas além do HTML Sigen. Em todas as 143, `anexos_no_corpo: 0` e `imagens_omitidas: 5`. As 5 imagens são chrome do portal (senado.svg, hands.svg, icon-camara, icon-congresso, icon-tcu) — amostras conferidas em LCT-1, LCT-2, LCT-3, AIT-1, AIT-2, AIT-3, ACP-1, ACP-2, ACP-3; nenhuma outra `<img>` nem marcador `<<ANEXO>>`/`<<TABELA>>` nessas capturas. Isso **não** prova ausência de anexos em PDF/outras publicações oficiais.

3. **Publicar Markdown integral por edição, com procedência, captura, hashes e provas de conversão; preservar dúvidas.**  
   **Comprovado:** front matter com fonte/captura/hashes; `edicao_id` `…@publicacao-original-senado`; `vigencia_certificada: false`; verify de espécie confere série, vigência e snapshot.

4. **Publicar limites de cada catálogo e estados de acesso; lista vazia ≠ inexistência.**  
   **Comprovado:** `limites.json`, `matriz-lote.json`, nota de canal Sigen vs normas.leg.br; SHA da issue registrado como não batendo.

5. **Relacionar cada ato à série/regime constitucional correspondente e aos diplomas que altera, com evidência e cobertura parcial explícita.**  
   **Pendente (bloqueio real):** há apenas série da espécie (`lei-constitucional-1938-1946`, `ato-institucional-1964-1969`, `ato-complementar-1965-1978`) e nota genérica de dependência da #79. **Nenhum** dos 143 carrega `texto_base_relacionado`, regime constitucional evidenciado ou lista dos diplomas alterados com prova. Não inferir vínculos a partir do texto sem colação.

6. **Preservar denominação e texto da fonte, sem normalização editorial de natureza jurídica.**  
   **Comprovado (parcial):** títulos/epígrafes seguem a fonte; padrão ACP aceita grafia histórica «acto»; notas proíbem misturar com LC/EMC-1988.  
   **Risco:** chrome do portal removido na conversão (`trim_species_blocks`); corpo normativo depende do recorte a partir do título da espécie.

7. **Não misturar nos filtros de leis complementares ou emendas CF/1988; reutilizar textos-base #79.**  
   **Comprovado (parcial):** ids/séries/notas separam as espécies; textos-base #79 existem neste PR para uso futuro.  
   **Pendente:** filtros #70 / rastreador #83 e vínculos evidentes ato→texto-base.

8. **Integrar filtros/alertas à #70 e dependências ao rastreador #83.**  
   **Pendente.**

## Amostras de risco

| amostra | fonte | risco |
| --- | --- | --- |
| LCT 21 (23/01/1946) | https://legis.senado.leg.br/norma/572933 | íntegra Sigen publicada; sem vínculo evidenciado à Constituição 1937/transição 1946 |
| LCT 1 (16/05/1938) | https://legis.senado.leg.br/norma/572913 | `imagens_omitidas: 5` = chrome; pode ser lido como anexo normativo omitido |
| AIT 17 (14/10/1969) | https://legis.senado.leg.br/norma/584069 | série AIT ok; sem `texto_base_relacionado` à Constituição 1967 |
| AIT 5 (13/12/1968) | https://legis.senado.leg.br/norma/584057 | mesmo padrão; relações “só com evidência própria” na nota |
| ACP 105 (09/06/1978) | https://legis.senado.leg.br/norma/372575 | catálogo SHA ≠ issue; edição única `@publicacao-original-senado` |
| ACP 1 (27/10/1965) | https://legis.senado.leg.br/norma/372471 | `edicao_relacionada: nenhuma` — não inventaria retificações/outras publicações |

## Bloqueios reais para fechar a issue

- Vínculos evidentes de cada ato ao regime/texto-base constitucional e aos diplomas que altera (critério 5).
- Colação de anexos/retificações/imagens normativas fora do HTML Sigen (critério 2) — presença de arquivo Markdown não basta.
- Reconferência do SHA dos catálogos oficiais citáveis na issue (captura atual diverge; preservar ambos os hashes).
- Filtros #70 e rastreador #83.
- Não fechar a issue só porque 143/143 Markdown existem.
