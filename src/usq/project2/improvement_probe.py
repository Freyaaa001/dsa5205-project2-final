"""Exploratory improvement diagnostics; never overwrite or reselect main v2."""
from __future__ import annotations
import argparse
import gc
import json
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from .models import Design,fit_model,halves
from .factors import rank
from .extensions import CachedMarket,digest,summarize_information,progress
from .screen import information_series


def rank_training_target(y,universe,observed,ends,start):
    """Rank labels only on mature eligible training rows, with exact date gates."""
    dates=(y.index>='20150101')&(y.index<start)&ends.lt(start).fillna(False).to_numpy()
    valid=universe.eq(1).to_numpy()&np.asarray(observed)&np.isfinite(y.to_numpy())&dates[:,None]
    frame=y.where(valid);ranks=frame.rank(axis=1,pct=True);ranks=ranks.sub(ranks.mean(axis=1),axis=0)
    raw=y.to_numpy()[valid];ordered=ranks.to_numpy()[valid]
    # Match pooled training-target mean/std, so the same Ridge penalty is not
    # confounded with a simple seven-fold increase of target units.
    scale=float(raw.std()/ordered.std());target=ordered*scale+raw.mean()
    assert np.isfinite(target).all()
    return valid,target,{'raw_target_mean':float(raw.mean()),'raw_target_std':float(raw.std()),'rank_scale':scale}


