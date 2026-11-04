# Lote ampliado de divergências caminho×cabeçalho (issue #102)

O caso canônico **Decreto-Lei 4.014-A** está colacionado em `NOTA-DIVERGENCIA-4014-A.md` (Câmara `4.014-A` × Senado publicação `1.014-A`).

A issue #102 exige verificar um lote delimitado **sem** forçar título≡caminho (isso corromperia transcrições fiéis e séries/complementos).

## Exemplos citados na issue — colação ato a ato (2026-11-04)

Fontes: Senado dados abertos (ficha + publicação textual `temTexto=S`). Snapshots em `divergencias/detalhe-*.json` e `divergencias/senado-pub-*.html.xz`.

| Arquivo | Catálogo Senado | Publicação Senado (literal) | Corpo / ementa | Decisão |
| --- | --- | --- | --- | --- |
| `federal/br-federal-decreto-1958-12-31-45171.md` | id 467738 · `DEC-45171-1958-12-31` · «Decreto nº **45.171**» · ementa José Esmeraldo / Corumbá (ferro/manganês) · DOU 07/01/1959 p.279 | pub 15805509: cabeçalho literal **`decreto nº 41.171, de 31 de dezembro de 1958`** | Marcador `###DEC-045171`; ementa e dispositivo batem com a ficha 45.171. Decreto **41.171/1957** é outro ato (mica/quartzo Goiânia, id 463753). | **Erro literal da fonte** (publicação Senado). Preservar cabeçalho 41.171 no Markdown; identidade canônica do acervo = **45.171**. Sem reescrita. |
| `federal/br-federal-decreto-1959-01-28-45353.md` | id 467918 · `DEC-45353-1959-01-28` · «Decreto nº **45.353**» · ementa doação Montes Claros · DOU 05/02/1959 p.2279 | pub 15700630: cabeçalho literal **`DECRETO Nº 453.353, DE 28 DE JANEIRO DE 1959`** | Marcador `###DEC-045353`; ementa/dispositivo batem com 45.353. Busca Senado por 453353: sem norma. | **Erro literal da fonte** (dígito extra). Preservar `453.353`; identidade = **45.353**. Sem reescrita. |
| `federal/br-federal-decreto-1959-09-30-46934.md` | id 469503 · `DEC-46934-1959-09-30` · «Decreto nº **46.934**» · ementa Joaquim de Souza Novo / DF · DOU 16/11/1959 p.24041 | pub 15804419: cabeçalho literal **`DECRETO Nº 56.934, DE 30 DE SETEMBRO DE 1959`** | Marcador `###DEC-046934`; ementa/dispositivo batem com 46.934. Decreto **56.934/1965** é outro ato (Incalesa mineração, id 479529). | **Erro literal da fonte**. Preservar `56.934`; identidade = **46.934**. Sem reescrita. |

Planalto HTML destes três números não foi obtido nesta sessão (reset de conexão); a colação Senado ficha×publicação basta para o critério «erro da fonte vs corrupção do corpus»: o Markdown reproduz a publicação textual do Senado, não inventa o número do caminho.

## Amostra 1958–1959 (diagnóstico, sem reescrita)

Varredura restrita a `federal/br-federal-decreto-1958*.md` e `1959*.md` (metodologia da issue): dezenas de candidatos path≠header; parte é citação de outra norma no preâmbulo; equivalências de formatação excluídas. **Não** autoriza reescrita em massa. Complementos e séries (`-A`, `-B`) permanecem distintos.

## Decisão deste PR

1. Identidade **4.014-A** (Câmara) com divergência Senado documentada — mantida.
2. Três exemplos da issue **colacionados**: cabeçalhos divergentes = literais da publicação Senado; corpus preservado; notas nesta matriz.
3. O teste do lote **não** impõe título≡caminho em todo o federal.
4. Critério do lote ampliado: colação dos três atos citados + amostra documentada; demais candidatos da varredura histórica permanecem fora deste lote delimitado.

Refs #102
