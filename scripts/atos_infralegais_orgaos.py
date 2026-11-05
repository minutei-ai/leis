#!/usr/bin/env python3
"""Atos infralegais por órgão — issue #75."""
from __future__ import annotations

import hashlib
import json
import lzma
import re
import sys
from pathlib import Path

import nucleo_licitacoes as nl

ROOT = Path(__file__).resolve().parent.parent
PROVAS = ROOT / 'provas/atos-infralegais-orgaos'
MANIFEST = ROOT / 'metadados/atos-infralegais-orgaos.json'
SLUG_RDC = 'br-federal-rdc-anvisa-2002-02-21-50'
SLUG_RFB_V = 'br-federal-in-rfb-2022-10-17-2110'
SLUG_RFB_O = 'br-federal-in-rfb-2022-10-17-2110-original'
SLUG_CMN = 'br-federal-resolucao-cmn-2021-11-25-4966'
EXPECTED = [SLUG_RDC, SLUG_RFB_V, SLUG_RFB_O, SLUG_CMN]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_frontmatter(text: str):
    if not text.startswith('---\n'):
        raise ValueError('sem cabeçalho')
    end = text.index('\n---\n', 4)
    meta = {}
    for line in text[4:end].splitlines():
        key, _, value = line.partition(': ')
        meta[key] = json.loads(value)
    body = text[end + len('\n---\n'):]
    if body.startswith('\n'):
        body = body[1:]
    return meta, body


def verify_doc(errors: list[str], docs: dict, slug: str, norma_tipo: str, orgao: str) -> None:
    if slug not in docs:
        errors.append(f'{slug} ausente do manifesto')
        return
    doc = docs[slug]
    path = ROOT / doc['arquivo']
    if not path.is_file():
        errors.append(f'{slug}: arquivo ausente')
        return
    text = path.read_text(encoding='utf-8')
    meta, body = parse_frontmatter(text)
    if meta.get('norma_tipo') != norma_tipo:
        errors.append(f'{slug}: norma_tipo deve ser {norma_tipo}')
    if meta.get('orgao_emissor') != orgao:
        errors.append(f'{slug}: orgao_emissor deve ser {orgao}')
    if meta.get('vigencia_certificada') is not False:
        errors.append(f'{slug}: vigencia_certificada deve ser false')
    if sha256(body.encode('utf-8')) != meta.get('sha256_markdown'):
        errors.append(f'{slug}: sha256_markdown diverge')
    if not re.search(r'(?m)^Art\.\s*1', body):
        errors.append(f'{slug}: Art. 1 ausente')
    if orgao not in slug:
        errors.append(f'{slug}: órgão ausente do id')


