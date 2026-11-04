# Provas — Espécies legislativas federais (DLG, RSF, RCD, RCN)

Lote dos issues [#65](https://github.com/minutei-ai/leis/issues/65), [#66](https://github.com/minutei-ai/leis/issues/66), [#89](https://github.com/minutei-ai/leis/issues/89) e [#94](https://github.com/minutei-ai/leis/issues/94).

## Escopo

| Código | Espécie | Órgão emissor | Issue |
| --- | --- | --- | --- |
| DLG | Decreto Legislativo | Congresso Nacional | #65 |
| RSF | Resolução do Senado Federal | Senado Federal | #66 |
| RCD | Resolução da Câmara dos Deputados | Câmara dos Deputados | #89 |
| RCN | Resolução do Congresso Nacional | Congresso Nacional | #94 |

Espécies distintas: número/ano sem órgão não identifica a norma. Não confundir com decreto do Executivo nem com decreto-lei (`DEL`).

## Artefatos

| Arquivo | Função |
| --- | --- |
| `catalogos.json` + `fontes/senado-lista-*.json.xz` | Capturas oficiais da API do Senado, com hashes |
| `reconciliacao-*.json` | Identidade, ID, URL, URN, estado de coleta e caminho publicado |
| `resumo-reconciliacao.json` | Totais por espécie |
| `limites-catalogos.json` | Limites do catálogo RCD (Senado até 1991) e fontes complementares |
| `coleta.json` / `coletas/` | Lote inicial de HTML recuperado |
| `fontes.json` / `manifesto.json` / `cobertura-conversao.json` | Provas do Markdown publicado neste lote |

## Reprodução

```bash
python3 scripts/especies_legislativas_federais.py capture
python3 scripts/especies_legislativas_federais.py reconcile
python3 scripts/especies_legislativas_federais.py collect
python3 scripts/especies_legislativas_federais.py build
python3 scripts/especies_legislativas_federais.py verify
python3 -m unittest tests.test_especies_legislativas_federais -v
```

## Fontes de texto

- **DLG / parte de RCN:** HTML em `normas.leg.br` (`/api/public/binario/.../texto`), a partir da URN LexML.
- **RSF / RCD / fallback:** HTML da publicação na página do Senado (`/norma/{id}/publicacao/{pubId}`), usando o ID linkado na página quando o JSON de detalhe aponta só para PDF vazio.

## Limites deste lote

- O catálogo completo foi reconciliado; a íntegra Markdown deste PR cobre um **lote inicial** (amostra por espécie). Demais identidades permanecem `identificado-nao-coletado`.
- A lista do Senado para **RCD** observa o intervalo até 1991. Isso **não** encerra a série: o Regimento Interno da Câmara atualizado até a Resolução 16/2025 evidencia atividade posterior; a descoberta complementar no catálogo da Câmara fica pendente.
- RCN com anexos essenciais (ex.: 1/2025 e 2/2025) cujas peças ANX voltaram como PDF vazio no Senado **não** foram publicadas neste lote.
- Presença no catálogo ou no repositório não certifica vigência.
- README agregado / contagens globais ficam com a coordenação.
