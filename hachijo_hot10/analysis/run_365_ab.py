#!/usr/bin/env python3
"""Non-production F4.1-B annual A/B diagnostics. Never writes production state/output."""
from __future__ import annotations
import argparse, csv, html, json, math, random, statistics, sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import hot10

START, DAYS, SEEDS = date(2026, 8, 26), 365, (20260826, 12345, 20260901, 777, 424242)
BUCKETS = (("0",0,0),("1",1,1),("2-4",2,4),("5-9",5,9),("10-19",10,19),("20-49",20,49),("50-99",50,99),("100+",100,10**9))

def pct(values, p):
    values=sorted(values); x=(len(values)-1)*p; lo,hi=math.floor(x),math.ceil(x)
    return values[lo] if lo==hi else values[lo]+(values[hi]-values[lo])*(x-lo)

def run(tracks, config, seed):
    state,rng=hot10.initial_state(tracks,config),random.Random(seed)
    return [hot10.generate_chart(START+timedelta(days=i),tracks,state,config,rng) for i in range(DAYS)]

def roll(charts, tracks):
    d={t['track_id']:{'days':0,'n1':0,'re':0} for t in tracks}
    for c in charts:
        for x in c['chart']:
            d[x['track_id']]['days']+=1; d[x['track_id']]['n1']+=int(x['rank']==1); d[x['track_id']]['re']+=int(x['movement']=='RE')
    return d

def changes(charts, start=1):
    keep=[]; prior=None
    for i,c in enumerate(charts):
        now={x['track_id'] for x in c['chart']}
        if prior is not None and i>=start: keep.append(len(prior&now))
        prior=now
    return keep,[10-x for x in keep]

def longest(charts, first_only=False):
    active=defaultdict(int); best=0
    for c in charts:
        now={x['track_id'] for x in c['chart'] if not first_only or x['rank']==1}
        for k in list(active):
            if k not in now: active[k]=0
        for k in now: active[k]+=1; best=max(best,active[k])
    return best

def analyse(charts, tracks, variant):
    r=roll(charts,tracks); days=[r[t['track_id']]['days'] for t in tracks]; keep,repl=changes(charts)
    warm_keep,warm_repl=changes(charts,30); warm=charts[30:]
    slots=[x for c in charts for x in c['chart']]
    shown=[x for x in days if x]
    dist=[{'bucket':n,'tracks':sum(a<=x<=b for x in days),'share':sum(a<=x<=b for x in days)/len(days)} for n,a,b in BUCKETS]
    return {'variant':variant,'charts':charts,'tracks':tracks,'roll':r,'days':days,'retention':statistics.fmean(keep),'replacements':statistics.fmean(repl),'replacement_distribution':{'0':sum(x==0 for x in repl),'1':sum(x==1 for x in repl),'2':sum(x==2 for x in repl),'3+':sum(x>=3 for x in repl)},'ever':len(shown),'ever_rate':len(shown)/len(days),'new':sum(x['movement']=='NEW' for x in slots),'re':sum(x['movement']=='RE' for x in slots),'re_tracks':sum(v['re']>0 for v in r.values()),'max_re':max(v['re'] for v in r.values()),'n1_streak':longest(charts,True),'top10_streak':longest(charts),'dist':dist,'population':{'mean_all':statistics.fmean(days),'median_all':statistics.median(days),'mean_shown':statistics.fmean(shown),'median_shown':statistics.median(shown),'p75':pct(days,.75),'p90':pct(days,.9),'p95':pct(days,.95),'max':max(days)},'concentration':{f'top{n}':sum(sorted(days,reverse=True)[:n])/(DAYS*10) for n in (10,25,50,100)}|{'hhi':sum((x/(DAYS*10))**2 for x in days)},'post_warmup':{'retention':statistics.fmean(warm_keep) if warm_keep else 0,'replacements':statistics.fmean(warm_repl) if warm_repl else 0,'unique':len({x['track_id'] for c in warm for x in c['chart']}),'re':sum(x['movement']=='RE' for c in warm for x in c['chart'])}}

