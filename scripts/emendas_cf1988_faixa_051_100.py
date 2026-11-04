"""Emendas CF/1988 ausentes na faixa 51–100 (lote issue #63).

Recupera o texto autônomo oficial no Planalto para os números
53,54,56,57,63,64,71,72,73,76,77,79,82,83,85–99. Reutiliza o conversor
HTML→Markdown de `nucleo_licitacoes` sem alterá-lo. Provas e matriz ficam
somente em `provas/emendas-cf1988/faixa-051-100/`. README agregado e matriz
global ficam com o orquestrador.

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

LOTE = 'emendas-cf1988-faixa-051-100'
PROVAS = ROOT / 'provas/emendas-cf1988/faixa-051-100'
FONTES_DIR = PROVAS / 'fontes'
MANIFESTO = PROVAS / 'manifesto.json'
MATRIZ = PROVAS / 'matriz.json'
FONTES_JSON = PROVAS / 'fontes.json'
UNKNOWN = nl.UNKNOWN
PLANALTO = nl.PLANALTO
USER_AGENT = nl.USER_AGENT
CONTRACT_VERSION = nl.CONTRACT_VERSION

# Números deste lote (faixa 51–100, ausentes no main remoto na abertura da issue).
LOTE_NUMEROS = [53, 54, 56, 57, 63, 64, 71, 72, 73, 76, 77, 79, 82, 83, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99]

SOURCES = {
    'planalto-emc53': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc53.htm',
        file='planalto-emc53.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc54': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc54.htm',
        file='planalto-emc54.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc56': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc56.htm',
        file='planalto-emc56.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc57': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc57.htm',
        file='planalto-emc57.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc63': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc63.htm',
        file='planalto-emc63.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc64': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc64.htm',
        file='planalto-emc64.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc71': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc71.htm',
        file='planalto-emc71.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc72': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc72.htm',
        file='planalto-emc72.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc73': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc73.htm',
        file='planalto-emc73.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc76': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc76.htm',
        file='planalto-emc76.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc77': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc77.htm',
        file='planalto-emc77.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc79': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc79.htm',
        file='planalto-emc79.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc82': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc82.htm',
        file='planalto-emc82.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc83': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc83.htm',
        file='planalto-emc83.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc85': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc85.htm',
        file='planalto-emc85.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc86': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc86.htm',
        file='planalto-emc86.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc87': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc87.htm',
        file='planalto-emc87.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc88': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc88.htm',
        file='planalto-emc88.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc89': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc89.htm',
        file='planalto-emc89.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc90': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc90.htm',
        file='planalto-emc90.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc91': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc91.htm',
        file='planalto-emc91.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc92': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc92.htm',
        file='planalto-emc92.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc93': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc93.htm',
        file='planalto-emc93.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc94': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc94.htm',
        file='planalto-emc94.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc95': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc95.htm',
        file='planalto-emc95.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc96': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc96.htm',
        file='planalto-emc96.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc97': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc97.htm',
        file='planalto-emc97.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc98': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc98.htm',
        file='planalto-emc98.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-emc99': dict(
        url='https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc99.htm',
        file='planalto-emc99.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
}

DOCS = [
    dict(
        slug='br-federal-emenda-constitucional-2006-12-19-53',
        arquivo='federal/br-federal-emenda-constitucional-2006-12-19-53.md',
        fonte='planalto-emc53',
        numero=53,
        urn='urn:lex:br:federal:emenda.constitucional:2006-12-19;53',
        camara_catalogo_url='https://www2.camara.leg.br/legin/fed/emecon/2006/emendaconstitucional-53-19-dezembro-2006-548446-publicacaooriginal-63582-pl.html',
        norma=dict(
            tipo='emenda-constitucional', numero='53', data='2006-12-19',
            titulo='EMENDA CONSTITUCIONAL Nº 53, DE 19 DE DEZEMBRO DE 2006',
            ementa='Dá nova redação aos arts. 7º, 23, 30, 206, 208, 211 e 212 da Constituição Federal e ao art. 60 do Ato das Disposições Constitucionais Transitórias.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2007-09-20-54',
        arquivo='federal/br-federal-emenda-constitucional-2007-09-20-54.md',
        fonte='planalto-emc54',
        numero=54,
        urn='urn:lex:br:federal:emenda.constitucional:2007-09-20;54',
        camara_catalogo_url='https://www2.camara.leg.br/legin/fed/emecon/2007/emendaconstitucional-54-20-setembro-2007-559896-publicacaooriginal-82340-pl.html',
        norma=dict(
            tipo='emenda-constitucional', numero='54', data='2007-09-20',
            titulo='EMENDA CONSTITUCIONAL Nº 54, DE 20 DE SETEMBRO DE 2007',
            ementa='Dá nova redação à alínea c do inciso I do art. 12 da Constituição Federal e acrescenta art. 95 ao Ato das Disposições Constitucionais Transitórias, assegurando o registro nos consulados de brasileiros nascidos no estrangeiro.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2007-12-20-56',
        arquivo='federal/br-federal-emenda-constitucional-2007-12-20-56.md',
        fonte='planalto-emc56',
        numero=56,
        urn='urn:lex:br:federal:emenda.constitucional:2007-12-20;56',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='56', data='2007-12-20',
            titulo='EMENDA CONSTITUCIONAL Nº 56, DE 20 DE DEZEMBRO DE 2007',
            ementa='Prorroga o prazo previsto no caput do art. 76 do Ato das Disposições Constitucionais Transitórias e dá outras providências.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2008-12-18-57',
        arquivo='federal/br-federal-emenda-constitucional-2008-12-18-57.md',
        fonte='planalto-emc57',
        numero=57,
        urn='urn:lex:br:federal:emenda.constitucional:2008-12-18;57',
        camara_catalogo_url='https://www2.camara.leg.br/legin/fed/emecon/2008/emendaconstitucional-57-18-dezembro-2008-584930-publicacaooriginal-107792-pl.html',
        norma=dict(
            tipo='emenda-constitucional', numero='57', data='2008-12-18',
            titulo='EMENDA CONSTITUCIONAL Nº 57, DE 18 DE DEZEMBRO DE 2008',
            ementa='Acrescenta artigo ao Ato das Disposições Constitucionais Transitórias para convalidar os atos de criação, fusão, incorporação e desmembramento de Municípios.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2010-02-04-63',
        arquivo='federal/br-federal-emenda-constitucional-2010-02-04-63.md',
        fonte='planalto-emc63',
        numero=63,
        urn='urn:lex:br:federal:emenda.constitucional:2010-02-04;63',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='63', data='2010-02-04',
            titulo='EMENDA CONSTITUCIONAL Nº 63, DE 4 DE FEVEREIRO DE 2010',
            ementa='Altera o § 5º do art. 198 da Constituição Federal para dispor sobre piso salarial profissional nacional e diretrizes para os Planos de Carreira de agentes comunitários de saúde e de agentes de combate às endemias.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2010-02-04-64',
        arquivo='federal/br-federal-emenda-constitucional-2010-02-04-64.md',
        fonte='planalto-emc64',
        numero=64,
        urn='urn:lex:br:federal:emenda.constitucional:2010-02-04;64',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='64', data='2010-02-04',
            titulo='EMENDA CONSTITUCIONAL Nº 64, DE 4 DE FEVEREIRO DE 2010',
            ementa='Altera o art. 6º da Constituição Federal, para introduzir a alimentação como direito social.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2012-11-29-71',
        arquivo='federal/br-federal-emenda-constitucional-2012-11-29-71.md',
        fonte='planalto-emc71',
        numero=71,
        urn='urn:lex:br:federal:emenda.constitucional:2012-11-29;71',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='71', data='2012-11-29',
            titulo='EMENDA CONSTITUCIONAL Nº 71, DE 29 DE NOVEMBRO DE 2012',
            ementa='Acrescenta o art. 216-A à Constituição Federal para instituir o Sistema Nacional de Cultura.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2013-04-02-72',
        arquivo='federal/br-federal-emenda-constitucional-2013-04-02-72.md',
        fonte='planalto-emc72',
        numero=72,
        urn='urn:lex:br:federal:emenda.constitucional:2013-04-02;72',
        camara_catalogo_url='https://www2.camara.leg.br/legin/fed/emecon/2013/emendaconstitucional-72-2-abril-2013-775615-publicacaooriginal-139358-pl.html',
        norma=dict(
            tipo='emenda-constitucional', numero='72', data='2013-04-02',
            titulo='EMENDA CONSTITUCIONAL Nº 72, DE 2 DE ABRIL DE 2013',
            ementa='Altera a redação do parágrafo único do art. 7º da Constituição Federal para estabelecer a igualdade de direitos trabalhistas entre os trabalhadores domésticos e os demais trabalhadores urbanos e rurais.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2013-06-06-73',
        arquivo='federal/br-federal-emenda-constitucional-2013-06-06-73.md',
        fonte='planalto-emc73',
        numero=73,
        urn='urn:lex:br:federal:emenda.constitucional:2013-06-06;73',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='73', data='2013-06-06',
            titulo='EMENDA CONSTITUCIONAL Nº 73, DE 6 DE JUNHO DE 2013',
            ementa='Cria os Tribunais Regionais Federais da 6ª, 7ª, 8ª e 9ª Regiões.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2013-11-28-76',
        arquivo='federal/br-federal-emenda-constitucional-2013-11-28-76.md',
        fonte='planalto-emc76',
        numero=76,
        urn='urn:lex:br:federal:emenda.constitucional:2013-11-28;76',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='76', data='2013-11-28',
            titulo='EMENDA CONSTITUCIONAL Nº 76, DE 28 DE NOVEMBRO DE 2013',
            ementa='Altera o § 2º do art. 55 e o § 4º do art. 66 da Constituição Federal, para abolir a votação secreta nos casos de perda de mandato de Deputado ou Senador e de apreciação de veto.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2014-02-11-77',
        arquivo='federal/br-federal-emenda-constitucional-2014-02-11-77.md',
        fonte='planalto-emc77',
        numero=77,
        urn='urn:lex:br:federal:emenda.constitucional:2014-02-11;77',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='77', data='2014-02-11',
            titulo='EMENDA CONSTITUCIONAL Nº 77, DE 11 DE FEVEREIRO DE 2014',
            ementa='Altera os incisos II, III e VIII do § 3º do art. 142 da Constituição Federal, para estender aos profissionais de saúde das Forças Armadas a possibilidade de cumulação de cargo a que se refere o art. 37, inciso XVI, alínea "c".'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2014-05-27-79',
        arquivo='federal/br-federal-emenda-constitucional-2014-05-27-79.md',
        fonte='planalto-emc79',
        numero=79,
        urn='urn:lex:br:federal:emenda.constitucional:2014-05-27;79',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='79', data='2014-05-27',
            titulo='EMENDA CONSTITUCIONAL Nº 79, DE 27 DE MAIO DE 2014',
            ementa='Altera o art. 31 da Emenda Constitucional nº 19, de 4 de junho de 1998, para prever a inclusão, em quadro em extinção da Administração Federal, de servidores e policiais militares admitidos pelos Estados do Amapá e de Roraima, na fase de instalação dessas unidades federadas, e dá outras providências.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2014-07-16-82',
        arquivo='federal/br-federal-emenda-constitucional-2014-07-16-82.md',
        fonte='planalto-emc82',
        numero=82,
        urn='urn:lex:br:federal:emenda.constitucional:2014-07-16;82',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='82', data='2014-07-16',
            titulo='EMENDA CONSTITUCIONAL Nº 82, DE 16 DE JULHO DE 2014',
            ementa='Inclui o § 10 ao art. 144 da Constituição Federal, para disciplinar a segurança viária no âmbito dos Estados, do Distrito Federal e dos Municípios.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2014-08-05-83',
        arquivo='federal/br-federal-emenda-constitucional-2014-08-05-83.md',
        fonte='planalto-emc83',
        numero=83,
        urn='urn:lex:br:federal:emenda.constitucional:2014-08-05;83',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='83', data='2014-08-05',
            titulo='EMENDA CONSTITUCIONAL Nº 83, DE 5 DE AGOSTO DE 2014',
            ementa='Acrescenta o art. 92-A ao Ato das Disposições Constitucionais Transitórias - ADCT.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2015-02-26-85',
        arquivo='federal/br-federal-emenda-constitucional-2015-02-26-85.md',
        fonte='planalto-emc85',
        numero=85,
        urn='urn:lex:br:federal:emenda.constitucional:2015-02-26;85',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='85', data='2015-02-26',
            titulo='EMENDA CONSTITUCIONAL Nº 85, DE 26 DE FEVEREIRO DE 2015',
            ementa='Altera e adiciona dispositivos na Constituição Federal para atualizar o tratamento das atividades de ciência, tecnologia e inovação.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2015-03-17-86',
        arquivo='federal/br-federal-emenda-constitucional-2015-03-17-86.md',
        fonte='planalto-emc86',
        numero=86,
        urn='urn:lex:br:federal:emenda.constitucional:2015-03-17;86',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='86', data='2015-03-17',
            titulo='EMENDA CONSTITUCIONAL Nº 86, DE 17 DE MARÇO DE 2015',
            ementa='Altera os arts. 165, 166 e 198 da Constituição Federal, para tornar obrigatória a execução da programação orçamentária que especifica.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2015-04-16-87',
        arquivo='federal/br-federal-emenda-constitucional-2015-04-16-87.md',
        fonte='planalto-emc87',
        numero=87,
        urn='urn:lex:br:federal:emenda.constitucional:2015-04-16;87',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='87', data='2015-04-16',
            titulo='EMENDA CONSTITUCIONAL Nº 87, DE 16 DE ABRIL DE 2015',
            ementa='Altera o § 2º do art. 155 da Constituição Federal e inclui o art. 99 no Ato das Disposições Constitucionais Transitórias, para tratar da sistemática de cobrança do imposto sobre operações relativas à circulação de mercadorias e sobre prestações de serviços de transporte interestadual e intermunicipal e de comunicação incidente sobre as operações e prestações que destinem bens e serviços a consumidor final, contribuinte ou não do imposto, localizado em outro Estado.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2015-05-07-88',
        arquivo='federal/br-federal-emenda-constitucional-2015-05-07-88.md',
        fonte='planalto-emc88',
        numero=88,
        urn='urn:lex:br:federal:emenda.constitucional:2015-05-07;88',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='88', data='2015-05-07',
            titulo='EMENDA CONSTITUCIONAL Nº 88, DE 7 DE MAIO DE 2015',
            ementa='Altera o art. 40 da Constituição Federal, relativamente ao limite de idade para a aposentadoria compulsória do servidor público em geral, e acrescenta dispositivo ao Ato das Disposições Constitucionais Transitórias.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2015-09-15-89',
        arquivo='federal/br-federal-emenda-constitucional-2015-09-15-89.md',
        fonte='planalto-emc89',
        numero=89,
        urn='urn:lex:br:federal:emenda.constitucional:2015-09-15;89',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='89', data='2015-09-15',
            titulo='EMENDA CONSTITUCIONAL Nº 89, DE 15 DE SETEMBRO DE 2015',
            ementa='Dá nova redação ao art. 42 do Ato das Disposições Constitucionais Transitórias, ampliando o prazo em que a União deverá destinar às Regiões Centro-Oeste e Nordeste percentuais mínimos dos recursos destinados à irrigação.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2015-09-15-90',
        arquivo='federal/br-federal-emenda-constitucional-2015-09-15-90.md',
        fonte='planalto-emc90',
        numero=90,
        urn='urn:lex:br:federal:emenda.constitucional:2015-09-15;90',
        camara_catalogo_url='https://www2.camara.leg.br/legin/fed/emecon/2015/emendaconstitucional-90-15-setembro-2015-781520-publicacaooriginal-148098-pl.html',
        norma=dict(
            tipo='emenda-constitucional', numero='90', data='2015-09-15',
            titulo='EMENDA CONSTITUCIONAL Nº 90, DE 15 DE SETEMBRO DE 2015',
            ementa='Dá nova redação ao art. 6º da Constituição Federal, para introduzir o transporte como direito social.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2016-02-18-91',
        arquivo='federal/br-federal-emenda-constitucional-2016-02-18-91.md',
        fonte='planalto-emc91',
        numero=91,
        urn='urn:lex:br:federal:emenda.constitucional:2016-02-18;91',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='91', data='2016-02-18',
            titulo='EMENDA CONSTITUCIONAL Nº 91, DE 18 DE FEVEREIRO DE 2016',
            ementa='Altera a Constituição Federal para estabelecer a possibilidade, excepcional e em período determinado, de desfiliação partidária, sem prejuízo do mandato.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2016-07-12-92',
        arquivo='federal/br-federal-emenda-constitucional-2016-07-12-92.md',
        fonte='planalto-emc92',
        numero=92,
        urn='urn:lex:br:federal:emenda.constitucional:2016-07-12;92',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='92', data='2016-07-12',
            titulo='EMENDA CONSTITUCIONAL Nº 92, DE 12 DE JULHO DE 2016',
            ementa='Altera os arts. 92 e 111-A da Constituição Federal, para explicitar o Tribunal Superior do Trabalho como órgão do Poder Judiciário, alterar os requisitos para o provimento dos cargos de Ministros daquele Tribunal e modificar-lhe a competência.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2016-09-08-93',
        arquivo='federal/br-federal-emenda-constitucional-2016-09-08-93.md',
        fonte='planalto-emc93',
        numero=93,
        urn='urn:lex:br:federal:emenda.constitucional:2016-09-08;93',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='93', data='2016-09-08',
            titulo='EMENDA CONSTITUCIONAL Nº 93, DE 8 DE SETEMBRO DE 2016',
            ementa='Altera o Ato das Disposições Constitucionais Transitórias para prorrogar a desvinculação de receitas da União e estabelecer a desvinculação de receitas dos Estados, Distrito Federal e Municípios.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2016-12-15-94',
        arquivo='federal/br-federal-emenda-constitucional-2016-12-15-94.md',
        fonte='planalto-emc94',
        numero=94,
        urn='urn:lex:br:federal:emenda.constitucional:2016-12-15;94',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='94', data='2016-12-15',
            titulo='EMENDA CONSTITUCIONAL Nº 94, DE 15 DE DEZEMBRO DE 2016',
            ementa='Altera o art. 100 da Constituição Federal, para dispor sobre o regime de pagamento de débitos públicos decorrentes de condenações judiciais; e acrescenta dispositivos ao Ato das Disposições Constitucionais Transitórias, para instituir regime especial de pagamento para os casos em mora.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2016-12-15-95',
        arquivo='federal/br-federal-emenda-constitucional-2016-12-15-95.md',
        fonte='planalto-emc95',
        numero=95,
        urn='urn:lex:br:federal:emenda.constitucional:2016-12-15;95',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='95', data='2016-12-15',
            titulo='EMENDA CONSTITUCIONAL Nº 95, DE 15 DE DEZEMBRO DE 2016',
            ementa='Altera o Ato das Disposições Constitucionais Transitórias, para instituir o Novo Regime Fiscal, e dá outras providências.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2017-06-06-96',
        arquivo='federal/br-federal-emenda-constitucional-2017-06-06-96.md',
        fonte='planalto-emc96',
        numero=96,
        urn='urn:lex:br:federal:emenda.constitucional:2017-06-06;96',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='96', data='2017-06-06',
            titulo='EMENDA CONSTITUCIONAL Nº 96, DE 6 DE JUNHO DE 2017',
            ementa='Acrescenta § 7º ao art. 225 da Constituição Federal para determinar que práticas desportivas que utilizem animais não são consideradas cruéis, nas condições que especifica.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2017-10-04-97',
        arquivo='federal/br-federal-emenda-constitucional-2017-10-04-97.md',
        fonte='planalto-emc97',
        numero=97,
        urn='urn:lex:br:federal:emenda.constitucional:2017-10-04;97',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='97', data='2017-10-04',
            titulo='EMENDA CONSTITUCIONAL Nº 97, DE 4 DE OUTUBRO DE 2017',
            ementa='Altera a Constituição Federal para vedar as coligações partidárias nas eleições proporcionais, estabelecer normas sobre acesso dos partidos políticos aos recursos do fundo partidário e ao tempo de propaganda gratuito no rádio e na televisão e dispor sobre regras de transição.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2017-12-06-98',
        arquivo='federal/br-federal-emenda-constitucional-2017-12-06-98.md',
        fonte='planalto-emc98',
        numero=98,
        urn='urn:lex:br:federal:emenda.constitucional:2017-12-06;98',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='98', data='2017-12-06',
            titulo='EMENDA CONSTITUCIONAL Nº 98, DE 6 DE DEZEMBRO DE 2017',
            ementa='Altera o art. 31 da Emenda Constitucional nº 19, de 4 de junho de 1998, para prever a inclusão, em quadro em extinção da administração pública federal, de servidor público, de integrante da carreira de policial, civil ou militar, e de pessoa que haja mantido relação ou vínculo funcional, empregatício, estatutário ou de trabalho com a administração pública dos ex-Territórios ou dos Estados do Amapá ou de Roraima, inclusive suas prefeituras, na fase de instalação dessas unidades federadas, e dá outras providências.'),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'(?i)^emenda\s+constitucional',
    ),
    dict(
        slug='br-federal-emenda-constitucional-2017-12-14-99',
        arquivo='federal/br-federal-emenda-constitucional-2017-12-14-99.md',
        fonte='planalto-emc99',
        numero=99,
        urn='urn:lex:br:federal:emenda.constitucional:2017-12-14;99',
        camara_catalogo_url=None,
        norma=dict(
            tipo='emenda-constitucional', numero='99', data='2017-12-14',
            titulo='EMENDA CONSTITUCIONAL Nº 99, DE 14 DE DEZEMBRO DE 2017',
            ementa='Altera o art. 101 do Ato das Disposições Constitucionais Transitórias, para instituir novo regime especial de pagamento de precatórios, e os arts. 102, 103 e 105 do Ato das Disposições Constitucionais Transitórias.'),
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
        f'`provas/emendas-cf1988/faixa-051-100/reconciliacao-{doc["slug"]}.json`.')
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
    body = nl.blocks_to_markdown(conv.blocks, doc['title_pattern'])
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
        prova=f'provas/emendas-cf1988/faixa-051-100/reconciliacao-{doc["slug"]}.json',
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
    presentes_fora_lote = [51, 52, 55, 58, 59, 60, 61, 62, 65, 66, 67, 68, 69, 70, 74, 75, 78, 80, 81, 84, 100]
    return dict(
        lote=LOTE,
        faixa={'inicio': 51, 'fim': 100},
        gerado_em=now_utc(),
        vigencia_certificada=False,
        criterio=('Números ausentes na série CF/1988 no main remoto, na faixa 51–100, '
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
        descricao=('Textos autônomos das Emendas Constitucionais à CF/1988 ausentes na faixa 51–100 '
                   '(números listados em numeros_alvo), recuperados do Planalto oficial.'),
        gerado_em=now_utc(),
        vigencia_certificada=False,
        numeros_alvo=LOTE_NUMEROS,
        documentos=manifest_docs,
        limites=[
            'Não altera scripts/nucleo_licitacoes.py nem metadados/nucleo-licitacoes.json.',
            'Não atualiza README agregado nem matriz global (integração pelo orquestrador).',
            'Faixa 1–50 e números >100 ficam fora deste lote.',
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
        '# Provas — Emendas CF/1988 faixa 51–100\n\n'
        'Geradas por [`scripts/emendas_cf1988_faixa_051_100.py`](../../../scripts/emendas_cf1988_faixa_051_100.py). '
        'Não editar à mão.\n\n'
        '| Arquivo | Função |\n'
        '| --- | --- |\n'
        '| `fontes/` | Snapshots oficiais do Planalto (HTML em `.xz`). |\n'
        '| `fontes.json` | URL, data UTC, status HTTP, hashes e cabeçalhos de cada captura. |\n'
        '| `matriz.json` | Matriz por número/data/fonte/situação deste lote. |\n'
        '| `manifesto.json` | Metadados dos 29 documentos publicados. |\n'
        '| `reconciliacao-*.json` | Cobertura HTML→Markdown e reconversão por emenda. |\n'
        '| `ferramentas.json` | Versões usadas na geração. |\n\n'
        '## Verificar (sem rede)\n\n'
        '```sh\n'
        'python3 scripts/emendas_cf1988_faixa_051_100.py verify\n'
        'python3 -m unittest tests.test_emendas_cf1988_faixa_051_100 -v\n'
        '```\n\n'
        '## Recapturar\n\n'
        '```sh\n'
        'python3 scripts/emendas_cf1988_faixa_051_100.py fetch /tmp/captura-emendas-cf1988-faixa-051-100\n'
        'python3 scripts/emendas_cf1988_faixa_051_100.py ingest /tmp/captura-emendas-cf1988-faixa-051-100\n'
        'python3 scripts/emendas_cf1988_faixa_051_100.py build\n'
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
    if len(expected_slugs) != 29:
        problems.append('catálogo DOCS deste lote não tem 29 itens')
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
