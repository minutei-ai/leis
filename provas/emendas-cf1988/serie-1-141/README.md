# Provas — Emendas CF/1988, série 1–141

Consolidação da cobertura do issue [#63](https://github.com/minutei-ai/leis/issues/63) após os lotes de faixa já mesclados:

- [PR #91](https://github.com/minutei-ai/leis/pull/91) — faixa 001–050
- [PR #92](https://github.com/minutei-ai/leis/pull/92) — faixa 051–100
- [PR #97](https://github.com/minutei-ai/leis/pull/97) — faixa 101–141

## Escopo

Textos autônomos das Emendas Constitucionais nº 1 a 141 à Constituição de 1988.

Fora do escopo desta matriz:

- emendas constitucionais de revisão;
- emendas a constituições históricas (data &lt; 1988);
- a Constituição consolidada / ADCT como substituto do ato modificador;
- mapa artigo-a-artigo de toda a CF (o issue exige vínculos CF/ADCT → ato/dispositivos autônomos).

## Artefatos

| Arquivo | Função |
| --- | --- |
| `matriz-serie.json` | Número, data, caminho publicado, fonte, estado de coleta e vínculos |
| `matriz-criterios-aceite.json` | Estado de cada critério de aceite do #63 (contagem ≠ fechamento) |
| `mapa-constituicao-adct-dispositivos.json` | Mapa CF/ADCT → ato e dispositivos (escopo literal do issue) |
| `manifesto-frontmatter.json` | Frontmatter contrato acrescentado aos 79 MD sem metadados |
| `fontes-conferencia/fontes-conferencia.json` | Capturas oficiais atuais de EC 9, 12 e 44, com hashes dos bytes e do snapshot comprimido |
| `fontes-conferencia/reconciliacao-artigos.json` | Comparação literal por artigo entre as capturas e os três textos legados |
| `fontes-conferencia/fontes-conferencia-legados-1-106.json` | Capturas oficiais atuais adicionais de 54 emendas legadas, sem atribuir a captura à proveniência original |
| `fontes-conferencia/reconciliacao-artigos-legados-1-106.json` | Comparação literal de 55 textos legados com as capturas atuais; preserva diferenças, pareamentos pendentes e limites da árvore estruturada da EC 1 |
| `fontes-conferencia/conferencia-senado-ec1.json` | Identidade catalográfica confirmada pelo Senado e captura da árvore textual da versão original da EC 1 |

As provas de captura e reconversão permanecem nas pastas de faixa.

As capturas de EC 9, 12 e 44 foram feitas em 05/11/2026 só para conferência. O registro mantém a URL, a data e os hashes próprios da captura atual, sem atribuí-los à origem ou à captura original dos Markdown antigos. Nesses três arquivos, `fonte_url`, `capturado_em` e `sha256_fonte` continuam `desconhecido`; `fonte_conferencia` aponta para a publicação oficial conferida. As diferenças literais encontradas são explícitas na reconciliação: EC 9 tem variações de pontuação/reticências e posição de aspas; EC 12 difere em caixa de “único” e no glifo ordinal; os artigos de EC 44 coincidem depois de remover marcação HTML e colapsar somente espaços. Nenhum corpo jurídico legado foi substituído.

Para cobrir os legados cuja captura original não estava preservada, foram capturadas versões oficiais atuais de 54 textos na Câmara e a versão original estruturada da EC 1 no Senado/Normas.leg.br. Cada entrada registra URL, data e hora, bytes, hash SHA-256 bruto e hash do snapshot comprimido. A consulta de identidade do Senado confirmou tipo, número, data, ID 593578 e publicação DOU ID 14225820 para a EC 1; o endpoint PDF dessa publicação respondeu sem bytes, por isso a árvore JSON foi preservada como evidência distinta, sem apresentá-la como imagem do DOU.

A EC 1 foi comparada também nos componentes disponíveis da árvore: título, ementa, preâmbulo, artigos, fecho e assinaturas. A ementa estruturada coincide com o Markdown; o campo catalográfico `abstract` traz “do Vereadores”, divergente tanto da ementa estruturada quanto do texto legado (“dos Vereadores”). A epígrafe do Markdown não traz o dia e mês presentes no `headline` estruturado. Essas diferenças e as serializações distintas dos artigos/assinaturas estão registradas com hashes e trechos na reconciliação, sem escolher uma variante como correção. Nos demais 54 atos, a reconciliação por artigo preserva todos os itens divergentes e não pareados; pontuação, aspas, glifos, redação, estrutura citada e assinaturas não são normalizados para forçar igualdade. Capturas atuais não preenchem a proveniência original desconhecida e nenhum texto legado foi substituído.

A auditoria estrutural resolveu dois falsos não-pareamentos do extrator de fonte: na EC 23, “Art. 91” está em um `<dir>` citado sob o Art. 1º, e a sequência principal segue no Art. 2º; na EC 30, o parágrafo entre aspas iniciado por “Art. 78” é a redação inserida pelo Art. 2º, antes do Art. 3º. Os snapshots oficiais contêm os textos e os Markdown preservam esses trechos; o manifesto agora compara 2/2 e 3/3 artigos principais, sem artigos não pareados. Nas duas emendas, as sequências de palavras coincidem após normalizar caixa, diacríticos e glifos ordinais; os hashes literais continuam diferentes por aspas, reticências, espaços e apresentação de assinaturas. Essa verificação lexical só distingue palavras ausentes de variações formais; não declara igualdade literal ou equivalência jurídica.

A reconciliação das 55 fontes adicionais registra 137 divergências literais entre artigos/componentes e uma variante catalográfica adicional da EC 1; são diferenças a preservar e revisar, não uma certificação automática de que todas as edições são idênticas. Após o pareamento estrutural das EC 23 e 30, não restam rótulos de artigos principais sem par. Os snapshots e os trechos/hashes permitem revisar cada divergência sem substituir os corpos legados.

## Auditoria da hierarquia e classificação

O mapa segmenta títulos de artigos principais fora de aspas e guarda, em cada dispositivo, o trecho auditado, a regra literal e a hierarquia. Artigos dentro de citação só são listados como redação inserida quando o próprio texto traz uma expressão introdutória de alteração; eles não são contados como artigos autônomos da emenda. Por exemplo, na EC 31 os únicos artigos principais são 1º e 2º; os arts. 79–83 aparecem como redação citada sob o art. 1º.

Não há classificação padrão como alteração constitucional. A categoria de alteração exige expressão operacional literal; regras de vigência, revogação e proibição também são registradas só quando constam do texto externo à citação. Artigos sem regra reconhecida aparecem como `dispositivo-autonomo-regra-nao-classificada`, com `revisao-explicita-sem-inferencia-de-efeito`. O critério de recuperação textual avalia os 141 arquivos e as lacunas de segmentação; a revisão de classificação é um critério separado. Os trechos em revisão continuam completos e vinculados ao ato no mapa, sem inferência de efeito jurídico. A matriz permanece com `issue_fechavel: false` enquanto a revisão e a análise das diferenças de edição não estiverem concluídas.

## Reprodução

```bash
python3 scripts/emendas_cf1988_serie_1_141.py ensure-frontmatter
python3 scripts/emendas_cf1988_serie_1_141.py build
python3 scripts/emendas_cf1988_serie_1_141.py verify
python3 -m unittest tests.test_emendas_cf1988_serie_1_141 -v
```

## Limites

O acervo não certifica vigência. A presença do arquivo e as citações na Constituição consolidada não substituem o texto autônomo da emenda. A contagem 141/141 é necessária e insuficiente: `issue_fechavel` permanece `false`. Captura original desconhecida nos lotes pré-metadados fica explícita (`desconhecido`), sem atribuição retroativa de hash.
