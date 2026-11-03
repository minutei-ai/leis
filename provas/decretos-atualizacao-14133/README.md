# Decretos de atualização dos valores da Lei 14.133

Recuperação dos anexos/tabelas de valores dos Decretos 10.922/2021, 11.317/2022, 11.871/2023, 12.343/2024 e 12.807/2025.

## Conteúdo

- `fontes.json` — URL, data de captura, hashes e cabeçalhos HTTP de cada página do Planalto
- `fontes/*.htm.xz` — snapshots das páginas HTML capturadas
- `cobertura-anexos.json` — todas as linhas e valores de cada anexo, para conferência automatizada

## Como conferir

```bash
python3 -m unittest tests.test_decretos_atualizacao_14133 -v
```

Os testes leem somente o repositório (sem rede): conferem a presença do bloco `ANEXO`, a cobertura de **todas** as linhas/valores de `cobertura-anexos.json`, a integridade dos snapshots e a sequência de revogações/delegação literal do art. 3º do Decreto 12.807/2025, sem inferir atualizações futuras.

## Limites

- O corpo dos artigos nos Markdown preserva a redação já publicada no acervo; o anexo veio do Planalto.
- Páginas de decretos revogados no Planalto exibem riscado/`Revogado pelo…`; os Markdown desta recuperação não aplicam esse riscado posterior ao texto do ato.
- Nenhuma peça destes cinco atos ficou pendente nesta recuperação.