def verify() -> list[str]:
    errors: list[str] = []
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    fontes = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
    if manifest.get('vigencia_certificada') is not False:
        errors.append('vigencia_certificada do manifesto deve ser false')
    for org in ('anvisa', 'rfb', 'cmn-bcb'):
        if org not in manifest.get('catalogo_orgaos', {}):
            errors.append(f'catalogo_orgaos.{org} ausente')
        else:
            cat = manifest['catalogo_orgaos'][org]
            if not cat.get('fontes_oficiais'):
                errors.append(f'{org}: fontes_oficiais vazias')
            if not cat.get('ainda_nao_inventariado'):
                errors.append(f'{org}: ainda_nao_inventariado ausente')
            if cat.get('cobertura_completa'):
                errors.append(f'{org}: não declarar cobertura_completa')

    docs = {d['id']: d for d in manifest.get('documentos') or []}
    if sorted(docs) != sorted(EXPECTED):
        errors.append(f'documentos esperados {EXPECTED}, obtidos {sorted(docs)}')

    verify_doc(errors, docs, SLUG_RDC, 'rdc', 'anvisa')
    verify_doc(errors, docs, SLUG_RFB_V, 'in', 'rfb')
    verify_doc(errors, docs, SLUG_RFB_O, 'in', 'rfb')
    verify_doc(errors, docs, SLUG_CMN, 'resolucao-cmn', 'cmn')

    # RDC specifics
    if SLUG_RDC in docs:
        path = ROOT / docs[SLUG_RDC]['arquivo']
        text = path.read_text(encoding='utf-8')
        meta, body = parse_frontmatter(text)
        if meta.get('tabelas', 0) < 40:
            errors.append('esperadas dezenas de tabelas da RDC 50')
        if 'fac-simile:inicio' not in body:
            errors.append('fac-símile normativo ausente do Markdown')
        if '<table' not in body and body.count('| ---') < 5:
            errors.append('RDC 50 sem tabelas pesquisáveis no Markdown')
        fig = PROVAS / 'fac-similes/rdc-anvisa-50-2002-fig1.jpg'
        if not fig.is_file():
            errors.append('arquivo do fac-símile ausente')
        else:
            fig_meta = fontes.get('fac_simile_rdc50_fig1') or {}
            if fig_meta.get('sha256') and sha256(fig.read_bytes()) != fig_meta['sha256']:
                errors.append('sha256 do fac-símile diverge')
        fonte = fontes.get('rdc50-anvisa-bvs')
        if not fonte:
            errors.append('fonte rdc50 ausente')
        else:
            snap = ROOT / fonte['snapshot']
            raw = lzma.decompress(snap.read_bytes())
            if sha256(raw) != fonte['sha256']:
                errors.append('snapshot HTML RDC diverge')
            conv = nl.convert_html(raw, fonte.get('charset') or 'latin-1', fonte['url'])
            recon = nl.blocks_to_markdown(conv.blocks, r'^RESOLUÇÃO')
            if not re.search(r'(?m)^Art\.\s*1', recon):
                errors.append('reconversão RDC sem Art. 1')
        rec = json.loads((PROVAS / f'reconciliacao-{SLUG_RDC}.json').read_text(encoding='utf-8'))
        audit = rec.get('auditoria_tabelas_diagrama') or {}
        if audit.get('soma_tabelas_pesquisaveis', 0) < 40:
            errors.append('auditoria RDC: tabelas pesquisáveis insuficientes')
        if not audit.get('conteudo_celulas_pesquisavel'):
            errors.append('auditoria RDC: células devem ser pesquisáveis')

    # RFB snapshots + distinct editions
    for key in ('rfb-2110-vigente-json', 'rfb-2110-original-json', 'rfb-2110-multivigente-json', 'rfb-2110-shell', 'rfb-2110-dou'):
        if key not in fontes:
            errors.append(f'{key} ausente de fontes.json')
            continue
        sp = ROOT / fontes[key]['snapshot']
        if not sp.is_file():
            errors.append(f'{key}: snapshot ausente')
        else:
            raw = lzma.decompress(sp.read_bytes())
            if sha256(raw) != fontes[key]['sha256']:
                errors.append(f'{key}: sha256 diverge')
    if SLUG_RFB_V in docs and SLUG_RFB_O in docs:
        v = (ROOT / docs[SLUG_RFB_V]['arquivo']).read_text(encoding='utf-8')
        o = (ROOT / docs[SLUG_RFB_O]['arquivo']).read_text(encoding='utf-8')
        mo, bo = parse_frontmatter(o)
        _, bv = parse_frontmatter(v)
        if bv == bo:
            errors.append('edições RFB vigente e original não devem ser idênticas')
        if 'sijut-vigente' not in v or 'sijut-original' not in o:
            errors.append('edicao_id SIJUT ausente nas INs RFB')
        if mo.get('visao_path') != 'original':
            errors.append('RFB original: visao_path deve ser original')
        if mo.get('visao_payload') != 'conjunta':
            errors.append('RFB original: path /original devolve visao_payload=conjunta (literal SIJUT)')
        if docs[SLUG_RFB_O].get('visao_payload') != 'conjunta':
            errors.append('manifesto RFB original: visao_payload conjunta ausente')
        orig_fonte = fontes.get('rfb-2110-original-json') or {}
        if orig_fonte.get('visao_payload') != 'conjunta':
            errors.append('fontes.json RFB original: visao_payload conjunta ausente')

    # CMN
    for key in ('cmn-4966-dou', 'cmn-4966-shell'):
        if key not in fontes:
            errors.append(f'{key} ausente de fontes.json')
            continue
        sp = ROOT / fontes[key]['snapshot']
        if not sp.is_file():
            errors.append(f'{key}: snapshot ausente')
        else:
            raw = lzma.decompress(sp.read_bytes())
            if sha256(raw) != fontes[key]['sha256']:
                errors.append(f'{key}: sha256 diverge')
    if SLUG_CMN in docs:
        text = (ROOT / docs[SLUG_CMN]['arquivo']).read_text(encoding='utf-8')
        if 'instrumento financeiro' not in text.lower():
            errors.append('CMN 4966 sem menção a instrumentos financeiros')
        if 'resolucao-cmn' not in text:
            errors.append('CMN sem norma_tipo resolucao-cmn no frontmatter')
        if docs[SLUG_CMN].get('edicao_tipo') != 'original':
            errors.append('CMN 4966 publicada deve ser edicao_tipo original (DOU)')

    # Residual access notes — never falso negativo
    pend = manifest.get('pendencias_acesso') or []
    if len(pend) < 1:
        errors.append('pendencias residuais de acesso (BCB SPA / SIJUT shell) ausentes')
    for p in pend:
        if p.get('estado_acesso') in (None, 'inexistente'):
            errors.append(f"{p.get('tema') or p.get('slug_previsto')}: estado_acesso inválido")
        leitura = p.get('leitura', '')
        if 'inexist' not in leitura.lower():
            errors.append(f"{p.get('tema') or p.get('slug_previsto')}: leitura deve negar inexistência por falha de acesso")

    escopo = manifest.get('escopo') or {}
    if escopo.get('nao_cataloga_como_cobertura_completa') is not True and escopo.get('estado') != 'parcial':
        errors.append('escopo deve declarar parcialidade / não-cobertura completa')

    # Critério: catálogos com paginação/período + IDs/estados
    cat_ptr = manifest.get('catalogos_paginacao') or (fontes.get('catalogos_paginacao') or {}).get('arquivo')
    if not cat_ptr:
        errors.append('ponteiro catalogos_paginacao ausente do manifesto')
    else:
        cat_path = ROOT / cat_ptr
        if not cat_path.is_file():
            errors.append('catalogos-orgaos-paginacao.json ausente')
        else:
            cats = json.loads(cat_path.read_text(encoding='utf-8'))
            for org in ('anvisa', 'rfb', 'cmn-bcb'):
                if org not in (cats.get('por_orgao') or {}):
                    errors.append(f'catálogo paginado sem órgão {org}')
            rfb_cat = ((cats.get('por_orgao') or {}).get('rfb') or {}).get('fontes_catalogo') or []
            idx = next(
                (
                    f
                    for f in rfb_cat
                    if 'indexa' in (f.get('sistema') or '').lower()
                    or 'pesquisar' in (f.get('url') or '').lower()
                ),
                None,
            )
            if not idx:
                errors.append('RFB: fonte de indexação/paginação ausente do catálogo')
            else:
                if not idx.get('paginacao_parametros_tentados'):
                    errors.append('RFB: parâmetros de paginação/período ausentes')
                if not idx.get('ids_oficiais_preservados'):
                    errors.append('RFB: IDs oficiais ausentes do catálogo')
                if not idx.get('estado_acesso'):
                    errors.append('RFB: estado_acesso do catálogo ausente')
                leitura_idx = (idx.get('leitura') or '').lower()
                if 'inexist' not in leitura_idx:
                    errors.append('RFB: leitura do catálogo deve negar inexistência por lista vazia')
            anvisa_cat = ((cats.get('por_orgao') or {}).get('anvisa') or {}).get('fontes_catalogo') or []
            if not any(f.get('estado_acesso') == 'http-403' for f in anvisa_cat):
                errors.append('ANVISA: estado http-403 do índice deve estar registrado (≠ inexistência)')
            cmn_cat = ((cats.get('por_orgao') or {}).get('cmn-bcb') or {}).get('fontes_catalogo') or []
            if not any(f.get('estado_acesso') == 'shell-javascript' for f in cmn_cat):
                errors.append('CMN/BCB: shell-javascript deve constar do catálogo')

    # Critério: diferenças de edição RFB + CMN DOU ≠ BCB
    dif_ptr = manifest.get('diferencas_edicoes') or (fontes.get('diferencas_edicoes') or {}).get('arquivo')
    if not dif_ptr:
        errors.append('ponteiro diferencas_edicoes ausente')
    else:
        dif_path = ROOT / dif_ptr
        if not dif_path.is_file():
            errors.append('diferencas-edicoes-rfb-cmn.json ausente')
        else:
            dif = json.loads(dif_path.read_text(encoding='utf-8'))
            rfb = dif.get('rfb_2110') or {}
            vars_ = rfb.get('variantes') or {}
            for key in ('original_path', 'vigente', 'multivigente'):
                if key not in vars_:
                    errors.append(f'RFB: variante {key} ausente de diferencas-edicoes')
            hashes = {
                (vars_.get('original_path') or {}).get('sha256_segmentos'),
                (vars_.get('vigente') or {}).get('sha256_segmentos'),
                (vars_.get('multivigente') or {}).get('sha256_segmentos'),
            }
            if None in hashes or len(hashes) < 3:
                errors.append('RFB: hashes de segmentos das três visões devem ser distintos')
            if rfb.get('diferenca_markdown_original_vs_vigente') is not True:
                errors.append('RFB: diferença markdown original vs vigente deve ser explícita')
            if len(rfb.get('modificadores_no_historico_sijut') or []) < 3:
                errors.append('RFB: histórico SIJUT deve listar ao menos 3 modificadores literais')
            cmn = dif.get('cmn_4966') or {}
            if cmn.get('equivalencia') is not False:
                errors.append('CMN: equivalencia DOU↔BCB deve ser false')
            if (cmn.get('edicao_publicada') or {}).get('tipo') != 'original':
                errors.append('CMN: edição publicada deve ser original DOU')
            if (cmn.get('edicao_nao_recuperada') or {}).get('tipo') != 'consolidada':
                errors.append('CMN: consolidada BCB deve constar como não recuperada')
            leitura_cmn = (cmn.get('leitura') or '').lower()
            if 'não equivale' not in leitura_cmn and 'nao equivale' not in leitura_cmn and '≠' not in (cmn.get('leitura') or ''):
                errors.append('CMN: leitura deve declarar DOU ≠ consolidada BCB')

    # Critério: relações / efeitos com desconhecidos explícitos
    relacoes = manifest.get('relacoes') or []
    if len(relacoes) < 5:
        errors.append(f'relacoes insuficientes ({len(relacoes)}); esperado ≥5')
    rel_tipos = {r.get('tipo') for r in relacoes}
    for required in ('alteracao', 'variante-edicao', 'edicao-nao-equivalente'):
        if required not in rel_tipos:
            errors.append(f'relação obrigatória ausente: {required}')
    for r in relacoes:
        if not r.get('desconhecidos'):
            errors.append(f"{r.get('id')}: desconhecidos explícitos ausentes")
        if not (r.get('fonte') or r.get('leitura')):
            errors.append(f"{r.get('id')}: evidência/fonte ausente")

    # Critério: classificação normativa vs notícia/consulta/ato individual
    class_ptr = manifest.get('classificacao_fontes') or (fontes.get('classificacao_fontes') or {}).get('arquivo')
    if not class_ptr:
        errors.append('ponteiro classificacao_fontes ausente')
    else:
        class_path = ROOT / class_ptr
        if not class_path.is_file():
            errors.append('classificacao-fontes-orgaos.json ausente')
        else:
            clf = json.loads(class_path.read_text(encoding='utf-8'))
            if len(clf.get('incluidos_como_normativos_neste_lote') or []) < 4:
                errors.append('classificação: documentos normativos insuficientes')
            excl = {e.get('tipo') for e in (clf.get('excluidos_explicitamente') or [])}
            for tipo in ('consulta-publica', 'noticia', 'ato-individual', 'resolucao-bcb-ou-comunicado-mesmo-numero'):
                if tipo not in excl:
                    errors.append(f'classificação: exclusão {tipo} ausente')

    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] != 'verify':
        print('uso: atos_infralegais_orgaos.py verify', file=sys.stderr)
        return 2
    errors = verify()
    if errors:
        for e in errors:
            print('ERRO:', e, file=sys.stderr)
        return 1
    print('OK: atos infralegais por órgão conferidos')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