def pool(result, ids):
    ds=[result['roll'][i]['days'] for i in ids]; slots=sum(ds); return {'tracks':len(ids),'ever':sum(x>0 for x in ds),'ever_rate':sum(x>0 for x in ds)/len(ds),'slots':slots,'slot_share':slots/(DAYS*10),'mean':statistics.fmean(ds),'median':statistics.median(ds)}

def write(path, rows):
    fields=list(dict.fromkeys(k for row in rows for k in row)); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as f: w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def monthly(result, newpool=False):
    rows=[]
    for month in sorted({c['date'][:7] for c in result['charts']}):
        charts=[c for c in result['charts'] if c['date'].startswith(month)]; allrows=[x for c in charts for x in c['chart']]
        # transitions ending in this month, including first day against its real prior chart
        indexes=[i for i,c in enumerate(result['charts']) if c['date'].startswith(month)]; keep,repl=changes(result['charts'],indexes[0]); keep=keep[:len(indexes)] if indexes[0] else keep[:max(0,len(indexes)-1)]; repl=repl[:len(keep)]
        rows.append({'variant':result['variant'],'month':month,'average_retention':statistics.fmean(keep) if keep else 0,'average_replacements':statistics.fmean(repl) if repl else 0,'unique_tracks':len({x['track_id'] for x in allrows}),'NEW':sum(x['movement']=='NEW' for x in allrows),'RE':sum(x['movement']=='RE' for x in allrows),'new200_slot_share':sum(x['track_id']>=1390 for x in allrows)/len(allrows) if newpool else ''})
    return rows

def deciles(result, config):
    scored=sorted(((hot10.static_score(t,config),t) for t in result['tracks']),key=lambda pair:(pair[0],pair[1]['track_id'])); out=[]
    for n in range(10):
        g=scored[round(n*len(scored)/10):round((n+1)*len(scored)/10)]; ds=[result['roll'][t['track_id']]['days'] for _,t in g]
        out.append({'variant':result['variant'],'decile':n+1,'score_min':g[0][0],'score_max':g[-1][0],'tracks':len(g),'ever_charted_rate':sum(x>0 for x in ds)/len(ds),'mean_top10_days':statistics.fmean(ds),'median_top10_days':statistics.median(ds)})
    return out

def comparison_html(a, b):
    def cell(row): return f"<strong>{html.escape(row['artist'])}</strong><span>{html.escape(row['title'])} · {html.escape(row['movement'])}</span>"
    sections=[]
    for index,(ac,bc) in enumerate(zip(a['charts'],b['charts'])):
        rows=''.join(f"<tr><td>{rank}</td><td>{cell(ac['chart'][rank-1])}</td><td>{cell(bc['chart'][rank-1])}</td></tr>" for rank in range(1,11))
        open_attr=' open' if index==0 else ''
        sections.append(f"<details id=\"d-{ac['date']}\"{open_attr}><summary>{ac['date']}</summary><table><thead><tr><th>Rank</th><th>1389 A</th><th>1589 B</th></tr></thead><tbody>{rows}</tbody></table></details>")
    month_starts={}
    for chart in a['charts']: month_starts.setdefault(chart['date'][:7],chart['date'])
    nav=''.join(f'<a href="#d-{day}">{month}</a>' for month,day in month_starts.items())
    return f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HACHIJO HOT 10 — 1389 A / 1589 B · 365 days</title><style>
