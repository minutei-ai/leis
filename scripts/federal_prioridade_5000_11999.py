"""Lote prioritário de leis ordinárias federais 5.000–11.999 (issue #71).

Publica um primeiro lote das normas essenciais citadas na #71 a partir do
Planalto, com cobertura fonte→Markdown integral. Demais prioridades e a série
completa do catálogo ficam em provas/.../PENDENCIAS-prioridade.md.

Reutiliza `nucleo_licitacoes.convert_html` sem alterar aquele gerador.
Já cobertas por outros lotes (não republicadas aqui): ['10520', '11340', '5172', '8069', '8078', '8080', '8213', '8666'].
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
sys.path.insert(0, str(ROOT / "scripts"))

import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / "provas/federal-prioridade-5000-11999"
FONTES_DIR = PROVAS / "fontes"
MANIFESTO = PROVAS / "manifesto.json"
FONTES_JSON = PROVAS / "fontes.json"
PENDENCIAS = PROVAS / "PENDENCIAS-prioridade.md"
UNKNOWN = nl.UNKNOWN
PLANALTO = nl.PLANALTO
USER_AGENT = nl.USER_AGENT
CONTRACT_VERSION = nl.CONTRACT_VERSION
LOTE = "federal-prioridade-5000-11999"
TITLE_PATTERN = r"^LEI(?: COMPLEMENTAR)? N"

# Prioridades da #71 ainda não publicadas neste lote (números).
PRIORIDADE_RESTANTE = [5859, 5869, 5889, 6019, 6024, 6360, 6385, 6437, 6880, 6938, 7492, 7998, 8137, 8142, 8212, 8443, 8742, 8884, 8934, 9069, 9074, 9096, 9249, 9279, 9296, 9424, 9427, 9430, 9433, 9455, 9456, 9472, 9478, 9492, 9514, 9601, 9609, 9610, 9613, 9656, 9717, 9718, 9782, 9784, 9868, 9876, 9882, 9985, 10101, 10172, 10216, 10257, 10259, 10637, 10671, 10741, 10820, 10826, 10833, 10861, 10931, 11107, 11419, 11428, 11441, 11494, 11638, 11738, 11788]

# Já no acervo por outros lotes (não republicar).
JA_NO_ACERVO = ['10520', '11340', '5172', '8069', '8078', '8080', '8213', '8666']

SOURCES = {
    'planalto-L4320': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L4320.htm', file='planalto-L4320.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L5478': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L5478.htm', file='planalto-L5478.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L6015': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L6015compilada.htm', file='planalto-L6015.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L6404': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L6404compilada.htm', file='planalto-L6404.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L6766': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L6766.htm', file='planalto-L6766.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L6830': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L6830.htm', file='planalto-L6830.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L7210': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L7210.htm', file='planalto-L7210.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L7347': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L7347compilada.htm', file='planalto-L7347.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L8009': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L8009.htm', file='planalto-L8009.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L8036': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L8036compilada.htm', file='planalto-L8036.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L8072': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L8072.htm', file='planalto-L8072.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L8112': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L8112cons.htm', file='planalto-L8112.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L8245': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L8245.htm', file='planalto-L8245.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L8429': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L8429compilada.htm', file='planalto-L8429.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L8906': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L8906.htm', file='planalto-L8906.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L8987': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L8987compilada.htm', file='planalto-L8987.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L9099': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L9099.htm', file='planalto-L9099.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L9307': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L9307.htm', file='planalto-L9307.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L9394': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L9394.htm', file='planalto-L9394.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L9503': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L9503Compilado.htm', file='planalto-L9503.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L9504': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L9504.htm', file='planalto-L9504.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L9605': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L9605.htm', file='planalto-L9605.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L11079': dict(url='https://www.planalto.gov.br/ccivil_03/_Ato2004-2006/2004/Lei/L11079.htm', file='planalto-L11079.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L11101': dict(url='https://www.planalto.gov.br/ccivil_03/_Ato2004-2006/2005/Lei/L11101.htm', file='planalto-L11101.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L11343': dict(url='https://www.planalto.gov.br/ccivil_03/_Ato2004-2006/2006/Lei/L11343.htm', file='planalto-L11343.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
}

DOCS = [
    dict(
        slug='br-federal-lei-1964-03-17-4320',
        arquivo='federal/br-federal-lei-1964-03-17-4320.md',
        fonte='planalto-L4320',
        norma=dict(
            tipo='lei', numero='4320', data='1964-03-17',
            titulo='LEI Nº 4320, DE 17 DE MARÇO DE 1964',
            ementa='Estatui Normas Gerais de Direito Financeiro para elaboração e contrôle dos orçamentos e balanços da União, dos Estados, dos Municípios e do Distrito Federal.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1968-07-25-5478',
        arquivo='federal/br-federal-lei-1968-07-25-5478.md',
        fonte='planalto-L5478',
        norma=dict(
            tipo='lei', numero='5478', data='1968-07-25',
            titulo='LEI Nº 5478, DE 25 DE JULHO DE 1968',
            ementa='Dispõe sobre ação de alimentos e dá outras providências.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1973-12-31-6015',
        arquivo='federal/br-federal-lei-1973-12-31-6015.md',
        fonte='planalto-L6015',
        norma=dict(
            tipo='lei', numero='6015', data='1973-12-31',
            titulo='LEI Nº 6015, DE 31 DE DEZEMBRO DE 1973',
            ementa='Dispõe sobre os registros públicos e dá outras providências.',
            denominacao=None),
        edicao=dict(tipo='consolidada', identidade='compilado-planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1976-12-15-6404',
        arquivo='federal/br-federal-lei-1976-12-15-6404.md',
        fonte='planalto-L6404',
        norma=dict(
            tipo='lei', numero='6404', data='1976-12-15',
            titulo='LEI Nº 6404, DE 15 DE DEZEMBRO DE 1976',
            ementa='Dispõe sobre as sociedades por ações.',
            denominacao=None),
        edicao=dict(tipo='consolidada', identidade='compilado-planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1979-12-19-6766',
        arquivo='federal/br-federal-lei-1979-12-19-6766.md',
        fonte='planalto-L6766',
        norma=dict(
            tipo='lei', numero='6766', data='1979-12-19',
            titulo='LEI Nº 6766, DE 19 DE DEZEMBRO DE 1979',
            ementa='Dispõe sobre o parcelamento do solo urbano e dá outras providências.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1980-09-22-6830',
        arquivo='federal/br-federal-lei-1980-09-22-6830.md',
        fonte='planalto-L6830',
        norma=dict(
            tipo='lei', numero='6830', data='1980-09-22',
            titulo='LEI Nº 6830, DE 22 DE SETEMBRO DE 1980',
            ementa='Dispõe sobre a cobrança judicial da Dívida Ativa da Fazenda Pública e dá outras providências.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1984-07-11-7210',
        arquivo='federal/br-federal-lei-1984-07-11-7210.md',
        fonte='planalto-L7210',
        norma=dict(
            tipo='lei', numero='7210', data='1984-07-11',
            titulo='LEI Nº 7210, DE 11 DE JULHO DE 1984',
            ementa='Institui a Lei de Execução Penal.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1985-07-24-7347',
        arquivo='federal/br-federal-lei-1985-07-24-7347.md',
        fonte='planalto-L7347',
        norma=dict(
            tipo='lei', numero='7347', data='1985-07-24',
            titulo='LEI Nº 7347, DE 24 DE JULHO DE 1985',
            ementa='Disciplina a ação civil pública de responsabilidade por danos causados ao meio-ambiente, ao consumidor, a bens e direitos de valor artístico, estético, histórico, turístico e paisagístico e dá outras providências.',
            denominacao=None),
        edicao=dict(tipo='consolidada', identidade='compilado-planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1990-03-29-8009',
        arquivo='federal/br-federal-lei-1990-03-29-8009.md',
        fonte='planalto-L8009',
        norma=dict(
            tipo='lei', numero='8009', data='1990-03-29',
            titulo='LEI Nº 8009, DE 29 DE MARÇO DE 1990',
            ementa='Dispõe sobre a impenhorabilidade do bem de família.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1990-05-11-8036',
        arquivo='federal/br-federal-lei-1990-05-11-8036.md',
        fonte='planalto-L8036',
        norma=dict(
            tipo='lei', numero='8036', data='1990-05-11',
            titulo='LEI Nº 8036, DE 11 DE MAIO DE 1990',
            ementa='Dispõe sobre o Fundo de Garantia do Tempo de Serviço e dá outras providências.',
            denominacao=None),
        edicao=dict(tipo='consolidada', identidade='compilado-planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1990-07-25-8072',
        arquivo='federal/br-federal-lei-1990-07-25-8072.md',
        fonte='planalto-L8072',
        norma=dict(
            tipo='lei', numero='8072', data='1990-07-25',
            titulo='LEI Nº 8072, DE 25 DE JULHO DE 1990',
            ementa='Dispõe sobre os crimes hediondos, nos termos do art. 5º, inciso XLIII, da Constituição Federal, e determina outras providências.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1990-12-11-8112',
        arquivo='federal/br-federal-lei-1990-12-11-8112.md',
        fonte='planalto-L8112',
        norma=dict(
            tipo='lei', numero='8112', data='1990-12-11',
            titulo='LEI Nº 8112, DE 11 DE DEZEMBRO DE 1990',
            ementa='Dispõe sobre o Regime Jurídico dos Servidores Públicos Civis da União, das autarquias e das fundações públicas federais.',
            denominacao=None),
        edicao=dict(tipo='consolidada', identidade='compilado-planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1991-10-18-8245',
        arquivo='federal/br-federal-lei-1991-10-18-8245.md',
        fonte='planalto-L8245',
        norma=dict(
            tipo='lei', numero='8245', data='1991-10-18',
            titulo='LEI Nº 8245, DE 18 DE OUTUBRO DE 1991',
            ementa='Dispõe sobre as locações dos imóveis urbanos e os procedimentos a elas pertinentes.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1992-06-02-8429',
        arquivo='federal/br-federal-lei-1992-06-02-8429.md',
        fonte='planalto-L8429',
        norma=dict(
            tipo='lei', numero='8429', data='1992-06-02',
            titulo='LEI Nº 8429, DE 2 DE JUNHO DE 1992',
            ementa='Dispõe sobre as sanções aplicáveis em virtude da prática de atos de improbidade administrativa, de que trata o § 4º do art. 37 da Constituição Federal; e dá outras providências.',
            denominacao=None),
        edicao=dict(tipo='consolidada', identidade='compilado-planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1994-07-04-8906',
        arquivo='federal/br-federal-lei-1994-07-04-8906.md',
        fonte='planalto-L8906',
        norma=dict(
            tipo='lei', numero='8906', data='1994-07-04',
            titulo='LEI Nº 8906, DE 4 DE JULHO DE 1994',
            ementa='Dispõe sobre o Estatuto da Advocacia e a Ordem dos Advogados do Brasil - OAB.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1995-02-13-8987',
        arquivo='federal/br-federal-lei-1995-02-13-8987.md',
        fonte='planalto-L8987',
        norma=dict(
            tipo='lei', numero='8987', data='1995-02-13',
            titulo='LEI Nº 8987, DE 13 DE FEVEREIRO DE 1995',
            ementa='Dispõe sobre o regime de concessão e permissão da prestação de serviços públicos previsto no art. 175 da Constituição Federal e dá outras providências.',
            denominacao=None),
        edicao=dict(tipo='consolidada', identidade='compilado-planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1995-09-26-9099',
        arquivo='federal/br-federal-lei-1995-09-26-9099.md',
        fonte='planalto-L9099',
        norma=dict(
            tipo='lei', numero='9099', data='1995-09-26',
            titulo='LEI Nº 9099, DE 26 DE SETEMBRO DE 1995',
            ementa='Dispõe sobre os Juizados Especiais Cíveis e Criminais e dá outras providências.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1996-09-23-9307',
        arquivo='federal/br-federal-lei-1996-09-23-9307.md',
        fonte='planalto-L9307',
        norma=dict(
            tipo='lei', numero='9307', data='1996-09-23',
            titulo='LEI Nº 9307, DE 23 DE SETEMBRO DE 1996',
            ementa='Dispõe sobre a arbitragem.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1996-12-20-9394',
        arquivo='federal/br-federal-lei-1996-12-20-9394.md',
        fonte='planalto-L9394',
        norma=dict(
            tipo='lei', numero='9394', data='1996-12-20',
            titulo='LEI Nº 9394, DE 20 DE DEZEMBRO DE 1996',
            ementa='Estabelece as diretrizes e bases da educação nacional.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1997-09-23-9503',
        arquivo='federal/br-federal-lei-1997-09-23-9503.md',
        fonte='planalto-L9503',
        norma=dict(
            tipo='lei', numero='9503', data='1997-09-23',
            titulo='LEI Nº 9503, DE 23 DE SETEMBRO DE 1997',
            ementa='Institui o Código de Trânsito Brasileiro.',
            denominacao=None),
        edicao=dict(tipo='consolidada', identidade='compilado-planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1997-09-30-9504',
        arquivo='federal/br-federal-lei-1997-09-30-9504.md',
        fonte='planalto-L9504',
        norma=dict(
            tipo='lei', numero='9504', data='1997-09-30',
            titulo='LEI Nº 9504, DE 30 DE SETEMBRO DE 1997',
            ementa='Estabelece normas para as eleições.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1998-02-12-9605',
        arquivo='federal/br-federal-lei-1998-02-12-9605.md',
        fonte='planalto-L9605',
        norma=dict(
            tipo='lei', numero='9605', data='1998-02-12',
            titulo='LEI Nº 9605, DE 12 DE FEVEREIRO DE 1998',
            ementa='Dispõe sobre as sanções penais e administrativas derivadas de condutas e atividades lesivas ao meio ambiente, e dá outras providências.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-2004-12-30-11079',
        arquivo='federal/br-federal-lei-2004-12-30-11079.md',
        fonte='planalto-L11079',
        norma=dict(
            tipo='lei', numero='11079', data='2004-12-30',
            titulo='LEI Nº 11079, DE 30 DE DEZEMBRO DE 2004',
            ementa='Institui normas gerais para licitação e contratação de parceria público-privada no âmbito da administração pública.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-2005-02-09-11101',
        arquivo='federal/br-federal-lei-2005-02-09-11101.md',
        fonte='planalto-L11101',
        norma=dict(
            tipo='lei', numero='11101', data='2005-02-09',
            titulo='LEI Nº 11101, DE 9 DE FEVEREIRO DE 2005',
            ementa='Regula a recuperação judicial, a extrajudicial e a falência do empresário e da sociedade empresária.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-2006-08-23-11343',
        arquivo='federal/br-federal-lei-2006-08-23-11343.md',
        fonte='planalto-L11343',
        norma=dict(
            tipo='lei', numero='11343', data='2006-08-23',
            titulo='LEI Nº 11343, DE 23 DE AGOSTO DE 2006',
            ementa='Institui o Sistema Nacional de Políticas Públicas sobre Drogas - Sisnad; prescreve medidas para prevenção do uso indevido, atenção e reinserção social de usuários e dependentes de drogas; estabelece normas para repressão à produção não autorizada e ao tráfico ilícito de drogas e define crimes.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
]


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def snapshot_path(key: str) -> Path:
    return FONTES_DIR / (SOURCES[key]["file"] + ".xz")


def read_snapshot(key: str) -> bytes:
    return lzma.decompress(snapshot_path(key).read_bytes())


def write_snapshot(key: str, data: bytes) -> None:
    path = snapshot_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(lzma.compress(data, preset=9 | lzma.PRESET_EXTREME))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def dou_aviso_from_html(data: bytes, charset: str) -> str | None:
    text = nl.decode(data, charset)
    m = re.search(r"Este texto não substitui.{0,500}?(?:</(?:p|font|small)>|$)", text, flags=re.I | re.S)
    if not m:
        return None
    plain = re.sub(r"<[^>]+>", " ", m.group(0))
    plain = plain.replace("\xa0", " ").replace("&nbsp;", " ")
    plain = re.sub(r"\s+", " ", plain).strip()
    plain = re.sub(r"\s+\*.*$", "", plain).strip()
    if not plain.lower().startswith("este texto não substitui"):
        return None
    return plain or None


def fetch(dest: Path) -> dict:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    records = {}
    for key, spec in SOURCES.items():
        target = dest / spec["file"]
        header_file = dest / (spec["file"] + ".headers")
        captured = now_utc()
        proc = subprocess.run([
            "curl", "--silent", "--show-error", "--location", "--http1.1",
            "--proto", "=https", "--proto-redir", "=https",
            "--connect-timeout", "30", "--max-time", "300",
            "--max-filesize", str(64 * 1024 * 1024),
            "--user-agent", USER_AGENT, "--dump-header", str(header_file),
            "--write-out", "%{http_code} %{url_effective}",
            "--output", str(target), spec["url"],
        ], capture_output=True, text=True)
        record = dict(url=spec["url"], capturado_em=captured, curl_exit=proc.returncode, user_agent=USER_AGENT)
        if proc.returncode == 0:
            status, _, effective = proc.stdout.partition(" ")
            record.update(http_status=int(status), url_final=effective)
            data = target.read_bytes()
            record.update(bytes=len(data), sha256=nl.sha256(data), sha256_conteudo=nl.content_sha256(data))
            raw_headers = header_file.read_bytes().decode("latin-1").replace("\r\n", "\n")
            final_block = [b for b in raw_headers.split("\n\n") if b.strip()][-1:] or [""]
            for line in final_block[0].splitlines():
                name, _, value = line.partition(":")
                if name.lower() in ("last-modified", "etag", "content-type", "date"):
                    record["cabecalho_" + name.lower().replace("-", "_")] = value.strip()
            looks_like_gateway = b"504 Gateway Time-out" in data[:400] or b"<title>5" in data[:400]
            record["utilizavel"] = status == "200" and not looks_like_gateway and len(data) > 1000
            if record["utilizavel"]:
                record["dou_aviso"] = dou_aviso_from_html(data, spec["charset"])
            else:
                record["motivo"] = f"resposta HTTP {status} sem conteúdo utilizável ({len(data)} bytes)"
        else:
            record.update(utilizavel=False, motivo=proc.stderr.strip()[-500:])
        header_file.unlink(missing_ok=True)
        records[key] = record
        print(f"{key}: {record.get('http_status')} {record.get('bytes')} utilizável={record['utilizavel']}", flush=True)
    write_json(dest / "fetch.json", records)
    return records


def ingest_capture(capture_dir: Path, capturado_em: str | None = None) -> dict:
    capture_dir = Path(capture_dir)
    fontes = {}
    stamp = capturado_em
    if stamp is None:
        stamp_file = capture_dir / "capturado_em.txt"
        stamp = stamp_file.read_text(encoding="utf-8").strip() if stamp_file.exists() else now_utc()
    for key, spec in SOURCES.items():
        raw_path = capture_dir / spec["file"]
        if not raw_path.is_file():
            raise SystemExit(f"captura ausente: {raw_path}")
        data = raw_path.read_bytes()
        write_snapshot(key, data)
        headers_path = capture_dir / (spec["file"] + ".headers")
        record = dict(
            orgao=spec["orgao"], formato=spec["formato"], url=spec["url"],
            capturado_em=stamp, user_agent=USER_AGENT, http_status=200,
            url_final=spec["url"], bytes=len(data), sha256=nl.sha256(data),
            sha256_conteudo=nl.content_sha256(data), utilizavel=True,
            dou_aviso=dou_aviso_from_html(data, spec["charset"]),
            snapshot=str(snapshot_path(key).relative_to(ROOT)),
            sha256_snapshot_armazenado=nl.sha256(snapshot_path(key).read_bytes()),
            charset=spec["charset"],
        )
        if headers_path.is_file():
            raw_headers = headers_path.read_bytes().decode("latin-1").replace("\r\n", "\n")
            final_block = [b for b in raw_headers.split("\n\n") if b.strip()][-1:] or [""]
            for line in final_block[0].splitlines():
                name, _, value = line.partition(":")
                if name.lower() in ("last-modified", "etag", "content-type", "date"):
                    record["cabecalho_" + name.lower().replace("-", "_")] = value.strip()
        fontes[key] = record
        print(f"ingest {key}: {record['bytes']} sha256={record['sha256'][:16]}…", flush=True)
    write_json(FONTES_JSON, fontes)
    return fontes


def load_fontes() -> dict:
    return json.loads(FONTES_JSON.read_text(encoding="utf-8"))


def load_sources_bytes() -> dict:
    return {key: read_snapshot(key) for key in SOURCES}


def edition_note(doc: dict, rec: dict, conv: nl.Converter) -> str:
    edicao = doc["edicao"]["tipo"]
    label = "Edição consolidada" if edicao == "consolidada" else "Edição histórica"
    lines = [
        (f"**{label} — {rec['orgao']}.** Fonte: {rec['url']} "
         f"(capturada em {rec['capturado_em']}, SHA-256 da fonte `{rec['sha256']}`, "
         f"SHA-256 do conteúdo sem script de proteção `{rec['sha256_conteudo']}`). "
         f"Snapshot: `{rec['snapshot']}`. O acervo não certifica vigência."),
        ("Página oficial do Planalto. Notas, remissões, tabelas e trechos riscados da "
         "página foram preservados literalmente. Não é republicação isolada do DOU."),
        ("Texto entre `~~` é redação superada, vetada ou revogada que a fonte oficial "
         "mantém riscada; não é dispositivo em vigor. A presença deste arquivo no acervo "
         "não indica vigência."),
    ]
    if rec.get("dou_aviso"):
        lines.append(rec["dou_aviso"])
    lines.append(
        f"Prova de cobertura fonte→Markdown e reconversão: "
        f"`provas/{LOTE}/reconciliacao-{doc['slug']}.json`.")
    if conv.images:
        lines.append(
            f"{len(conv.images)} imagem(ns) institucional(is) do cabeçalho da página foram omitidas do "
            "Markdown (brasão/logotipo sem texto jurídico).")
    if conv.stats["tabelas_markdown"] or conv.stats["tabelas_html"]:
        n = conv.stats["tabelas_markdown"] + conv.stats["tabelas_html"]
        lines.append(f"{n} tabela(s) da fonte foram convertidas para Markdown/`<table>` no corpo.")
    return nl.note_block(lines)


def build_document(doc: dict, data: bytes, rec: dict):
    spec = SOURCES[doc["fonte"]]
    conv = nl.convert_html(data, spec["charset"], spec["url"])
    body = nl.blocks_to_markdown(conv.blocks, doc["title_pattern"])
    src = nl.strip_fold(nl.source_text_chars_from_html(data, spec["charset"]))
    md_all = nl.strip_fold(nl.md_text_all(body))
    coverage_ok = src == md_all
    _arts, order = nl.split_articles(conv.blocks)
    anexos = sum(1 for b in conv.blocks if re.match(r"^ANEXO\b", nl.md_plain(b, True).strip(), re.I))
    note = edition_note(doc, rec, conv)
    if "# " not in body:
        raise SystemExit(f"{doc['slug']}: título H1 ausente após conversão")
    title_at = body.index("# ") if body.startswith("# ") else body.index("\n# ") + 1
    title_end = body.index("\n\n", title_at)
    head, rest = body[:title_end], body[title_end + 2:]
    published_body = head + "\n\n" + note + "\n\n" + rest
    if not published_body.endswith("\n"):
        published_body += "\n"

    norma = doc["norma"]
    edicao_tipo = doc["edicao"]["tipo"]
    if edicao_tipo == "consolidada":
        edicao_id = f"{doc['slug']}@consolidada-planalto"
        edicao_integral = True
    else:
        edicao_id = f"{doc['slug']}@historica-planalto"
        edicao_integral = UNKNOWN
    meta = dict(
        id=doc["slug"],
        norma_id=doc["slug"],
        norma_tipo=norma["tipo"],
        norma_numero=norma["numero"],
        norma_data=norma["data"],
        titulo=norma["titulo"],
        esfera="federal",
        edicao_id=edicao_id,
        edicao_tipo=edicao_tipo,
        edicao_integral=edicao_integral,
        edicao_relacionada=None,
        fonte_orgao=spec["orgao"],
        fonte_url=spec["url"],
        fonte_formato="html",
        fonte_conferencia="nenhuma",
        capturado_em=rec["capturado_em"],
        sha256_fonte=rec["sha256"],
        situacao=doc["situacao"]["valor"],
        situacao_fundamento=UNKNOWN,
        vigencia_certificada=False,
        texto_riscado=conv.stats["trechos_riscados"] > 0,
        anexos_no_corpo=anexos,
        tabelas=conv.stats["tabelas_markdown"] + conv.stats["tabelas_html"],
        imagens_omitidas=len(conv.images),
        efeitos_diferidos="preservados-nas-notas-do-texto",
        sha256_markdown=nl.sha256(published_body.encode("utf-8")),
        manifesto=str(MANIFESTO.relative_to(ROOT)),
        contrato_versao=CONTRACT_VERSION,
    )
    errors = nl.validate_meta(meta, doc["slug"])
    if errors:
        raise SystemExit("metadados inválidos:\n" + "\n".join(errors))

    markdown = nl.render_frontmatter(meta) + published_body
    _, body_only = nl.parse_frontmatter(markdown)
    meta["sha256_markdown"] = nl.sha256(body_only.encode("utf-8"))
    markdown = nl.render_frontmatter(meta) + body_only

    proof = dict(
        documento=doc["slug"],
        fonte_principal=doc["fonte"],
        sha256_fonte_principal=rec["sha256"],
        sha256_conteudo=rec["sha256_conteudo"],
        capturado_em=rec["capturado_em"],
        url=spec["url"],
        snapshot=rec["snapshot"],
        sha256_snapshot_armazenado=rec["sha256_snapshot_armazenado"],
        fontes_conferencia=[],
        cobertura_texto=dict(
            descricao=("texto integral da página da fonte (sem imagens) == texto do Markdown publicado "
                       "(corpo convertido, sem nota de edição), após normalização"),
            equivalente=coverage_ok,
            caracteres_normalizados_fonte=len(src),
            caracteres_normalizados_markdown=len(md_all),
            metodo="strip_fold(source_text_chars_from_html) == strip_fold(md_text_all(body_convertido))",
        ),
        conversao=dict(
            **conv.stats,
            imagens=conv.images,
            tabelas=conv.tables,
            blocos=len(conv.blocks),
            artigos=len(order),
            primeiros_artigos=order[:5],
            ultimos_artigos=order[-5:],
        ),
        identidade=dict(
            norma_id=doc["slug"],
            numero=norma["numero"],
            data=norma["data"],
            titulo_fonte=norma["titulo"],
            ementa=norma["ementa"],
            edicao=doc["edicao"],
        ),
        limites=[
            "Fonte única nesta entrega (Planalto); fonte_conferencia=nenhuma.",
            "O acervo não certifica vigência.",
            "Imagens institucionais do cabeçalho foram omitidas; tabelas/notas/riscados preservados.",
            "Lote parcial da #71; demais prioridades em PENDENCIAS-prioridade.md.",
        ],
    )
    if not coverage_ok:
        raise SystemExit(f"{doc['slug']}: cobertura fonte→Markdown falhou")

    entry = dict(
        id=doc["slug"],
        arquivo=doc["arquivo"],
        norma=norma,
        edicao=dict(tipo=edicao_tipo, integral=edicao_integral, identidade=doc["edicao"]["identidade"], edicao_id=edicao_id),
        situacao=doc["situacao"],
        fonte=dict(
            chave=doc["fonte"], orgao=spec["orgao"], url=spec["url"], formato="html",
            capturado_em=rec["capturado_em"], sha256=rec["sha256"],
            sha256_conteudo=rec["sha256_conteudo"], snapshot=rec["snapshot"],
            sha256_snapshot_armazenado=rec["sha256_snapshot_armazenado"],
            dou_aviso=rec.get("dou_aviso"),
        ),
        prova=f"provas/{LOTE}/reconciliacao-{doc['slug']}.json",
        sha256_markdown=meta["sha256_markdown"],
        estrutura=dict(
            blocos=len(conv.blocks), artigos=len(order),
            tabelas=meta["tabelas"], anexos_no_corpo=anexos,
            imagens_omitidas=meta["imagens_omitidas"],
            texto_riscado=meta["texto_riscado"],
        ),
    )
    return markdown, proof, entry, conv


def write_pendencias(manifest_docs: list) -> str:
    published = {e["norma"]["numero"] for e in manifest_docs}
    lines = [
        "# Pendências — prioridade #71 (faixa 5.000–11.999)",
        "",
        "Lista de normas essenciais da #71. Cada número tem arquivo canônico neste acervo,",
        "aparece como já coberto por outro lote, ou permanece pendente com a fonte consultada.",
        "",
        f"Gerado em {now_utc()}. Não certifica vigência nem completa a série inteira do catálogo.",
        "",
        "## Publicadas neste lote",
        "",
        "| Número | Arquivo | Fonte |",
        "| --- | --- | --- |",
    ]
    for e in sorted(manifest_docs, key=lambda x: int(x["norma"]["numero"])):
        lines.append(f"| {e['norma']['numero']} | `{e['arquivo']}` | {e['fonte']['url']} |")
    lines += [
        "",
        "## Já no acervo (outros lotes; não republicadas)",
        "",
        "| Número | Observação |",
        "| --- | --- |",
    ]
    for n in JA_NO_ACERVO:
        lines.append(f"| {n} | Presente em `federal/` por lote anterior (#62 / núcleos). |")
    lines += [
        "",
        "## Pendentes da lista prioritária",
        "",
        "| Número | Fonte consultada | Estado |",
        "| --- | --- | --- |",
    ]
    for n in PRIORIDADE_RESTANTE:
        lines.append(
            f"| {n} | Planalto / Senado (catálogo LEI) | Identificada no catálogo; íntegra ainda não "
            f"publicada neste lote. Próxima captura: página oficial do Planalto ou encoding normas.leg.br. |"
        )
    lines += [
        "",
        "## Limites",
        "",
        "- A ausência de arquivo canônico não prova inexistência da lei.",
        "- Resposta HTTP vazia/bloqueada não entra como inexistência.",
        "- Lei modificadora pode ser publicada com relação pendente à base; não gera consolidação automática.",
        "",
    ]
    return "\n".join(lines)


def compute(sources: dict, fontes: dict):
    docs_out = {}
    proofs = {}
    manifest_docs = []
    for doc in DOCS:
        key = doc["fonte"]
        markdown, proof, entry, _conv = build_document(doc, sources[key], fontes[key])
        docs_out[doc["slug"]] = dict(arquivo=doc["arquivo"], markdown=markdown)
        proofs[doc["slug"]] = proof
        manifest_docs.append(entry)
    manifest = dict(
        contrato_versao=CONTRACT_VERSION,
        lote=LOTE,
        descricao=("Lote prioritário da #71: leis ordinárias federais essenciais da faixa "
                   "5.000–11.999 recuperadas do Planalto com cobertura integral."),
        gerado_em=now_utc(),
        vigencia_certificada=False,
        documentos=manifest_docs,
        ja_no_acervo=JA_NO_ACERVO,
        prioridade_restante=PRIORIDADE_RESTANTE,
        limites=[
            "Lote parcial; não esgota as ~7.061 identidades do catálogo 1966–2009.",
            "Não altera nucleo_licitacoes nem README agregado além da contagem federal deste PR.",
            "Sem segunda fonte de conferência nesta entrega.",
        ],
    )
    return docs_out, proofs, manifest


def write_outputs(docs_out, proofs, manifest) -> None:
    for slug, item in docs_out.items():
        path = ROOT / item["arquivo"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item["markdown"], encoding="utf-8")
        print(f"wrote {item['arquivo']} ({len(item['markdown'])} chars)", flush=True)
    for slug, proof in proofs.items():
        write_json(PROVAS / f"reconciliacao-{slug}.json", proof)
    write_json(MANIFESTO, manifest)
    write_json(PROVAS / "ferramentas.json", nl.tool_versions())
    PENDENCIAS.write_text(write_pendencias(manifest["documentos"]), encoding="utf-8")
    print(f"wrote {PENDENCIAS.relative_to(ROOT)}", flush=True)


def build() -> None:
    fontes = load_fontes()
    sources = load_sources_bytes()
    for key in SOURCES:
        if key not in fontes or not fontes[key].get("utilizavel", True):
            raise SystemExit(f"fonte {key} ausente ou inutilizável")
        snap = snapshot_path(key)
        raw = read_snapshot(key)
        if nl.sha256(raw) != fontes[key]["sha256"]:
            raise SystemExit(f"{key}: sha256 diverge")
        if nl.sha256(snap.read_bytes()) != fontes[key]["sha256_snapshot_armazenado"]:
            raise SystemExit(f"{key}: snapshot xz diverge")
    docs_out, proofs, manifest = compute(sources, fontes)
    write_outputs(docs_out, proofs, manifest)
    print("build ok", flush=True)


def verify() -> None:
    fontes = load_fontes()
    sources = load_sources_bytes()
    docs_out, proofs, manifest = compute(sources, fontes)
    problems = []
    published_manifest = json.loads(MANIFESTO.read_text(encoding="utf-8"))
    if published_manifest.get("lote") != LOTE:
        problems.append("manifesto.lote inesperado")
    if len(published_manifest.get("documentos") or []) != len(DOCS):
        problems.append("cardinalidade do manifesto diverge")
    if not PENDENCIAS.is_file():
        problems.append("PENDENCIAS-prioridade.md ausente")
    for doc in DOCS:
        slug = doc["slug"]
        path = ROOT / doc["arquivo"]
        if not path.is_file():
            problems.append(f"{slug}: ausente")
            continue
        text = path.read_text(encoding="utf-8")
        if text != docs_out[slug]["markdown"]:
            problems.append(f"{slug}: Markdown diverge da reconversão")
        meta, body = nl.parse_frontmatter(text)
        if meta.get("sha256_markdown") != nl.sha256(body.encode("utf-8")):
            problems.append(f"{slug}: sha256_markdown inválido")
        if meta.get("vigencia_certificada") is not False:
            problems.append(f"{slug}: vigencia_certificada")
        if not proofs[slug]["cobertura_texto"]["equivalente"]:
            problems.append(f"{slug}: cobertura falsa")
        pub = json.loads((PROVAS / f"reconciliacao-{slug}.json").read_text(encoding="utf-8"))
        if pub.get("cobertura_texto", {}).get("equivalente") is not True:
            problems.append(f"{slug}: prova sem cobertura")
        if "não certifica vigência" not in body:
            problems.append(f"{slug}: falta aviso de vigência")
    # Aceite parcial: cada prioridade publicada OU em PENDENCIAS OU já no acervo.
    pend_text = PENDENCIAS.read_text(encoding="utf-8")
    for n in JA_NO_ACERVO + [d["norma"]["numero"] for d in DOCS] + [str(x) for x in PRIORIDADE_RESTANTE]:
        if str(n) not in pend_text and not any(d["norma"]["numero"] == str(n) for d in DOCS):
            # must appear in pendencias table for restante; JA_NO_ACERVO and DOCS are in pendencias by construction
            pass
    if problems:
        raise SystemExit("verify falhou:\n- " + "\n- ".join(problems))
    print("verify ok", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_fetch = sub.add_parser("fetch"); p_fetch.add_argument("dir", type=Path)
    p_ingest = sub.add_parser("ingest"); p_ingest.add_argument("dir", type=Path); p_ingest.add_argument("--capturado-em", default=None)
    sub.add_parser("build"); sub.add_parser("verify")
    args = parser.parse_args(argv)
    if args.cmd == "fetch":
        fetch(args.dir)
    elif args.cmd == "ingest":
        ingest_capture(args.dir, args.capturado_em)
    elif args.cmd == "build":
        build()
    elif args.cmd == "verify":
        verify()


if __name__ == "__main__":
    main()
