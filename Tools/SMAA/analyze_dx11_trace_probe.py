"""Summarize captured CPU annotation ranges, never GPU shader execution times."""
import argparse,hashlib,json,sqlite3,statistics
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();db=a.directory/'api-trace.sqlite';receipt=json.loads((a.directory/'probe.json').read_text(encoding='utf-8-sig'))
assert receipt['profiler_exit_code']==0 and not receipt['timed_out'] and receipt['remaining_cmaa2']==0
assert not receipt['hardware_metrics_collected']
c=sqlite3.connect(f'file:{db.as_posix()}?mode=ro',uri=True)
tables=[r[0] for r in c.execute("select name from sqlite_master where type='table'")]
assert 'D3D11_PIX_DEBUG_API' in tables
assert 'GPU_METRICS' not in tables
rows=c.execute('''SELECT s.value,e.start-b.end FROM D3D11_PIX_DEBUG_API b
 JOIN D3D11_PIX_DEBUG_API e ON b.correlationId=e.correlationId AND b.globalTid=e.globalTid
 JOIN StringIds s ON b.textId=s.id WHERE b.textId IS NOT NULL AND e.textId IS NULL''').fetchall()
groups={}
for name,ns in rows:
    assert ns>=0
    groups.setdefault(name,[]).append(ns)
summary={}
for name in ['WholeFrame','SMAA','SMAASpatial','SMAATemporalResolve']:
    v=sorted(groups[name]);summary[name]=dict(instances=len(v),mean_cpu_ns=statistics.mean(v),
        median_cpu_ns=statistics.median(v),p95_cpu_ns=v[int((len(v)-1)*.95)],
        max_cpu_ns=max(v),sample_std_cpu_ns=statistics.stdev(v))
result=dict(classification='Instrumented CPU annotation diagnostic only, not GPU performance',
    receipt=receipt,sqlite_sha256=hashlib.sha256(db.read_bytes()).hexdigest(),
    trace_sha256=hashlib.sha256((a.directory/'api-trace.nsys-rep').read_bytes()).hexdigest(),
    tables=tables,ranges=summary,shader_hardware_stall_or_divergence_measured=False,
    individual_draw_api_table_exported='D3D11_API' in tables)
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print('PASS:',a.output)
