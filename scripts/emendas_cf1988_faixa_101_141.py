"""Emendas CF/1988 ausentes na faixa 101–141 (lote issue #63).

Recupera o texto autônomo oficial no Planalto para os números
102,107,109,111–118,120–141. Reutiliza o conversor HTML→Markdown de
`nucleo_licitacoes` sem alterá-lo. Provas e matriz ficam somente em
`provas/emendas-cf1988/faixa-101-141/`. README agregado e matriz global
ficam com o orquestrador. Não republica 103/2019 nem outros já presentes.

Subcomandos:
  fetch DIR   captura as fontes oficiais e grava DIR/fetch.json
  ingest DIR  grava snapshots + fontes.json a partir da captura
  build       reconverte snapshots → Markdown, manifesto, matriz e provas
  verify      confere offline Markdown, hashes e cobertura fonte→Markdown
"""
from __future__ import annotations

import argparse
import datetime
import json
import lzma
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import nucleo_licitacoes as nl  # noqa: E402

LOTE = 'emendas-cf1988-faixa-101-141'
PROVAS = ROOT / 'provas/emendas-cf1988/faixa-101-141'
FONTES_DIR = PROVAS / 'fontes'
MANIFESTO = PROVAS / 'manifesto.json'
MATRIZ = PROVAS / 'matriz.json'
FONTES_JSON = PROVAS / 'fontes.json'
UNKNOWN = nl.UNKNOWN
PLANALTO = nl.PLANALTO
USER_AGENT = nl.USER_AGENT
CONTRACT_VERSION = nl.CONTRACT_VERSION

# Números deste lote (faixa 101–141, ausentes no main remoto; exclui 103/101/104–106/108/110/119).
LOTE_NUMEROS = [102, 107, 109, 111, 112, 113, 114, 115, 116, 117, 118, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141]

SOURCES = {
    'planalto-emc102': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc102.htm',
        file='planalto-emc102.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc107': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc107.htm',
        file='planalto-emc107.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc109': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc109.htm',
        file='planalto-emc109.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc111': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc111.htm',
        file='planalto-emc111.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc112': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc112.htm',
        file='planalto-emc112.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc113': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc113.htm',
        file='planalto-emc113.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc114': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc114.htm',
        file='planalto-emc114.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc115': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc115.htm',
        file='planalto-emc115.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc116': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc116.htm',
        file='planalto-emc116.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc117': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc117.htm',
        file='planalto-emc117.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc118': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc118.htm',
        file='planalto-emc118.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc120': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc120.htm',
        file='planalto-emc120.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc121': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc121.htm',
        file='planalto-emc121.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc122': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc122.htm',
        file='planalto-emc122.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc123': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc123.htm',
        file='planalto-emc123.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc124': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc124.htm',
        file='planalto-emc124.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc125': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc125.htm',
        file='planalto-emc125.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc126': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc126.htm',
        file='planalto-emc126.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc127': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc127.htm',
        file='planalto-emc127.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc128': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc128.htm',
        file='planalto-emc128.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc129': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc129.htm',
        file='planalto-emc129.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc130': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc130.htm',
        file='planalto-emc130.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc131': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc131.htm',
        file='planalto-emc131.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc132': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc132.htm',
        file='planalto-emc132.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc133': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc133.htm',
        file='planalto-emc133.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc134': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc134.htm',
        file='planalto-emc134.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc135': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc135.htm',
        file='planalto-emc135.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc136': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc136.htm',
        file='planalto-emc136.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc137': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc137.htm',
        file='planalto-emc137.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc138': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc138.htm',
        file='planalto-emc138.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc139': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc139.htm',
        file='planalto-emc139.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc140': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc140.htm',
        file='planalto-emc140.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc141': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc141.htm',
        file='planalto-emc141.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
}

