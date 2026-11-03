# Contrato de metadados do núcleo de licitações

Este contrato vale para os arquivos Markdown do núcleo de legislação de licitações (Leis 14.133/2021, 13.303/2016,
8.666/1993 e 10.520/2002 e Lei Complementar 123/2006). Cada arquivo começa com um cabeçalho `---` de campos planos
(`campo: valor`, valores em JSON) e o detalhamento fica em [`nucleo-licitacoes.json`](nucleo-licitacoes.json). O cabeçalho
e o manifesto dizem de onde veio cada texto, que edição ele é e quando foi capturado, **sem** deduzir nada do texto, do ano
da norma, da presença no repositório ou da data do commit.

Os demais arquivos do acervo ainda não têm esse cabeçalho. A ausência dele significa "metadados não registrados", nunca
"vigente".

## Regras gerais

- **Desconhecido é explícito.** O que o acervo não sabe recebe `"desconhecido"`; um campo obrigatório ausente é erro.
- **O acervo não certifica vigência.** `vigencia_certificada` é sempre `false`. `situacao` só traz o que a fonte informa:
  `revogada` (com `situacao_fundamento`), `vigente-informada` ou `nao-informada`. Nunca se infere vigência.
- **Edição ≠ norma.** Edições alternativas de uma norma que já tem arquivo em `federal/` ficam em `federal/edicoes/` e não entram na contagem de normas do README. `norma_id` identifica a norma; `edicao_id` identifica o arquivo (norma + tipo de edição + órgão).
  A Lei 14.133 tem duas edições com o mesmo `norma_id` e `edicao_id` diferentes.
- **Edições:** `historica` (redação preservada de um momento anterior; não incorpora alterações posteriores) ou `consolidada`
  (texto atualizado publicado por um órgão oficial). `edicao_integral` é `true` só quando a reprodução foi conferida
  inteira contra a fonte; `"desconhecido"` quando não se sabe.
- **Texto riscado.** Onde a fonte oficial mantém riscada uma redação superada, vetada ou revogada, o Markdown usa `~~…~~`.
  Esse trecho não é dispositivo em vigor. Em norma revogada, a fonte risca o texto quase inteiro.

## Campos do cabeçalho

| Campo | Significado |
| --- | --- |
| `id` | Nome do arquivo sem `.md`. |
| `norma_id`, `norma_tipo`, `norma_numero`, `norma_data`, `titulo`, `esfera` | Identidade da norma. |
| `edicao_id`, `edicao_tipo`, `edicao_integral`, `edicao_relacionada` | Identidade da edição e a outra edição da mesma norma, quando houver. |
| `fonte_orgao`, `fonte_url`, `fonte_formato` | Origem oficial da reprodução. |
| `fonte_conferencia` | Fontes oficiais usadas só para conferir (lista de URLs) ou `"nenhuma"`. |
| `capturado_em`, `sha256_fonte` | Quando (UTC) e o que foi capturado (hash dos bytes recebidos; o hash do conteúdo sem o script de proteção do Planalto, estável entre capturas, está em `sha256_conteudo` no manifesto e em `fontes.json`). |
| `situacao`, `situacao_fundamento`, `vigencia_certificada` | Situação informada pela fonte; ver acima. |
| `texto_riscado`, `anexos_no_corpo`, `tabelas`, `imagens_omitidas` | Tratamento de conteúdo: ver abaixo. |
| `efeitos_diferidos` | Como os efeitos diferidos aparecem; o detalhe estruturado está no manifesto. |
| `sha256_corpo_preservado` | Só nos arquivos que preservam texto anterior: hash do corpo original. |
| `sha256_markdown` | Hash do que vem depois do cabeçalho (inclui a nota de edição). |
| `manifesto`, `contrato_versao` | Ligação com o manifesto e versão deste contrato. |

## Anexos e blocos não textuais

- Anexos que fazem parte da fonte ficam no corpo; `anexos_no_corpo` conta os blocos `ANEXO …`.
- Tabelas viram tabela Markdown; com células mescladas viram `<table>` simples (só `rowspan`/`colspan`).
- Imagens (brasão e logotipos do cabeçalho das páginas oficiais) são omitidas do Markdown e registradas no manifesto com
  tipo, dimensões e, quando embutidas, tamanho e SHA-256. Nenhuma imagem das fontes conferidas carrega texto jurídico.
  Imagem com conteúdo normativo deve ser publicada como fac-símile identificado, nunca omitida.

## Provas

`provas/nucleo-licitacoes/` guarda: `fontes.json` (URL, data, hashes e cabeçalhos de cada captura), os snapshots das fontes,
a conferência artigo a artigo entre fontes oficiais (`reconciliacao-*.json`), a comparação entre a edição histórica e a
consolidada da Lei 14.133 e entre a LC 123 anterior e a atual. Veja o `README.md` dessa pasta para reproduzir.
