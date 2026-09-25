import json, os, signal, time
from pathlib import Path
from datetime import datetime, timezone
pid = 28165
root = Path('/work/results/snowball')
proc = Path('/proc') / str(pid)
events = []
held = False

def event(name, **fields):
    row = dict(event=name, time=datetime.now(timezone.utc).isoformat(), **fields)
    events.append(row)
    (root/'fixed-drain-coordination.json').write_text(json.dumps(events, indent=2)+'\n')
    print(row, flush=True)

try:
    deadline = time.monotonic()+3600
    while time.monotonic() < deadline:
        children = (proc/'task'/str(pid)/'children').read_text().split()
        matches = []
        for child in children:
            path = Path('/proc')/child/'cmdline'
            if path.exists() and b'benchmarks.llm_validation.supervisor_validation' in path.read_bytes():
                matches.append(child)
        if matches:
            os.kill(pid, signal.SIGSTOP)
            held = True
            event('parent_held_while_supervisor_runs', parent_pid=pid, supervisor_pids=matches)
            break
        time.sleep(1)
    else:
        raise TimeoutError('Supervisor child did not start')
    deadline = time.monotonic()+7200
    while not (root/'supervisor-validation.json').exists():
        if time.monotonic() > deadline:
            raise TimeoutError('Supervisor did not finish')
        time.sleep(2)
    event('fixed_report_complete')
    deadline = time.monotonic()+660
    while True:
        pending = [p.name for p in (root/'wire').glob('*.json') if json.loads(p.read_text())['state']=='pending']
        if not pending:
            break
        if time.monotonic() > deadline:
            raise TimeoutError('Recorder still has pending fixed requests')
        time.sleep(2)
    event('fixed_requests_drained')
finally:
    if held:
        os.kill(pid, signal.SIGCONT)
        event('campaign_launcher_resumed')
