# Provas do núcleo de licitações

Provas e snapshots são gerados por [`scripts/nucleo_licitacoes.py`](../../scripts/nucleo_licitacoes.py); não edite à mão.
O diretório `baselines/` é fixture imutável (texto auditado + procedência), não saída do `build`.

| Arquivo | O que prova |
| --- | --- |
| `fontes/` | Os bytes capturados de cada fonte oficial (HTML compactado em `.xz`; PDF como recebido). |
| `fontes.json` | Para cada fonte: URL, data da captura (UTC), status HTTP, tamanho, `sha256`, `sha256_conteudo` e cabeçalhos (`Last-Modified`, `ETag`). A página HTML da Câmara da Lei 14.133 devolveu apenas uma página de erro "504 Gateway Time-out" (HTTP 200, 160 bytes) e não é usada. |
| `reconciliacao-<norma>.json` | Cobertura do texto (a página da fonte e o Markdown têm o mesmo texto normalizado), tabelas e imagens tratadas, e conferência artigo a artigo contra uma segunda fonte oficial. |
| `historica-vs-consolidada-14133.json` | Quais artigos a edição histórica da Lei 14.133 não tem ou tem diferentes do texto consolidado. |
| `lc123-anterior-vs-nova.json` | O que mudou na LC 123 em relação ao baseline auditado (remissões à LC 238/2026 e demais campos recalculados). |
| `baselines/lc123-edicao-auditada.md` | Texto imutável da LC 123 no commit auditado (`baseline_commit`), autenticado por SHA-256. **Não** é captura de fonte oficial. |
| `baselines/lc123-edicao-auditada.json` | Procedência do baseline (commit, caminho, hash, papel `baseline-texto-auditado`). |

## Verificar (sem rede)

```sh
python3 scripts/nucleo_licitacoes.py verify
python3 -m unittest discover -s tests
```

Dependências: `beautifulsoup4==4.15.0`, `lxml==6.1.3` e `poppler-utils` (`pdftotext`); as versões usadas estão em `ferramentas.json`. O `verify` reconverte os snapshots, confere
byte a byte os Markdown e as provas publicados (incluindo **todos** os campos de `lc123-anterior-vs-nova.json`, recalculados a partir do baseline vendido) e valida o contrato de metadados. O baseline vive em `baselines/` e dispensa histórico Git completo em checkout raso.

## Refazer a captura

```sh
python3 scripts/nucleo_licitacoes.py fetch /tmp/captura   # grava /tmp/captura/fetch.json
python3 scripts/nucleo_licitacoes.py build /tmp/captura   # reescreve Markdown, provas e manifesto
git diff --stat
```

O Planalto recusa agentes sem aparência de navegador e às vezes injeta na página um `<script>` de proteção que muda a
cada resposta; por isso a captura envia um `User-Agent` de navegador (registrado em `fontes.json`) e a conversão ignora
`<script>`. `sha256` é o hash dos bytes recebidos; `sha256_conteudo` é o hash sem esse script e é o que deve coincidir
entre capturas. Se ele mudar, o conteúdo da fonte mudou: o `build` só publica se a conferência artigo a artigo fechar.

## Limites

- O baseline `baselines/lc123-edicao-auditada.md` é só o texto anterior do acervo para a prova `lc123-anterior-vs-nova.json`. Não confundir com `fontes/` (capturas oficiais). Alterar, remover ou corromper o baseline ou qualquer campo da prova faz o `verify` falhar.
- O texto de cada edição vale pela fonte oficial citada; o acervo não certifica vigência nem substitui o diário oficial.
- Lei 14.133: o Markdown segue o Planalto; a conferência usa o texto atualizado da Câmara em PDF (a versão HTML da Câmara
  não respondeu). Há uma divergência explicada: o PDF repete "§ 4º" no art. 121.
- LC 123: o Markdown segue a edição da Câmara; a conferência com o Planalto aponta o art. 47, caput (redação anterior à
  LC 147/2014 na Câmara) e o art. 87-B (ausente na página do Planalto). O texto não foi corrigido: confira a fonte.
  Esses conflitos jurídicos estão em `divergencias_conhecidas` do manifesto (por dispositivo). Diferenças nos arts. 63,
  64 e 89 são editoriais/estruturais; os arts. 63-A a 63-E são marcadores de veto na Câmara.
- Leis 8.666 e 10.520: uma só fonte oficial (Planalto). A conferência é de cobertura do texto, não contra segunda fonte.
- LC 238: uma só fonte oficial (Planalto). A conferência é de cobertura do texto integral. O art. 10 (produção de efeitos) é
  transcrito literalmente; a edição consultada da LC 123 apenas remete a esta norma e não incorpora as redações futuras.
- A Lei 14.133 histórica não tem fonte nem data de captura registradas.
