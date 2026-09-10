"""The callee-shape bucket (bench tooling, 2026-09-10): join an oracle
cell's misses to the checker's callee-shape record (shapes.mjs) and to
lane A's own facts at the same site, bucket them by shape, and print the
collapsed recall (one pair per site line x target file x target name —
the oracle's overload grain removed). docs/oracle/oracle-misses.md.

    python3 bench/oracle/shape/bucket.py <cell-dir> <oracle.json> <shapes.json> <facts.json>

<cell-dir> holds report.json (oracle grade --json); <facts.json> is
`node tsextract/extract.mjs --repo <clone>`.
"""
import json, re, sys
from collections import Counter, defaultdict
D=sys.argv[1]
rep=json.load(open(D+'/report.json')); orc=json.load(open(sys.argv[2]))
shapes=json.load(open(sys.argv[3])); facts=json.load(open(sys.argv[4]))
misses=rep['misses']; rows=rep['rows']
def tname(n): return n.split('.')[-1].strip('"')
# hobbes rows by site line
rows_at=defaultdict(list)
for r in rows: rows_at[(r['edge']['site']['path'], r['edge']['site']['line'])].append(r)
# oracle sites by (path,line)
osites=defaultdict(list)
for s in orc['sites']: osites[(s['pos']['path'], s['pos']['line'])].append(s)
# shapes by path,line (both terminal line and callee-start line)
sh_at=defaultdict(list)
for x in shapes:
    sh_at[(x['path'], x['line'])].append(x)
    if x['cline']!=x['line']: sh_at[(x['path'], x['cline'])].append(x)
# lane A facts by path,line
fa_at=defaultdict(list)
for f in facts['files']:
    for c in f.get('calls',[]): fa_at[(f['path'], c['line'])].append(c)
def ident_bucket(x):
    ds=x['decls']
    if not ds: return 'identifier:unresolved'
    k=ds[0]['kind']
    if k.startswith('var:'):
        parts=k.split(':')  # var:kw:top|nested:init
        return f"identifier:{parts[1]}-{parts[2]}-{parts[3]}"
    return 'identifier:'+k
def shape_bucket(x):
    if x['shape']=='identifier': return ident_bucket(x)
    if x['shape']=='member':
        r=x['recv']
        if r.startswith('ident:var:'):
            p=r.split(':'); return f"member:on-{p[2]}-{p[3]}-{p[4]}"
        return 'member:on-'+r
    return x['shape']
out=Counter(); detail=defaultdict(Counter); examples=defaultdict(list); laneA=defaultdict(Counter)
for m in misses:
    key=(m['site']['path'], m['site']['line']); t=m['target']; tn=tname(t['name']); cls=m['class']
    # 1. overload/sibling grain: Hobbes has a confirmed edge at this line to same file+name, other line
    sib=[r for r in rows_at[key] if r['bucket']=='confirmed' and r['edge']['target']['path']==t['pos']['path'] and tname(r['edge']['target_id'])==tn and r['edge']['target']['line']!=t['pos']['line']]
    if sib:
        b='oracle-grain:sibling-declaration-confirmed'
    else:
        cands=[x for x in sh_at[key] if x['name']==tn] or sh_at[key]
        if not cands: b='no-lane-A-site-on-line'
        else:
            # nearest col to oracle site col
            oc=[s for s in osites[key] if any(tt['pos']==t['pos'] for tt in s['targets'])]
            col=oc[0]['col'] if oc else None
            x=min(cands, key=lambda x: abs((x['ccol'] if col is not None else 0)-(col or 0))) if col is not None else cands[0]
            b=shape_bucket(x)
            fa=[c for c in fa_at[key] if c['name']==tn] or fa_at[key]
            if fa:
                c=fa[0]; laneA[b][('callee' if c['callee'] else 'no-callee', c['origin'], c['ambiguous'])]+=1
            else: laneA[b][('no-lane-A-record',)]+=1
    out[(cls,b)]+=1; detail[b][(t['kind'], t['pos']['path'], t['pos']['line'], tn)]+=1
    if len(examples[b])<4: examples[b].append(f"{key[0]}:{key[1]} -> {t['pos']['path']}:{t['pos']['line']} {tn} [{cls}]")
print('TOTAL misses', len(misses))
tot=Counter()
for (cls,b),n in out.items(): tot[b]+=n
for b,n in tot.most_common():
    print(f"\n== {b}: {n} ({100*n/len(misses):.1f}%)")
    print('   by class:', {cls:k for (cls,bb),k in out.items() if bb==b})
    print('   lane A record:', dict(laneA[b]))
    print('   top targets:', detail[b].most_common(6))
    for e in examples[b]: print('   e.g.', e)

# collapsed recall (one pair per site line x target file x target name)
pairs=set(); kind={}
for s in orc['sites']:
    for t in s['targets']:
        if t.get('external'): continue
        k=(s['pos']['path'],s['pos']['line'],t['pos']['path'],tname(t['name'])); pairs.add(k); kind[k]=t['kind']
hits=set((r['edge']['site']['path'],r['edge']['site']['line'],r['edge']['target']['path'],tname(r['edge']['target_id'])) for r in rows if r['bucket']=='confirmed')
hit=pairs&hits
print('\nCOLLAPSED in-repo pairs', len(pairs), 'hit', len(hit), 'recall %.1f%%'%(100*len(hit)/len(pairs)))
bk=Counter(kind[k] for k in pairs); hk=Counter(kind[k] for k in hit)
for k,n in bk.most_common(): print(f'  {k:22s} {hk[k]:5d}/{n:5d}  {100*hk[k]/n:5.1f}%   misses {n-hk[k]}')
