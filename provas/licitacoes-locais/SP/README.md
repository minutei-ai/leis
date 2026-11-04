# Provas — licitações locais SP

Capturas e conferência do recorte de São Paulo do catálogo temático `metadados/licitacoes-locais/SP.json` (issue #57).

## Conteúdo

- `fontes.json` — URLs, datas UTC, SHA-256 e caminhos dos snapshots.
- `fontes/*.html.xz` — HTML oficial do Catálogo de Legislação Municipal (página principal do Decreto 62.100/2022, detalhes e consolidado).
- `cobertura-decreto-62100.json` — trechos obrigatórios, marcadores de alteração e pendências.

## Reprodução

```bash
python3 -m unittest tests.test_licitacoes_locais_SP -v
```

A conversão do Markdown usou `scripts/nucleo_licitacoes.py::Converter` sobre o bloco `.col.s12.customStyle` da página principal. Não se usa navegador/Playwright. A presença dos arquivos não certifica vigência. O Decreto estadual 67.608/2023 é apenas reutilizado (`estaduais/SP/br-sp-norma-207462.md`), sem nova captura nesta pasta.
