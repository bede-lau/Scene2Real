"""Render local measured evidence without replacing missing checks with claims."""
import argparse
import json
from pathlib import Path
import statistics


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('output/integration-campaign'))
    args=parser.parse_args()
    root=args.output
    rows=[json.loads(line) for line in (root/'results.jsonl').read_text().splitlines()]
    summary=json.loads((root/'summary.json').read_text())
    manifest=json.loads((root/'manifest.json').read_text())
    links=json.loads((root/'links.json').read_text())
    lines=['# Merged Scene2Real evaluation','',
           '**Decision: keep Astra active. No automatic promotion.**','',
           f"Source commit: `{manifest['source_commit']}`; exact source hashes in `manifest.json`.",
           f"Dataset SHA256: `{manifest['dataset']['dataset_sha256']}`.",'',
           'New synthetic reviewed evidence: four development cases; eight locked families repeated twice. '
           'This is a small engineering benchmark, not real-world fire-response reliability evidence.','',
           '| Provider / split | Valid | Simulation success | Collision trials | Median inference latency | Tokens |',
           '|---|---:|---:|---:|---:|---:|']
    for provider in ('reference','astra','wandb'):
        for split in ('development','locked_test'):
            subset=[r for r in rows if r['provider']==provider and r['split']==split]
            if not subset: continue
            valid=sum(r['valid'] for r in subset);success=sum(r['simulation_success'] for r in subset)
            collision=sum((r.get('collision_count') or 0)>0 for r in subset)
            times=[r.get('inference_latency_s',r['total_wall_s']) for r in subset]
            tokens=sum((r.get('metadata',{}).get('usage') or {}).get('total_tokens',0) or 0 for r in subset)
            median=f'{statistics.median(times):.3f}s' if times else 'unavailable'
            lines.append(f'| {provider} / {split} | {valid}/{len(subset)} | {success}/{len(subset)} | {collision} | {median} | {tokens if tokens else "unavailable / deterministic"} |')
    lines+=['','The reference is a deterministic authored plan; it is not the active Astra baseline.',
            'Astra baseline requests were skipped because `OPENAI_API_KEY` is absent. '
            'W&B comparative promotion remains blocked even if candidate scores pass.','',
            f"Request ledger: `{json.dumps(summary['requests'],sort_keys=True)}`. Price/cost not verified; token totals are provider-reported. "
            'Rejected completion usage may be unavailable, so totals are a lower bound rather than a billing estimate.','',
            f"G1 physics controls: {summary['g1_physics_controls']['passed']}/{summary['g1_physics_controls']['count']}; explicit test fixture authorization, no inference.",
            'Mobile success requires two seconds of continuous valid exposure for every target and zero unintended contacts. '
            'G1 separately reduces authored intensity using actual nozzle-ray hits; contracts are not conflated.','',
            'Saved-plan replay and independent qpos exposure audits:',
            f"- Identical measured replay: {sum(r.get('saved_plan_replay_identical',False) for r in rows)}/{sum(r['valid'] for r in rows)} valid plans.",
            f"- Exposure audit agrees: {sum(r.get('replay_exposure_consistent',False) for r in rows)}/{sum(r['valid'] for r in rows)} valid plans.",'']
    failures=[r for r in rows if not r['simulation_success']]
    lines+=['Failures:']+[f"- {r['provider']} {r['case_id']} trial {r['trial']}: {r.get('error',r.get('metrics',{}).get('unintended_collisions',[]))}; total wall time {r['total_wall_s']:.3f}s" for r in failures]
    if not failures:lines+=['- None in attempted cases.']
    groups={}
    for row in rows:
        if row['split']=='locked_test' and row['provider']=='wandb':groups.setdefault(row['case_id'],[]).append(row)
    variable=sum(len({json.dumps(r.get('plan'),sort_keys=True) for r in group})>1 for group in groups.values())
    lines+=['',f'Candidate response variability: {variable}/{len(groups)} locked families returned different plan payloads across repeats. '
            'Physics is deterministic; these are repeated inference outputs, not stochastic simulator seeds.','',
            'Weave links:']
    for link in links:
        if link.get('url'): lines.append(f"- [{link['provider']} / {link['split']}]({link['url']})")
        else:lines.append(f"- {link['provider']}: {link.get('reason','unavailable')}")
    lines+=['','Perception/association boundary: this campaign uses frozen observations. Live rendered G1 camera '
            'positive/no-fire results are separate browser evidence. Existing source-video annotations require exact '
            'source hashes and timestamps; cross-view physical identity is not independently annotated. Historical '
            '25/30 results belong to the older revision recorded in the dataset manifest.','']
    (root/'report.md').write_text('\n'.join(lines))
    print(root/'report.md')


if __name__=='__main__':main()
