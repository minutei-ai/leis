# Contrato — atos infralegais SEGES (issue #72)

Contrato do lote `atos-infralegais-seges`: primeiras instruções normativas
federais de contratação (SEGES/ME e SEGES/MGI) publicadas no acervo com espécie
própria e órgão no identificador.

## Espécie e nome

| Campo | Valor |
| --- | --- |
| `norma_tipo` | `in` (instrução normativa) |
| Padrão de `norma_id` / arquivo | `br-federal-in-<orgao>-<AAAA-MM-DD>-<numero>.md` |
| Órgãos neste lote | `seges-me`, `seges`, `seges-mgi` (e `seges-mpdg` só catalogado na pendência da IN 5/2017) |

Exemplos: `br-federal-in-seges-me-2021-07-07-65`, `br-federal-in-seges-2022-08-08-58`,
`br-federal-in-seges-mgi-2023-02-07-2`.

Espécies de outros órgãos (RDC ANVISA, IN RFB, Resolução CMN) ficam na issue #75
e **não** reutilizam este prefixo sem o órgão correspondente.

## Regras

1. **Sem vigência inferida.** `vigencia_certificada` é sempre `false`.
2. **Órgão no id.** Número sozinho não identifica o ato; SEGES/ME ≠ SEGES/MGI.
3. **Lei regulamentada.** O campo `lei_regulamentada` e as `relacoes` tipo
   `regulamento` ligam à Lei 14.133 (ou leis anteriores, quando couber), sem
   afirmar vigência aplicável a casos concretos.
4. **Fonte do portal ≠ DOU certificado.** O Markdown segue o HTML de
   Compras.gov.br e preserva o aviso de que o conteúdo não substitui o DOU.
5. **Acesso falho ≠ inexistência.** IN 5/2017 permanece em `pendencias_acesso`
   com URLs tentadas e resultado (403/FAQ); não se publica resumo no lugar do
   texto integral.
6. **Escopo parcial.** Demais INs, portarias de catálogo/PCA e outros órgãos
   ficam fora deste lote.
7. **Provas.** Snapshots `.html.xz`, `fontes.json`, `reconciliacao-*.json` e
   verify offline a partir dos snapshots.

## Cabeçalho

Além da identidade (`norma_id`, `norma_tipo`, `norma_numero`, `norma_data`,
`titulo`, `esfera`), o lote exige `orgao_emissor`, `orgao_emissor_label`,
`lei_regulamentada`, `tema`, captura/hash, `situacao`/`vigencia_certificada`,
`manifesto` e `lote`.
