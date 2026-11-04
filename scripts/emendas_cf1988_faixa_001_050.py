#!/usr/bin/env python3
"""Lote faixa 001–050: emendas da CF/1988 ausentes (issue #63).

Recupera textos autônomos (publicação original Câmara), com snapshots e
reconversão. Reusa convert_html/coverage de nucleo_licitacoes sem editá-lo.
Não certifica vigência. Planalto é conferência quando a captura existir.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import lzma
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

from nucleo_licitacoes import (  # noqa: E402
    compare_articles,
    convert_html,
    coverage,
    md_plain,
    sha256,
    split_articles,
    strip_fold,
    write_json,
)

PROVAS = ROOT / 'provas' / 'emendas-cf1988' / 'faixa-001-050'
FONTES_DIR = PROVAS / 'fontes'
CATALOGO_PATH = PROVAS / 'catalogo-lote.json'
FONTES_PATH = PROVAS / 'fontes.json'
MATRIZ_PATH = PROVAS / 'matriz-lote.json'
COBERTURA_PATH = PROVAS / 'cobertura-conversao.json'
RECONC_PATH = PROVAS / 'reconciliacao-camara-planalto.json'
FEDERAL = ROOT / 'federal'

UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
TITLE_PAT = re.compile(r'^EMENDA CONSTITUCIONAL Nº\s*(\d+)\b', re.I)


def load_catalogo() -> list[dict]:
    return json.loads(CATALOGO_PATH.read_text())


def load_fontes() -> dict:
    return json.loads(FONTES_PATH.read_text())


def camara_key(n: int) -> str:
    return f'camara-ec-{n:03d}-publicacaooriginal'


def planalto_key(n: int) -> str:
    return f'planalto-ec-{n:03d}'


def published_path(item: dict) -> Path:
    return FEDERAL / f"br-federal-emenda-constitucional-{item['data']}-{item['numero']}.md"


def read_snapshot(rel_or_key_path: str) -> bytes:
    path = ROOT / rel_or_key_path
    data = path.read_bytes()
    if path.suffix == '.xz' or str(path).endswith('.xz'):
        return lzma.decompress(data)
    return data


def trim_ec_blocks(blocks: list[str], numero: int) -> list[str]:
    """Mantém título da EC até as assinaturas; exclui rodapé de publicação da página."""
    title_re = re.compile(rf'^EMENDA CONSTITUCIONAL Nº\s*{numero}\b', re.I)
    start = None
    for i, block in enumerate(blocks):
        plain = md_plain(block, True).strip()
        if title_re.match(plain):
            # evita o breadcrumb "Legislação Informatizada - EMENDA..."
            if 'Legislação Informatizada' in plain:
                continue
            start = i
            break
    if start is None:
        raise RuntimeError(f'EC {numero}: título não encontrado nos blocos convertidos')

    end = None
    for i in range(start + 1, len(blocks)):
        plain = md_plain(blocks[i], True).strip()
        if re.match(r'^Este texto não substitui', plain, re.I):
            end = i
            break
        if re.match(r'^Publicação\s*:', plain, re.I):
            end = i
            break
        if re.match(r'^Diário Oficial da União', plain, re.I):
            end = i
            break
        if re.match(r'^Diário do (?:Senado|Congresso|Câmara)', plain, re.I):
            end = i
            break
        if re.match(r'^Coleção de Leis do Brasil', plain, re.I):
            end = i
            break
    if end is None:
        bras = next(
            (i for i, b in enumerate(blocks)
             if i >= start and md_plain(b, True).startswith('Brasília')),
            None,
        )
        end = min(len(blocks), (bras + 40) if bras is not None else start + 80)
    out = blocks[start:end]
    if not out:
        raise RuntimeError(f'EC {numero}: recorte vazio')
    # identidade
    head = md_plain(out[0], True)
    m = TITLE_PAT.match(head)
    if not m or int(m.group(1)) != numero:
        raise RuntimeError(f'EC {numero}: identidade do título falhou: {head[:120]!r}')
    joined = '\n'.join(md_plain(b, True) for b in out)
    if re.search(r'EMENDA CONSTITUCIONAL DE REVIS', joined, re.I):
        raise RuntimeError(f'EC {numero}: texto parece Emenda de Revisão')
    # Fecho: Brasília (maioria) ou apenas Mesas/assinaturas (ex.: EC 43 na Câmara)
    has_fecho = (
        re.search(r'^Brasília,', joined, re.M) is not None
        or re.search(r'Mesa da Câmara dos Deputados', joined, re.I) is not None
    )
    if not has_fecho:
        raise RuntimeError(f'EC {numero}: fecho (Brasília/Mesas) ausente no recorte')
    if not re.search(r'(?:Art\.|Artigo)\s*', joined, re.I):
        raise RuntimeError(f'EC {numero}: nenhum artigo no recorte')
    return out


def convert_camara(item: dict, fontes: dict) -> tuple[list[str], str]:
    n = item['numero']
    key = camara_key(n)
    rec = fontes[key]
    if not rec.get('utilizavel') or not rec.get('snapshot'):
        raise RuntimeError(f'EC {n}: fonte Câmara indisponível')
    data = read_snapshot(rec['snapshot'])
    conv = convert_html(data, rec.get('charset') or 'utf-8', rec['url'])
    blocks = trim_ec_blocks(conv.blocks, n)
    body = '\n\n'.join(blocks) + '\n'
    if not coverage(blocks, body):
        raise RuntimeError(f'EC {n}: coverage(blocks, markdown) falhou')
    return blocks, body


def identity_guards_ok(item: dict, body: str) -> list[str]:
    """Rejeita histórico/revisão e exige número/data no corpo."""
    errs = []
    n = item['numero']
    plain = md_plain(body, True)
    if not re.search(rf'EMENDA CONSTITUCIONAL Nº\s*{n}\b', plain, re.I):
        errs.append('número ausente no corpo')
    if re.search(r'EMENDA CONSTITUCIONAL DE REVIS', plain, re.I):
        errs.append('emenda de revisão')
    # data de promulgação (Brasília, D de mês de YYYY)
    year = item['data'][:4]
    if year not in plain:
        errs.append(f'ano {year} ausente')
    # arquivo não deve colidir com série histórica: data >= 1988
    if int(year) < 1988:
        errs.append('data pré-1988')
    return errs


def publish(item: dict, body: str) -> Path:
    path = published_path(item)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding='utf-8')
    return path


def cmd_convert(args: argparse.Namespace) -> int:
    fontes = load_fontes()
    catalogo = load_catalogo()
    matriz = json.loads(MATRIZ_PATH.read_text())
    by_n = {r['numero']: r for r in matriz['itens']}
    cobertura = {}
    reconc = {}
    published = []
    for item in catalogo:
        n = item['numero']
        print(f'convert EC {n}…', flush=True)
        try:
            blocks, body = convert_camara(item, fontes)
        except Exception as e:
            by_n[n]['situacao_coleta'] = 'pendente-conversao'
            by_n[n].setdefault('notas', []).append(f'Falha conversão: {e}')
            by_n[n].setdefault('riscos', []).append('Texto não inventado; permanece pendente.')
            cobertura[str(n)] = dict(ok=False, erro=str(e))
            continue
        errs = identity_guards_ok(item, body)
        if errs:
            by_n[n]['situacao_coleta'] = 'pendente-identidade'
            by_n[n].setdefault('notas', []).append('Identidade: ' + '; '.join(errs))
            cobertura[str(n)] = dict(ok=False, erro=errs)
            continue

        # Reconversão independente a partir do snapshot
        blocks2, body2 = convert_camara(item, fontes)
        if body2 != body:
            raise RuntimeError(f'EC {n}: reconversão divergiu do primeiro convert')

        path = publish(item, body)
        art_keys, art_order = split_articles(blocks)
        cobertura[str(n)] = dict(
            ok=True,
            arquivo=str(path.relative_to(ROOT)),
            blocos=len(blocks),
            chars=len(body),
            sha256_markdown=sha256(body.encode('utf-8')),
            artigos_detectados=art_order,
            coverage_blocos_markdown=True,
            reconversao_identica=True,
            fonte=camara_key(n),
            sha256_fonte=fontes[camara_key(n)]['sha256'],
        )

        # Conferência Planalto (quando snapshot existir)
        pk = planalto_key(n)
        prec = fontes.get(pk) or {}
        if prec.get('utilizavel') and prec.get('snapshot'):
            try:
                pdata = read_snapshot(prec['snapshot'])
                pconv = convert_html(pdata, prec.get('charset') or 'cp1252', prec['url'])
                try:
                    pblocks = trim_ec_blocks(pconv.blocks, n)
                except RuntimeError:
                    # Planalto às vezes embute o título em links/tabelas
                    start = next(
                        (i for i, b in enumerate(pconv.blocks)
                         if re.search(rf'EMENDA CONSTITUCIONAL Nº\s*{n}\b', md_plain(b, True), re.I)),
                        0,
                    )
                    bras = next(
                        (i for i, b in enumerate(pconv.blocks)
                         if i >= start and (
                             md_plain(b, True).startswith('Brasília')
                             or 'Mesa da Câmara' in md_plain(b, True)
                         )),
                        len(pconv.blocks) - 1,
                    )
                    pblocks = pconv.blocks[start:bras + 15]
                cmp = compare_articles(split_articles(blocks), split_articles(pblocks))
                reconc[str(n)] = dict(
                    ok=True,
                    camara=camara_key(n),
                    planalto=pk,
                    comparacao=cmp,
                    nota='Comparação artigo a artigo do texto autônomo; divergências tipográficas/editoriais podem existir sem invalidar a publicação Câmara.',
                )
            except Exception as e:
                reconc[str(n)] = dict(ok=False, erro=str(e), planalto=pk)
        else:
            reconc[str(n)] = dict(
                ok=False,
                pendente=True,
                erro=prec.get('erro') or 'snapshot Planalto ausente',
                nota='Acesso falho ≠ inexistência; publicação segue Câmara.',
            )

        by_n[n]['situacao_coleta'] = 'publicada'
        by_n[n]['arquivo'] = str(path.relative_to(ROOT))
        by_n[n]['sha256_markdown'] = cobertura[str(n)]['sha256_markdown']
        by_n[n]['vigencia_certificada'] = False
        published.append(n)
        print(f'  -> {path.name} ({len(body)} chars)')

    matriz['itens'] = [by_n[i['numero']] for i in catalogo]
    matriz['publicadas'] = published
    matriz['atualizado_em'] = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    write_json(MATRIZ_PATH, matriz)
    write_json(COBERTURA_PATH, cobertura)
    write_json(RECONC_PATH, reconc)
    print('publicadas', len(published), '/', len(catalogo))
    return 0 if len(published) == len(catalogo) else 1


def cmd_verify(args: argparse.Namespace) -> int:
    fontes = load_fontes()
    catalogo = load_catalogo()
    cobertura = json.loads(COBERTURA_PATH.read_text()) if COBERTURA_PATH.is_file() else {}
    errors = []

    # hashes dos snapshots
    for key, rec in fontes.items():
        snap = rec.get('snapshot')
        if not snap:
            continue
        path = ROOT / snap
        if not path.is_file():
            errors.append(f'{key}: snapshot ausente {snap}')
            continue
        got = sha256(path.read_bytes())
        exp = rec.get('sha256_snapshot_armazenado')
        if exp and got != exp:
            errors.append(f'{key}: sha256_snapshot divergente')
        raw = lzma.decompress(path.read_bytes()) if str(path).endswith('.xz') else path.read_bytes()
        if rec.get('sha256') and sha256(raw) != rec['sha256']:
            errors.append(f'{key}: sha256 do conteúdo divergente do manifesto')

    for item in catalogo:
        n = item['numero']
        path = published_path(item)
        if not path.is_file():
            errors.append(f'EC {n}: arquivo publicado ausente')
            continue
        body = path.read_text(encoding='utf-8')
        blocks, body2 = convert_camara(item, fontes)
        if body2 != body:
            errors.append(f'EC {n}: markdown publicado ≠ reconversão do snapshot')
        if not coverage(blocks, body):
            errors.append(f'EC {n}: coverage falhou')
        for err in identity_guards_ok(item, body):
            errors.append(f'EC {n}: {err}')
        # não confundir com histórico: nome do arquivo usa data >= 1988
        if int(item['data'][:4]) < 1988:
            errors.append(f'EC {n}: data inválida para série CF/1988')
        cov = cobertura.get(str(n)) or {}
        if cov.get('sha256_markdown') and sha256(body.encode()) != cov['sha256_markdown']:
            errors.append(f'EC {n}: sha256_markdown da cobertura desatualizado')

        # Duplicata só na série CF/1988 (ano >= 1988). Emendas históricas
        # (ex.: 1980) e de revisão usam outra identidade e não entram aqui.
        twins = []
        for p in FEDERAL.glob('br-federal-emenda-constitucional-*.md'):
            if p.resolve() == path.resolve():
                continue
            m = re.fullmatch(
                r'br-federal-emenda-constitucional-(\d{4})-\d{2}-\d{2}-(\d+)\.md',
                p.name,
            )
            if m and int(m.group(1)) >= 1988 and int(m.group(2)) == n:
                twins.append(p.name)
        if twins:
            errors.append(f'EC {n}: possível duplicata CF/1988 {twins}')

    if errors:
        print('VERIFY FAIL')
        for e in errors:
            print(' -', e)
        return 1
    print('VERIFY OK', len(catalogo), 'emendas')
    return 0


def cmd_check_absent(args: argparse.Namespace) -> int:
    """Confere ausência no tree atual (working tree = main base)."""
    catalogo = load_catalogo()
    missing_ok = []
    present = []
    for item in catalogo:
        n = item['numero']
        hits = []
        for p in FEDERAL.glob('br-federal-emenda-constitucional-*.md'):
            m = re.fullmatch(
                r'br-federal-emenda-constitucional-(\d{4})-\d{2}-\d{2}-(\d+)\.md', p.name)
            if m and int(m.group(1)) >= 1988 and int(m.group(2)) == n:
                hits.append(p.name)
        if hits:
            present.append((n, hits))
        else:
            missing_ok.append(n)
    print('ausentes (ok para publicar):', missing_ok)
    if present:
        print('JÁ PRESENTES:', present)
        return 1
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sp = ap.add_subparsers(dest='cmd', required=True)
    sp.add_parser('check-absent', help='Confirma ausência dos números CF/1988 no tree')
    sp.add_parser('convert', help='Converte snapshots Câmara → Markdown e publica')
    sp.add_parser('verify', help='Reconversão + hashes + identidade')
    args = ap.parse_args(argv)
    if args.cmd == 'check-absent':
        return cmd_check_absent(args)
    if args.cmd == 'convert':
        return cmd_convert(args)
    if args.cmd == 'verify':
        return cmd_verify(args)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
