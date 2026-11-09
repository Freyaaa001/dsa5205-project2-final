"""English v2 report built only from frozen baseline and completed extensions."""
from __future__ import annotations
import json
from pathlib import Path
from xml.sax.saxutils import escape
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak
from pypdf import PdfReader
from .extensions import digest

SHORT={'F01_EP_reconstructed':'F1 EP residual','F02_BP_reconstructed':'F2 BP residual','F03_SPQ_reconstructed':'F3 quarterly SP residual','F04_ROEQ_reconstructed':'F4 quarterly ROE residual','F05_FCF_yield':'F5 FCF yield','F06_earnings_surprise':'F6 earnings surprise','equal_weight_scores_A':'Equal-score A','equal_weight_scores_B':'Equal-score B','equal_weight_scores_C':'Equal-score C','equal_weight_eligible_pool':'Eligible-pool EW'}
def short(x):return SHORT.get(str(x),str(x).replace('xgboost','XGB').replace('_',' '))
def pct(x):return f'{x:.2%}' if pd.notna(x) else 'undefined'
def num(x):return f'{x:.3f}' if pd.notna(x) else 'undefined'


def run(database,baseline,extensions,pdf_output):
    base,ext,pdf=map(Path,(baseline,extensions,pdf_output))
    protocol=json.loads((base/'research_protocol.json').read_text())
    if protocol.get('label_policy',{}).get('label_version')!='next_close_10d_v2':raise ValueError('v2 results required')
    binding=json.loads((ext/'baseline_binding.json').read_text())
    for path,h in binding.items():
        if digest(base/path)!=h:raise ValueError('Extension baseline binding changed')
    figs=ext/'paper_figures';figs.mkdir(exist_ok=True);pdf.parent.mkdir(exist_ok=True,parents=True)
    read=lambda root,p:pd.read_csv(root/p)
    main=read(base,'backtests/summary.csv').set_index('strategy');names=main.index.tolist()
    supplemental=read(base,'supplement/portfolio_summary.csv').set_index('strategy')
    stats=read(ext,'statistics/factor_summary.csv');factors=stats.factor.drop_duplicates().tolist()
    selection=json.loads((base/'factor_selection.json').read_text());chosen=json.loads((base/'frozen_model_choices.json').read_text())
    members=json.loads((Path(__file__).resolve().parents[3]/'reports/Team34_members.json').read_text())['members']
    member_names=', '.join(m['name'] for m in members)
    dec=read(ext,'deciles/summary.csv');mono=read(ext,'deciles/monotonicity.csv');C=read(ext,'pure_C/summary.csv').set_index('strategy')
    ratios=read(ext,'comparisons/ratio_portfolios.csv');bootstrap=read(ext,'robustness/block_intervals.csv');haircuts=read(ext,'robustness/terminal_haircuts.csv')
    smooth=read(ext,'robustness/all_model_smoothing.csv');diag=read(ext,'lasso/diagnostics.csv');profiles=read(ext,'lasso/missingness_profiles.csv')
    daily={n:pd.read_csv(base/'backtests'/f'{n}_daily.csv',dtype={'date':str}).set_index('date') for n in names}
    dates=pd.to_datetime(daily[names[0]].index,format='%Y%m%d');spy=main.spy_annual_return.iloc[0]
    scope_path=ext/'audit/data_scope.json'
    if database:
        u=pd.read_pickle(Path(database)/'panels/universe.pkl');counts=u.loc['20150101':'20251231'].eq(1).sum(axis=1)
        scope={'axis_dates':len(u),'union_sids':u.shape[1],'first':u.index[0],'last':u.index[-1],'min_daily':int(counts.min()),'median_daily':float(counts.median()),'max_daily':int(counts.max())}
        scope_path.write_text(json.dumps(scope,indent=2))
        fig,ax=plt.subplots(figsize=(9,3));ax.plot(pd.to_datetime(counts.index,format='%Y%m%d'),counts,color='#167b87');ax.set_ylabel('Eligible securities');ax.set_title('Provided daily universe, not the SID union');fig.tight_layout();fig.savefig(figs/'universe.png',dpi=170);plt.close(fig)
    else:scope=json.loads(scope_path.read_text())
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.2})
    story=[];titles=[];source_files=set();width=A4[0]-88
    body=ParagraphStyle('body',fontName='Helvetica',fontSize=9.4,leading=13.4,spaceAfter=7,textColor=colors.HexColor('#263747'))
    title=ParagraphStyle('title',parent=body,fontName='Helvetica-Bold',fontSize=19,leading=23,spaceAfter=13,textColor=colors.HexColor('#17334d'))
    small=ParagraphStyle('small',parent=body,fontSize=7.6,leading=10,spaceAfter=4)
    def text(s):story.append(Paragraph(s,body))
    def page(t):
        if titles:story.append(PageBreak())
        titles.append(t);story.append(Paragraph(f'{len(titles):02d} / {t}',title))
    def table(headers,rows,widths=None):
        data=[[Paragraph(escape(str(x)),small) for x in headers]]+[[Paragraph(escape(str(x)),small) for x in row] for row in rows]
        t=Table(data,colWidths=widths or [width/len(headers)]*len(headers),repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e5eff3')),('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f8fa')]),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),4),('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#acc0cd'))]));story.extend([t,Spacer(1,9)])
    def chart(name,fig,height=220,caption=''):
        fig.tight_layout();path=figs/(name+'.png');fig.savefig(path,dpi=180,bbox_inches='tight');plt.close(fig)
        from PIL import Image as PILImage
        with PILImage.open(path) as im:w,h=im.size
        display_w=min(width,height*w/h);story.append(Image(str(path),width=display_w,height=display_w*h/w,hAlign='CENTER'))
        if caption:story.append(Paragraph(escape(caption),small))
    def provenance(*paths):
        source_files.update(paths);story.append(Paragraph('Evidence: '+escape('; '.join(paths)),small))
    def statrows(phase,variant='raw'):
        z=stats.loc[stats.phase.eq(phase)&stats.variant.eq(variant)].set_index('factor').reindex(factors)
        return [[short(n),num(r.ic),num(r.rankic),num(r.icir_daily),num(r.rankicir_daily),pct(r.mean_coverage),str(int(r.rankic_days))] for n,r in z.iterrows()]
    def performance_rows(frame):return [[short(n),pct(r.annual_return),pct(r.annual_volatility),num(r.sharpe),pct(r.max_drawdown),pct(r.mean_daily_turnover)] for n,r in frame.iterrows()]

    page('Fundamental information in a price-signal portfolio')
    text('<b>DSA5205 Project 2 | Team 34 | English report draft | 10 November 2026</b>')
    text('<b>Members:</b> '+escape(member_names)+'.<br/><b>Student IDs:</b> ____________________<br/><b>Actual contributions:</b> ____________________')
    text('Research question: do reconstructed accounting signals add useful information to selected price-volume signals, once information timing, trading costs, and style exposures are treated consistently?')
    text(f'We study the supplied US equity panel over 2015-2025, using 2015-2021 for development, 2022 for validation, and six expanding training windows during 2023-2025. The target runs from the T+1 close to the T+11 close. Three of 36 implemented WorldQuant candidates are retained alongside six fundamental signals.')
    text(f'<b>Abstract.</b> Fusion changes net CAGR from {pct(main.loc["ridge_A","annual_return"])} to {pct(main.loc["ridge_B","annual_return"])} for Ridge and from {pct(main.loc["xgboost_A","annual_return"])} to {pct(main.loc["xgboost_B","annual_return"])} for XGBoost. Paired block intervals include zero. Lasso A and B are identical because all factor-value coefficients are zero; its observed trades are explained by one missingness flag. The simple fundamental score earns {pct(supplemental.loc["equal_weight_scores_C","annual_return"])}, versus SPY at {pct(spy)}. These results support a limited, model-dependent incremental-information claim, rather than robust outperformance.')
    text('Extensions add 810 funded decile backtests, matched neutralization diagnostics, 18 pure-fundamental model fits, and sensitivity checks. They are retrospective analyses of an already observed evaluation period; the frozen main models are not reselected.')
    table(['Submission status','Action still required'],[['Research and local computation','Completed subject to explicitly disclosed data/source limitations'],['Student IDs and actual contributions','Blank at user request; names confirmed'],['Video, independent teammate reproduction, final upload','Pending human/team action']],[140,width-140])
    text('<b>Draft limitation.</b> Historical universe construction, strict financial vintages, and some terminal payoffs cannot be recovered from the supplied files. Three original Chinese research PDFs are unavailable. This document is a reviewable research draft, not a claim that these external requirements are complete.')

    page('Questions, comparisons and research chronology')
    table(['Question','Test','Decision rule'],[['Does reconstruction improve ratios?','Paired RankIC and common-sample Top100 portfolios','Keep both positive and negative evidence'],['Do fundamentals improve price signals?','A versus B within Ridge, Lasso and XGBoost','Same samples, fitted windows, hyperparameters and trading rules'],['Do costs explain performance differences?','Gross/net returns, turnover, smoothing and block intervals','No selection on retrospective evaluation returns']],[135,190,width-325])
    text('A uses the three selected price-volume signals. B adds all six fundamental signals. C is a supplementary fundamental-only group. Equal-score A/B/C and an eligible-pool equal-weight portfolio provide simpler benchmarks.')
    text('The discussion plan initially proposed five-day open-based returns, roughly ten WQ factors, and an 80% coverage threshold. The implemented v2 target was explicitly revised to next-close ten-day returns; actual screening retains WQ040, WQ019 and WQ026. The executed threshold is 50%; a later 80% diagnostic produces the same pre-deduplication passing set.')
    text('The 2023-2025 period had already been inspected during earlier work. This version is chronological and mechanically out of training at each forecast date, but it is not an untouched blind holdout. Several fundamental source reports date to 2026; their use is a retrospective research design, not evidence that a live 2015 investor used these published methods.')
    text('Changes from v1 include the target, factor list, validation choices and stable tie handling. Aggregate return differences across versions cannot be assigned to any single change without a controlled ablation.')
    provenance('factor_selection.json','frozen_model_choices.json','extensions/robustness/coverage_thresholds.json')

    page('Data scope and unresolved provenance')
    table(['Quantity','Observed supplied data'],[['Panel calendar',f'{scope["first"]} to {scope["last"]}: {scope["axis_dates"]:,} sessions'],['Security-ID union',f'{scope["union_sids"]:,} columns, not simultaneous daily membership'],['2015-2025 daily eligibility',f'Min {scope["min_daily"]:,}; median {scope["median_daily"]:,.0f}; max {scope["max_daily"]:,}'],['Input integrity','75 source files and the independent v2 snapshot verified by hashes'],['Research acceptance flag','False: retained honestly, not overridden']],[170,width-170])
    story.append(Image(str(figs/'universe.png'),width=width,height=165))
    text('The supplied daily universe is substantially smaller than the original 4,000+ daily ambition. Export/filter code and verified historical security-type/primary-issue eligibility are unavailable. The union must not be substituted for daily membership. Current comparisons are conditional on the provided universe.')
    text('Statements are latest available vintages with approximate release availability, not a complete historical point-in-time archive. Historical SIC and security links also have source limitations. Original CCM/universe lineage and unresolved terminal settlements require the data provider; numerical sensitivity cannot establish those facts.')
    provenance('input_signature.json','run_verification.json','extensions/audit/data_scope.json','extensions/audit/data_limits.json')

    page('Target timing and expanding training windows')
    text('<b>Label:</b> y[T] = adjusted_close[T+11] / adjusted_close[T+1] - 1. It spans exactly ten close-to-close holding intervals. The final eleven signal sessions are censored, and missing execution/ending prices or broken adjustment segments are not bridged.')
    table(['When','Information / action'],[['T close','Build factors from information available by signal date'],['T+1 close','Execute the signal after one full-session delay'],['T+2','First close-to-close return earned by the new holdings'],['T+11 close','The ten-interval target is fully realized']],[100,width-100])
    hist=json.loads((ext/'pure_C/training_history.json').read_text());h=[x for x in hist if x['model']=='ridge']
    table(['Forecast half','Training rows','Last signal','Last label end'],[[r['half'],f'{r["samples"]:,}',r['train_last_signal'],r['train_last_label_end']] for r in h])
    text('Each fit starts from 2015 and includes only eligible, observed-feature rows with finite labels whose exact label end is strictly before the forecast half begins. The same row mask is used across A/B/C. Cross-sectional transforms use the current eligible cross-section; they do not estimate future moments. Each half is a fresh fit, including XGBoost.')
    text('Daily IC summaries also remove labels ending beyond the reported phase/year. Reported ICIR is daily mean divided by daily standard deviation, without annualization. Newey-West t statistics use lag 10 and retain missing calendar slots; they remain approximate under overlap and selection.')
    provenance('training_history.json','extensions/pure_C/training_history.json','extensions/statistics/factor_summary.csv')

    page('Six fundamental signals: implementation and limits')
    table(['Signal','Implemented definition','Source in team plan'],[['F1 EP residual','OLS residual: signed-log TTM net income on signed-log market cap','Orient Securities 2024, pp.8,23'],['F2 BP residual','OLS residual: signed-log book equity on signed-log market cap','Orient Securities 2024, pp.8,29'],['F3 quarterly SP residual','OLS residual: signed-log quarterly sales on signed-log market cap','Orient Securities 2024, pp.8,25'],['F4 quarterly ROE residual','OLS residual: signed-log quarterly income on signed-log book equity','Orient Securities 2024, pp.8,37'],['F5 FCF yield','(TTM operating cash flow - TTM capex) / (market cap + liabilities - cash)','Northeast Securities 2026, p.5'],['F6 simple earnings surprise','(Actual quarterly income - seasonal historical prediction) / pre-release market cap','China Merchants Securities 2026, pp.12-13,27']],[100,255,width-355])
    text('For F1-F4, g(x) = sign(x) log(1 + |x| / 1,000,000); daily OLS includes an intercept and at least 30 finite eligible pairs. Fixing USD millions matters because signed-log is not scale invariant. Traditional positive-denominator ratios are retained as separate controls.')
    text('F5 masks non-positive EV and SIC2 60-69 at factor level. It does not remove whole security histories or claim replication of the source strategy. F6 predicts NI[q] as NI[q-4] plus the mean of the prior eight year-on-year dollar changes. All twelve historical quarters must be available before the new release; normalization uses the last close strictly before release.')
    text('The six implementations pass independent sampled numerical checks against the team-defined formulas. The original Chinese report PDFs are missing, so their exact formulas, accounting mapping and page references remain unverified. This is an explicit external-source gap.')
    provenance('extensions/audit/fundamental_formula_inventory.csv','extensions/audit/independent_formula_checks.csv')

    page('WorldQuant candidates and formula audit')
    text('Only 36 supported price-volume formulas are implemented; this is not a screen of all 101. Their field dependencies, windows, source identifiers, missing rules and operator conventions are inventoried. No implemented candidate requires VWAP or average dollar volume.')
    table(['Selected signal','Main construction','Economic hypothesis'],[['WQ019','7-session price-change sign interacting with ranked 250-session return sum','Short-horizon reversal conditional on longer return history'],['WQ026','Rolling maximum of correlation between 5-session time ranks of volume and high','Price-volume co-movement and reversal'],['WQ040','Negative ranked 10-session high-price volatility times high/volume correlation','Volatility and participation interaction']],[95,240,width-335])
    text('The sign/window/operator structures were checked against Appendix A of Kakushadze (2015). Independent loop references for the three selected formulas include tied volume values and missing windows. All 36 candidates have a future-perturbation causality regression test. These are distinct checks: causal code can still implement a wrong formula.')
    text('Project conventions are explicit: average percentile ranks, full rolling windows, sample standard deviation (ddof=1), segmented forward-anchored prices and the contemporaneous eligible cross-section. The source does not fully specify every numerical convention. WQ053/054 were originally delay-0 expressions; this study deliberately evaluates all candidates with T+1 execution and a longer target. It is a signal adaptation, not replication of the original portfolios.')
    audit=read(ext,'audit/independent_formula_checks.csv')
    text(f'The audit contains {len(audit)} independent numeric checks. Frozen fundamental residuals use float32 arithmetic; the maximum sampled discrepancy against double-precision OLS is {audit.loc[audit.factor.str.startswith("F0"),"max_abs_error"].max():.2g}. This small rounding difference is disclosed and is not labeled exact numerical identity.')
    text('Primary WQ source: <link href="https://arxiv.org/pdf/1601.00991" color="#167b87">101 Formulaic Alphas, Appendix A</link>. Three original Chinese reports still require team verification.')
    provenance('extensions/audit/wq_formula_inventory.csv','extensions/audit/formula_audit.json')

    page('Screening and unified single-factor statistics')
    screen=read(base,'evaluation/factor_screen.csv').set_index('factor')
    table(['Candidate','2019-21 signed RankIC','Coverage','Disposition'],[[n,num(screen.loc[n,'stability_rankic_signed']),pct(screen.loc[n,'stability_coverage']),('Selected' if n in selection['wq'] else 'Correlated with WQ040' if n=='WQ006' else 'Below 0.01 RankIC')] for n in ['WQ040','WQ019','WQ026','WQ006','WQ052']],[95,125,95,width-315])
    text('Direction is fixed from 2015-2018. Stability uses 2019-2021, requiring signed RankIC at least 0.01, eligible coverage at least 50%, and two positive stability years; redundancy is then removed. Raising coverage to 80% leaves the same passing candidate set. WQ006 is removed for its approximately 0.801 daily rank correlation with WQ040. No factor is added to meet an arbitrary count.')
    text('<b>2019-2021, frozen directions, raw factors.</b> IR columns below are daily, not annualized. Coverage measures finite factor/label pairs relative to eligible rows.')
    table(['Factor','IC','RankIC','ICIR','RankICIR','Cover','Days'],statrows('stability'),[135,52,58,55,65,65,width-430])
    provenance('evaluation/factor_screen.csv','extensions/statistics/factor_summary.csv','extensions/robustness/coverage_thresholds.json')

    page('Validation stability and prediction horizons')
    text('<b>2022 validation statistics.</b> These descriptive statistics do not change the frozen direction or shortlist.')
    table(['Factor','IC','RankIC','ICIR','RankICIR','Cover','Days'],statrows('validation'),[135,52,58,55,65,65,width-430])
    horizon=read(base,'supplement/factor_horizons.csv');fig,ax=plt.subplots(figsize=(9,3))
    for name in factors:
        z=horizon.loc[horizon.factor.eq(name)&horizon.phase.eq('2019-2021')].sort_values('horizon');ax.plot(z.horizon,z.rankic,marker='o',label=short(name))
    ax.axhline(0,color='gray',lw=.7);ax.set_xticks([1,5,10,20]);ax.set_xlabel('Next-close holding intervals');ax.set_ylabel('Mean signed RankIC');ax.legend(ncol=3,fontsize=7)
    chart('horizons',fig,190,'2019-2021 horizon diagnostics; overlapping labels are not trading returns.')
    text('An increasing long-horizon RankIC can coexist with weak daily execution performance. Signal persistence, universe coverage, concentration and costs also affect a funded portfolio. Full early-period, annual and evaluation statistics are supplied as CSV rather than used for retrospective reselection.')
    provenance('extensions/statistics/factor_annual.csv','supplement/factor_horizons.csv')

    page('Redundancy: all nine signals on paired samples')
    cor=pd.read_csv(ext/'correlation/stability_spearman.csv',index_col=0).reindex(index=factors,columns=factors)
    fig,ax=plt.subplots(figsize=(8,6));im=ax.imshow(cor,vmin=-1,vmax=1,cmap='RdBu_r');ax.set_xticks(range(9),[short(n) for n in factors],rotation=45,ha='right');ax.set_yticks(range(9),[short(n) for n in factors]);fig.colorbar(im,ax=ax,shrink=.75,label='Mean daily Spearman')
    for i in range(9):
        for j in range(9):ax.text(j,i,f'{cor.iloc[i,j]:.2f}',ha='center',va='center',fontsize=7,color='white' if abs(cor.iloc[i,j])>.65 else 'black')
    chart('correlations',fig,350)
    tri=[(abs(cor.iloc[i,j]),factors[i],factors[j],cor.iloc[i,j]) for i in range(9) for j in range(i)];tri.sort(reverse=True)
    text('Each cell first computes a same-day Spearman correlation on the pair-specific finite eligible sample (minimum 30), then averages across days. It is not a pooled time-series correlation and is separate from correlation with risk-model styles. Pair counts and matrices for all four phases are exported.')
    table(['Largest absolute pair','Mean correlation'],[[short(a)+' / '+short(b),num(c)] for _,a,b,c in tri[:3]],[width-110,110])
    provenance('extensions/correlation/stability_spearman.csv','extensions/correlation/stability_mean_pairs.csv')

    page('Funded deciles: design and net return ordering')
    text('For each signal, rank currently tradable eligible securities using the frozen direction; divide the sorted list into ten exhaustive equal-count groups. SHA256 of seed 5205 and security ID resolves ties. Group sizes differ by at most one at formation. Every sleeve is long-only and funded; group size is approximately one tenth of the valid pool, unlike the separate Top100 experiments.')
    text('Orders execute at T+1 close, rebalance every five sessions and pay 10 bps per traded dollar. Constant-score days supply no ranking signal and target cash on the scheduled trade. Delayed exits, stale marks and terminal policies use the same ledger as the main experiment. Separate 2019-2021, 2022 and 2023-2025 portfolios each start from cash; their paths are not spliced.')
    z=dec.loc[dec.variant.eq('raw')&dec.phase.eq('evaluation')].pivot(index='factor',columns='group',values='annual_return').reindex(factors)
    fig,axes=plt.subplots(3,3,figsize=(10,6),sharex=True)
    for ax,(name,row) in zip(axes.flat,z.iterrows()):ax.bar(range(1,11),row,color='#258695');ax.set_title(short(name),fontsize=9);ax.yaxis.set_major_formatter(PercentFormatter(1));ax.axhline(0,color='gray',lw=.7)
    fig.supxlabel('Decile (1 = lowest signed signal; 10 = highest)');chart('decile_cagr',fig,330,'2023-2025 net CAGR. This period was observed before these diagnostics were added.')
    provenance('extensions/deciles/summary.csv','extensions/extension_protocol.json')

    page('Decile wealth paths and monotonicity')
    fig,axes=plt.subplots(3,3,figsize=(10,6),sharex=True)
    for ax,name in zip(axes.flat,factors):
        for g in range(1,11):
            d=pd.read_csv(ext/'deciles'/name/'raw'/'evaluation'/f'G{g:02}'/'daily.csv',dtype={'date':str})
            ax.plot(pd.to_datetime(d.date,format='%Y%m%d'),d.net_nav,color=plt.cm.viridis((g-1)/9),lw=.65)
        ax.set_title(short(name),fontsize=9);ax.tick_params(axis='x',rotation=25,labelsize=6)
    chart('decile_wealth',fig,300,'Each sleeve starts from cash. Purple = G1; yellow = G10. These are actual net wealth paths.')
    mm=mono.loc[mono.variant.eq('raw')&mono.phase.eq('evaluation')].set_index('factor').reindex(factors)
    table(['Factor','CAGR rank rho','Ordered adjacent pairs','G10-G1 ann. mean','HAC t'],[[short(n),num(r.group_cagr_spearman),pct(r.adjacent_non_decreasing_fraction),pct(r.G10_minus_G1_arithmetic_annualized),num(r.G10_minus_G1_hac_t_lag10)] for n,r in mm.iterrows()],[150,80,100,100,width-430])
    text('G10 minus G1 is the difference between two funded long-only sleeve returns, annualized arithmetically for diagnosis. It is not a live long-short portfolio: leverage, financing, borrow costs and availability have not been implemented. Positive RankIC alone does not guarantee ordered net decile returns.')
    provenance('extensions/deciles/monotonicity.csv','extensions/deciles/*/raw/evaluation/G*/daily.csv')

    page('Industry and size neutralization: matched prediction')
    text('On each signal date, regress the signed factor percentile on full SIC2 industry dummies and standardized log market cap. Full dummies span the intercept. Use only positive-cap, known-industry, finite-factor eligible securities. At least 30 pairs and more observations than design rank plus two are required. Near-zero residual variance supplies no neutral signal.')
    text('Raw-common and neutral-common statistics use exactly the same finite residual mask. The first is the signed percentile before OLS; the second is its residual. This keeps sample loss separate from neutralization. RankIC remains comparable; Pearson IC here concerns percentiles/residuals and differs from raw-level Pearson IC on page 7. There is no target input to neutralization.')
    z=stats.loc[stats.phase.eq('stability')&stats.variant.isin(['raw_common','neutral_common'])].pivot(index='factor',columns='variant',values='rankic').reindex(factors)
    coverage=stats.loc[stats.phase.eq('stability')&stats.variant.eq('neutral_common')].set_index('factor')
    table(['Factor','Raw common RankIC','Neutral RankIC','Difference','Common coverage'],[[short(n),num(r.raw_common),num(r.neutral_common),num(r.neutral_common-r.raw_common),pct(coverage.loc[n,'mean_coverage'])] for n,r in z.iterrows()],[155,90,90,85,width-420])
    fit=read(ext,'neutral/fit_summary.csv');text(f'The maximum double-precision normal-equation orthogonality error over all fits is {fit.max_abs_orthogonality.max():.2g}. Residuals are stored as float32 after estimation. Missing controls remove observations from both sides of the matched comparison, rather than being treated as zero controls.')
    text('This is a diagnostic extension. It does not replace the original model inputs, change target returns, or choose a new strategy using evaluation-period results. Historical industry/cap quality still limits the interpretation of residual information.')
    provenance('extensions/neutral/fit_summary.csv','extensions/statistics/factor_summary.csv')

    page('Neutralization: matched funded portfolio evidence')
    zs=dec.loc[dec.phase.eq('evaluation')&dec.group.eq(10)&dec.variant.isin(['raw_common','neutral_common'])].pivot(index='factor',columns='variant',values='annual_return').reindex(factors)
    fig,ax=plt.subplots(figsize=(10,3.5));x=np.arange(9);ax.bar(x-.19,zs.raw_common,.38,label='Raw common');ax.bar(x+.19,zs.neutral_common,.38,label='Neutral common');ax.set_xticks(x,[short(n) for n in factors],rotation=35,ha='right');ax.yaxis.set_major_formatter(PercentFormatter(1));ax.legend();chart('neutral_deciles',fig,250,'G10 net CAGR, 2023-2025; both variants use matched signal-date coverage.')
    mn=mono.loc[mono.phase.eq('evaluation')&mono.variant.eq('neutral_common')].set_index('factor')
    table(['Factor','Raw G10 CAGR','Neutral G10 CAGR','Neutral ordering rho'],[[short(n),pct(r.raw_common),pct(r.neutral_common),num(mn.loc[n,'group_cagr_spearman'])] for n,r in zs.iterrows()],[170,105,110,width-385])
    text('Removing industry and size can alter signal strength and funded returns in different directions. Matched coverage avoids attributing a changed security sample to neutralization itself. These comparisons do not establish a causal structural effect and do not remove omitted styles or all fundamental accounting risk.')
    text('Month-end G10 style snapshots are exported for both matched variants, including missing-exposure weights and industries. Neutralizing factor scores does not guarantee that a ranked G10 portfolio has zero industry or size exposure. These are monthly beginning-holdings snapshots with lagged risk exposures, not daily means.')
    provenance('extensions/deciles/summary.csv','extensions/deciles/monotonicity.csv','extensions/neutral/monthly_G10_mean_styles.csv')

    page('Model design and 2022 validation')
    text('Each factor is transformed to its eligible cross-sectional percentile, centered and paired with a missingness flag. Missing values receive a zero centered score and flag one. A has 6 columns (3 values + 3 flags); B has 18; C has 12. At least one A price feature must be observed for the shared row mask; missing fundamental inputs do not delete rows differently across A/B/C.')
    grid=read(base,'validation/hyperparameters.csv')
    table(['Model','Candidate parameters','2022 RankIC'],[[r.model,r.params,num(r.rankic)] for r in grid.itertuples()],[85,310,width-395])
    table(['Frozen choice','Value'],[['Ridge','alpha = 0.01 x training sample count'],['Lasso','alpha = 0.0005; no post-test reduction'],['XGBoost','depth 2; 120 trees; remaining settings fixed in code'],['Trading','1-session score mean; rebalance every 5 sessions; Top100; 10 bps']],[140,width-140])
    text('Hyperparameters are selected using A-only validation RankIC; identical parameters are applied to B and supplementary C. Trading choices are selected from the small 2022 grid using the declared main validation procedure. Score smoothing averages daily percentile scores and does not smooth realized returns. Ties are resolved with the same fixed seed for every model family.')
    text('A/B comparisons share all training rows and forecast dates. Fundamental additions therefore test added columns within a fixed design, not a better-tuned B model. Their uncertainty still includes selection and historical-data limitations not captured by a simple return bootstrap.')
    provenance('model_protocol.json','validation/hyperparameters.csv','validation/trading_rules.csv','frozen_model_choices.json')

    page('Main net results and SPY comparison')
    table(['Strategy','CAGR','Volatility','Sharpe','Max DD','Daily turnover'],performance_rows(main),[110,75,80,70,80,width-415])
    fig,ax=plt.subplots(figsize=(10,4))
    for n in names:ax.plot(dates,daily[n].net_nav,label=short(n),lw=1)
    ax.plot(dates,(1+daily[names[0]].benchmark_return).cumprod(),color='black',ls='--',label='SPY');ax.set_ylabel('Net wealth from 1');ax.legend(ncol=4,fontsize=7);chart('main_wealth',fig,250)
    text(f'SPY net wealth here is a supplied return benchmark with no additional benchmark trading fee; its CAGR is {pct(spy)}. Strategy returns pay 10 bps per traded dollar, including initial entry and final liquidation. Cash earns zero, and Sharpe uses a zero risk-free rate. No main strategy beats SPY on CAGR in this sample.')
    text('Ridge and XGBoost fusion slightly improve CAGR; XGBoost B has higher volatility and a lower Sharpe than A. Lasso A/B are exactly identical and require the mechanism diagnosis on page 18. An identical pair is not statistical evidence that economic fundamental information has no effect in every model.')
    provenance('backtests/summary.csv','backtests/*_daily.csv')

    page('Annual and half-year variation')
    annual=read(base,'backtests/annual.csv');halves=read(base,'supplement/halfyear_performance.csv');p=annual.pivot(index='strategy',columns='year',values='total_return').reindex(names)
    table(['Strategy']+[str(y) for y in p.columns],[[short(n)]+[pct(v) for v in r] for n,r in p.iterrows()],[width*.34]+[width*.22]*3)
    z=halves.assign(strategy=halves.model+'_'+halves.family).pivot(index='strategy',columns='half',values='total_return').reindex(names)
    fig,ax=plt.subplots(figsize=(10,4));im=ax.imshow(z,cmap='RdBu',vmin=-.35,vmax=.35,aspect='auto');ax.set_xticks(range(6),z.columns);ax.set_yticks(range(6),[short(n) for n in names]);fig.colorbar(im,ax=ax,label='Actual half-year total return')
    for i in range(6):
        for j in range(6):ax.text(j,i,pct(z.iloc[i,j]),ha='center',va='center',fontsize=8)
    chart('half_returns',fig,245)
    text('Half-year cells are actual total returns for each evaluation segment; they are not annualized. They describe different market environments and freshly trained models. Results do not justify picking one half or changing hyperparameters after seeing the cell values.')
    text('The final 2025H2 Lasso forecast becomes constant, so scheduled trades liquidate into cash. Its full-period performance partly reflects earlier missingness-driven holdings. Report both return and cash exposure; interpreting the whole period as a continuously invested stock-selection model is misleading.')
    provenance('backtests/annual.csv','supplement/halfyear_performance.csv','extensions/lasso/diagnostics.csv')

    page('Costs, turnover and smoothing across all models')
    rows=[]
    for n in names:
        d=daily[n];gross=(1+d.gross_return).prod()**(252/len(d))-1
        rows.append([short(n),pct(gross),pct(main.loc[n,'annual_return']),pct(d.cost.sum()),pct(main.loc[n,'mean_daily_turnover'])])
    table(['Strategy','Gross CAGR','Net CAGR','Sum daily costs','Daily turnover'],rows,[110,95,95,110,width-410])
    fig,axes=plt.subplots(1,3,figsize=(10,3),sharey=True)
    for ax,family in zip(axes,['ridge','lasso','xgboost']):
        for group in ['A','B']:
            for freq in [1,5]:
                z=smooth.loc[smooth.model.eq(family)&smooth.family.eq(group)&smooth.rebalance_every.eq(freq)].sort_values('smooth');ax.plot(z.smooth,z.annual_return,marker='o',label=f'{group}, every {freq}')
        ax.set_title(family);ax.set_xticks([1,3,5,10]);ax.yaxis.set_major_formatter(PercentFormatter(1))
    axes[-1].legend(fontsize=6);fig.supxlabel('Trailing score smoothing sessions');chart('all_smoothing',fig,205,'All 48 cases are descriptive; frozen main choice remains smooth=1, rebalance=5.')
    text('Sum of daily fee fractions is an arithmetic cost diagnostic, not a CAGR subtraction. The gross/net CAGR gap also compounds over time. Smoother signals and fewer trades may reduce costs but can lose responsiveness or change holdings; select neither window nor model using this retrospective grid.')
    provenance('backtests/*_costs.csv','extensions/robustness/all_model_smoothing.csv')

    page('Lasso: a missingness rule rather than value selection')
    da=diag.loc[diag.model.eq('lasso_A')]
    table(['Half','Nonzero value coefs','Nonzero missing coefs','Median score levels','Constant days'],[[r.half,r.nonzero_values,r.nonzero_missing,num(r.median_unique),r.constant_days] for r in da.itertuples()],[90,110,115,105,width-420])
    co=read(ext,'lasso/coefficients.csv');active=co.loc[co.model.eq('lasso_A')&co.missing_coef.ne(0)]
    table(['Half','Active missing flag','Coefficient'],[[r.half,r.factor,f'{r.missing_coef:.6f}'] for r in active.itertuples()],[100,240,width-340])
    eq=json.loads((ext/'lasso/missingness_only_summary.json').read_text())
    text(f'All A/B factor-value coefficients are zero in all six evaluation fits. Before 2025H2, WQ019 missingness is the only nonzero input coefficient, with a negative sign: the model prefers the observed group. Scores typically have two levels, creating large boundary ties. The fixed seed provides reproducible Top100 selection within that bucket, without value information to distinguish those stocks.')
    text(f'The algebraic score consisting only of saved intercepts plus missing-indicator coefficients reproduces the main Lasso portfolio daily net returns with maximum absolute error {eq["max_daily_error"]:.2g}. It is the same strategy written explicitly, not an independent winning model. A/B identity reflects this fitted degeneracy; zero paired intervals are mechanical.')
    text('Validation diagnostics cover both 2022 halves under the already chosen parameter. The result is reported as a failure mode. Lowering alpha now to force value coefficients would be a new retrospective experiment requiring separate labeling; no such reselection is performed here.')
    provenance('extensions/lasso/diagnostics.csv','extensions/lasso/coefficients.csv','extensions/lasso/missingness_only_summary.json')

    page('What WQ019 missingness selects')
    z=profiles.loc[profiles.phase.eq('evaluation')].sort_values('missing')
    table(['WQ019 group','Mean group size','Mean log cap','Observed quote age','Eligibility streak','Left censored share'],[[('Missing' if r.missing else 'Observed'),f'{r.mean_group_size:.1f}',num(r.mean_log_cap),f'{r.mean_observed_quote_age_sessions:.0f}',f'{r.mean_consecutive_eligible_sessions:.0f}',pct(r.first_quote_left_censored_share)] for r in z.itertuples()],[80,85,80,90,85,width-420])
    ind=read(ext,'lasso/missingness_industries.csv');p=ind.loc[ind.phase.eq('evaluation')].pivot_table(index='industry',columns='missing',values='stock_day_share',fill_value=0);p['difference']=p.get(True,0)-p.get(False,0);p=p.reindex(p.difference.abs().sort_values(ascending=False).index).head(8)
    table(['Industry','Observed share','Missing share','Difference'],[[n,pct(r.get(False,0)),pct(r.get(True,0)),pct(r['difference'])] for n,r in p.iterrows()],[150,115,115,width-380])
    text('Profiles use daily eligible/observed-feature groups, then average daily means; industry shares pool stock-days. Missing WQ019 is associated with smaller market capitalization and shorter continuous eligibility histories. A 250-session return-sum window can be absent because of limited eligible price history or gaps, so the flag captures more than absence of an accounting fact.')
    text('Observed quote age counts sessions since the first valid quote in this supplied panel. It is left censored and is not verified IPO age, firm age or security listing age. Eligibility streak measures the current consecutive run inside the provided universe. The table documents an association and cannot establish a causal economic explanation.')
    provenance('extensions/lasso/missingness_profiles.csv','extensions/lasso/missingness_industries.csv')

    page('Fundamental-only models and simple benchmarks')
    table(['Strategy','CAGR','Volatility','Sharpe','Max DD','Daily turnover'],performance_rows(C),[110,75,80,70,80,width-415])
    simple=supplemental.loc[['equal_weight_scores_A','equal_weight_scores_B','equal_weight_scores_C','equal_weight_eligible_pool']]
    table(['Simple baseline','CAGR','Volatility','Sharpe','Max DD','Daily turnover'],performance_rows(simple),[110,75,80,70,80,width-415])
    text('The supplementary C model fits use exactly the A-chosen parameters and shared sample masks: six fundamental values plus six flags, no C-specific tuning. All 18 fits are separate from the frozen A/B experiment. This controls flexibility but does not claim the parameters are optimal for C.')
    text(f'XGBoost C earns {pct(C.loc["xgboost_C","annual_return"])} and Ridge C earns {pct(C.loc["ridge_C","annual_return"])}. Lasso C has no nonzero coefficients and remains in cash under the constant-score policy. The equal-score fundamental strategy earns {pct(simple.loc["equal_weight_scores_C","annual_return"])}. Added model complexity does not consistently beat this simple aggregation in the observed sample.')
    text('Equal-score C is a Top100 ranking from an equal-weight average of available centered factor percentiles, not a portfolio of six separately funded sleeves. Its performance should not be attributed to the trained C models. All use the same execution, tie and cost conventions, and its best observed return does not retroactively make it the selected main model.')
    provenance('extensions/pure_C/summary.csv','extensions/pure_C/training_history.json','supplement/portfolio_summary.csv')

    page('Reconstruction versus traditional ratios')
    controls=read(base,'supplement/reconstruction_vs_ratio.csv');cc=controls.loc[controls.phase.eq('2019-2021')]
    table(['Reconstructed signal','Reconstructed RankIC','Ratio RankIC','Difference'],[[short(r.reconstructed),num(r.reconstructed_rankic),num(r.ratio_rankic),num(r.difference)] for r in cc.itertuples()],[165,115,110,width-390])
    rows=[]
    for phase in ['stability','validation','evaluation']:
        for name in selection['fundamental'][:4]:
            z=ratios.loc[ratios.pair.eq(name)&ratios.phase.eq(phase)].set_index('factor');control=name.replace('reconstructed','ratio').replace('F0','C0');a,b=z.loc[name],z.loc[control]
            rows.append([short(name),phase,pct(a.annual_return),pct(b.annual_return),pct(a.annual_return-b.annual_return)])
    table(['Signal','Phase','Residual CAGR','Ratio CAGR','Difference'],rows,[145,85,90,90,width-410])
    text('Each paired portfolio uses the common finite sample for that reconstructed signal and its traditional ratio, the already frozen individual direction, and identical Top100 trading rules. Sample coverage and directions therefore remain explicit. A change in RankIC does not guarantee a trading advantage; net CAGR also depends on tail rankings and turnover.')
    text('Results vary by accounting dimension and phase. The evidence supports signal-specific comparisons, not a blanket claim that residual reconstruction always improves a traditional ratio. Matched portfolio paths and costs are available for all 24 sleeves.')
    provenance('supplement/reconstruction_vs_ratio.csv','extensions/comparisons/ratio_portfolios.csv')

    page('Research risk model and reconciled attribution')
    styles=read(base,'barra_style/mean_style_exposures.csv').set_index('strategy')
    fig,ax=plt.subplots(figsize=(10,3.3));im=ax.imshow(styles,cmap='RdBu_r',vmin=-2,vmax=2,aspect='auto');ax.set_xticks(range(styles.shape[1]),styles.columns,rotation=35,ha='right');ax.set_yticks(range(6),[short(n) for n in styles.index]);fig.colorbar(im,ax=ax,label='Mean standardized exposure');chart('style_exposures',fig,215)
    attr=read(base,'barra_style/attribution_summary.csv').set_index('strategy')
    table(['Strategy','Market','Industry','Style','Specific','Costs'],[[short(n)]+[pct(r[k]) for k in ['Market','Industry','Style','Specific_or_unexplained','Costs']] for n,r in attr.iterrows()],[110,79,79,79,79,width-426])
    text('Entries are Carino-linked contributions to cumulative strategy return minus SPY, in percentage points over the whole evaluation period; they are not annualized returns. The benchmark subtraction component is exported separately. Daily components reconcile to net strategy minus benchmark returns, including costs.')
    text('This is an estimated research model with nine styles and industry dummies, not a commercial Barra replication. Growth is unavailable; missing financial values and imperfect historical industries remain. Exposures are lagged to the held-return date and factor returns are estimated cross-sectionally. Size tilts are material, especially for price-signal portfolios.')
    text('Specific_or_unexplained is the residual required for reconciliation. It contains omitted styles, idiosyncratic effects and data/model error; it is not certified alpha. The same risk-factor return series is used for the supplementary C attribution, whose reconciled output is exported separately.')
    provenance('barra_style/mean_style_exposures.csv','barra_style/attribution_summary.csv','extensions/pure_C/attribution/summary.csv')

    page('Paired uncertainty and terminal-payoff sensitivity')
    table(['Model','Block sessions','B-A CAGR','95% lower','95% upper'],[[r.model,r.block,pct(r.cagr_difference),pct(r.cagr_diff_ci_low),pct(r.cagr_diff_ci_high)] for r in bootstrap.itertuples()],[100,100,100,100,width-400])
    text('The paired circular block bootstrap resamples the same blocks for A and B (2,000 replications; seed 5205). All nondegenerate CAGR-difference intervals include zero across block lengths 10, 20, 40 and 60. These intervals describe realized paired returns, conditional on model selection; they do not adjust for the full research search or prove equivalence.')
    hp=haircuts.pivot(index='strategy',columns='unknown_terminal_haircut',values='annual_return').reindex(names)
    table(['Strategy','0% haircut','50% haircut','100% haircut'],[[short(n)]+[pct(v) for v in r] for n,r in hp.iterrows()],[170,110,110,width-390])
    text('There are 61 terminal rows without a valid source payoff across the complete panel. The scenarios haircut the marked terminal value only on those rows, then replay the complete ledger; most rows are not held by every strategy. They are hypothetical losses, not recovered settlements. A zero haircut reproduces the baseline. Event counts and held weights are exported to prioritize source follow-up.')
    provenance('extensions/robustness/block_intervals.csv','extensions/robustness/terminal_haircuts.csv','extensions/audit/event_impact.csv')

    page('Conclusions, correctness and remaining boundaries')
    text('<b>Reconstruction.</b> Matched prediction and funded portfolios differ by signal and period. Residual accounting strength is not a universal replacement for ratios. Its incremental content should be described using the corresponding paired rows, rather than the most favorable factor alone.')
    text('<b>Fusion.</b> Ridge/XGBoost B deliver small CAGR improvements with intervals spanning zero; XGBoost B increases risk. Lasso provides no value-coefficient evidence at the chosen penalty. Simple fundamental aggregation remains a strong explanatory benchmark, while SPY outperforms all main strategies on CAGR.')
    text('<b>Implementation.</b> Turnover and fees materially affect active price-signal portfolios. Neutralization and funded deciles add evidence on ranking versus style exposure, without replacing the frozen main experiment. The missingness diagnosis explains why one apparently successful regularized model is not selecting factor values.')
    table(['Issue','Approved correction / consequence'],[['B001, P1 terminal boundary','Vendor terminal payoff overrides a finite stale mark; log assumptions. Current supplied trigger impact was zero.'],['B002, P3 metadata wording','Replace fixed ten-factor claim with all actually selected factors.'],['B003, P1 Top100 partial ties','Seed-5205 stable SID hash; all-constant remains cash; validation and all backtests rerun.'],['B004, P3 NumPy dates','Explicit nanosecond NaT; unchanged arrays; regression verified.']],[115,width-115])
    text('Validation includes meaningful operator/ledger tests, independent label and holdings checks, extension algebraic checks, and baseline/source hash preservation. A documented third-party pandas/calendar timezone deprecation warning remains; it is not concealed by a claim that all warnings-as-errors checks pass.')
    text('External gaps remain: universe lineage, original Chinese reports, verified financial vintages and terminal facts, student IDs/contributions, video and a teammate independently reproducing the final commands. Member names are confirmed. These limitations restrict inference and submission readiness; they are not resolved by adding models.')
    provenance('run_verification.json','run_issues.md','extensions/audit/extension_verification.json')

    page('References, reproducibility and team handoff')
    text('<b>Primary methodological source.</b> Kakushadze, Z. (2015), <i>101 Formulaic Alphas</i>, arXiv:1601.00991, Appendix A. Source expressions and operator definitions checked online. <link href="https://arxiv.org/pdf/1601.00991" color="#167b87">https://arxiv.org/pdf/1601.00991</link>')
    text('<b>Fundamental sources cited in the team plan.</b> Orient Securities (2024-03-21), Fundamental Factor Reconstruction, pp.8,23,25,29,37. Northeast Securities (2026-07-22), Free Cash Flow Strategy Quality and Trend Enhancement, p.5. China Merchants Securities (2026-05-18), Beyond Analyst Expectations: Earnings Expectation Models, pp.12-13,27. English titles are descriptive translations; original PDFs and page claims still await verification.')
    text('<b>Data and software.</b> Supplied CRSP/Compustat-derived local export and SPY return series; no claim of unrestricted redistribution. Python dependencies and exact installed versions are recorded with the run. Ridge/Lasso: scikit-learn. Boosted trees: XGBoost. Statistics and plotting: NumPy, pandas, SciPy, matplotlib. PDF: ReportLab and pypdf.')
    text('<b>Execution.</b> From a clean virtual environment install requirements-project2.txt. README gives exact snapshot/build, run, supplement, risk, extension, verification and PDF commands. Keep the v2 baseline and extension output directories distinct. The main result directory is bound by hashes and is not overwritten by this report generator. A report-only rebuild can consume retained aggregate report inputs and charts.')
    table(['Local output','Role'],[['runs/project2_nextclose10_v2_fixed/','Frozen main v2 experiment and independent verification'],['runs/project2_nextclose10_v2_extensions/','All supplementary computations, report figures and audits'],['reports/Team34_Project2_Report_v2_Draft.pdf','This draft; retained separately from the historical v1 PDF'],['Chinese completion ledger (Markdown, repo root)','Conclusions and remaining team actions; linked from README']],[250,width-250])
    table(['Member (confirmed order)','Student ID','Actual contribution'],[[m['name'],m['student_id'] or '',m['contribution'] or ''] for m in members],[180,120,width-300])
    text('<b>Before submission.</b> Fill the deliberately blank student IDs/contributions; verify unavailable original sources; have another member reproduce the documented commands; record a 15-25 minute video with readable figures and audible narration; check Canvas group, filenames, access and deadline. Do not include restricted raw data or credentials in a public submission.')
    provenance('README.md','extensions/extension_protocol.json','extensions/audit/completion_manifest.json')

    def footer(canvas,doc):
        canvas.setStrokeColor(colors.HexColor('#d6e0e7'));canvas.line(44,39,A4[0]-44,39);canvas.setFont('Helvetica',7);canvas.setFillColor(colors.HexColor('#567080'));canvas.drawString(44,27,'DSA5205 | Team 34 | v2 next-close ten-day research draft');canvas.drawRightString(A4[0]-44,27,str(doc.page))
    SimpleDocTemplate(str(pdf),pagesize=A4,leftMargin=44,rightMargin=44,topMargin=39,bottomMargin=51,title='DSA5205 Team34 Project2 v2 Research Draft',author=member_names).build(story,onFirstPage=footer,onLaterPages=footer)
    reader=PdfReader(pdf);actual=len(reader.pages)
    if actual!=len(titles) or not 15<=actual<=25:raise ValueError(f'Report overflow: expected {len(titles)}, got {actual}')
    for i,t in enumerate(titles):
        if ' '.join(t.split()) not in ' '.join(reader.pages[i].extract_text().split()):raise ValueError(f'Page title missing: {i+1}')
    manifest={'pages':actual,'page_titles':titles,'pdf_sha256':digest(pdf),'baseline_binding':binding,'source_tables':sorted(source_files),'roster_names_confirmed':True,'student_ids_and_contributions_complete':False,'visual_qa':'pending separate render verification','no_models_refit':True}
    (ext/'paper_manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps({'pdf':str(pdf),'pages':actual},ensure_ascii=False))
