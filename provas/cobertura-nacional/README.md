# Provas — cobertura nacional e metadados BM25

Artefatos das issues #70 (contrato/export BM25), #74 (inventário territorial),
#77 (fac-símile × transcrição) e #83 (matriz nacional).

## O que esta pasta prova

- Contrato global versionado em `metadados/CONTRATO-acervo.md`, reutilizando os
  contratos setoriais sem identidades paralelas.
- Captura IBGE de localidades (hash da resposta completa + slim publicado).
- Inventário territorial com estados de trabalho; diretório ≠ completude;
  Brasília/DF e Fernando de Noronha como entidades especiais.
- Inventário de `fac-simile-oficial` e de `data:image` sem marcador, com
  `representacao` e `cobertura_transcricao` distintas da vigência.
- Extração do formulário anexo do CPP (DL 3.689/1941) para asset com SHA-256
  `d8811277…`, mantendo pendência explícita de transcrição.
- Errata do comparador Senado que passa a preservar `complemento`.
- Demonstração offline de mapping/filtros/BM25 **sem** provisionar Elasticsearch.

## O que esta pasta não prova

- Completude da legislação brasileira.
- Vigência de qualquer norma.
- Que OCR/transcrição dos fac-símiles esteja validada.
- Que um índice de busca esteja em produção.

## Reprodução

```bash
python3 scripts/cobertura_nacional.py generate
python3 scripts/cobertura_nacional.py verify
python3 -m unittest tests.test_cobertura_nacional -v
```

Somente leitura local; sem rede.
