# Leis brasileiras em Markdown

Acervo público do [Minutei](https://minutei.legal), coletado diretamente de fontes oficiais. Um arquivo Markdown por norma, com origem, versão, data de coleta e hashes SHA-256. O objetivo é ampliar o acesso à legislação brasileira em texto simples, com coleta reproduzível e histórico real das atualizações.

As quantidades publicadas, os catálogos consultados e o que falta coletar estão em **[COBERTURA.md](COBERTURA.md)**. O acervo está em formação e ainda não contém todas as leis brasileiras. A coleta em lotes está configurada no GitHub Actions a cada seis horas, além da execução manual. A automação só publica material que passa pelos testes e pela auditoria; isso não certifica completude nacional.

## Consultar

- [Constituição Federal de 1988](federal/br-federal-constituicao-1988-10-05.md)
- [Código Civil — Lei nº 10.406/2002](federal/br-federal-lei-2002-01-10-10406.md)
- [Código de Processo Civil — Lei nº 13.105/2015](federal/br-federal-lei-2015-03-16-13105.md)
- [Demais normas federais](federal/)
- [Normas de Minas Gerais](estaduais/MG/)
- [Normas do estado de São Paulo](estaduais/SP/)
- [Normas da Bahia](estaduais/BA/)
- [Leis do município de São Paulo](municipais/3550308/)

O cabeçalho de cada arquivo informa a versão: texto atualizado da Câmara, compilação atual disponibilizada pelo Senado ou publicação original. O coletor do Senado prefere a compilação atual em HTML; se ela não existir nos metadados, usa a publicação original em HTML. Retificações isoladas não substituem uma norma inteira. O projeto não infere vigência nem eficácia a partir da versão disponível.

Os textos têm caráter informativo. Consulte a fonte e a publicação no Diário Oficial antes de citar ou aplicar uma norma.

## Fontes e proveniência

A descoberta federal usa a [API de Dados Abertos do Senado](https://legis.senado.leg.br/dadosabertos/api-docs/swagger-ui/index.html), particionada por tipo e ano. Os metadados do [Portal das Normas Jurídicas Brasileiras](https://normas.leg.br/) fornecem os arquivos de texto e suas versões. O acesso aos arquivos segue o caminho público usado pelo próprio portal. Os três documentos iniciais vieram diretamente da [Legislação Informatizada da Câmara](https://www2.camara.leg.br/atividade-legislativa/legislacao).

- `federal/`: texto convertido, com cabeçalho YAML.
- `estaduais/MG/`: normas mineiras convertidas de fontes da ALMG.
- `fontes/`: HTML comprimido, metadados JSON e respostas JSON originais do Senado e da ALMG.
- `catalogos/almg/`: inventários anuais e CSVs oficiais comprimidos de Minas Gerais.
- `catalogos/alesp/`: páginas do inventário paulista e respostas JSON originais comprimidas.
- `catalogos/bahia/`: pesquisas por categoria, páginas HTML originais comprimidas e totais declarados.
- `catalogos/pmsp/`: inventários anuais das leis municipais de São Paulo e páginas HTML originais das pesquisas.
- `municipais/3550308/`: leis do município de São Paulo, identificado pelo código IBGE.
- `falhas-catalogos/`: anos/famílias federais cuja descoberta falhou; não são catálogos vazios.
- `catalogos/senado/<tipo>/<ano>.json`: inventário identificado e pendências de identidade.
- `catalogos/senado/<tipo>/<ano>.fonte.json.gz`: resposta original do catálogo oficial, inclusive quando vazio.
- `falhas/`: erros individuais; uma coleta posterior bem-sucedida remove o erro correspondente.
- `scripts/`: descoberta, coleta, conversão, auditoria e relatório.

`sha256_fonte` identifica os bytes HTML descomprimidos; `sha256_dados` identifica a resposta JSON de metadados descomprimida, quando presente; `sha256_markdown` identifica o corpo convertido, sem o cabeçalho YAML e o título acrescentados pelo coletor. A URN identifica a norma por autoridade, tipo, data e número, incluindo complemento quando existir. Datas dos commits representam coleta ou manutenção.

A conversão preserva links absolutos, tabelas, notas e tachados, inclusive tachados declarados em estilos inline. Não remove redações históricas. Imagens e anexos vinculados continuam como referências; o coletor não baixa esses recursos nem executa OCR. O HTML original permite conferir a transformação. Tamanho mínimo e presença do artigo inicial detectam algumas falhas; os três documentos iniciais também exigem dispositivos finais específicos. Isso não equivale a uma revisão jurídica integral.

A coleta mineira usa o CSV anual e os documentos da [API de Dados Abertos da ALMG](https://dadosabertos.almg.gov.br/). Prefere o link de texto atualizado quando o catálogo o fornece e, caso contrário, usa a publicação original. O JSON recebido é preservado e a auditoria verifica a identidade do documento e a extração do HTML.

A coleta paulista usa a API pública consumida pelo [portal de legislação da Alesp](https://www.al.sp.gov.br/legislacao/). Preserva cada página com o total informado, confere a identidade nos detalhes da norma e baixa o link de íntegra atualizado ou original fornecido pelo portal. O identificador do arquivo é o ID oficial imutável da Alesp, sob a autoridade `br-sp`.

A coleta municipal de São Paulo usa o [Catálogo de Legislação Municipal](https://legislacao.prefeitura.sp.gov.br/), com consultas por ano de publicação e tipo LEI. Cada página e o total de resultados são preservados; buscas que atinjam o limite de 10.000 resultados são recusadas para evitar publicar um inventário truncado. O Markdown contém a íntegra compilada, sem menus ou controles do portal. Sua identidade usa município, tipo, data e número.

A coleta baiana usa o [Portal de Legislação da Casa Civil](https://www.legislabahia.ba.gov.br/documentos), por categorias oficiais de leis ordinárias, complementares, delegadas, emendas e constituições históricas. Segue os links de próxima página, valida intervalo e total e preserva cada resposta. `--pages` limita novas consultas de páginas por execução (100 por padrão), sem contar páginas em cache; atingir esse limite preserva a descoberta parcial para retomada e não indica esgotamento. A identidade `br-ba-norma-<node ID>` vem do shortlink Drupal, conferido no documento; título, data e endereço também são verificados. A conversão isola a íntegra, mantendo tabelas, notas e redações históricas. Falhas anteriores à resolução da identidade ficam na fila sob um hash do endereço.

## Skills jurídicas

Os guias em `skills/` orientam agentes e pessoas a pesquisar e analisar normas com fontes verificáveis:

- [Pesquisa legislativa](skills/pesquisa-legislativa/SKILL.md): localizar normas, conferir proveniência e registrar lacunas.
- [Vigência e aplicação](skills/vigencia-e-aplicacao/SKILL.md): identificar a redação pertinente ao tempo e ao território dos fatos.
- [Interpretação jurídica](skills/interpretacao-juridica/SKILL.md): examinar requisitos, exceções, teses e aplicação aos fatos.

Para usar manualmente, abra o guia e siga o procedimento com os arquivos do acervo. Para um agente, mantenha o clone acessível e peça que leia o `SKILL.md` escolhido antes da análise. Em ferramentas compatíveis com esse formato, copie a pasta inteira da skill para o diretório de skills da ferramenta; a descoberta e a ativação dependem dela. Os guias não instalam ferramentas, não atualizam o acervo e não conferem acesso à internet.

Exemplo de pedido ao agente:

```text
Leia skills/pesquisa-legislativa/SKILL.md e skills/interpretacao-juridica/SKILL.md.
Pesquise no Código Civil a diferença entre personalidade e capacidade.
Confira a fonte oficial, cite os dispositivos e separe texto legal de interpretação.
Declare se não conseguir confirmar a redação atual.
```

As skills são roteiros de pesquisa, sujeitos a revisão; não certificam vigência nem substituem a análise profissional de um caso.

## Reproduzir e ampliar

Requer [Bun](https://bun.sh), na versão registrada no CI.

```sh
bun install --frozen-lockfile
bun run check

# atualizar os três documentos iniciais da Câmara
bun run collect

# descobrir leis ordinárias federais por ano
bun run discover --from 1822 --to 2026 --type LEI

# descobrir todas as famílias federais suportadas
bun run discover --from 1822 --to 2026 --all

# coletar os textos dos catálogos locais, retomando arquivos íntegros
bun run collect:senado

# descobrir o catálogo anual mineiro sem baixar os textos
bun run collect:almg --from 2026 --to 2026 --discover-only

# coletar um lote mineiro, retomando arquivos íntegros
bun run collect:almg --from 2026 --to 2026 --limit 100

# descobrir todas as páginas do catálogo paulista
bun run collect:alesp --discover-only

# coletar um lote paulista
bun run collect:alesp --limit 100

# descobrir leis municipais paulistanas por ano de publicação
bun run collect:pmsp --from 1800 --to 2026 --discover-only

# coletar um lote municipal paulistano
bun run collect:pmsp --from 2026 --to 2026 --limit 100

# descobrir as categorias baianas suportadas, incluindo constituições históricas
bun run collect:bahia --discover-only

# coletar um lote baiano; --categories restringe categorias oficiais
bun run collect:bahia --limit 100

# auditar todos os arquivos publicados e regenerar as contagens
bun run audit
bun run coverage
```

Famílias aceitas: `LEI`, `LCP`, `LDL`, `DEL`, `EMC`, `DEC`, `MPV`. Execute a descoberta para cada família desejada. Intervalos ausentes do relatório ainda não foram consultados. A API do Senado não fornece, nessa operação, paginação ou um total independente para certificar a completude da resposta.

A descoberta reutiliza catálogos locais. Para atualizar um ano já consultado, use `bun run discover --from 2026 --to 2026 --type LEI --refresh`. A coleta pode ser limitada com `bun run collect:senado --limit 100`; use `--refresh` para consultar novamente textos já íntegros. Respostas idênticas preservam os arquivos e a data anterior. Mudanças devem ser revisadas no diff antes de novo commit.

As requisições são sequenciais, com intervalo e timeout. Na descoberta federal, falhas são registradas por família/ano, os demais anos continuam e o comando termina com código diferente de zero se houver falhas. Os catálogos concluídos são preservados para retomada. Na ALMG, falhas anuais são registradas e os demais anos continuam. Na Bahia, falhas interrompem a paginação da categoria afetada, preservam as páginas concluídas e permitem continuar as demais categorias. Na coleta dos textos, uma falha é registrada por norma e as demais continuam; o processo termina com código diferente de zero se houver falhas. Arquivos incompletos ou com hashes divergentes são recolhidos na próxima execução. Uma interrupção pode deixar arquivos parciais: confira a auditoria antes de publicar.

Os testes usam fontes reais preservadas, sem acesso à rede, e cobrem identidade, versões, rejeição de páginas inválidas e conversão. `bun run audit` verifica os hashes e reproduz a conversão de todas as normas disponíveis no checkout. O CI executa ambos. O relatório mede o material presente, sem equiparar reprodução e hash a completude nacional.

## Coleta contínua e limites de cobertura

O workflow [Ampliar acervo oficial](.github/workflows/coletar.yml) executa a descoberta e lotes de até 1.000 novas tentativas por fonte a cada seis horas, seguidos de até 100 retentativas por fonte. Também pode ser iniciado pela aba Actions, com limite ajustável. Uma única execução roda por vez. A descoberta renova as páginas da Alesp e os catálogos do ano corrente do Senado, da ALMG e da PMSP, para que novos atos não fiquem presos aos inventários em cache. Na Bahia, a descoberta avança por até 100 páginas novas a cada rodada, retomando as páginas preservadas; a atualização de categorias já consultadas usa `--refresh --pages 1000000` para percorrer a categoria inteira. Catálogos históricos já consultados são reutilizados; alterações retroativas nesses catálogos exigem uma execução com `--refresh`. Ela coleta os arquivos ausentes, valida o acervo e publica o lote na `main`; se a auditoria falhar, não publica. O CI verde certifica os checks executados, não que todas as leis estejam presentes.

O modo `--skip-failures`, usado na automação, permite avançar pelos registros ainda não tentados sem que os mesmos documentos indisponíveis ocupem todos os lotes. A automação também reavalia até 100 falhas por fonte, priorizando a data de tentativa mais antiga para que erros persistentes não monopolizem a fila. Para reavaliar apenas falhas manualmente, execute o coletor com `--only-failures --limit 100`. As opções `--only-failures` e `--skip-failures` são mutuamente exclusivas. Os erros continuam em `falhas/` até uma tentativa bem-sucedida. Pendências do inventário (por exemplo, norma sem link para texto) permanecem no catálogo oficial preservado e no relatório. Duplicações equivalentes da ALMG são contadas uma vez como norma e mantidas como linhas pendentes; identidades conflitantes interrompem a descoberta para revisão.

O objetivo abrange a legislação federal, dos 26 estados, do Distrito Federal e dos municípios, inclusive normas históricas e revogadas. A presença de um catálogo não equivale à presença dos textos. As fontes integradas até aqui são Senado/Câmara, ALMG, Alesp, Casa Civil da Bahia e o catálogo municipal da Prefeitura de São Paulo; os demais entes ainda precisam de coletores e validação. O acesso SRU do LexML retornou uma verificação de segurança na consulta realizada, sem inventário utilizável.

Os coletores atuais convertem HTML. Fontes que oferecem somente PDF, imagens ou documentos sem texto continuam como lacunas; não são convertidas em sucesso nem em transcrição presumida. Os anexos vinculados também precisam de coleta própria para que uma norma possa ser considerada integral com anexos. O relato de cobertura deve manter essas distinções.

## Contribuir

Envie uma issue com a norma e a URL oficial ou um PR com o coletor, a fonte preservada e o Markdown. Novas fontes precisam de validação própria, limites de requisição e evidência de reprodução. Não substitua um texto atualizado por publicação original sob a mesma identidade. O gravador recusa essa substituição antes de alterar os arquivos existentes. A expansão inclui as demais famílias federais e fontes estaduais, distritais e municipais, com contagens verificáveis por fonte.

Agradecemos ao pessoal da **Supersonic Labs** pela inspiração para tornar a legislação brasileira mais acessível em Markdown. A referência encontrada durante a pesquisa foi [ctresb/leis](https://github.com/ctresb/leis). Este projeto é uma iniciativa independente do Minutei, com coleta própria de fontes oficiais; não usamos o acervo nem os scripts daquele repositório.

## Licenças e créditos

Código, documentação e skills produzidos pelo Minutei usam a [licença MIT](LICENSE). Os textos oficiais permanecem sujeitos ao regime próprio dos atos oficiais; a licença do código não atribui ao Minutei autoria sobre as normas.

Os dados e arquivos obtidos do Portal das Normas Jurídicas Brasileiras são atribuídos ao Senado Federal, à Câmara dos Deputados e ao Congresso Nacional, conforme os metadados de cada fonte. Preserve também a licença indicada em `licenca_fonte` — nas respostas já coletadas, [Creative Commons Atribuição 4.0](https://creativecommons.org/licenses/by/4.0/) — e a origem dos textos ao redistribuir. A conversão para Markdown e o cabeçalho de proveniência são alterações feitas pelo Minutei. Os metadados originais permanecem preservados em `fontes/`.