DOCS = [
    dict(
        slug='br-federal-emenda-constitucional-2019-09-26-102',
        arquivo='federal/br-federal-emenda-constitucional-2019-09-26-102.md',
        fonte='planalto-emc102',
        numero=102,
        urn='urn:lex:br:federal:emenda.constitucional:2019-09-26;102',
        camara_catalogo_url='https://www2.camara.leg.br/legin/fed/emecon/2019/emendaconstitucional-102-26-setembro-2019-789165-publicacaooriginal-159100-pl.html',
        norma=dict(
            tipo='emenda-constitucional', numero='102', data='2019-09-26',
            titulo='EMENDA CONSTITUCIONAL Nº 102, DE 26 DE SETEMBRO DE 2019',
            ementa='Dá nova redação ao art. 20 da Constituição Federal e altera o art. 165 da Constituição Federal e o art. 107 do Ato das Disposições Constitucionais Transitórias.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2020-07-02-107',
        arquivo='federal/br-federal-emenda-constitucional-2020-07-02-107.md',
        fonte='planalto-emc107',
        numero=107,
        urn='urn:lex:br:federal:emenda.constitucional:2020-07-02;107',
        camara_catalogo_url='https://www2.camara.leg.br/legin/fed/emecon/2020/emendaconstitucional-107-3-julho-2020-790377-publicacaooriginal-160989-pl.html',
        norma=dict(
            tipo='emenda-constitucional', numero='107', data='2020-07-02',
            titulo='EMENDA CONSTITUCIONAL Nº 107, DE 2 DE JULHO DE 2020',
            ementa='Adia, em razão da pandemia da Covid-19, as eleições municipais de outubro de 2020 e os prazos eleitorais respectivos'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2021-03-15-109',
        arquivo='federal/br-federal-emenda-constitucional-2021-03-15-109.md',
        fonte='planalto-emc109',
        numero=109,
        urn='urn:lex:br:federal:emenda.constitucional:2021-03-15;109',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='109', data='2021-03-15',
            titulo='EMENDA CONSTITUCIONAL Nº 109, DE 15 DE MARÇO DE 2021',
            ementa='Altera os arts. 29-A, 37, 49, 84, 163, 165, 167, 168 e 169 da Constituição Federal e os arts. 101 e 109 do Ato das Disposições Constitucionais Transitórias; acrescenta à Constituição Federal os arts. 164-A, 167-A, 167-B, 167-C, 167-D, 167-E, 167-F e 167-G; revoga dispositivos do Ato das Disposições Constitucionais Transitórias e institui regras transitórias sobre redução de benefícios tributários; desvincula parcialmente o superávit financeiro de fundos públicos; e suspende condicionalidades para realização de despesas com concessão de auxílio emergencial residual para enfrentar as consequências sociais e econômicas da pandemia da Covid-19.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2021-09-28-111',
        arquivo='federal/br-federal-emenda-constitucional-2021-09-28-111.md',
        fonte='planalto-emc111',
        numero=111,
        urn='urn:lex:br:federal:emenda.constitucional:2021-09-28;111',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='111', data='2021-09-28',
            titulo='EMENDA CONSTITUCIONAL Nº 111, DE 28 DE SETEMBRO DE 2021',
            ementa='Altera a Constituição Federal para disciplinar a realização de consultas populares concomitantes às eleições municipais, dispor sobre o instituto da fidelidade partidária, alterar a data de posse de Governadores e do Presidente da República e estabelecer regras transitórias para distribuição entre os partidos políticos dos recursos do fundo partidário e do Fundo Especial de Financiamento de Campanha (FEFC) e para o funcionamento dos partidos políticos.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2021-10-27-112',
        arquivo='federal/br-federal-emenda-constitucional-2021-10-27-112.md',
        fonte='planalto-emc112',
        numero=112,
        urn='urn:lex:br:federal:emenda.constitucional:2021-10-27;112',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='112', data='2021-10-27',
            titulo='EMENDA CONSTITUCIONAL Nº 112, DE 27 DE OUTUBRO DE 2021',
            ementa='Altera o art. 159 da Constituição Federal para disciplinar a distribuição de recursos pela União ao Fundo de Participação dos Municípios.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2021-12-08-113',
        arquivo='federal/br-federal-emenda-constitucional-2021-12-08-113.md',
        fonte='planalto-emc113',
        numero=113,
        urn='urn:lex:br:federal:emenda.constitucional:2021-12-08;113',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='113', data='2021-12-08',
            titulo='EMENDA CONSTITUCIONAL Nº 113, DE 8 DE DEZEMBRO DE 2021',
            ementa='Altera a Constituição Federal e o Ato das Disposições Constitucionais Transitórias para estabelecer o novo regime de pagamentos de precatórios, modificar normas relativas ao Novo Regime Fiscal e autorizar o parcelamento de débitos previdenciários dos Municípios; e dá outras providências.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2021-12-16-114',
        arquivo='federal/br-federal-emenda-constitucional-2021-12-16-114.md',
        fonte='planalto-emc114',
        numero=114,
        urn='urn:lex:br:federal:emenda.constitucional:2021-12-16;114',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='114', data='2021-12-16',
            titulo='EMENDA CONSTITUCIONAL Nº 114, DE 16 DE DEZEMBRO DE 2021',
            ementa='Altera a Constituição Federal e o Ato das Disposições Constitucionais Transitórias para estabelecer o novo regime de pagamentos de precatórios, modificar normas relativas ao Novo Regime Fiscal e autorizar o parcelamento de débitos previdenciários dos Municípios; e dá outras providências.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2022-02-10-115',
        arquivo='federal/br-federal-emenda-constitucional-2022-02-10-115.md',
        fonte='planalto-emc115',
        numero=115,
        urn='urn:lex:br:federal:emenda.constitucional:2022-02-10;115',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='115', data='2022-02-10',
            titulo='EMENDA CONSTITUCIONAL Nº 115, DE 10 DE FEVEREIRO DE 2022',
            ementa='Altera a Constituição Federal para incluir a proteção de dados pessoais entre os direitos e garantias fundamentais e para fixar a competência privativa da União para legislar sobre proteção e tratamento de dados pessoais.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2022-02-17-116',
        arquivo='federal/br-federal-emenda-constitucional-2022-02-17-116.md',
        fonte='planalto-emc116',
        numero=116,
        urn='urn:lex:br:federal:emenda.constitucional:2022-02-17;116',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='116', data='2022-02-17',
            titulo='EMENDA CONSTITUCIONAL Nº 116, DE 17 DE FEVEREIRO DE 2022',
            ementa='Acrescenta § 1º-A ao art. 156 da Constituição Federal para prever a não incidência sobre templos de qualquer culto do Imposto sobre a Propriedade Predial e Territorial Urbana (IPTU), ainda que as entidades abrangidas pela imunidade tributária sejam apenas locatárias do bem imóvel.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2022-04-05-117',
        arquivo='federal/br-federal-emenda-constitucional-2022-04-05-117.md',
        fonte='planalto-emc117',
        numero=117,
        urn='urn:lex:br:federal:emenda.constitucional:2022-04-05;117',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='117', data='2022-04-05',
            titulo='EMENDA CONSTITUCIONAL Nº 117, DE 5 DE ABRIL DE 2022',
            ementa='Altera o art. 17 da Constituição Federal para impor aos partidos políticos a aplicação de recursos do fundo partidário na promoção e difusão da participação política das mulheres, bem como a aplicação de recursos desse fundo e do Fundo Especial de Financiamento de Campanha e a divisão do tempo de propaganda gratuita no rádio e na televisão no percentual mínimo de 30% (trinta por cento) para candidaturas femininas.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2022-04-26-118',
        arquivo='federal/br-federal-emenda-constitucional-2022-04-26-118.md',
        fonte='planalto-emc118',
        numero=118,
        urn='urn:lex:br:federal:emenda.constitucional:2022-04-26;118',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='118', data='2022-04-26',
            titulo='EMENDA CONSTITUCIONAL Nº 118, DE 26 DE ABRIL DE 2022',
            ementa='Dá nova redação às alíneas "b" e "c" do inciso XXIII do caput do art. 21 da Constituição Federal, para autorizar a produção, a comercialização e a utilização de radioisótopos para pesquisa e uso médicos.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2022-05-05-120',
        arquivo='federal/br-federal-emenda-constitucional-2022-05-05-120.md',
        fonte='planalto-emc120',
        numero=120,
        urn='urn:lex:br:federal:emenda.constitucional:2022-05-05;120',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='120', data='2022-05-05',
            titulo='EMENDA CONSTITUCIONAL Nº 120, DE 5 DE MAIO DE 2022',
            ementa='Acrescenta §§ 7º, 8º, 9º, 10 e 11 ao art. 198 da Constituição Federal, para dispor sobre a responsabilidade financeira da União, corresponsável pelo Sistema Único de Saúde (SUS), na política remuneratória e na valorização dos profissionais que exercem atividades de agente comunitário de saúde e de agente de combate às endemias.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2022-05-10-121',
        arquivo='federal/br-federal-emenda-constitucional-2022-05-10-121.md',
        fonte='planalto-emc121',
        numero=121,
        urn='urn:lex:br:federal:emenda.constitucional:2022-05-10;121',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='121', data='2022-05-10',
            titulo='EMENDA CONSTITUCIONAL Nº 121, DE 10 DE MAIO DE 2022',
            ementa='Altera o inciso IV do § 2º do art. 4º da Emenda Constitucional nº 109, de 15 de março de 2021.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2022-05-17-122',
        arquivo='federal/br-federal-emenda-constitucional-2022-05-17-122.md',
        fonte='planalto-emc122',
        numero=122,
        urn='urn:lex:br:federal:emenda.constitucional:2022-05-17;122',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='122', data='2022-05-17',
            titulo='EMENDA CONSTITUCIONAL Nº 122, DE 17 DE MAIO DE 2022',
            ementa='Altera a Constituição Federal para elevar para setenta anos a idade máxima para a escolha e nomeação de membros do Supremo Tribunal Federal, do Superior Tribunal de Justiça, dos Tribunais Regionais Federais, do Tribunal Superior do Trabalho, dos Tribunais Regionais do Trabalho, do Tribunal de Contas da União e dos Ministros civis do Superior Tribunal Militar.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2022-07-14-123',
        arquivo='federal/br-federal-emenda-constitucional-2022-07-14-123.md',
        fonte='planalto-emc123',
        numero=123,
        urn='urn:lex:br:federal:emenda.constitucional:2022-07-14;123',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='123', data='2022-07-14',
            titulo='EMENDA CONSTITUCIONAL Nº 123, DE 14 DE JULHO DE 2022',
            ementa='Altera o art. 225 da Constituição Federal para estabelecer diferencial de competitividade para os biocombustíveis; inclui o art. 120 no Ato das Disposições Constitucionais Transitórias para reconhecer o estado de emergência decorrente da elevação extraordinária e imprevisível dos preços do petróleo, combustíveis e seus derivados e dos impactos sociais dela decorrentes; autoriza a União a entregar auxílio financeiro aos Estados e ao Distrito Federal que outorgarem créditos tributários do Imposto sobre Operações relativas à Circulação de Mercadorias e sobre Prestações de Serviços de Transporte Interestadual e Intermunicipal e de Comunicação (ICMS) aos produtores e distribuidores de etanol hidratado; expande o auxílio Gás dos Brasileiros, de que trata a Lei nº 14.237, de 19 de novembro de 2021; institui auxílio para caminhoneiros autônomos; expande o Programa Auxílio Brasil, de que trata a Lei nº 14.284, de 29 de dezembro de 2021; e institui auxílio para entes da Federação financiarem a gratuidade do transporte público.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2022-07-14-124',
        arquivo='federal/br-federal-emenda-constitucional-2022-07-14-124.md',
        fonte='planalto-emc124',
        numero=124,
        urn='urn:lex:br:federal:emenda.constitucional:2022-07-14;124',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='124', data='2022-07-14',
            titulo='EMENDA CONSTITUCIONAL Nº 124, DE 14 DE JULHO DE 2022',
            ementa='Institui o piso salarial nacional do enfermeiro, do técnico de enfermagem, do auxiliar de enfermagem e da parteira.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2022-07-14-125',
        arquivo='federal/br-federal-emenda-constitucional-2022-07-14-125.md',
        fonte='planalto-emc125',
        numero=125,
        urn='urn:lex:br:federal:emenda.constitucional:2022-07-14;125',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='125', data='2022-07-14',
            titulo='EMENDA CONSTITUCIONAL Nº 125, DE 14 DE JULHO DE 2022',
            ementa='Altera o art. 105 da Constituição Federal para instituir no recurso especial o requisito da relevância das questões de direito federal infraconstitucional.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2022-12-21-126',
        arquivo='federal/br-federal-emenda-constitucional-2022-12-21-126.md',
        fonte='planalto-emc126',
        numero=126,
        urn='urn:lex:br:federal:emenda.constitucional:2022-12-21;126',
        camara_catalogo_url='https://www2.camara.leg.br/legin/fed/emecon/2022/emendaconstitucional-126-21-dezembro-2022-793528-publicacaooriginal-166603-pl.html',
        norma=dict(
            tipo='emenda-constitucional', numero='126', data='2022-12-21',
            titulo='EMENDA CONSTITUCIONAL Nº 126, DE 21 DE DEZEMBRO DE 2022',
            ementa='Altera a Constituição Federal, para dispor sobre as emendas individuais ao projeto de lei orçamentária, e o Ato das Disposições Constitucionais Transitórias para excluir despesas dos limites previstos no art. 107; define regras para a transição da Presidência da República aplicáveis à Lei Orçamentária de 2023; e dá outras providências.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2022-12-22-127',
        arquivo='federal/br-federal-emenda-constitucional-2022-12-22-127.md',
        fonte='planalto-emc127',
        numero=127,
        urn='urn:lex:br:federal:emenda.constitucional:2022-12-22;127',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='127', data='2022-12-22',
            titulo='EMENDA CONSTITUCIONAL Nº 127, DE 22 DE DEZEMBRO DE 2022',
            ementa='Altera a Constituição Federal e o Ato das Disposições Constitucionais Transitórias para estabelecer que compete à União prestar assistência financeira complementar aos Estados, ao Distrito Federal e aos Municípios e às entidades filantrópicas, para o cumprimento dos pisos salariais profissionais nacionais para o enfermeiro, o técnico de enfermagem, o auxiliar de enfermagem e a parteira; altera a Emenda Constitucional nº 109, de 15 de março de 2021, para estabelecer o superávit financeiro dos fundos públicos do Poder Executivo como fonte de recursos para o cumprimento dos pisos salariais profissionais nacionais para o enfermeiro, o técnico de enfermagem, o auxiliar de enfermagem e a parteira; e dá outras providências.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2022-12-22-128',
        arquivo='federal/br-federal-emenda-constitucional-2022-12-22-128.md',
        fonte='planalto-emc128',
        numero=128,
        urn='urn:lex:br:federal:emenda.constitucional:2022-12-22;128',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='128', data='2022-12-22',
            titulo='EMENDA CONSTITUCIONAL Nº 128, DE 22 DE DEZEMBRO DE 2022',
            ementa='Acrescenta § 7º ao art. 167 da Constituição Federal, para proibir a imposição e a transferência, por lei, de qualquer encargo financeiro decorrente da prestação de serviço público para a União, os Estados, o Distrito Federal e os Municípios.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2023-07-05-129',
        arquivo='federal/br-federal-emenda-constitucional-2023-07-05-129.md',
        fonte='planalto-emc129',
        numero=129,
        urn='urn:lex:br:federal:emenda.constitucional:2023-07-05;129',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='129', data='2023-07-05',
            titulo='EMENDA CONSTITUCIONAL Nº 129, DE 5 DE JULHO DE 2023',
            ementa='Acrescenta o art. 123 ao Ato das Disposições Constitucionais Transitórias, para assegurar prazo de vigência adicional aos instrumentos de permissão lotérica.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2023-10-03-130',
        arquivo='federal/br-federal-emenda-constitucional-2023-10-03-130.md',
        fonte='planalto-emc130',
        numero=130,
        urn='urn:lex:br:federal:emenda.constitucional:2023-10-03;130',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='130', data='2023-10-03',
            titulo='EMENDA CONSTITUCIONAL Nº 130, DE 3 DE OUTUBRO DE 2023',
            ementa='Altera o art. 93 da Constituição Federal para permitir a permuta entre juízes de direito vinculados a diferentes tribunais.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2023-10-03-131',
        arquivo='federal/br-federal-emenda-constitucional-2023-10-03-131.md',
        fonte='planalto-emc131',
        numero=131,
        urn='urn:lex:br:federal:emenda.constitucional:2023-10-03;131',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='131', data='2023-10-03',
            titulo='EMENDA CONSTITUCIONAL Nº 131, DE 3 DE OUTUBRO DE 2023',
            ementa='Altera o art. 12 da Constituição Federal para suprimir a perda da nacionalidade brasileira em razão da mera aquisição de outra nacionalidade, incluir a exceção para situações de apatridia e acrescentar a possibilidade de a pessoa requerer a perda da própria nacionalidade.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2023-12-20-132',
        arquivo='federal/br-federal-emenda-constitucional-2023-12-20-132.md',
        fonte='planalto-emc132',
        numero=132,
        urn='urn:lex:br:federal:emenda.constitucional:2023-12-20;132',
        camara_catalogo_url='https://www2.camara.leg.br/legin/fed/emecon/2023/emendaconstitucional-132-20-dezembro-2023-795084-publicacaooriginal-170513-pl.html',
        norma=dict(
            tipo='emenda-constitucional', numero='132', data='2023-12-20',
            titulo='EMENDA CONSTITUCIONAL Nº 132, DE 20 DE DEZEMBRO DE 2023',
            ementa='Altera o Sistema Tributário Nacional.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2024-08-22-133',
        arquivo='federal/br-federal-emenda-constitucional-2024-08-22-133.md',
        fonte='planalto-emc133',
        numero=133,
        urn='urn:lex:br:federal:emenda.constitucional:2024-08-22;133',
        camara_catalogo_url='https://www2.camara.leg.br/legin/fed/emecon/2024/emendaconstitucional-133-22-agosto-2024-796112-publicacaooriginal-172800-pl.html',
        norma=dict(
            tipo='emenda-constitucional', numero='133', data='2024-08-22',
            titulo='EMENDA CONSTITUCIONAL Nº 133, DE 22 DE AGOSTO DE 2024',
            ementa='Impõe aos partidos políticos a obrigatoriedade da aplicação de recursos financeiros para candidaturas de pessoas pretas e pardas; estabelece parâmetros e condições para regularização e refinanciamento de débitos de partidos políticos; e reforça a imunidade tributária dos partidos políticos conforme prevista na Constituição Federal.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2024-09-24-134',
        arquivo='federal/br-federal-emenda-constitucional-2024-09-24-134.md',
        fonte='planalto-emc134',
        numero=134,
        urn='urn:lex:br:federal:emenda.constitucional:2024-09-24;134',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='134', data='2024-09-24',
            titulo='EMENDA CONSTITUCIONAL Nº 134, DE 24 DE SETEMBRO DE 2024',
            ementa='Altera o art. 96 da Constituição Federal, para dispor sobre a eleição dos órgãos diretivos de Tribunais de Justiça.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2024-12-20-135',
        arquivo='federal/br-federal-emenda-constitucional-2024-12-20-135.md',
        fonte='planalto-emc135',
        numero=135,
        urn='urn:lex:br:federal:emenda.constitucional:2024-12-20;135',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='135', data='2024-12-20',
            titulo='EMENDA CONSTITUCIONAL Nº 135, DE 20 DE DEZEMBRO DE 2024',
            ementa='Altera os arts. 37, 163, 165, 212-A e 239 da Constituição Federal e o Ato das Disposições Constitucionais Transitórias (ADC T).'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2025-09-09-136',
        arquivo='federal/br-federal-emenda-constitucional-2025-09-09-136.md',
        fonte='planalto-emc136',
        numero=136,
        urn='urn:lex:br:federal:emenda.constitucional:2025-09-09;136',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='136', data='2025-09-09',
            titulo='EMENDA CONSTITUCIONAL Nº 136, DE 9 DE SETEMBRO DE 2025',
            ementa='Altera a Constituição Federal, o Ato das Disposições Constitucionais Transitórias e a Emenda Constitucional nº 113, de 8 de dezembro de 2021, a fim de instituir limite para o pagamento de precatórios pelos Estados, pelo Distrito Federal e pelos Municípios e de estipular novo prazo de parcelamento especial de débitos dos Estados, dos Municípios e do Distrito Federal com seus regimes próprios de previdência social e dos Municípios com o Regime Geral de Previdência Social; e dá outras providências.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2025-12-09-137',
        arquivo='federal/br-federal-emenda-constitucional-2025-12-09-137.md',
        fonte='planalto-emc137',
        numero=137,
        urn='urn:lex:br:federal:emenda.constitucional:2025-12-09;137',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='137', data='2025-12-09',
            titulo='EMENDA CONSTITUCIONAL Nº 137, DE 9 DE DEZEMBRO DE 2025',
            ementa='Altera o art. 155 da Constituição Federal para conceder imunidade do Imposto sobre a Propriedade de Veículos Automotores (IPVA) aos veículos que especifica.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2025-12-19-138',
        arquivo='federal/br-federal-emenda-constitucional-2025-12-19-138.md',
        fonte='planalto-emc138',
        numero=138,
        urn='urn:lex:br:federal:emenda.constitucional:2025-12-19;138',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='138', data='2025-12-19',
            titulo='EMENDA CONSTITUCIONAL Nº 138, DE 19 DE DEZEMBRO DE 2025',
            ementa='Altera o art. 37 da Constituição Federal para permitir a acumulação remunerada de um cargo de professor com outro de qualquer natureza.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2026-05-05-139',
        arquivo='federal/br-federal-emenda-constitucional-2026-05-05-139.md',
        fonte='planalto-emc139',
        numero=139,
        urn='urn:lex:br:federal:emenda.constitucional:2026-05-05;139',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='139', data='2026-05-05',
            titulo='EMENDA CONSTITUCIONAL Nº 139, DE 5 DE MAIO DE 2026',
            ementa='Altera o § 1º do art. 31 e o art. 75 da Constituição Federal para estabelecer os Tribunais de Contas como órgãos permanentes e essenciais ao controle externo da administração pública.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2026-10-16-140',
        arquivo='federal/br-federal-emenda-constitucional-2026-10-16-140.md',
        fonte='planalto-emc140',
        numero=140,
        urn='urn:lex:br:federal:emenda.constitucional:2026-10-16;140',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='140', data='2026-10-16',
            titulo='EMENDA CONSTITUCIONAL Nº 140, DE 16 DE OUTUBRO DE 2026',
            ementa='Altera os arts. 40, 198 e 201 da Constituição Federal, para estabelecer o direito à aposentadoria diferenciada aos agentes comunitários de saúde e aos agentes de combate às endemias, bem como para determinar a regularização do vínculo funcional desses agentes; e dá outras providências.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2026-10-16-141',
        arquivo='federal/br-federal-emenda-constitucional-2026-10-16-141.md',
        fonte='planalto-emc141',
        numero=141,
        urn='urn:lex:br:federal:emenda.constitucional:2026-10-16;141',
        camara_catalogo_url='https://www2.camara.leg.br/legin/fed/emecon/2026/emendaconstitucional-141-16-outubro-2026-800062-publicacaooriginal-181622-pl.html',
        norma=dict(
            tipo='emenda-constitucional', numero='141', data='2026-10-16',
            titulo='EMENDA CONSTITUCIONAL Nº 141, DE 16 DE OUTUBRO DE 2026',
            ementa='Altera o art. 7º da Constituição Federal para reduzir a duração máxima semanal do trabalho e prever 2 (dois) dias de repouso semanal remunerado, sem qualquer redução salarial.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
]



def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def snapshot_path(key: str) -> Path:
    return FONTES_DIR / (SOURCES[key]['file'] + '.xz')


def read_snapshot(key: str) -> bytes:
    return lzma.decompress(snapshot_path(key).read_bytes())


def write_snapshot(key: str, data: bytes) -> None:
    path = snapshot_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(lzma.compress(data, preset=9 | lzma.PRESET_EXTREME))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + '\n', encoding='utf-8')


def dou_aviso_from_html(data: bytes, charset: str) -> str | None:
    """Extrai o aviso DOU/republicação do rodapé do Planalto (EMC usa 'DOU D.M.AAAA')."""
    text = nl.decode(data, charset)
    m = re.search(r'Este texto não substitui.{0,500}?(?:</(?:p|font|small)>|$)', text, flags=re.I | re.S)
    if not m:
        return None
    plain = re.sub(r'<[^>]+>', ' ', m.group(0))
    plain = re.sub(r'\s+', ' ', plain).strip()
    plain = plain.replace('\xa0', ' ')
    # Formas observadas: "DOU 20.12.2006", "DOU de 20.12.2006", "republicado em 03.03.2015".
    m2 = re.search(
        r'Este texto não substitui o publicado no DOU(?:\s+de)?\s+(\d{1,2}\.\d{1,2}\.\d{4})'
        r'(?:\s+republicado em\s+(\d{1,2}\.\d{1,2}\.\d{4}))?',
        plain, flags=re.I)
    if not m2:
        return plain or None
    aviso = f'Este texto não substitui o publicado no DOU de {m2.group(1)}'
    if m2.group(2):
        aviso += f' e republicado em {m2.group(2)}'
    return aviso


def fetch(dest: Path) -> dict:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    records = {}
    for key, spec in SOURCES.items():
        target = dest / spec['file']
        header_file = dest / (spec['file'] + '.headers')
        captured = now_utc()
        proc = subprocess.run([
            'curl', '--silent', '--show-error', '--location', '--http1.1',
            '--proto', '=https', '--proto-redir', '=https',
            '--connect-timeout', '30', '--max-time', '180',
            '--max-filesize', str(64 * 1024 * 1024),
            '--user-agent', USER_AGENT, '--dump-header', str(header_file),
            '--write-out', '%{http_code} %{url_effective}',
            '--output', str(target), spec['url'],
        ], capture_output=True, text=True)
        record = dict(url=spec['url'], capturado_em=captured, curl_exit=proc.returncode, user_agent=USER_AGENT)
        if proc.returncode == 0:
            status, _, effective = proc.stdout.partition(' ')
            record.update(http_status=int(status), url_final=effective)
            data = target.read_bytes()
            record.update(bytes=len(data), sha256=nl.sha256(data), sha256_conteudo=nl.content_sha256(data))
            raw_headers = header_file.read_bytes().decode('latin-1').replace('\r\n', '\n')
            final_block = [b for b in raw_headers.split('\n\n') if b.strip()][-1:] or ['']
            for line in final_block[0].splitlines():
                name, _, value = line.partition(':')
                if name.lower() in ('last-modified', 'etag', 'content-type', 'date'):
                    record['cabecalho_' + name.lower().replace('-', '_')] = value.strip()
            looks_like_gateway = b'504 Gateway Time-out' in data[:400] or b'<title>5' in data[:400]
            record['utilizavel'] = status == '200' and not looks_like_gateway and len(data) > 1000
            if record['utilizavel']:
                record['dou_aviso'] = dou_aviso_from_html(data, spec['charset'])
            else:
                record['motivo'] = f'resposta HTTP {status} sem conteúdo utilizável ({len(data)} bytes)'
        else:
            record.update(utilizavel=False, motivo=proc.stderr.strip()[-500:])
        header_file.unlink(missing_ok=True)
        records[key] = record
        print(f'{key}: {record.get("http_status")} {record.get("bytes")} utilizável={record["utilizavel"]}', flush=True)
    (dest / 'capturado_em.txt').write_text(now_utc() + '\n', encoding='utf-8')
    write_json(dest / 'fetch.json', records)
    return records


def ingest_capture(capture_dir: Path, capturado_em: str | None = None) -> dict:
    capture_dir = Path(capture_dir)
    fontes = {}
    stamp = capturado_em
    if stamp is None:
        stamp_file = capture_dir / 'capturado_em.txt'
        stamp = stamp_file.read_text(encoding='utf-8').strip() if stamp_file.exists() else now_utc()
    for key, spec in SOURCES.items():
        raw_path = capture_dir / spec['file']
        if not raw_path.is_file():
            raise SystemExit(f'captura ausente: {raw_path}')
        data = raw_path.read_bytes()
        write_snapshot(key, data)
        headers_path = capture_dir / (spec['file'] + '.headers')
        record = dict(
            orgao=spec['orgao'], formato=spec['formato'], url=spec['url'],
            capturado_em=stamp, user_agent=USER_AGENT, http_status=200,
            url_final=spec['url'], bytes=len(data), sha256=nl.sha256(data),
            sha256_conteudo=nl.content_sha256(data), utilizavel=True,
            dou_aviso=dou_aviso_from_html(data, spec['charset']),
            snapshot=str(snapshot_path(key).relative_to(ROOT)),
            sha256_snapshot_armazenado=nl.sha256(snapshot_path(key).read_bytes()),
            charset=spec['charset'],
        )
        if headers_path.is_file():
            raw_headers = headers_path.read_bytes().decode('latin-1').replace('\r\n', '\n')
            final_block = [b for b in raw_headers.split('\n\n') if b.strip()][-1:] or ['']
            for line in final_block[0].splitlines():
                name, _, value = line.partition(':')
                if name.lower() in ('last-modified', 'etag', 'content-type', 'date'):
                    record['cabecalho_' + name.lower().replace('-', '_')] = value.strip()
        fontes[key] = record
        print(f'ingest {key}: {record["bytes"]} sha256={record["sha256"][:16]}…', flush=True)
    write_json(FONTES_JSON, fontes)
    return fontes


def load_fontes() -> dict:
    return json.loads(FONTES_JSON.read_text(encoding='utf-8'))


def load_sources_bytes() -> dict:
    return {key: read_snapshot(key) for key in SOURCES}


def flatten_nested_md_links(text: str) -> str:
    """Remove artefato `[[rótulo](url1)](url2)` gerado por <a> aninhados no HTML do Planalto.

    Não altera o conversor compartilhado: só normaliza o Markdown deste lote para
    equivalência textual com `source_text_chars_from_html` (que não inclui hrefs).
    """
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r'\[(\[[^\[\]]*\]\([^)]*\))\]\([^)]*\)', r'\1', text)
    return text


def edition_note(doc: dict, rec: dict, conv: nl.Converter) -> str:
    lines = [
        (f'**Edição Planalto — texto autônomo da Emenda Constitucional nº {doc["numero"]}.** '
         f'Fonte: {rec["url"]} (capturada em {rec["capturado_em"]}, SHA-256 da fonte `{rec["sha256"]}`, '
         f'SHA-256 do conteúdo sem script de proteção `{rec["sha256_conteudo"]}`). '
         f'Snapshot: `{rec["snapshot"]}`. O acervo não certifica vigência.'),
        ('Texto autônomo do ato modificador (regras de transição, produção de efeitos, aplicação, '
         'revogações e dispositivos próprios), conforme publicado pelo Planalto — não é apenas a '
         'redação incorporada no corpo consolidado da Constituição/ADCT.'),
        ('Texto entre `~~` é redação superada, vetada ou revogada que a fonte oficial mantém riscada; '
         'não é dispositivo em vigor. A presença deste arquivo no acervo não indica vigência.'),
        ('Série: Emenda Constitucional à Constituição de 1988. Não confundir com Emenda Constitucional '
         'de Revisão nem com emendas a constituições históricas.'),
    ]
    if doc.get('camara_catalogo_url'):
        lines.append(
            f'Referência de catálogo da Câmara (não usada como fonte principal nesta entrega): '
            f'{doc["camara_catalogo_url"]}.')
    else:
        lines.append(
            'URL de publicação original da Câmara não estava vinculada no texto constitucional '
            'publicado neste acervo para este número; a coleta usou o Planalto oficial. '
            'Falha de acesso à Câmara não foi tratada como ausência da norma.')
    if rec.get('dou_aviso'):
        lines.append(rec['dou_aviso'])
    lines.append(
        f'Prova de cobertura fonte→Markdown e reconversão: '
        f'`provas/emendas-cf1988/faixa-101-141/reconciliacao-{doc["slug"]}.json`.')
    if conv.images:
        lines.append(
            f'{len(conv.images)} imagem(ns) institucional(is) do cabeçalho da página foram omitidas do '
            'Markdown (brasão/logotipo sem texto jurídico).')
    if conv.stats['tabelas_markdown'] or conv.stats['tabelas_html']:
        n = conv.stats['tabelas_markdown'] + conv.stats['tabelas_html']
        lines.append(f'{n} tabela(s) da fonte foram convertidas para Markdown/`<table>` no corpo.')
    return nl.note_block(lines)


def build_document(doc: dict, data: bytes, rec: dict) -> tuple[str, dict, dict, nl.Converter]:
    spec = SOURCES[doc['fonte']]
    conv = nl.convert_html(data, spec['charset'], spec['url'])
    body = flatten_nested_md_links(nl.blocks_to_markdown(conv.blocks, doc['title_pattern']))
    src = nl.strip_fold(nl.source_text_chars_from_html(data, spec['charset']))
    md_all = nl.strip_fold(nl.md_text_all(body))
    coverage_ok = src == md_all
    arts, order = nl.split_articles(conv.blocks)
    anexos = sum(1 for b in conv.blocks if re.match(r'^ANEXO\b', nl.md_plain(b, True).strip(), re.I))
    note = edition_note(doc, rec, conv)
    if '# ' not in body:
        raise SystemExit(f'{doc["slug"]}: título H1 ausente após conversão')
    title_at = body.index('# ') if body.startswith('# ') else body.index('\n# ') + 1
    title_end = body.index('\n\n', title_at)
    head, rest = body[:title_end], body[title_end + 2:]
    published_body = head + '\n\n' + note + '\n\n' + rest
    if not published_body.endswith('\n'):
        published_body += '\n'

    norma = doc['norma']
    edicao_id = f'{doc["slug"]}@consolidada-planalto'
    meta = dict(
        id=doc['slug'],
        norma_id=doc['slug'],
        norma_tipo=norma['tipo'],
        norma_numero=norma['numero'],
        norma_data=norma['data'],
        titulo=norma['titulo'],
        esfera='federal',
        edicao_id=edicao_id,
        edicao_tipo='consolidada',
        edicao_integral=True,
        edicao_relacionada=None,
        fonte_orgao=PLANALTO,
        fonte_url=spec['url'],
        fonte_formato='html',
        fonte_conferencia='nenhuma',
        capturado_em=rec['capturado_em'],
        sha256_fonte=rec['sha256'],
        situacao=doc['situacao']['valor'],
        situacao_fundamento=UNKNOWN,
        vigencia_certificada=False,
        texto_riscado=conv.stats['trechos_riscados'] > 0,
        anexos_no_corpo=anexos,
        tabelas=conv.stats['tabelas_markdown'] + conv.stats['tabelas_html'],
        imagens_omitidas=len(conv.images),
        efeitos_diferidos='preservados-nas-notas-do-texto',
        sha256_markdown=nl.sha256(published_body.encode('utf-8')),
        manifesto=str(MANIFESTO.relative_to(ROOT)),
        contrato_versao=CONTRACT_VERSION,
    )
    errors = nl.validate_meta(meta, doc['slug'])
    if errors:
        raise SystemExit('metadados inválidos:\n' + '\n'.join(errors))

    markdown = nl.render_frontmatter(meta) + published_body
    _, body_only = nl.parse_frontmatter(markdown)
    meta['sha256_markdown'] = nl.sha256(body_only.encode('utf-8'))
    markdown = nl.render_frontmatter(meta) + body_only

    proof = dict(
        documento=doc['slug'],
        fonte_principal=doc['fonte'],
        sha256_fonte_principal=rec['sha256'],
        sha256_conteudo=rec['sha256_conteudo'],
        capturado_em=rec['capturado_em'],
        url=spec['url'],
        snapshot=rec['snapshot'],
        sha256_snapshot_armazenado=rec['sha256_snapshot_armazenado'],
        fontes_conferencia=[],
        camara_catalogo_url=doc.get('camara_catalogo_url'),
        cobertura_texto=dict(
            descricao=('texto integral da página da fonte (sem imagens) == texto do Markdown publicado '
                       '(corpo convertido, sem nota de edição), após normalização'),
            equivalente=coverage_ok,
            caracteres_normalizados_fonte=len(src),
            caracteres_normalizados_markdown=len(md_all),
            metodo='strip_fold(source_text_chars_from_html) == strip_fold(md_text_all(body_convertido))',
        ),
        conversao=dict(
            **conv.stats,
            imagens=conv.images,
            tabelas=conv.tables,
            blocos=len(conv.blocks),
            artigos=len(order),
            primeiros_artigos=order[:5],
            ultimos_artigos=order[-5:],
            titulos_e_capitulos=len(nl.headings(nl.main_body_blocks(conv.blocks))),
        ),
        identidade=dict(
            norma_id=doc['slug'],
            numero=norma['numero'],
            data=norma['data'],
            titulo_fonte=norma['titulo'],
            ementa=norma['ementa'],
            urn=doc.get('urn'),
            serie='emenda-constitucional-cf1988',
            edicao=doc['edicao'],
        ),
        limites=[
            'Fonte principal: Planalto (emcN.htm). fonte_conferencia=nenhuma nesta entrega.',
            'Texto autônomo da emenda; não substitui a Constituição consolidada nem edições alternativas.',
            'O acervo não certifica vigência nem reconstrói texto ausente a partir de citações.',
            'Imagens institucionais do cabeçalho foram omitidas; tabelas/notas/riscados da fonte foram preservados.',
            'Não confundir com Emenda Constitucional de Revisão nem emendas a constituições históricas.',
        ],
    )
    if not coverage_ok:
        raise SystemExit(f'{doc["slug"]}: cobertura fonte→Markdown falhou')

    entry = dict(
        id=doc['slug'],
        arquivo=doc['arquivo'],
        numero=doc['numero'],
        norma=norma,
        urn=doc.get('urn'),
        edicao=dict(tipo='consolidada', integral=True, identidade=doc['edicao']['identidade'], edicao_id=edicao_id),
        situacao=doc['situacao'],
        fonte=dict(
            chave=doc['fonte'], orgao=PLANALTO, url=spec['url'], formato='html',
            capturado_em=rec['capturado_em'], sha256=rec['sha256'],
            sha256_conteudo=rec['sha256_conteudo'], snapshot=rec['snapshot'],
            sha256_snapshot_armazenado=rec['sha256_snapshot_armazenado'],
            dou_aviso=rec.get('dou_aviso'),
            camara_catalogo_url=doc.get('camara_catalogo_url'),
        ),
        prova=f'provas/emendas-cf1988/faixa-101-141/reconciliacao-{doc["slug"]}.json',
        sha256_markdown=meta['sha256_markdown'],
        estrutura=dict(
            blocos=len(conv.blocks), artigos=len(order),
            tabelas=meta['tabelas'], anexos_no_corpo=anexos,
            imagens_omitidas=meta['imagens_omitidas'],
            texto_riscado=meta['texto_riscado'],
        ),
    )
    return markdown, proof, entry, conv


def build_matriz(manifest_docs: list, fontes: dict) -> dict:
    itens = []
    for entry in manifest_docs:
        n = entry['numero']
        fonte = entry['fonte']
        itens.append(dict(
            numero=n,
            data=entry['norma']['data'],
            id=entry['id'],
            arquivo=entry['arquivo'],
            situacao_coleta='recuperada',
            fonte_principal=dict(orgao=fonte['orgao'], url=fonte['url'], sha256=fonte['sha256'],
                                 capturado_em=fonte['capturado_em'], snapshot=fonte['snapshot']),
            camara_catalogo_url=fonte.get('camara_catalogo_url'),
            urn=entry.get('urn'),
            ementa=entry['norma']['ementa'],
            vigencia_certificada=False,
            serie='emenda-constitucional-cf1988',
            notas=[
                'Texto autônomo do Planalto; regras de transição/efeitos/revogações preservadas quando presentes na fonte.',
                'Não é Emenda Constitucional de Revisão nem emenda a constituição histórica.',
            ],
        ))
    presentes_fora_lote = [101, 103, 104, 105, 106, 108, 110, 119]
    return dict(
        lote=LOTE,
        faixa={'inicio': 101, 'fim': 141},
        gerado_em=now_utc(),
        vigencia_certificada=False,
        criterio=('Números ausentes na série CF/1988 no main remoto, na faixa 101–141, '
                  'excluídas emendas de revisão e constituições históricas. Outro agente cobre 1–50.'),
        numeros_alvo=LOTE_NUMEROS,
        recuperados=[it['numero'] for it in itens],
        lacunas_neste_lote=[],
        presentes_na_faixa_fora_deste_lote=presentes_fora_lote,
        itens=itens,
        limites=[
            'Matriz deste lote apenas; matriz global e contagens do README ficam com o orquestrador.',
            'Acesso falho a uma fonte alternativa ≠ ausência da norma.',
            'Sem inventar vigência, texto ou fonte.',
        ],
    )


def compute(sources: dict, fontes: dict):
    docs_out = {}
    proofs = {}
    manifest_docs = []
    for doc in DOCS:
        key = doc['fonte']
        markdown, proof, entry, _conv = build_document(doc, sources[key], fontes[key])
        docs_out[doc['slug']] = dict(arquivo=doc['arquivo'], markdown=markdown, meta=nl.parse_frontmatter(markdown)[0])
        proofs[doc['slug']] = proof
        manifest_docs.append(entry)
    if [d['numero'] for d in DOCS] != LOTE_NUMEROS:
        raise SystemExit('catálogo DOCS diverge de LOTE_NUMEROS')
    manifest = dict(
        contrato_versao=CONTRACT_VERSION,
        lote=LOTE,
        descricao=('Textos autônomos das Emendas Constitucionais à CF/1988 ausentes na faixa 101–141 '
                   '(números listados em numeros_alvo), recuperados do Planalto oficial.'),
        gerado_em=now_utc(),
        vigencia_certificada=False,
        numeros_alvo=LOTE_NUMEROS,
        documentos=manifest_docs,
        limites=[
            'Não altera scripts/nucleo_licitacoes.py nem metadados/nucleo-licitacoes.json.',
            'Não atualiza README agregado nem matriz global (integração pelo orquestrador).',
            'Faixas 1–50 e 51–100 ficam fora deste lote; 103/2019 e demais já presentes não são republicados.',
            'Sem segunda fonte oficial de conferência artigo a artigo nesta entrega.',
        ],
    )
    matriz = build_matriz(manifest_docs, fontes)
    return docs_out, proofs, manifest, matriz


def write_outputs(docs_out, proofs, manifest, matriz) -> None:
    for slug, item in docs_out.items():
        path = ROOT / item['arquivo']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item['markdown'], encoding='utf-8')
        print(f'wrote {item["arquivo"]} ({len(item["markdown"])} chars)', flush=True)
    for slug, proof in proofs.items():
        write_json(PROVAS / f'reconciliacao-{slug}.json', proof)
    write_json(MANIFESTO, manifest)
    write_json(MATRIZ, matriz)
    write_json(PROVAS / 'ferramentas.json', nl.tool_versions())
    readme = PROVAS / 'README.md'
    readme.write_text(
        '# Provas — Emendas CF/1988 faixa 101–141\n\n'
        'Geradas por [`scripts/emendas_cf1988_faixa_101_141.py`](../../../scripts/emendas_cf1988_faixa_101_141.py). '
        'Não editar à mão.\n\n'
        '| Arquivo | Função |\n'
        '| --- | --- |\n'
        '| `fontes/` | Snapshots oficiais do Planalto (HTML em `.xz`). |\n'
        '| `fontes.json` | URL, data UTC, status HTTP, hashes e cabeçalhos de cada captura. |\n'
        '| `matriz.json` | Matriz por número/data/fonte/situação deste lote. |\n'
        '| `manifesto.json` | Metadados dos 33 documentos publicados. |\n'
        '| `reconciliacao-*.json` | Cobertura HTML→Markdown e reconversão por emenda. |\n'
        '| `ferramentas.json` | Versões usadas na geração. |\n\n'
        '## Verificar (sem rede)\n\n'
        '```sh\n'
        'python3 scripts/emendas_cf1988_faixa_101_141.py verify\n'
        'python3 -m unittest tests.test_emendas_cf1988_faixa_101_141 -v\n'
        '```\n\n'
        '## Recapturar\n\n'
        '```sh\n'
        'python3 scripts/emendas_cf1988_faixa_101_141.py fetch /tmp/captura-emendas-cf1988-faixa-101-141\n'
        'python3 scripts/emendas_cf1988_faixa_101_141.py ingest /tmp/captura-emendas-cf1988-faixa-101-141\n'
        'python3 scripts/emendas_cf1988_faixa_101_141.py build\n'
        '```\n',
        encoding='utf-8')


def build() -> None:
    fontes = load_fontes()
    sources = load_sources_bytes()
    for key in SOURCES:
        if key not in fontes or not fontes[key].get('utilizavel', True):
            raise SystemExit(f'fonte {key} ausente ou inutilizável em {FONTES_JSON}')
        snap = snapshot_path(key)
        if not snap.is_file():
            raise SystemExit(f'snapshot ausente: {snap}')
        raw = read_snapshot(key)
        if nl.sha256(raw) != fontes[key]['sha256']:
            raise SystemExit(f'{key}: sha256 do snapshot diverge de fontes.json')
        if nl.sha256(snap.read_bytes()) != fontes[key]['sha256_snapshot_armazenado']:
            raise SystemExit(f'{key}: sha256_snapshot_armazenado diverge')
    docs_out, proofs, manifest, matriz = compute(sources, fontes)
    write_outputs(docs_out, proofs, manifest, matriz)
    print('build ok', flush=True)


def verify() -> None:
    fontes = load_fontes()
    sources = load_sources_bytes()
    docs_out, proofs, manifest, matriz = compute(sources, fontes)
    problems = []

    published_manifest = json.loads(MANIFESTO.read_text(encoding='utf-8'))
    published_matriz = json.loads(MATRIZ.read_text(encoding='utf-8'))
    if published_manifest.get('lote') != LOTE:
        problems.append('manifesto.lote inesperado')
    if published_matriz.get('lote') != LOTE:
        problems.append('matriz.lote inesperado')
    if len(published_manifest.get('documentos') or []) != len(DOCS):
        problems.append('manifesto.documentos com cardinalidade divergente')
    if published_matriz.get('numeros_alvo') != LOTE_NUMEROS:
        problems.append('matriz.numeros_alvo diverge')
    if published_matriz.get('lacunas_neste_lote') != []:
        problems.append('matriz.lacunas_neste_lote deveria estar vazia após recuperação completa')

    for doc in DOCS:
        slug = doc['slug']
        path = ROOT / doc['arquivo']
        if not path.is_file():
            problems.append(f'{slug}: arquivo ausente')
            continue
        text = path.read_text(encoding='utf-8')
        meta, body = nl.parse_frontmatter(text)
        expected_md = docs_out[slug]['markdown']
        if text != expected_md:
            problems.append(f'{slug}: Markdown publicado diverge da reconversão integral')
        if meta.get('sha256_markdown') != nl.sha256(body.encode('utf-8')):
            problems.append(f'{slug}: sha256_markdown não confere com o corpo')
        if meta.get('vigencia_certificada') is not False:
            problems.append(f'{slug}: vigencia_certificada deve ser false')
        if meta.get('fonte_conferencia') != 'nenhuma':
            problems.append(f'{slug}: fonte_conferencia esperada "nenhuma" neste lote')
        if meta.get('norma_tipo') != 'emenda-constitucional':
            problems.append(f'{slug}: norma_tipo inesperado')
        proof_path = PROVAS / f'reconciliacao-{slug}.json'
        published_proof = json.loads(proof_path.read_text(encoding='utf-8'))
        recomputed = proofs[slug]
        if not recomputed['cobertura_texto']['equivalente']:
            problems.append(f'{slug}: cobertura fonte→Markdown falsa no recomputo')
        if published_proof.get('cobertura_texto', {}).get('equivalente') is not True:
            problems.append(f'{slug}: prova publicada sem cobertura equivalente')
        if published_proof.get('sha256_fonte_principal') != fontes[doc['fonte']]['sha256']:
            problems.append(f'{slug}: sha256_fonte_principal da prova diverge')
        if f'EMENDA CONSTITUCIONAL Nº {doc["numero"]}' not in body.upper().replace('N°', 'Nº').replace('N.', 'Nº'):
            # tolerate typographic variants already normalized in title
            if str(doc['numero']) not in body[:800]:
                problems.append(f'{slug}: identidade numérica não encontrada no corpo')
        if 'não certifica vigência' not in body and 'nao certifica vigencia' not in nl.strip_fold(body):
            problems.append(f'{slug}: nota de edição sem aviso de não-certificação de vigência')
        if 'Emenda Constitucional de Revisão' not in body:
            problems.append(f'{slug}: nota deveria distinguir revisão/históricas')

        key = doc['fonte']
        raw = sources[key]
        if nl.sha256(raw) != fontes[key]['sha256']:
            problems.append(f'{key}: snapshot sha256 diverge')
        if nl.content_sha256(raw) != fontes[key]['sha256_conteudo']:
            problems.append(f'{key}: content sha256 diverge')

    expected_slugs = {d['slug'] for d in DOCS}
    if len(expected_slugs) != 33:
        problems.append('catálogo DOCS deste lote não tem 33 itens')
    if {d['numero'] for d in DOCS} != set(LOTE_NUMEROS):
        problems.append('números do catálogo divergem do lote')

    if problems:
        raise SystemExit('verify falhou:\n- ' + '\n- '.join(problems))
    print('verify ok', flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    p_fetch = sub.add_parser('fetch', help='captura fontes oficiais')
    p_fetch.add_argument('dir', type=Path)
    p_ingest = sub.add_parser('ingest', help='grava snapshots a partir de captura local')
    p_ingest.add_argument('dir', type=Path)
    p_ingest.add_argument('--capturado-em', default=None)
    sub.add_parser('build', help='reconverte e escreve Markdown/provas')
    sub.add_parser('verify', help='confere offline')
    args = parser.parse_args(argv)
    if args.cmd == 'fetch':
        fetch(args.dir)
    elif args.cmd == 'ingest':
        ingest_capture(args.dir, args.capturado_em)
    elif args.cmd == 'build':
        build()
    elif args.cmd == 'verify':
        verify()
    else:
        parser.error(args.cmd)


if __name__ == '__main__':
    main()
