---
name: pesquisa-legislativa
description: Pesquisa normas brasileiras com identificação e proveniência verificáveis. Use quando precisar localizar leis, consultar este acervo ou reunir dispositivos para uma questão jurídica.
---

# Pesquisa legislativa

## Procedimento

1. Delimite a questão, os fatos relevantes, o território e a data de referência. Peça apenas dados ausentes que mudem a pesquisa; registre hipóteses quando continuar sem eles.
2. Leia `COBERTURA.md` na raiz deste acervo antes de interpretar uma ausência. O catálogo mede o que foi recebido; o repositório não contém toda a legislação brasileira.
3. Busque por número, ano, assunto e sinônimos. Leia o dispositivo completo, com caput, parágrafos, incisos, definições, remissões e exceções. Uma ocorrência textual é uma pista, não uma conclusão.
4. Confira no cabeçalho `id`, `fonte`, `versao` e `coletado_em`. `data` identifica a norma; não prova publicação ou início de vigência. URN e hashes ajudam a identificar e reproduzir o arquivo, não certificam sua aplicabilidade.
5. Abra a fonte oficial e confira a redação pertinente à data dos fatos. Se a rede estiver indisponível, declare que a pesquisa está limitada ao snapshot local e não certifique atualização.
6. Pesquise normas modificadoras, regulamentação e decisões relevantes em portais oficiais. Não invente artigos, processos ou trechos. Diferencie texto legal, interpretação e jurisprudência.
7. Registre resultados contrários à hipótese inicial e as lacunas que impedem uma conclusão. Ausência no acervo não demonstra inexistência de norma.

## Busca local

Execute na raiz do clone:

```sh
rg -n -i 'personalidade|capacidade' federal estaduais
rg --files federal estaduais | rg '2002-01-10-10406'
sed -n '1,35p' federal/br-federal-lei-2002-01-10-10406.md
```

As buscas também encontram cabeçalhos, notas e redações históricas tachadas. Abra o contexto antes de usar um resultado. Se uma pasta ainda não existir no checkout, consulte apenas as disponíveis.

## Entrega

Apresente a questão e a data de referência; depois, para cada norma, informe autoridade, tipo, número/ano, dispositivo, versão consultada, caminho local e URL oficial. Separe o achado da conclusão e identifique o que ainda precisa ser verificado. Cite apenas trechos que tenha efetivamente lido.

## Exemplo

Pedido: “Encontre a regra de início da personalidade civil.”

Pesquise o Código Civil, leia o art. 2º e as disposições relacionadas e confira a fonte. Não transforme a regra sobre personalidade em conclusão automática sobre capacidade ou legitimidade processual.
