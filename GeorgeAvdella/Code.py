import sys, os
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import deque

# ---------------- Process ----------------
@dataclass
class Process:
    name: str
    arrival: int
    burst: int
    remaining: int = field(init=False)
    start_time: Optional[int] = None
    finish_time: Optional[int] = None

    def __post_init__(self):
        self.remaining = self.burst

# ---------------- Helpers ----------------
def arrivals_index(processes: List[Process]) -> Dict[int, List[Process]]:
    idx: Dict[int, List[Process]] = {}
    for p in processes:
        idx.setdefault(p.arrival, []).append(p)
    for t in idx:
        idx[t].sort(key=lambda x: x.name)  # deterministic order within a tick
    return idx

def calc_metrics(ps: List[Process]):
    out = {}
    for p in ps:
        if p.finish_time is None or p.start_time is None:
            out[p.name] = {"waiting": None, "turnaround": None, "response": None}
        else:
            tat = p.finish_time - p.arrival
            wait = tat - p.burst
            resp = p.start_time - p.arrival
            out[p.name] = {"waiting": wait, "turnaround": tat, "response": resp}
    return out

def fmt3(x):
    return f"{x:3d}" if isinstance(x, int) else "  -"

# ---------------- FCFS (FIFO) ----------------
def fcfs(processes: List[Process], runfor: int, out: List[str]):
    t = 0
    by_time = arrivals_index(processes)

    def emit_arrivals(now: int):
        for p in by_time.pop(now, []):
            out.append(f"Time {now:3d} : {p.name} arrived")

    # Stable order by arrival then name
    ready_order = sorted(processes, key=lambda p: (p.arrival, p.name))

    for p in ready_order:
        # idle until this process arrives
        while t < p.arrival and t < runfor:
            emit_arrivals(t)
            out.append(f"Time {t:3d} : Idle")
            t += 1
        if t >= runfor:
            break

        emit_arrivals(t)

        if p.start_time is None:
            p.start_time = t
            out.append(f"Time {t:3d} : {p.name} selected (burst {p.remaining:3d})")

        # run tick-by-tick so arrivals are logged during execution
        while p.remaining > 0 and t < runfor:
            t += 1
            p.remaining -= 1
            emit_arrivals(t)

        if p.remaining == 0:
            p.finish_time = t
            out.append(f"Time {t:3d} : {p.name} finished")

    # after last process, idle until runfor and still emit arrivals
    while t < runfor:
        emit_arrivals(t)
        out.append(f"Time {t:3d} : Idle")
        t += 1

# ---- Preemptive SJF (Shortest Remaining Time First) ----
def sjf_preemptive(processes: List[Process], runfor: int, out: List[str]):
    t = 0
    by_time = arrivals_index(processes)

    def emit_arrivals(now: int):
        for p in by_time.pop(now, []):
            out.append(f"Time {now:3d} : {p.name} arrived")

    current: Optional[Process] = None

    def pick(now: int) -> Optional[Process]:
        r = [p for p in processes if p.arrival <= now and p.remaining > 0]
        if not r:
            return None
        r.sort(key=lambda p: (p.remaining, p.arrival, p.name))
        return r[0]

    while t < runfor:
        emit_arrivals(t)
        if not any(p.arrival <= t and p.remaining > 0 for p in processes):
            out.append(f"Time {t:3d} : Idle")
            t += 1
            continue

        best = pick(t)
        if current is not best:
            current = best
            if current.start_time is None:
                current.start_time = t
            out.append(f"Time {t:3d} : {current.name} selected (burst {current.remaining:3d})")

        current.remaining -= 1
        t += 1
        emit_arrivals(t)
        if current.remaining == 0:
            current.finish_time = t
            out.append(f"Time {t:3d} : {current.name} finished")
            current = None

