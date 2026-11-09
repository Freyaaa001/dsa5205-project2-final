"""Generate manuscript tables/figures from the compact final replay, never literals."""
import argparse
import json
import os
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
cache = Path('runs/final_report_runtime/mpl').resolve()
cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', str(cache))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

LABELS = {'fundamental_equal':'Fundamental EW', 'fundamental_sqrt_cap':'Fundamental sqrt-cap',
          'fundamental_cap':'Fundamental cap', 'pool_equal':'Pool EW',
          'pool_sqrt_cap':'Pool sqrt-cap', 'pool_cap':'Pool cap',
          'ridge_A':'Ridge A', 'ridge_B':'Ridge B', 'buffered_ridge_A':'Buffered Ridge A',
          'buffered_ridge_B':'Buffered Ridge B', 'extra_A':"Expanded A'", 'extra_B':"Expanded B'",
          'fusion_25':'Fusion 0.25', 'fusion_50':'Fusion 0.50', 'SPY':'SPY'}


def esc(x):
    return str(x).replace('&',r'\&').replace('_',r'\_').replace('%',r'\%')


def table(path, headers, rows, align=None):
    align = align or 'l'+'r'*(len(headers)-1)
    text = r'\begin{tabular}{'+align+'}\n'+r'\toprule'+'\n'
    text += ' & '.join(headers)+r' \\'+'\n'+r'\midrule'+'\n'
    text += '\n'.join(' & '.join(map(str,row))+r' \\' for row in rows)
    text += '\n'+r'\bottomrule'+'\n'+r'\end{tabular}'+'\n'
    path.write_text(text)