:root{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#172033;background:#f4f7fb}}body{{margin:0;padding:32px 18px 56px}}main{{max-width:1120px;margin:auto}}h1{{margin:0;font-size:clamp(24px,4vw,34px)}}p{{color:#5b677a;font-size:14px;margin:8px 0 20px}}nav{{position:sticky;top:0;z-index:1;display:flex;flex-wrap:wrap;gap:6px;padding:10px 0;background:#f4f7fb}}nav a{{padding:5px 8px;border:1px solid #dce3ee;border-radius:6px;background:#fff;color:#334155;font-size:11px;text-decoration:none}}details{{margin:12px 0;background:#fff;border:1px solid #dce3ee;border-radius:12px;overflow:hidden}}summary{{padding:14px 18px;cursor:pointer;font-size:16px;font-weight:700;background:#f8faff}}table{{width:100%;border-collapse:collapse;table-layout:fixed}}th,td{{padding:10px 14px;text-align:left;vertical-align:top;border-top:1px solid #edf0f5}}th{{color:#52617a;font-size:12px}}th:first-child,td:first-child{{width:56px;text-align:center}}th:nth-child(2),td:nth-child(2){{background:#f0f6ff}}th:nth-child(3),td:nth-child(3){{background:#fff7ee}}strong,span{{display:block}}strong{{font-size:14px}}span{{margin-top:3px;color:#48566d;font-size:13px}}@media(max-width:560px){{body{{padding:18px 10px 40px}}th,td{{padding:10px 8px}}strong{{font-size:13px}}span{{font-size:12px}}}}</style></head><body><main><h1>HACHIJO HOT 10 — 1389 A / 1589 B</h1><p>Canonical seed 20260826 · 2026-08-26〜2027-08-25 · 日別TOP 10</p><nav>{nav}</nav>{''.join(sections)}</main></body></html>'''

def main():
    p=argparse.ArgumentParser();p.add_argument('--proposed-master',type=Path,required=True);p.add_argument('--output-dir',type=Path,default=ROOT/'analysis'/'results');a=p.parse_args();out=a.output_dir
    config=hot10.load_config(); A=hot10.load_tracks(hot10.resolve_master_path(config),1389);B=hot10.load_tracks(a.proposed_master,1589)
    def sig(t): return (t['track_id'],t['artist'],t['title'],*(t[k] for k in hot10.SCORE_COLUMNS),t['enabled'],t['release_year'],t['freshness_bonus'])
    if [sig(t) for t in A] != [sig(t) for t in B[:1389]]: raise ValueError('B ids 1-1389 differ from A')
    g=analyse(run(A,config,20260826)[:14],A,'A'); actual=(g['retention'],g['replacements'],g['ever'],g['new'],g['re'],g['n1_streak'],g['top10_streak'])
    if actual!=(8.0,2.0,35,35,1,3,12): raise RuntimeError(f'golden mismatch: {actual}')
    ca,cb=analyse(run(A,config,20260826),A,'A'),analyse(run(B,config,20260826),B,'B')
    seedrows=[]
    for seed in SEEDS:
        for label,tracks in (('A',A),('B',B)):
            z=analyse(run(tracks,config,seed),tracks,label); row={'seed':seed,'variant':label,'average_daily_retention':z['retention'],'average_daily_replacements':z['replacements'],'ever_charted_tracks':z['ever'],'ever_charted_rate':z['ever_rate'],'NEW':z['new'],'RE':z['re'],'longest_number1_streak':z['n1_streak'],'longest_top10_streak':z['top10_streak'],'top25_share':z['concentration']['top25'],'top100_share':z['concentration']['top100']}
            if label=='B': row|={f'new200_{k}':v for k,v in pool(z,range(1390,1590)).items()}
            seedrows.append(row)
    byA={t['track_id']:t for t in A};byB={t['track_id']:t for t in B}
    tracks=[]
    for i,t in byB.items():
        av=ca['roll'].get(i);bv=cb['roll'][i];tracks.append({'track_id':i,'artist':t['artist'],'title':t['title'],'pool':'new200' if i>=1390 else 'existing','A_top10_days':'' if av is None else av['days'],'B_top10_days':bv['days'],'difference':'' if av is None else bv['days']-av['days'],'B_number1_days':bv['n1'],'B_RE_count':bv['re'],'static_score':hot10.static_score(t,config)})
    artists=defaultdict(lambda:{'A_track_count':0,'B_track_count':0,'new200_track_count':0,'A_slots':0,'B_slots':0,'B_new200_slots':0,'B_new200_charted_tracks':0})
    for t in A: artists[t['artist']]['A_track_count']+=1;artists[t['artist']]['A_slots']+=ca['roll'][t['track_id']]['days']
    for t in B:
        q=artists[t['artist']];q['B_track_count']+=1;q['B_slots']+=cb['roll'][t['track_id']]['days']
        if t['track_id']>=1390:q['new200_track_count']+=1;q['B_new200_slots']+=cb['roll'][t['track_id']]['days'];q['B_new200_charted_tracks']+=int(cb['roll'][t['track_id']]['days']>0)
    artistrows=[{'artist':name,**v} for name,v in sorted(artists.items())]
    write(out/'hot10_365_AB_per_track.csv',tracks);write(out/'hot10_365_AB_per_artist.csv',artistrows);write(out/'hot10_365_AB_monthly.csv',monthly(ca)+monthly(cb,True));write(out/'hot10_365_AB_score_deciles.csv',deciles(ca,config)+deciles(cb,config));write(out/'hot10_365_AB_seed_summary.csv',seedrows)
    new=pool(cb,range(1390,1590));oldA,oldB=pool(ca,range(1,1390)),pool(cb,range(1,1390)); diffs=[abs(x['difference']) for x in tracks if x['pool']=='existing'];top=lambda z,n:{i for i,v in z['roll'].items() if v['days'] in []}
    compact=lambda z:{k:v for k,v in z.items() if k not in {'charts','tracks','roll','days'}}
    (out/'hot10_365_AB_results.json').write_text(json.dumps({'start':str(START),'days':DAYS,'seeds':SEEDS,'golden':actual,'canonical':{'A':compact(ca),'B':compact(cb)},'new200':new,'existing':{'A':oldA,'B':oldB}},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'hot10_365_AB_canonical.html').write_text(comparison_html(ca,cb),encoding='utf-8')
    md=['# HACHIJO HOT 10 — 1389 vs 1589 annual A/B','','## 1. 結論','','分析のみ。engine、score、master、本番state/output/Web UIは変更していない。','','## 2. A/B基本指標','','| 指標 | A 1389 | B 1589 | 差 |','|---|---:|---:|---:|']
    for label,key in [('平均日次残留','retention'),('平均日次入替','replacements'),('年間TOP10経験曲数','ever'),('年間TOP10経験率','ever_rate'),('最長#1 streak','n1_streak'),('最長TOP10 streak','top10_streak'),('NEW','new'),('RE','re')]:
        av,bv=ca[key],cb[key];md.append(f'| {label} | {av:.2%}'+' | ' + f'{bv:.2%}' if key=='ever_rate' else f'| {label} | {av} | {bv} | {bv-av:+} |')
    md+=['',f"入替分布 A 0/1/2/3+: {ca['replacement_distribution']}",f"入替分布 B 0/1/2/3+: {cb['replacement_distribution']}",'','## 3. 出現率・集中度','','| 指標 | A | B |','|---|---:|---:|']
    for key in ('ever_rate','mean','median','p90'):
        aa=oldA['ever_rate'] if key=='ever_rate' else (ca['population']['p90'] if key=='p90' else ca['population']['mean_all'] if key=='mean' else ca['population']['median_all']);bb=oldB['ever_rate'] if key=='ever_rate' else (cb['population']['p90'] if key=='p90' else cb['population']['mean_all'] if key=='mean' else cb['population']['median_all']);md.append(f'| {key} | {aa:.2%}'+' | '+f'{bb:.2%} |' if key=='ever_rate' else f'| {key} | {aa:.2f} | {bb:.2f} |')
    for key in ('top10','top25','top50','top100','hhi'):md.append(f"| {key} concentration | {ca['concentration'][key]:.2%} | {cb['concentration'][key]:.2%} |" if key!='hhi' else f"| HHI | {ca['concentration'][key]:.5f} | {cb['concentration'][key]:.5f} |")
    md+=['','## 4. 追加200曲',f"母集団比率: {200/1589:.2%}",f"ever: {new['ever']}/200 ({new['ever_rate']:.2%})",f"slots: {new['slots']}/3650 ({new['slot_share']:.2%})",f"平均/中央値: {new['mean']:.2f}/{new['median']:.2f}",'','## 5. 既存1389曲への影響',f"A existing ever {oldA['ever']}/{oldA['tracks']} ({oldA['ever_rate']:.2%}), slots {oldA['slots']}",f"B existing ever {oldB['ever']}/{oldB['tracks']} ({oldB['ever_rate']:.2%}), slots {oldB['slots']}",f"既存track登場日数差分絶対値 平均 {statistics.fmean(diffs):.2f} / 中央 {statistics.median(diffs):.2f} / ±5日以上 {sum(x>=5 for x in diffs)} / ±10日以上 {sum(x>=10 for x in diffs)}",'','## 6. 出現日数分布','','| bucket | A tracks | A share | B tracks | B share |','|---|---:|---:|---:|---:|']
    md += [f"| {x['bucket']} | {x['tracks']} | {x['share']:.2%} | {y['tracks']} | {y['share']:.2%} |" for x,y in zip(ca['dist'],cb['dist'])]
    md+=['','## 7. 月別・artist・score帯','`hot10_365_AB_monthly.csv` / `hot10_365_AB_per_artist.csv` / `hot10_365_AB_score_deciles.csv` を参照。','','## 8. 追加200曲 上位30 / 下位30','','| id | artist | title | score | days | #1 | RE |','|---:|---|---|---:|---:|---:|---:|']
    newrows=[x for x in tracks if x['pool']=='new200']
    for x in sorted(newrows,key=lambda x:(-x['B_top10_days'],x['track_id']))[:30]:md.append(f"| {x['track_id']} | {x['artist']} | {x['title']} | {x['static_score']:.2f} | {x['B_top10_days']} | {x['B_number1_days']} | {x['B_RE_count']} |")
    md+=['','### 下位30','','| id | artist | title | score | days | #1 | RE |','|---:|---|---|---:|---:|---:|---:|']
    for x in sorted(newrows,key=lambda x:(x['B_top10_days'],x['track_id']))[:30]:md.append(f"| {x['track_id']} | {x['artist']} | {x['title']} | {x['static_score']:.2f} | {x['B_top10_days']} | {x['B_number1_days']} | {x['B_RE_count']} |")
    md+=['','## 9. 5 seeds × 365日平均','','| variant | retention | replacements | ever | NEW | RE |','|---|---:|---:|---:|---:|---:|']
    for v in ('A','B'):
        q=[x for x in seedrows if x['variant']==v];md.append(f"| {v} | {statistics.fmean(x['average_daily_retention'] for x in q):.2f} | {statistics.fmean(x['average_daily_replacements'] for x in q):.2f} | {statistics.fmean(x['ever_charted_tracks'] for x in q):.1f} | {statistics.fmean(x['NEW'] for x in q):.1f} | {statistics.fmean(x['RE'] for x in q):.1f} |")
    md+=['','## 10. 注意点','同一seedでも母集団曲数によりRNG call orderは一致しない。paired比較と5 seed平均を併記した。','',f"post-warmup Day31–365: A retention {ca['post_warmup']['retention']:.2f}, replacements {ca['post_warmup']['replacements']:.2f}, unique {ca['post_warmup']['unique']}, RE {ca['post_warmup']['re']}; B retention {cb['post_warmup']['retention']:.2f}, replacements {cb['post_warmup']['replacements']:.2f}, unique {cb['post_warmup']['unique']}, RE {cb['post_warmup']['re']}."]
    (out/'hot10_365_AB_summary.md').write_text('\n'.join(md)+'\n',encoding='utf-8');print(out)
if __name__=='__main__':main()
