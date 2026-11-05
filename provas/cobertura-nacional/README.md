# Provas — cobertura nacional e metadados BM25

Artefatos das issues #70 (contrato/export BM25), #74 (inventário territorial),
#77 (fac-símile × transcrição) e #83 (matriz nacional).

## O que esta pasta prova

- Contrato global versionado em `metadados/CONTRATO-acervo.md`, reutilizando os
  contratos setoriais sem identidades paralelas.
- Piloto de cabeçalhos gerais (`metadados/acervo-geral-piloto.json`) com
  `campo_fontes` / `fonte_do_campo`, corpo Markdown preservado e desconhecidos
  explícitos (#70).
- Captura IBGE de localidades (hash da resposta completa + slim publicado).
- Inventário territorial com estados de trabalho; diretório ≠ completude;
  Brasília/DF e Fernando de Noronha como entidades especiais.
- Registro de fontes por jurisdição (`registro-fontes-jurisdicao.json`): UFs,
  municípios publicados e regra de não inferir ausência por pasta/HTTP (#74).
- Inventário de `fac-simile-oficial` e de `data:image` sem marcador, com
  `representacao` e `cobertura_transcricao` distintas da vigência.
- Formulário anexo do CPP (DL 3.689/1941): asset SHA-256 `d8811277…` e
  colação visual estrutural dos rótulos (`cobertura_transcricao=parcial`) (#77).
- Reconciliação de espécies publicadas no federal + blockers concretos
  (#102/#103 e demais) (#83).
- Errata do comparador Senado que passa a preservar `complemento`.
- Demonstração offline de mapping/filtros/BM25 **sem** provisionar Elasticsearch.

## O que esta pasta não prova

- Completude da legislação brasileira.
- Vigência de qualquer norma.
- Que todos os fac-símiles tenham transcrição validada.
- Que um índice de busca esteja em produção.
- Que os 5.555 municípios sem diretório careçam de legislação.

## Reprodução

```bash
python3 scripts/cobertura_nacional.py generate
python3 scripts/cobertura_nacional.py verify
python3 -m unittest tests.test_cobertura_nacional -v
```

Somente leitura local; sem rede.
