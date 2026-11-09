"""Controlled retrospective improvements with a separate development/validation freeze."""
from __future__ import annotations
import argparse
import gc
import hashlib
import inspect
import json
from pathlib import Path
import time
import joblib
import numpy as np
import pandas as pd
from .models import Design,fit_model,halves
from .factors import rank
from .improvement_probe import rank_training_target
from .research_portfolio import ResearchMarket,additional_features
from .extensions import digest,progress
from .research_cache import atomic_json,bundle_complete,finish_bundle

PHASES={'development':('20190101','20211231'),'validation':('20220101','20221231'),'evaluation':('20230101','20251231')}
POLICY={'version':1,'status':'retrospective research; all years previously inspected; main v2 remains frozen',
        'target':'T+1 close to T+11 close, raw return evaluation; rank training target retains pooled training units',
        'core_cases':'raw/rank Ridge x A/B x no buffer/150-rank retention x 5/10-session rebalance = 16',
        'phases':PHASES,'development_caveat':'2019-2021 influenced factor selection; developmental diagnostics, not independent OOS',
        'selection':'2022 A-only maximum paired net active information ratio; mean cash <=5%; tie lower turnover; same objective/rule applied to B',
        'evaluation':'freeze selection first, then display all 16 evaluation cases; no evaluation reselection',
        'weights':'selected A/B and simple C; equal/sqrt-cap/cap on common positive-cap samples, 2% target per-name cap; pure pool benchmarks uncapped',
        'features':['momentum_12_1','low_volatility_63','log_cap','log_dollar_volume_20'],
        'feature_comparison':'append four values and four missing flags to A/B; shared original rows/parameters and selected objective/trading rule; no additional tuning',
        'constants':{'cost_bps':10,'top_n':100,'smooth':1,'tie_seed':5205},
        'buffer':'retain eligible existing T holdings if rank <=150, fill up to100 from T ranking; no replacement using T+1 availability',
        'price_rules':'same terminal/stale/segment policies as baseline; target caps apply at formation, holdings can drift or lock',
        'notebook':'default loads completed aggregates; full recompute explicit opt-in'}


