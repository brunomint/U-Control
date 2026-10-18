"""Converte uma Bíblia em USFM (eBible.org) pro formato do U-Control:
lista de 66 livros {abbrev, name, chapters: [[versículo, ...], ...]}.

Usado pra Bíblia Livre (porbr2018) e Nova Bíblia Viva (poronbv), ambas de
licença aberta. Só use com traduções livres (ou com licença da editora).

    curl -LO https://ebible.org/Scriptures/porbr2018_usfm.zip && unzip -d usfm porbr2018_usfm.zip
    python3 -I scripts/usfm_para_json.py usfm bibles/books_metadata.json bibles/blivre.json

Depois cadastre a tradução em bibles/books_metadata.json ("translations",
com "credit" se a licença pedir atribuição)."""
import json, re, sys, glob, os

IDS = ("GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SNG "
       "ISA JER LAM EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL MAT MRK LUK JHN ACT ROM "
       "1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV").split()
DESCARTA = {'id', 'ide', 'h', 'toc1', 'toc2', 'toc3', 'mt1', 'mt', 'd', 's1', 's2', 's', 'sp', 'qa', 'r', 'ms', 'cl'}

def limpa(t):
    t = re.sub(r'\\f\s.*?\\f\*', ' ', t)          # nota de rodapé
    t = re.sub(r'\\x\s.*?\\x\*', ' ', t)          # referência cruzada
    t = re.sub(r'\\rq\s.*?\\rq\*', ' ', t)        # citação (ex.: Isaías 64:4)
    t = re.sub(r'\\w\s+([^|\\]*?)(\|[^\\]*)?\\w\*', r'\1', t)
    t = re.sub(r'\\\+?[a-z]+[0-9]*\*', '', t)     # fecha marcador de caractere (\add* \nd* \it*)
    t = re.sub(r'\\\+?[a-z]+[0-9]*\s?', '', t)    # abre marcador (\add \nd \it ...)
    t = re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'\s+([?!;,.])', r'\1', t)      # "gado ?" -> "gado?"
    # Rótulo no começo do versículo, do próprio texto (Cantares "Ela :",
    # Salmo 119 "Álefe :"): só acerta o espaço — "Ela: Beije-me"
    return re.sub(r'^([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-zà-ÿ]{0,15})\s*:\s*', r'\1: ', t)

def converte(pasta, metadados):
    livros_meta = metadados['books']
    arquivos = {}
    for f in glob.glob(os.path.join(pasta, '*.usfm')):
        with open(f, encoding='utf-8-sig') as fh:
            primeira = fh.readline()
        arquivos[primeira.split()[1]] = f
    faltando = [i for i in IDS if i not in arquivos]
    if faltando:
        raise SystemExit(f'livros faltando: {faltando}')
    saida, avisos = [], []
    for idx, bid in enumerate(IDS):
        caps = []          # lista de dicts {num: texto}
        atual = None
        cap = None
        with open(arquivos[bid], encoding='utf-8-sig') as fh:
            for linha in fh:
                linha = linha.strip()
                if not linha:
                    continue
                m = re.match(r'\\([a-z]+[0-9]*)\s*(.*)', linha)
                if not m:
                    if atual is not None: cap[atual] += ' ' + linha
                    continue
                marc, resto = m.groups()
                if marc == 'c':
                    cap = {}; caps.append(cap); atual = None
                    continue
                if marc in DESCARTA or cap is None:
                    continue
                # pode haver vários \v na mesma linha
                partes = re.split(r'\\v\s+(\d+(?:[-–]\d+)?)\s*', (('\\v ' + resto) if marc == 'v' else resto))
                if partes[0].strip() and atual is not None:
                    cap[atual] += ' ' + partes[0]
                for k in range(1, len(partes), 2):
                    num = partes[k]
                    if '-' in num or '–' in num:
                        a, b = [int(x) for x in re.split('[-–]', num)]
                        avisos.append(f'{bid} {len(caps)}:{num} versículos juntos')
                        cap[a] = partes[k + 1]
                        for n in range(a + 1, b + 1): cap[n] = ''
                        atual = a
                    else:
                        atual = int(num); cap[atual] = partes[k + 1]
        capitulos = []
        for ci, cap in enumerate(caps, 1):
            if not cap:
                capitulos.append([]); continue
            maior = max(cap)
            versos = []
            for n in range(1, maior + 1):
                if n not in cap:
                    avisos.append(f'{bid} {ci}:{n} ausente'); versos.append('')
                else:
                    versos.append(limpa(cap[n]))
            capitulos.append(versos)
        meta = livros_meta[idx]
        saida.append({'abbrev': meta['abbrev'], 'chapters': capitulos, 'name': meta['name']})
    return saida, avisos

if __name__ == '__main__':
    pasta, meta_path, destino = sys.argv[1:4]
    meta = json.load(open(meta_path, encoding='utf-8'))
    biblia, avisos = converte(pasta, meta)
    json.dump(biblia, open(destino, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'{destino}: {len(biblia)} livros, {sum(len(b["chapters"]) for b in biblia)} capítulos, '
          f'{sum(len(c) for b in biblia for c in b["chapters"])} versículos; {len(avisos)} avisos')
    for a in avisos[:15]: print('  aviso:', a)