def run(output, report):
    out, rep = map(Path,(output,report)); figs=rep/'figures'; tabs=rep/'tables'
    figs.mkdir(parents=True,exist_ok=True);tabs.mkdir(exist_ok=True)
    cfg=json.loads((out/'protocol.json').read_text());base=Path(cfg['baseline']);db=Path(cfg['database']);exp=Path(cfg['exploration']);deep=Path(cfg['deep'])
    s=pd.read_csv(out/'portfolio_summary.csv');ev=s.loc[s.phase.eq('evaluation')].set_index('case')
    pct=lambda x:f'{x*100:.2f}';num=lambda x:f'{x:.3f}'
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,
                         'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18})
    def save(name,fig):
        fig.tight_layout();fig.savefig(figs/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
    def daily(name):
        return pd.read_csv(out/'portfolios'/name/'evaluation/daily.csv',dtype={'date':str}).set_index('date')
    def performance(name,cases):
        rows=[]
        for key in cases:
            r=ev.loc[key];rows.append([esc(LABELS[key]),pct(r.annual_return),pct(r.annual_volatility),num(r.sharpe),pct(r.max_drawdown),pct(r.mean_daily_turnover)])
        table(tabs/(name+'.tex'),['Strategy',r'CAGR (\%)',r'Vol. (\%)','Sharpe',r'MDD (\%)',r'Turn. (\%)'],rows)
    performance('final_comparison',['fundamental_sqrt_cap','fundamental_equal','fundamental_cap','pool_cap','extra_A','extra_B'])
    performance('pool_comparison',['pool_equal','pool_sqrt_cap','pool_cap'])
    performance('implementation',['ridge_A','buffered_ridge_A','ridge_B','buffered_ridge_B'])
    performance('fusion',['fundamental_sqrt_cap','fusion_25','fusion_50'])
    original=pd.read_csv(out/'tables/original_models.csv').set_index('strategy')
    table(tabs/'original_models.tex',['Model',r'A CAGR (\%)',r'B CAGR (\%)','B$-$A (pp)'],
        [[k.title() if k!='xgboost' else 'XGBoost',pct(original.loc[k+'_A','annual_return']),pct(original.loc[k+'_B','annual_return']),pct(original.loc[k+'_B','annual_return']-original.loc[k+'_A','annual_return'])] for k in ['ridge','lasso','xgboost']])
    training=pd.read_csv(out/'tables/training_windows.csv',dtype={'last_training_signal':str,'last_label_end':str})
    table(tabs/'training.tex',['Forecast','Training rows','Last signal','Last target end'],
          [[r.half,f'{r.samples:,}',r.last_training_signal,r.last_label_end] for r in training.itertuples()])
    stats=pd.read_csv(out/'tables/factor_statistics.csv');sel=json.loads((out/'tables/factor_selection.json').read_text());names=sel['fundamental']+sel['wq']
    labels={n:('F'+str(i+1) if i<6 else n) for i,n in enumerate(names)}
    a=stats.query("variant=='raw' and phase=='stability'").set_index('factor')
    b=stats.query("variant=='raw' and phase=='validation'").set_index('factor')
    table(tabs/'factor_statistics.tex',['Signal','Direction','2019--21 RankIC','2022 RankIC',r'2019--21 coverage (\%)'],
          [[labels[n],f'{sel["directions"][n]:+d}',num(a.loc[n,'rankic']),num(b.loc[n,'rankic']),pct(a.loc[n,'mean_coverage'])] for n in names])
    annual=pd.read_csv(out/'tables/annual.csv');ac=annual.loc[annual.case.eq('fundamental_sqrt_cap')]
    table(tabs/'annual.tex',['Year',r'Candidate return (\%)',r'SPY return (\%)','Difference (pp)'],
          [[int(r.year),pct(r.net_return),pct(r.SPY_return),pct(r.net_return-r.SPY_return)] for r in ac.itertuples()])
    rows=[]
    for phase in ['validation','evaluation']:
        z=s.loc[s.phase.eq(phase)].set_index('case');full=z.loc['fundamental_sqrt_cap','annual_return']
        rows.append([phase.title(),'All six',pct(full),'0.00'])
        for i in range(1,7):
            r=z.loc[f'without_F0{i}'];rows.append([phase.title(),f'Without F{i}',pct(r.annual_return),pct(r.annual_return-full)])
    table(tabs/'ablation.tex',['Phase','Composite',r'CAGR (\%)','Change (pp)'],rows,align='llrr')
    table(tabs/'stress.tex',['Scenario',r'CAGR (\%)','Sharpe',r'MDD (\%)'],
          [[name,pct(ev.loc[key,'annual_return']),num(ev.loc[key,'sharpe']),pct(ev.loc[key,'max_drawdown'])] for key,name in [('fundamental_sqrt_cap','10bps; baseline timing'),('cost_20','20bps'),('cost_30','30bps'),('lag_5','Extra five-session delay'),('lag_20','Extra twenty-session delay')]])
    ci=pd.read_csv(out/'tables/paired_intervals.csv')
    table(tabs/'intervals.tex',['Comparator','CAGR difference (pp)',r'95\% interval (pp)'],
          [[esc(LABELS[r.a]),pct(r.cagr_difference),f'[{pct(r.cagr_diff_ci_low)}, {pct(r.cagr_diff_ci_high)}]'] for r in ci.query('block==20').itertuples()])
    ratios=pd.read_csv(out/'tables/reconstruction_vs_ratio.csv')
    z=ratios.loc[ratios.phase.eq('2019-2021')]
    table(tabs/'ratios.tex',['Pair','Residual RankIC','Ratio RankIC','Difference'],
          [[f'F{i+1}',num(r.reconstructed_rankic),num(r.ratio_rankic),num(r.difference)] for i,r in enumerate(z.itertuples())])
    cnt=pd.read_csv(out/'tables/universe_counts.csv',dtype={'date':str}).set_index('date')['count']
    fig,ax=plt.subplots(figsize=(7.1,2.7));ax.plot(pd.to_datetime(cnt.index),cnt,color='#17365d');ax.set(ylabel='Eligible securities',xlabel='Date');save('universe',fig)
    paths={n:daily(n) for n in ['fundamental_sqrt_cap','fundamental_equal','pool_cap','pool_equal']}
    ref=paths['fundamental_sqrt_cap'];dates=pd.to_datetime(ref.index)
    fig,axes=plt.subplots(2,1,figsize=(7.1,5.2),sharex=True,gridspec_kw={'height_ratios':[2,1]})
    for key,d in paths.items():
        axes[0].plot(dates,d.net_nav,label=LABELS[key],lw=1.2)
    spy=(1+ref.benchmark_return).cumprod();axes[0].plot(dates,spy,color='black',ls='--',label='SPY');axes[0].set_ylabel('Net wealth (initial = 1)');axes[0].legend(fontsize=8,ncol=2)
    for key in ['fundamental_sqrt_cap','pool_cap']:
        nav=paths[key].net_nav;axes[1].plot(dates,nav/np.maximum(1,nav.cummax())-1,label=LABELS[key])
    axes[1].plot(dates,spy/np.maximum(1,spy.cummax())-1,color='black',ls='--',label='SPY');axes[1].set_ylabel('Drawdown');axes[1].yaxis.set_major_formatter(PercentFormatter(1));save('wealth_drawdown',fig)
    fig,axes=plt.subplots(1,2,figsize=(7.1,2.7));positions=np.arange(3)
    for j,(key,lab) in enumerate([('net_return','Candidate'),('SPY_return','SPY')]):axes[0].bar(positions+(j-.5)*.35,ac[key],width=.35,label=lab)
    axes[0].set_xticks(positions,ac.year.astype(str));axes[0].yaxis.set_major_formatter(PercentFormatter(1));axes[0].legend(fontsize=8);axes[0].set_ylabel('Annual total return')
    rolling=((1+ref.net_return)/(1+ref.benchmark_return)).rolling(252).apply(np.prod,raw=True)-1
    axes[1].plot(dates,rolling,color='#17365d');axes[1].axhline(0,color='black',lw=.7);axes[1].set_ylabel('Trailing 252-session relative return');axes[1].yaxis.set_major_formatter(PercentFormatter(1));axes[1].tick_params(axis='x',rotation=25);save('annual_rolling',fig)
    fig,axes=plt.subplots(1,2,figsize=(7.1,3))
    for ax,phase in zip(axes,['validation','evaluation']):
        z=s.loc[s.phase.eq(phase)].set_index('case');vals=[z.loc['fundamental_sqrt_cap','annual_return']]+[z.loc[f'without_F0{i}','annual_return'] for i in range(1,7)]
        ax.barh(['All six']+[f'Without F{i}' for i in range(1,7)],vals,color=['#17365d']+['#3c8d95']*6);ax.set_title(phase.title());ax.xaxis.set_major_formatter(PercentFormatter(1));ax.invert_yaxis()
    save('ablation',fig)
    fig,axes=plt.subplots(1,2,figsize=(7.1,2.7));axes[0].plot([10,20,30],[ev.loc[k,'annual_return'] for k in ['fundamental_sqrt_cap','cost_20','cost_30']],marker='o');axes[0].set(xlabel='Cost (bps per traded dollar)',ylabel='Net CAGR')
    axes[1].plot([0,5,20],[ev.loc[k,'annual_return'] for k in ['fundamental_sqrt_cap','lag_5','lag_20']],marker='o');axes[1].set(xlabel='Extra financial-availability sessions',ylabel='Net CAGR')
    for ax in axes:ax.axhline(ev.loc['fundamental_sqrt_cap','spy_annual_return'],ls='--',color='black',label='SPY');ax.yaxis.set_major_formatter(PercentFormatter(1));ax.legend(fontsize=8)
    save('stress',fig)
    fig,axes=plt.subplots(1,2,figsize=(7.1,2.7))
    for ax,phase in zip(axes,['validation','evaluation']):
        z=s.loc[s.phase.eq(phase)].set_index('case');ax.plot([0,.25,.5],[z.loc[k,'annual_return'] for k in ['fundamental_sqrt_cap','fusion_25','fusion_50']],marker='o');ax.axvline(.25,color='black',ls=':');ax.set(title=phase.title(),xlabel='Price score weight',ylabel='Net CAGR',xticks=[0,.25,.5]);ax.yaxis.set_major_formatter(PercentFormatter(1))
    save('fusion',fig)
    fig,ax=plt.subplots(figsize=(7.1,2.8));z=ci.query('block==20').reset_index(drop=True)
    for i,r in z.iterrows():ax.plot([r.cagr_diff_ci_low*100,r.cagr_diff_ci_high*100],[i,i],color='#3c8d95');ax.scatter(r.cagr_difference*100,i,color='#17365d',s=25)
    ax.axvline(0,color='black',ls='--');ax.set_yticks(range(len(z)),[LABELS[n] for n in z.a]);ax.set_xlabel('Candidate minus comparator CAGR (percentage points)');save('intervals',fig)
    cor=pd.read_csv(out/'tables/correlation.csv',index_col=0).reindex(index=names,columns=names)
    fig,ax=plt.subplots(figsize=(6,4.1));im=ax.imshow(cor,vmin=-1,vmax=1,cmap='RdBu_r');ax.set_xticks(range(9),[labels[n] for n in names],rotation=45,ha='right');ax.set_yticks(range(9),[labels[n] for n in names]);fig.colorbar(im,ax=ax,shrink=.8,label='Mean daily rank correlation');save('correlation',fig)
    style=pd.read_csv(out/'tables/style_exposures.csv').query("batch=='weights' and case=='simple_C_sqrt_cap'").iloc[0]
    keys=['Size','Beta','Momentum','ResidualVolatility','NonLinearSize','BookToPrice','Liquidity','EarningsYield','Leverage']
    fig,ax=plt.subplots(figsize=(7.1,2.9));ax.barh(keys,[style[k] for k in keys],color='#3c8d95');ax.axvline(0,color='black',lw=.6);ax.set_xlabel('Mean beginning-of-day style exposure (model units)');ax.invert_yaxis();save('styles',fig)
    # Record all numeric manuscript inputs, including inherited comparisons.
    (rep/'asset_inventory.json').write_text(json.dumps({'figures':sorted(p.name for p in figs.glob('*.pdf')),'tables':sorted(p.name for p in tabs.glob('*.tex')),'results':str(out),'note':'No returns fitted or selected by the report builder.'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='results/project2_final');p.add_argument('--report',default='reports/final');a=p.parse_args();run(a.output,a.report)