class Exploration:
    def __init__(self,database,baseline,pilot,output):
        self.db,self.base,self.pilot,self.out=map(Path,(database,baseline,pilot,output))
        if self.out.resolve()==self.base.resolve() or self.base.resolve() in self.out.resolve().parents:raise ValueError('Separate output required')
        self.out.mkdir(parents=True,exist_ok=True)
        # JSON round-trip normalizes tuples in the phase map.
        policy=json.loads(json.dumps(POLICY));p=self.out/'protocol.json'
        if p.exists() and json.loads(p.read_text())!=policy:raise ValueError('Protocol changed; new output required')
        if not p.exists():p.write_text(json.dumps(policy,indent=2))
        for sub in ['models','predictions','portfolios','features','audit']:(self.out/sub).mkdir(exist_ok=True)
        self.design=Design(self.db,self.base);self.market=ResearchMarket(self.db)
        self.u=self.design.u;self.allowed=self.u.eq(1)&pd.DataFrame(self.design.observed,index=self.u.index,columns=self.u.columns)
        self.y=pd.DataFrame(self.design.y,index=self.u.index,columns=self.u.columns)
        self.choices=json.loads((self.base/'frozen_model_choices.json').read_text());self.params=self.choices['hyperparameters']['ridge']['params']
        self.binding={p:digest(self.base/p) for p in ['factor_selection.json','frozen_model_choices.json','input_signature.json','backtests/summary.csv']}
        binding=self.out/'baseline_binding.json'
        if binding.exists() and json.loads(binding.read_text())!=self.binding:raise ValueError('Baseline changed')
        if not binding.exists():binding.write_text(json.dumps(self.binding,indent=2))
        path=self.out/'portfolio_summary.csv';self.summaries=pd.read_csv(path).to_dict('records') if path.exists() else []
        path=self.out/'training_history.json';self.history=json.loads(path.read_text()) if path.exists() else []
        self.history=list({(r['name'],r['half']):r for r in self.history}.values())
        if path.exists():atomic_json(path,self.history)
        self.extras=None;self.extra_names=[];self.extra_signature=None;self._rank_cache=None;self._score_hash_cache=None
        cp=pd.read_pickle(self.db/'panels/close_adj.pkl').astype(float);seg=pd.read_pickle(self.db/'panels/adjustment_segment.pkl')
        asset=(cp.ffill()/cp.ffill().shift()-1).where(seg.eq(seg.where(seg>0).ffill().shift())&seg.gt(0))
        terminal=pd.read_pickle(self.db/'panels/delisting_event.pkl').eq(1);vendor=pd.read_pickle(self.db/'panels/daily_return.pkl')
        self.asset=asset.where(~(terminal&np.isfinite(vendor)&vendor.ge(-1)),vendor).fillna(0)

    def training(self,start,family,objective,extra=False):
        d=self.design;dates=(d.index>='20150101')&(d.index<start)&d.end.lt(start).fillna(False).to_numpy()
        valid=dates[:,None]&self.allowed.to_numpy()&np.isfinite(d.y);ii,jj=np.nonzero(valid);nf=2*d.nq if family=='A' else len(d.names)*2
        x=np.asarray(d.x[ii,jj,:nf],dtype='float32')
        if extra:x=np.concatenate([x,self.extras[ii,jj,:]],axis=1)
        target=np.asarray(d.y[ii,jj],dtype='float32');used=np.flatnonzero(valid.any(axis=1))
        meta={'samples':len(target),'train_first':d.index[used[0]],'train_last_signal':d.index[used[-1]],'train_last_label_end':str(d.end.iloc[used].max()),'forecast_start':start,'feature_count':x.shape[1]}
        if objective=='rank':
            if self._rank_cache is None or self._rank_cache[0]!=start:
                mask,r,unit=rank_training_target(self.y,self.u,d.observed,d.end,start)
                np.testing.assert_array_equal(mask,valid);self._rank_cache=(start,r,unit)
            target=self._rank_cache[1];meta.update(self._rank_cache[2])
        assert meta['train_last_label_end']<start
        return x,target,meta

    def piece(self,objective,family,year,half,start,end,extra=False):
        name=('extra_' if extra else '')+objective+'_'+family;path=self.out/'predictions'/f'{name}_{half}.pkl';meta_path=path.with_suffix('.json')
        if path.exists() and meta_path.exists():
            try:
                cached=json.loads(meta_path.read_text())
                if cached.get('prediction_sha256')==digest(path) and (not extra or cached.get('extra_feature_cache_signature')==self.extra_signature):
                    return pd.read_pickle(path)
            except (OSError,ValueError,EOFError):pass
        source=None
        if not extra and objective=='raw' and year>=2023:source=self.base/'predictions'/f'ridge_{family}_{half}.pkl'
        elif not extra and objective=='raw' and family=='A' and year==2022:
            source=self.base/'validation'/f'ridge_grid{self.choices["hyperparameters"]["ridge"]["candidate"]}_{half}.pkl'
        elif not extra and year==2022:source=self.pilot/'predictions'/f'{objective}_Ridge_{family}_2022.pkl'
        if source is not None:
            score=pd.read_pickle(source).loc[start:end];meta={'name':name,'half':half,'reused_from':str(source),'source_sha256':digest(source),'fit_in_this_run':False}
        else:
            x,target,meta=self.training(start,family,objective,extra)
            model=fit_model('ridge',self.params,x,target);rows=[];d=self.design;nf=2*d.nq if family=='A' else len(d.names)*2
            for i in np.flatnonzero((d.index>=start)&(d.index<=end)):
                xx=np.asarray(d.x[i,:,:nf],dtype='float32')
                if extra:xx=np.concatenate([xx,self.extras[i]],axis=1)
                prediction=model.predict(xx).astype('float32');rows.append(np.where(self.allowed.iloc[i],prediction,np.nan))
            score=pd.DataFrame(rows,index=d.index[(d.index>=start)&(d.index<=end)],columns=d.columns)
            joblib.dump(model,self.out/'models'/f'{name}_{half}.joblib',compress=3)
            names=(d.names[:d.nq] if family=='A' else d.names)+(self.extra_names if extra else [])
            effects=pd.DataFrame({'factor':names,'value_coefficient':model.coef_[::2],'missing_coefficient':model.coef_[1::2]})
            effects.to_csv(self.out/'models'/f'{name}_{half}_coefficients.csv',index=False)
            meta.update(name=name,half=half,objective=objective,family=family,params=self.params,fit_in_this_run=True,extra_features=extra)
            self.history=[r for r in self.history if (r['name'],r['half'])!=(name,half)]+[meta]
            atomic_json(self.out/'training_history.json',self.history)
            progress('exploration_fit',name=name,half=half,samples=len(target));del x,target,model;gc.collect()
        score.to_pickle(path);meta['prediction_sha256']=digest(path)
        if extra:meta['extra_feature_cache_signature']=self.extra_signature
        atomic_json(meta_path,meta);return score

    def scores(self,years,extra=False,objective_only=None):
        parts={o+'_'+f:[] for o in ([objective_only] if objective_only else ['raw','rank']) for f in ['A','B']}
        for year in years:
            for half,start,end in halves(year):
                for key in parts:
                    objective,family=key.split('_');parts[key].append(self.piece(objective,family,year,half,start,end,extra))
                self._rank_cache=None
        return {key:pd.concat(pieces).sort_index() for key,pieces in parts.items()}

    def upsert_summary(self,summary):
        self.summaries=[r for r in self.summaries if (r['batch'],r['case'],r['phase'])!=(summary['batch'],summary['case'],summary['phase'])]
        self.summaries.append(summary);tmp=self.out/'portfolio_summary.csv.tmp';pd.DataFrame(self.summaries).to_csv(tmp,index=False);tmp.replace(self.out/'portfolio_summary.csv')

    def save(self,batch,case,phase,score,**kwargs):
        folder=self.out/'portfolios'/batch/case/phase;folder.mkdir(parents=True,exist_ok=True)
        meta_path=folder/'summary.json'
        required=['summary.json','daily.csv','events.csv','selection_decisions.csv','monthly_holdings.parquet']
        if batch in ['features','weights','benchmarks'] and phase=='evaluation':required.append('weights.pkl')
        if self._score_hash_cache is None or self._score_hash_cache[0] is not score:
            h=hashlib.sha256();h.update(json.dumps([score.index.tolist(),score.columns.tolist()]).encode());h.update(str(score.dtypes.iloc[0]).encode());h.update(score.to_numpy().tobytes(order='C'));self._score_hash_cache=(score,h.hexdigest())
        signature={'batch':batch,'case':case,'phase':phase,'parameters':kwargs,'score_sha256':self._score_hash_cache[1],'ledger_version':'signal-date-holdings-hooks-v1','input_binding':self.binding}
        if bundle_complete(folder,'complete.json',signature,required):
            summary=json.loads(meta_path.read_text());self.upsert_summary(summary);return summary
        (folder/'complete.json').unlink(missing_ok=True)
        lo,hi=PHASES[phase];d,w,events,s=self.market.backtest(score,lo,hi,weights=True,**kwargs)
        np.testing.assert_allclose(d.net_return,d.gross_return-d.cost,atol=1e-12);np.testing.assert_allclose(d.cost,d.traded_notional*.001,atol=1e-12)
        np.testing.assert_allclose((1+d.net_return).cumprod(),d.net_nav,atol=1e-11)
        gross=(w.astype(float)*self.asset.reindex(w.index)).sum(axis=1);error=float((gross-d.gross_return).abs().max());assert error<2e-7
        active=d.net_return-d.benchmark_return;te=float(active.std(ddof=1)*np.sqrt(252));ir=float(active.mean()*252/te) if te>1e-12 else np.nan
        s.update(batch=batch,case=case,phase=phase,net_active_information_ratio=ir,tracking_error=te,mean_cash=float(d.cash_weight.mean()),gross_cagr=float((1+d.gross_return).prod()**(252/len(d))-1),sum_daily_costs=float(d.cost.sum()),max_held_weight=float(w.to_numpy().max()),mean_positions=float((w>0).sum(axis=1).mean()),independent_gross_error=error)
        d.to_csv(folder/'daily.csv');events.to_csv(folder/'events.csv',index=False);pd.DataFrame(self.market.decisions).to_csv(folder/'selection_decisions.csv',index=False)
        months=w.groupby(w.index.str[:6]).tail(1);ii,jj=np.where(months.to_numpy()>0)
        pd.DataFrame({'date':months.index.to_numpy()[ii],'sid':months.columns.to_numpy()[jj],'weight':months.to_numpy()[ii,jj]}).to_parquet(folder/'monthly_holdings.parquet',index=False)
        # Keep full weights only for final selected cases and independent baselines.
        if batch in ['features','weights','benchmarks'] and phase=='evaluation':w.to_pickle(folder/'weights.pkl')
        atomic_json(meta_path,s);finish_bundle(folder,'complete.json',signature,required);self.upsert_summary(s)
        return s

    def development(self):
        scores=self.scores([2019,2020,2021,2022])
        for key,score in scores.items():
            for phase in ['development','validation']:
                for buffer in [None,150]:
                    for every in [5,10]:
                        case=f'{key}_b{buffer or 0}_r{every}';self.save('core',case,phase,score,buffer_n=buffer,rebalance_every=every)
            progress('exploration_development_portfolios',model=key)
        table=pd.DataFrame(self.summaries);a=table.loc[table.batch.eq('core')&table.phase.eq('validation')&table.case.str.contains('_A_')&table.mean_cash.le(.05)]
        a=a.loc[np.isfinite(a.net_active_information_ratio)].sort_values(['net_active_information_ratio','mean_daily_turnover','case'],ascending=[False,True,True])
        if a.empty:raise ValueError('No eligible validation config')
        best=a.iloc[0];objective=best['case'].split('_')[0];buffer=150 if '_b150_' in best['case'] else None;every=int(best['rebalance_every'])
        frozen={'objective':objective,'buffer_n':buffer,'rebalance_every':every,'top_n':100,'cost_bps':10,'selection_uses':'2022 A only; reused validation','selected_A_case':best['case'],'validation_A_net_active_IR':float(best.net_active_information_ratio),'validation_A_CAGR':float(best.annual_return),'evaluation_used_for_selection':False}
        path=self.out/'frozen_exploration_choice.json'
        if path.exists() and json.loads(path.read_text())!=frozen:raise ValueError('Frozen exploration choice changed')
        path.write_text(json.dumps(frozen,indent=2));progress('exploration_choice_frozen',**frozen)

    def evaluation(self):
        if not (self.out/'frozen_exploration_choice.json').exists():raise ValueError('Run development and freeze first')
        scores=self.scores([2023,2024,2025])
        for key,score in scores.items():
            for buffer in [None,150]:
                for every in [5,10]:self.save('core',f'{key}_b{buffer or 0}_r{every}','evaluation',score,buffer_n=buffer,rebalance_every=every)
            progress('exploration_evaluation_portfolios',model=key)

    def selected_scores(self,years):
        choice=json.loads((self.out/'frozen_exploration_choice.json').read_text());return choice,self.scores(years,objective_only=choice['objective'])

    def composite_C(self):
        names=self.design.names[self.design.nq:];score=pd.DataFrame(0.,index=self.u.index,columns=self.u.columns)
        selection=json.loads((self.base/'factor_selection.json').read_text())
        for name in names:
            f=pd.read_pickle(self.base/'factors'/f'{name}.pkl')*selection['directions'][name]
            score+=(rank(f.where(self.allowed))-.5).fillna(0)/len(names)
        return score.where(self.allowed)

    def weights(self):
        positive=pd.DataFrame(np.isfinite(self.market.cap)&(self.market.cap>0),index=self.u.index,columns=self.u.columns)
        choice,scores=self.selected_scores([2022,2023,2024,2025]);scores['simple_C']=self.composite_C()
        for phase in ['validation','evaluation']:
            baseline=pd.DataFrame(1.,index=self.u.index,columns=self.u.columns).where(self.allowed&positive)
            for weighting in ['equal','sqrt_cap','cap']:
                self.save('benchmarks','pool_'+weighting,phase,baseline,all_eligible=True,weighting=weighting,rebalance_every=5)
            for model,score in scores.items():
                for weighting in ['equal','sqrt_cap','cap']:
                    self.save('weights',model+'_'+weighting,phase,score.where(positive.reindex(score.index)),buffer_n=choice['buffer_n'],rebalance_every=choice['rebalance_every'],weighting=weighting,max_weight=.02)
        progress('exploration_weight_probes_complete')

    def features(self):
        load=lambda n:pd.read_pickle(self.db/'panels'/f'{n}.pkl')
        raw=additional_features(load('close_adj'),load('adjustment_segment'),load('market_cap'),load('close'),load('volume'))
        self.extra_names=list(raw);shape=(*self.u.shape,2*len(raw));path=self.out/'features/features.npy'
        folder=self.out/'features';required=['features.npy','coverage.csv']+[name+'.pkl' for name in self.extra_names]
        signature={'shape':list(shape),'features':self.extra_names,'definition_sha256':hashlib.sha256(inspect.getsource(additional_features).encode()).hexdigest(),'input_binding':self.binding,'transform':'universe percentile minus .5 + missing flag'}
        if not bundle_complete(folder,'complete.json',signature,required):
            (folder/'complete.json').unlink(missing_ok=True)
            temporary=path.with_name(path.name+'.tmp');array=np.lib.format.open_memmap(temporary,mode='w+',dtype='float32',shape=shape);meta=[]
            for k,(name,f) in enumerate(raw.items()):
                f=f.where(self.u.eq(1));z=rank(f)-.5;array[:,:,2*k]=z.fillna(0).to_numpy('float32');array[:,:,2*k+1]=z.isna().to_numpy('float32')
                f.astype('float32').to_pickle(self.out/'features'/f'{name}.pkl');meta.append({'feature':name,'coverage_2015_2022':float(f.loc['20150101':'20221231'].notna().sum().sum()/self.u.loc['20150101':'20221231'].eq(1).sum().sum()),'direction':'fixed formula sign; fitted Ridge coefficients determine contribution'})
            array.flush();del array;temporary.replace(path);pd.DataFrame(meta).to_csv(self.out/'features/coverage.csv',index=False)
            finish_bundle(folder,'complete.json',signature,required)
        self.extra_signature=digest(path)
        del raw;gc.collect();self.extras=np.load(path,mmap_mode='r')
        choice=json.loads((self.out/'frozen_exploration_choice.json').read_text())
        scores=self.scores([2022,2023,2024,2025],extra=True,objective_only=choice['objective'])
        for name,score in scores.items():
            for phase in ['validation','evaluation']:
                self.save('features','extra_'+name,phase,score,buffer_n=choice['buffer_n'],rebalance_every=choice['rebalance_every'])
        self.extras=None;progress('exploration_feature_probes_complete')

    def verify(self):
        records=pd.read_csv(self.out/'portfolio_summary.csv');assert len(records)==76 and not records.duplicated(['batch','case','phase']).any()
        assert records.independent_gross_error.max()<2e-7
        # Hooks must preserve the original default ledger and source result.
        score=pd.read_pickle(self.base/'predictions/ridge_A_2023_2025.pkl');d,_,_,s=self.market.backtest(score,'20230101','20251231',rebalance_every=5)
        ref=pd.read_csv(self.base/'backtests/ridge_A_daily.csv');np.testing.assert_allclose(d.net_return,ref.net_return,atol=1e-12)
        original=json.loads((self.base/'run_manifest.json').read_text())
        for row in original['files']:assert digest(self.base/row['path'])==row['sha256'],row['path']
        choice=json.loads((self.out/'frozen_exploration_choice.json').read_text());assert choice['evaluation_used_for_selection'] is False
        result={'passed':True,'portfolios':len(records),'new_model_fits':len(self.history),'baseline_artifacts_unchanged':len(original['files']),'default_ledger_replay_max_error':float(np.max(np.abs(d.net_return.to_numpy()-ref.net_return.to_numpy()))),'maximum_independent_holdings_gross_error':float(records.independent_gross_error.max()),'main_selection_unchanged':True,'exploration_selection':choice,'research_status':'all comparisons retrospective; 2022 reused'}
        (self.out/'audit/verification.json').write_text(json.dumps(result,indent=2));progress('exploration_verified',**result)


def main():
    p=argparse.ArgumentParser();p.add_argument('--database',required=True);p.add_argument('--baseline',required=True);p.add_argument('--pilot',required=True);p.add_argument('--output',required=True)
    p.add_argument('--stage',choices=['development','evaluation','weights','features','verify','all'],default='all');a=p.parse_args();e=Exploration(a.database,a.baseline,a.pilot,a.output)
    for stage in ['development','evaluation','weights','features','verify']:
        if a.stage in [stage,'all']:
            t=time.time();getattr(e,stage)();progress('exploration_stage_complete',stage_name=stage,seconds=round(time.time()-t,1))


if __name__=='__main__':main()
