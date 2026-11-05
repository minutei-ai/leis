# Contrato — atos infralegais SEGES (issue #72)

Contrato do lote `atos-infralegais-seges`: instruções normativas e portarias
federais de contratação (SEGES/ME, SEGES/MGI e histórico SEGES/MPDG) publicadas
no acervo com espécie própria e órgão no identificador.

## Espécie e nome

| Campo | Valor |
| --- | --- |
| `norma_tipo` | `in` (instrução normativa) ou `portaria` |
| Padrão de `norma_id` / arquivo (IN) | `br-federal-in-<orgao>-<AAAA-MM-DD>-<numero>.md` |
| Padrão de `norma_id` / arquivo (portaria) | `br-federal-portaria-<orgao>-<AAAA-MM-DD>-<numero>.md` |
| Órgãos neste lote | `seges-me`, `seges`, `seges-mgi`, `seges-mpdg` |

Exemplos: `br-federal-in-seges-me-2021-07-07-65`, `br-federal-in-seges-mpdg-2017-05-26-5`,
`br-federal-portaria-seges-me-2021-07-19-8678`, `br-federal-in-seges-me-2022-12-26-98`,
`br-federal-portaria-seges-me-2022-02-02-938`.

Espécies de outros órgãos (RDC ANVISA, IN RFB, Resolução CMN) ficam na issue #75
e **não** reutilizam este prefixo sem o órgão correspondente.

## Classificação (Portaria 8.678 × PCA/PGC × catálogo)

- **Portaria SEGES/ME 8.678/2021** = governança das contratações. O PCA aparece
  como instrumento; isso **não** equivale ao regulamento do PCA/PGC.
- **Decreto 10.947/2022** = regulamento do PCA e instituição do PGC (espécie
  decreto; já no acervo; fora deste lote).
- **Portaria SEGES/ME 938/2022** = catálogo eletrônico de padronização (art. 19,
  II, Lei 14.133). Distinto do sistema CATMAT/CATSER.

## Regras

1. **Sem vigência inferida.** `vigencia_certificada` é sempre `false`.
2. **Órgão no id.** Número sozinho não identifica o ato; SEGES/ME ≠ SEGES/MGI.
3. **Lei regulamentada.** O campo `lei_regulamentada` e as `relacoes` tipo
   `regulamento` ligam à lei de referência (14.133 ou leis anteriores, quando
   couber), sem afirmar vigência aplicável a casos concretos. Relações adicionais
   (`autorizacao-aplicacao`, `alteracao`, `referencia-tematica`) exigem evidência
   literal e desconhecidos explícitos.
4. **Fonte do portal ≠ DOU certificado.** O Markdown segue o HTML de
   Compras.gov.br ou do DOU, conforme a fonte de cada ato, e preserva o aviso
   de que o conteúdo não substitui a versão certificada.
5. **Acesso falho ≠ inexistência.** Tentativas DOU 403, portal restrito, FAQ sem
   íntegra e índices sem ementa de catálogo permanecem documentados; não se
   publica resumo no lugar do texto integral nem se declara inexistência.
6. **Escopo parcial.** Demais INs e portarias pontuais de atualização operacional
   CATMAT/CATSER não localizadas por título/ementa no inventário **paginado**
   dos índices oficiais ficam fora deste lote, com pendência explícita (sem
   falso negativo). Inventário em
   `provas/atos-infralegais-seges/inventario-portarias-catalogo-pca.json`.
7. **Provas.** Snapshots `.html.xz`, `fontes.json`, `reconciliacao-*.json`,
   integridade de anexos da IN 5 e verify offline a partir dos snapshots. PDFs
   oficiais (ex.: CGU) podem ser citados por URL/hash sem upload no repositório.

## Cabeçalho

Além da identidade (`norma_id`, `norma_tipo`, `norma_numero`, `norma_data`,
`titulo`, `esfera`), o lote exige `orgao_emissor`, `orgao_emissor_label`,
`lei_regulamentada`, `tema`, captura/hash, `situacao`/`vigencia_certificada`,
`manifesto` e `lote`.
