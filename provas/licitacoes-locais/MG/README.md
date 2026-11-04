# Provas — licitações locais MG

Recuperação do **Decreto municipal de Belo Horizonte nº 18.289, de 28/03/2023** (IBGE `3106200`, ato DOM `200561`) para a issue #57.

## Reprodução offline

```bash
python3 -m venv /tmp/venv-mg && /tmp/venv-mg/bin/pip install beautifulsoup4==4.15.0 lxml==6.1.3
/tmp/venv-mg/bin/python scripts/licitacoes_locais_mg.py verify
/tmp/venv-mg/bin/python -m unittest tests.test_licitacoes_locais_mg -v
```

## Fontes preservadas

| Chave | Conteúdo |
| --- | --- |
| `dom-ato-200561-json` | JSON da API `.../atos/200561/publicado` |
| `dom-ato-200561-html` | HTML integral `conteudoAto_id200561.html` |
| `dom-edicao-6824-json` | Metadados da edição DOM 6730 (2023-03-29) |
| `dom-jornal-6730-pdf` | PDF completo do jornal do dia |
| `dom-ato-200561-anexos` | Lista de anexos do ato (vazia) |
| `pgm-regulamentacao-municipal` | Catálogo PGM (ementa/identificação) |

Detalhes e hashes: [`fontes.json`](fontes.json). Cobertura artigo a artigo: [`cobertura-18289.json`](cobertura-18289.json).

## Limites

- Edição histórica da publicação; Decreto 18.621/2024 (alteração) não incorporado.
- Vigência não certificada.
- Catálogo PGM não prova íntegra.
- Decreto estadual 48.723/2023 é só reutilizado (`estaduais/MG/...`); sem recaptura nesta entrega.
- Candidatos 17.813 / 18.096 / 18.240 / 18.242: existência verificada na API; íntegra pendente.
