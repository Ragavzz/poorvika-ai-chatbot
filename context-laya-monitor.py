import os,subprocess,time,json,psutil
from pathlib import Path
root=Path.cwd()
env=dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONFAULTHANDLER='1', PYTHONUNBUFFERED='1')
with (root/'context-laya-monitored.stdout.log').open('w') as out, (root/'context-laya-monitored.stderr.log').open('w') as err, (root/'context-laya-monitor.jsonl').open('w') as metrics:
    proc=subprocess.Popen([str(root/'laya_v2_service/.venv/Scripts/python.exe'), '-u', '-X', 'faulthandler', str(root/'laya_v2_service/service.py')],env=env,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
    print('Monitoring PID',proc.pid,flush=True)
    while proc.poll() is None:
        memory=psutil.virtual_memory()
        row={'elapsed':round(time.monotonic(),1),'available':memory.available,'processes':[]}
        try:
            parent=psutil.Process(proc.pid)
            for p in [parent,*parent.children(recursive=True)]:
                m=p.memory_info()
                row['processes'].append({'pid':p.pid,'rss':m.rss,'private':m.private,'vms':m.vms})
        except psutil.NoSuchProcess:
            pass
        metrics.write(json.dumps(row)+'\n');metrics.flush()
        time.sleep(2)
    code=proc.returncode
    metrics.write(json.dumps({'exit_code':code,'hex':hex(code & 0xffffffff)})+'\n')
    print('Exit:',code,hex(code & 0xffffffff),flush=True)
print((root/'context-laya-monitored.stderr.log').read_text(),flush=True)
