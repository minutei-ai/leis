# Contrato de metadados do núcleo de licitações

Este contrato vale para os arquivos Markdown do núcleo de legislação de licitações (Leis 14.133/2021, 13.303/2016,
8.666/1993 e 10.520/2002 e Leis Complementares 123/2006, 227/2026 e 238/2026). Cada arquivo começa com um cabeçalho `---` de campos planos
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
| `fonte_conferencia` | Fontes oficiais usadas só para conferir (lista de URLs) ou `"nenhuma"`. Não repete a URL de `fonte_url`. |
| `capturado_em`, `sha256_fonte` | Quando (UTC) e o que foi capturado (hash dos bytes recebidos; o hash do conteúdo sem o script de proteção do Planalto, estável entre capturas, está em `sha256_conteudo` no manifesto e em `fontes.json`). Em edição com corpo preservado e captura original desconhecida, ficam `"desconhecido"`; a captura atual usada só para conferir registra hash/data na prova, sem atribuí-los retroativamente a estes campos. |
| `situacao`, `situacao_fundamento`, `vigencia_certificada` | Situação informada pela fonte; ver acima. |
| `texto_riscado`, `anexos_no_corpo`, `tabelas`, `imagens_omitidas` | Tratamento de conteúdo: ver abaixo. |
| `efeitos_diferidos` | Como os efeitos diferidos aparecem; o detalhe estruturado está no manifesto. Datas e leituras só saem após o gerador exigir o literal revisado do dispositivo (lista vazia / fonte vazia / data alterada interrompem a geração; o acervo não calcula vigência). |
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
consolidada da Lei 14.133 e entre a LC 123 anterior e a atual. O baseline imutável da LC 123 (`baselines/lc123-edicao-auditada.md`,
com procedência em `baselines/lc123-edicao-auditada.json`) autentica a edição anterior por SHA-256 e commit; não é fonte de
captura e não depende de `git show` em checkout raso. O `verify` recalcula **todos** os campos de `lc123-anterior-vs-nova.json`
a partir desse baseline e dos snapshots. Veja o `README.md` dessa pasta para reproduzir.

## Divergências conhecidas (manifesto)

O campo `divergencias_conhecidas` de cada documento em [`nucleo-licitacoes.json`](nucleo-licitacoes.json) propaga, por
dispositivo, os conflitos entre fontes oficiais que o aviso editorial já descreve. Quem fragmenta a norma por artigo
consulta esse mapa sem depender do cabeçalho editorial inteiro.

Formatos admitidos:

| Formato | Quando | Forma |
| --- | --- | --- |
| Legado (string) | Lei 14.133 consolidada, art. 121 | `"121": "descrição…"` — a string é a explicação completa; o texto publicado segue a fonte principal. |
| Estruturado (objeto) | LC 123, arts. 47 e 87-B | chave = número do artigo; valor = objeto abaixo. |

Objeto estruturado (obrigatório para divergências jurídicas da LC 123):

| Campo | Significado |
| --- | --- |
| `dispositivo` | Identificação legível (ex.: `art. 47, caput`). |
| `fontes` | Chaves das fontes oficiais em conflito (ex.: `camara-lc123`, `planalto-lc123`). |
| `descricao` | O que diverge entre as fontes, sem escolher redação. |
| `tratamento` | O que o acervo faz: qual fonte o Markdown segue e onde o alerta permanece. |
| `natureza` | `juridica` para conflito de redação/presença normativa; diferenças só de título, seção, fecho ou marcador de veto não entram aqui. |

Regras:

- `divergencias_conhecidas: {}` só é válido quando não há conflito jurídico conhecido documentado no aviso editorial nem nas provas.
- A LC 123 tem duas edições integrais com o mesmo `norma_id` e `edicao_id` distintos: a da Câmara em `federal/br-federal-lei-complementar-2006-12-14-123.md` e a do Planalto em `federal/edicoes/br-federal-lei-complementar-2006-12-14-123-planalto.md` (fora da contagem de normas). Cada Markdown segue só a sua fonte principal; o art. 47 e o art. 87-B ficam alertados no manifesto e no aviso de ambas, sem substituição silenciosa nem composição de redações.
- O consumidor escolhe a edição (`edicao_id` / `edicao_relacionada` / hashes de captura) sem presumir vigência.
- Na prova de reconciliação de cada edição da LC 123, `divergencias_editoriais` cobre os arts. 63, 64 e 89 (títulos, notas de seção, fecho/assinaturas) e `marcadores_veto` cobre os arts. 63-A a 63-E (veto anotado na Câmara, sem conteúdo normativo novo).
- A nota do art. 87-B (acréscimo pela LC 214/2025 com efeitos a partir de 1º/1/2027; revogação pela LC 227/2026) permanece
  no dispositivo; a LC 227 publicada no acervo traz o art. 181 com datas próprias por alínea e o art. 182 com produção de
  efeitos diferenciada — sem atribuir 2027 a toda revogação nem reconstruir a redação do 87-B.

## Eventos de revogação (manifesto)

O campo opcional `eventos_revogacao` de um documento em [`nucleo-licitacoes.json`](nucleo-licitacoes.json) registra a cronologia estruturada de revogações com dispositivo, fundamento e data. Ele complementa o campo legado `revogacao` (situação final informada pela fonte) e **não** substitui o corpo normativo.

Cada evento:

| Campo | Significado |
| --- | --- |
| `id` | Identificador estável do evento. |
| `tipo` | `revogacao-parcial` ou `revogacao`. |
| `alcance` | Descrição legível do que o evento atinge. |
| `dispositivos` | Lista recuperável (`art. N` ou a lei integral citada no fundamento). |
| `fundamento` | Norma e dispositivo que ordenam o evento (`norma_id`, `dispositivo`, `texto_literal`, `fonte_url`, `sha256_fonte`; `norma_modificadora` quando houver). |
| `data` | Ver tabela abaixo. |
| `leitura` | Limite explícito: o acervo não aplica a data a contratos concretos nem resolve transição. |

Campo `data`:

| Campo | Significado |
| --- | --- |
| `valor` | ISO `AAAA-MM-DD` ou `"desconhecido"`. |
| `origem` | `informada-explicitamente` (data literal no texto), `resolvida-da-publicacao-oficial` (expressão relativa resolvida com prova de publicação) ou `"desconhecido"`. |
| `expressao_na_fonte` | Trecho temporal literal (ex.: `na data de publicação desta Lei`, `em 30 de dezembro de 2023`). |
| `prova` | Obrigatória quando `origem` é `resolvida-da-publicacao-oficial`: chave/URL/hash da fonte e `trecho` que prova a publicação. |

Regras:

- Publicação, vigência e aplicação/transição são campos distintos; um evento de revogação não afirma vigência residual nem aplica o art. 191 da Lei 14.133 a casos concretos.
- Sem prova oficial preservada (ou nova captura) para resolver uma data relativa, `valor` e `origem` ficam `"desconhecido"`.
- A Lei 8.666 traz dois eventos: arts. 89–108 no art. 193, I (publicação da Lei 14.133) e a lei integral no art. 193, II, a (30/12/2023, redação da LC 198/2023).
