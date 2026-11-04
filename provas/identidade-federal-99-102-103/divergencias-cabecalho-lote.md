# Lote ampliado de divergências caminho×cabeçalho (issue #102)

O caso canônico **Decreto-Lei 4.014-A** está colacionado em `NOTA-DIVERGENCIA-4014-A.md` (Câmara `4.014-A` × Senado publicação `1.014-A`).

A issue #102 exige ainda verificar um lote delimitado de divergências semelhantes **sem** forçar título≡caminho (isso corromperia transcrições fiéis e séries/complementos).

## Exemplos citados na issue (estado atual do acervo)

| Arquivo | Marcador / caminho | Cabeçalho literal (primeiras linhas) | Leitura |
| --- | --- | --- | --- |
| `federal/br-federal-decreto-1958-12-31-45171.md` | `###DEC-045171` / 45171 | `decreto nº 41.171, de 31 de dezembro de 1958` | Divergência numérica 45171×41171; **não** reescrito neste lote |
| `federal/br-federal-decreto-1959-01-28-45353.md` | `###DEC-045353` / 45353 | `DECRETO Nº 453.353, DE 28 DE JANEIRO DE 1959` | Possível dígito extra no cabeçalho; **não** reescrito |
| `federal/br-federal-decreto-1959-09-30-46934.md` | `###DEC-046934` / 46934 | `DECRETO Nº 56.934, DE 30 DE SETEMBRO DE 1959` | Divergência 46934×56934; **não** reescrito |

Nenhuma dessas três foi tratada como erro automático do conversor: falta colação da publicação oficial (Câmara/DOU/Senado) ato a ato, no mesmo espírito do 4.014-A.

## Amostra 1958–1959 (detector local, só diagnóstico)

Varredura restrita a `federal/br-federal-decreto-1958*.md` e `1959*.md`, comparando o número do caminho ao primeiro cabeçalho `DECRETO`/`LEI` nas ~800 primeiras caracteres:

- Dezenas de candidatos com path≠header (ex.: 43021×44021, 43223×43233, 45171×41171, 45353×453353, 45440×54440).
- Parte cita Decreto-lei/Lei no preâmbulo (falso positivo se o detector pegar a norma citada, não o epígrafe).
- Equivalências de formatação (pontos/espaços/sufixos) devem ser excluídas como na metodologia da issue (294/504 no snapshot histórico).

Esta amostra **não** autoriza reescrita em massa. Complementos e séries (`-A`, `-B`, etc.) permanecem distintos.

## Decisão deste PR

1. Publicar e testar apenas a identidade **4.014-A** (Câmara) com divergência Senado documentada.
2. Registrar os três exemplos da issue e a amostra 1958–1959 como **pendências de colação**.
3. O teste do lote **não** impõe título≡caminho em todo o federal.

Refs #102 — critério do lote ampliado permanece aberto.
