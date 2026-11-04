# Provas — licitações locais GO

Capturas e conferência do recorte de Goiás do catálogo temático `metadados/licitacoes-locais/GO.json` (issue #57).

## Conteúdo

- `fontes.json` — URLs, datas UTC, SHA-256 e caminhos dos snapshots.
- `fontes/sileg-dc-2469.html.xz` — HTML oficial do SILEG (Decreto municipal de Goiânia 2.469/2024).
- `fontes/dom-8318-20240625.pdf.xz` — fac-símile da edição DOM 8318 (25/06/2024) para conferência.
- `cobertura-decreto-2469.json` — trechos obrigatórios, conferência DOM e limites.

## Reprodução

```bash
python3 -m unittest tests.test_licitacoes_locais_GO -v
```

A conversão do Markdown usou `scripts/nucleo_licitacoes.py::Converter` sobre a página SILEG, a partir da epígrafe `DECRETO Nº 2.469` (BOM da fonte removido; brasão/cabeçalho institucional omitidos). Não se usa navegador/Playwright. A presença dos arquivos não certifica vigência. O Decreto estadual 10.247/2023 é apenas reutilizado (`estaduais/GO/br-go-norma-106877.md`), sem nova captura nesta pasta.

O teste reconverte integralmente o corpo normativo do snapshot HTML e compara o corpo publicado byte a byte. Também confere trechos do fac-símile DOM e os hashes das capturas.