# ---------------- Round Robin ----------------
def rr(processes: List[Process], runfor: int, quantum: int, out: List[str]):
    if quantum <= 0:
        print("Error: Missing quantum parameter when use is 'rr'")
        sys.exit(1)

    t = 0
    by_time = arrivals_index(processes)
    rq = deque()

    def emit_and_enqueue(now: int):
        for p in by_time.pop(now, []):
            out.append(f"Time {now:3d} : {p.name} arrived")
            rq.append(p)

    emit_and_enqueue(0)

    while t < runfor:
        emit_and_enqueue(t)
        if not rq:
            out.append(f"Time {t:3d} : Idle")
            t += 1
            emit_and_enqueue(t)
            continue

        p = rq.popleft()
        if p.start_time is None:
            p.start_time = t
        out.append(f"Time {t:3d} : {p.name} selected (burst {p.remaining:3d})")

        ticks = min(quantum, p.remaining, runfor - t)
        for _ in range(ticks):
            p.remaining -= 1
            t += 1
            emit_and_enqueue(t)
            if p.remaining == 0:
                p.finish_time = t
                out.append(f"Time {t:3d} : {p.name} finished")
                break

        if p.remaining > 0:
            rq.append(p)

# ---------------- Main ----------------
def main():
    # exactly one parameter with .in extension
    if len(sys.argv) != 2:
        print("Usage: scheduler-gpt.py <input file>")
        sys.exit(1)
    infile = sys.argv[1]
    if not infile.endswith(".in"):
        print("Error: Input file must have .in extension")
        sys.exit(1)
    outfile = os.path.splitext(infile)[0] + ".out"

    # read + strip inline comments
    try:
        raw_lines = []
        with open(infile) as f:
            for line in f:
                line = line.split('#', 1)[0].strip()  # remove inline comments
                if line:
                    raw_lines.append(line)
    except FileNotFoundError:
        print(f"Error: File {infile} not found")
        sys.exit(1)

    processcount = None
    runfor = None
    algo = None
    quantum = None
    processes: List[Process] = []

    for line in raw_lines:
        if line.startswith("processcount"):
            processcount = int(line.split()[1])
        elif line.startswith("runfor"):
            runfor = int(line.split()[1])
        elif line.startswith("use"):
            algo = line.split()[1]
        elif line.startswith("quantum"):
            quantum = int(line.split()[1])
        elif line.startswith("process"):
            # format: process name X arrival a burst b
            parts = line.split()
            name = parts[2]
            arrival = int(parts[4])
            burst = int(parts[6])
            processes.append(Process(name, arrival, burst))
        elif line == "end":
            break

    # required params
    if processcount is None:
        print("Error: Missing parameter processcount")
        sys.exit(1)
    if runfor is None:
        print("Error: Missing parameter runfor")
        sys.exit(1)
    if algo is None:
        print("Error: Missing parameter use")
        sys.exit(1)
    if algo == "rr" and quantum is None:
        print("Error: Missing quantum parameter when use is 'rr'")
        sys.exit(1)
    if processcount != len(processes):
        print(f"Error: processcount ({processcount}) does not match number of process lines ({len(processes)})")
        sys.exit(1)

    out: List[str] = []
    out.append(f"{processcount} processes")
    if algo == "fcfs":
        out.append("Using First-Come First-Served")
        fcfs(processes, runfor, out)
    elif algo == "sjf":
        out.append("Using preemptive Shortest Job First")
        sjf_preemptive(processes, runfor, out)
    elif algo == "rr":
        out.append("Using Round Robin")
        out.append(f"Quantum {quantum}\n")
        rr(processes, runfor, quantum, out)
    else:
        print(f"Error: Unknown scheduling algorithm '{algo}'")
        sys.exit(1)

    out.append(f"Finished at time {runfor:3d}")
    out.append("")  # blank line before metrics

    # -------- Unified metrics printing across all algorithms --------
    metrics = calc_metrics(processes)

    # print metrics only for processes that finished
    for p in sorted(processes, key=lambda x: x.name):
        if p.finish_time is not None:
            m = metrics[p.name]
            out.append(f"{p.name} wait {fmt3(m['waiting'])} "
                       f"turnaround {fmt3(m['turnaround'])} "
                       f"response {fmt3(m['response'])}")

    # list unfinished processes separately
    unfinished = [p for p in processes if p.finish_time is None]
    for p in sorted(unfinished, key=lambda x: x.name):
        out.append(f"{p.name} did not finish")

    with open(outfile, "w") as f:
        f.write("\n".join(out) + "\n")

if __name__ == "__main__":
    main()