def run(database,baseline,output):
    db,base,out=map(Path,(database,baseline,output))
    if out.resolve()==base.resolve() or base.resolve() in out.resolve().parents:raise ValueError('Separate output required')
    out.mkdir(parents=True,exist_ok=True)
    policy={'status':'retrospective exploration; 2022 is reused validation, not a new blind holdout',
            'target':'economic return remains T+1 to T+11; only training loss target transformed in explicitly labeled probes',
            'models':['raw_Ridge_A','raw_Ridge_B','rank_Ridge_A','rank_Ridge_B'],
            'ridge_parameters':'same frozen A alpha_per_sample; rank target matched to pooled train raw mean/std',
            'validation_only':'2022; 2023-2025 used only for existing-portfolio profiles and prespecified capitalization diagnostics',
            'trading_probes':['Top100 every5','Top100 every10','Top100 every20','Top300 every5','Top100 every5 inside largest cap half'],
            'capitalization_diagnostics':['eligible EW','largest500 EW','largest100 EW'],
            'cost_bps':10,'smooth':1,'tie_seed':5205,'no_main_reselection':True}
    p=out/'protocol.json'
    if p.exists() and json.loads(p.read_text())!=policy:raise ValueError('Different probe protocol')
    p.write_text(json.dumps(policy,indent=2))
    for sub in ['portfolios','models','predictions','diagnostics']:(out/sub).mkdir(exist_ok=True)
    design=Design(db,base);market=CachedMarket(db);u=design.u
    allowed=u.eq(1)&pd.DataFrame(design.observed,index=u.index,columns=u.columns)
    cap=pd.read_pickle(db/'panels/market_cap.pkl').where(u.eq(1));caprank=rank(cap.where(cap>0));large=caprank.ge(.5)
    choices=json.loads((base/'frozen_model_choices.json').read_text());params=choices['hyperparameters']['ridge']['params']
    y=pd.DataFrame(design.y,index=u.index,columns=u.columns)
    selections=json.loads((base/'factor_selection.json').read_text())
    composites={k:pd.DataFrame(0.,index=u.index,columns=u.columns) for k in ['B','C']}
    for name in design.names:
        f=pd.read_pickle(base/'factors'/f'{name}.pkl')*selections['directions'][name]
        z=(rank(f.where(allowed))-.5).fillna(0)
        composites['B']+=z/len(design.names)
        if name in selections['fundamental']:composites['C']+=z/len(selections['fundamental'])
    scores={'equal_B':composites['B'].where(allowed),'equal_C':composites['C'].where(allowed)};history=[];coefs=[]
    for objective in ['raw','rank']:
        for family in ['A','B']:
            name=f'{objective}_Ridge_{family}';pieces=[]
            for half,start,end in halves(2022):
                if objective=='raw' and family=='A':
                    candidate=choices['hyperparameters']['ridge']['candidate'];score=pd.read_pickle(base/'validation'/f'ridge_grid{candidate}_{half}.pkl');pieces.append(score);continue
                x,target,meta=design.training(start,family)
                if objective=='rank':
                    mask,target,extra=rank_training_target(y,u,design.observed,design.end,start)
                    assert mask.sum()==len(x)==meta['samples'];meta.update(extra)
                model=fit_model('ridge',params,x,target);score=design.predict(model,start,end,family)
                pieces.append(score);joblib.dump(model,out/'models'/f'{name}_{half}.joblib',compress=3)
                meta.update(name=name,half=half,objective=objective,params=params);history.append(meta)
                names=selections['wq'] if family=='A' else design.names
                for k,n in enumerate(names):coefs.append({'name':name,'half':half,'factor':n,'value_coef':float(model.coef_[2*k]),'missing_coef':float(model.coef_[2*k+1])})
                progress('probe_fit',name=name,half=half,samples=len(target));del x,target,model;gc.collect()
            scores[name]=pd.concat(pieces).sort_index();scores[name].to_pickle(out/'predictions'/f'{name}_2022.pkl')
    (out/'training_history.json').write_text(json.dumps(history,indent=2));pd.DataFrame(coefs).to_csv(out/'coefficients.csv',index=False)
    rows=[];info=[]
    def backtest(name,score,phase='validation',**kwargs):
        lo,hi=('20220101','20221231') if phase=='validation' else ('20230101','20251231')
        case=f'{name}_{phase}';d,_,events,s=market.backtest(score,lo,hi,weights=False,**kwargs)
        np.testing.assert_allclose(d.net_return,d.gross_return-d.cost,atol=1e-12)
        np.testing.assert_allclose(d.cost,d.traded_notional*.001,atol=1e-12)
        d.to_csv(out/'portfolios'/f'{case}_daily.csv');events.to_csv(out/'portfolios'/f'{case}_events.csv',index=False)
        rows.append({'case':name,'phase':phase,**s,'mean_cash':float(d.cash_weight.mean()),'gross_cagr':float((1+d.gross_return).prod()**(252/len(d))-1)})
        return d
    for name,score in scores.items():
        d=backtest(name,score,rebalance_every=5)
        target=y.reindex(score.index).where(design.end.reindex(score.index).le('20221231'),axis=0)
        target=target.loc['20220101':'20221231'];s=information_series(score.reindex(target.index),target,u.reindex(target.index))
        info.append({'name':name,**summarize_information(s)})
        if name=='raw_Ridge_A':
            old=pd.read_csv(base/'validation/trading_rules.csv');r=old.loc[old.smooth.eq(1)&old.rebalance_every.eq(5)].iloc[0]
            np.testing.assert_allclose(rows[-1]['annual_return'],r.annual_return,atol=1e-12)
    for name in ['raw_Ridge_A','equal_C']:
        score=scores[name]
        for every in [10,20]:backtest(name+f'_every{every}',score,rebalance_every=every)
        backtest(name+'_Top300',score,rebalance_every=5,top_n=300)
        backtest(name+'_large_half',score.where(large.reindex(score.index)),rebalance_every=5)
    baseline=pd.DataFrame(1.,index=u.index,columns=u.columns).where(allowed)
    for phase in ['validation','evaluation']:
        backtest('eligible_EW',baseline,phase,all_eligible=True,rebalance_every=5)
        for top in [100,500]:backtest(f'cap_Top{top}_EW',cap.where(allowed),phase,top_n=top,rebalance_every=5)
    pd.DataFrame(rows).to_csv(out/'portfolio_summary.csv',index=False);pd.DataFrame(info).to_csv(out/'validation_predictive.csv',index=False)
    # Ex-post mechanism diagnostics on existing, already published holdings.
    previous=caprank.shift(1);profiles=[]
    existing=[(n,base/'backtests') for n in ['ridge_A','ridge_B','lasso_A','xgboost_A','xgboost_B']]+[(n,base/'supplement/portfolios') for n in ['equal_weight_scores_C','equal_weight_eligible_pool']]
    for name,root in existing:
        w=pd.read_pickle(root/f'{name}_weights.pkl').astype(float);r=previous.reindex(w.index);valid=r.notna();invested=w.sum(axis=1);known=(w*valid).sum(axis=1)
        pctmean=(w*r).sum(axis=1)/known.replace(0,np.nan);topshare=(w*r.ge(.9)).sum(axis=1)/invested.replace(0,np.nan)
        profiles.append({'strategy':name,'mean_cap_percentile_when_invested':float(pctmean.mean()),'mean_top_cap_decile_share_when_invested':float(topshare.mean()),'mean_beginning_cash':float((1-invested).mean()),'mean_unknown_cap_weight':float((invested-known).mean())})
    pd.DataFrame(profiles).to_csv(out/'diagnostics/held_size_and_cash.csv',index=False)
    costs=[]
    for path in (base/'backtests').glob('*_costs.csv'):
        a=pd.read_csv(path);zero=a.loc[a.cost_bps.eq(0)].iloc[0];net=a.loc[a.cost_bps.eq(10)].iloc[0]
        costs.append({'strategy':zero.strategy,'zero_cost_CAGR':zero.annual_return,'net_10bps_CAGR':net.annual_return,'CAGR_difference_not_additive_attribution':zero.annual_return-net.annual_return})
    pd.DataFrame(costs).to_csv(out/'diagnostics/existing_cost_gap.csv',index=False)
    original=json.loads((base/'run_manifest.json').read_text())
    for row in original['files']:assert digest(base/row['path'])==row['sha256'],row['path']
    verification={'baseline_artifacts_unchanged':len(original['files']),'portfolios':len(rows),'new_2022_fits':len(history),'economic_target_unchanged':True,'no_new_2023_2025_model_predictions':True,'source_sha256':digest(Path(__file__)),'limitations':'2022 reused; names screened on 2015-2021; cap diagnostics retrospective, not alpha evidence'}
    (out/'verification.json').write_text(json.dumps(verification,indent=2));progress('improvement_probe_complete',**verification)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--database',required=True);p.add_argument('--baseline',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.database,a.baseline,a.output)
