
import sys, os, html, re, webbrowser
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
        idx[t].sort(key=lambda x: x.name)
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

# ---------------- FCFS ----------------
def fcfs(processes: List[Process], runfor: int, timeline: List[str]):
    t = 0
    by_time = arrivals_index(processes)

    def emit_arrivals(now: int):
        for p in by_time.pop(now, []):
            timeline.append(f"Time {now:3d} : {p.name} arrived")

    ready_order = sorted(processes, key=lambda p: (p.arrival, p.name))

    for p in ready_order:
        while t < p.arrival and t < runfor:
            emit_arrivals(t)
            timeline.append(f"Time {t:3d} : Idle")
            t += 1
        if t >= runfor:
            break

        emit_arrivals(t)

        if p.start_time is None:
            p.start_time = t
            timeline.append(f"Time {t:3d} : {p.name} selected (burst {p.remaining:3d})")

        while p.remaining > 0 and t < runfor:
            t += 1
            p.remaining -= 1
            emit_arrivals(t)

        if p.remaining == 0:
            p.finish_time = t
            timeline.append(f"Time {t:3d} : {p.name} finished")

    while t < runfor:
        emit_arrivals(t)
        timeline.append(f"Time {t:3d} : Idle")
        t += 1

# ---------------- SJF Preemptive ----------------
def sjf_preemptive(processes: List[Process], runfor: int, timeline: List[str]):
    t = 0
    by_time = arrivals_index(processes)

    def emit_arrivals(now: int):
        for p in by_time.pop(now, []):
            timeline.append(f"Time {now:3d} : {p.name} arrived")

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
            timeline.append(f"Time {t:3d} : Idle")
            t += 1
            continue

        best = pick(t)
        if current is not best:
            current = best
            if current.start_time is None:
                current.start_time = t
            timeline.append(f"Time {t:3d} : {current.name} selected (burst {current.remaining:3d})")

        current.remaining -= 1
        t += 1
        emit_arrivals(t)
        if current.remaining == 0:
            current.finish_time = t
            timeline.append(f"Time {t:3d} : {current.name} finished")
            current = None

# ---------------- Round Robin ----------------
def rr(processes: List[Process], runfor: int, quantum: int, timeline: List[str]):
    if quantum <= 0:
        print("Error: Missing quantum parameter when use is 'rr'")
        sys.exit(1)

    t = 0
    by_time = arrivals_index(processes)
    rq = deque()

    def emit_and_enqueue(now: int):
        for p in by_time.pop(now, []):
            timeline.append(f"Time {now:3d} : {p.name} arrived")
            rq.append(p)

    emit_and_enqueue(0)

    while t < runfor:
        emit_and_enqueue(t)
        if not rq:
            timeline.append(f"Time {t:3d} : Idle")
            t += 1
            emit_and_enqueue(t)
            continue

        p = rq.popleft()
        if p.start_time is None:
            p.start_time = t
        timeline.append(f"Time {t:3d} : {p.name} selected (burst {p.remaining:3d})")

        ticks = min(quantum, p.remaining, runfor - t)
        for _ in range(ticks):
            p.remaining -= 1
            t += 1
            emit_and_enqueue(t)
            if p.remaining == 0:
                p.finish_time = t
                timeline.append(f"Time {t:3d} : {p.name} finished")
                break

        if p.remaining > 0:
            rq.append(p)

# ---------------- HTML Renderer ----------------
def render_html(htmlfile: str, title: str, runfor: int, quantum: Optional[int],
                timeline: List[str], processes: List[Process], metrics: Dict[str, Dict[str, Optional[int]]]) -> None:
    def td(x):
        return html.escape(str(x)) if x is not None else "&nbsp;"

    # process metrics
    rows = []
    for p in sorted(processes, key=lambda x: x.name):
        status = "Finished" if p.finish_time is not None else "Did not finish"
        m = metrics[p.name]
        rows.append(f"""
        <tr>
          <td>{html.escape(p.name)}</td>
          <td>{p.arrival}</td>
          <td>{p.burst}</td>
          <td>{"" if p.start_time is None else p.start_time}</td>
          <td>{"" if p.finish_time is None else p.finish_time}</td>
          <td>{"" if m["turnaround"] is None else m["turnaround"]}</td>
          <td>{"" if m["waiting"]    is None else m["waiting"]}</td>
          <td>{"" if m["response"]   is None else m["response"]}</td>
          <td>{status}</td>
        </tr>""")

    # timeline rows
    trows = []
    for line in timeline:
        try:
            parts = line.split(":", 1)
            time_part = parts[0].replace("Time", "").strip()
            msg = parts[1].strip()
            # highlight bursts in red
            msg = re.sub(r"\(burst\s+(\d+)\)", r'<span class="burst">(burst \1)</span>', msg)
            trows.append(f"<tr><td>{html.escape(time_part)}</td><td>{msg}</td></tr>")
        except Exception:
            trows.append(f"<tr><td></td><td>{html.escape(line)}</td></tr>")

    css = """
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; }
    h1 { margin-bottom: 0; }
    .meta { color: #555; margin: 4px 0 20px; }
    table { border-collapse: collapse; width: 100%; margin: 18px 0; }
    th, td { border: 1px solid #ddd; padding: 8px 10px; text-align: left; }
    th { background: #f7f7f7; }
    caption { text-align: left; font-weight: 600; margin-bottom: 6px; }
    .burst { color: red; font-weight: 600; }
    """

    html_doc = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>{css}</style>
<body>
  <h1>{html.escape(title)}</h1>
  <div class="meta">Process count: <b>{len(processes)}</b>{"<br>Quantum: <b>"+str(quantum)+"</b>" if quantum else ""}</div>

  <table>
    <thead><tr><th>Time</th><th>Event</th></tr></thead>
    <tbody>
      {''.join(trows)}
    </tbody>
  </table>
  <div class="meta">Finished at time <b>{runfor}</b></div>

  <table>
    <thead>
      <tr>
        <th>Process</th><th>Arrival</th><th>Burst</th>
        <th>Start</th><th>Finish</th>
        <th>Turnaround</th><th>Waiting</th><th>Response</th><th>Status</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</body>
</html>"""

    with open(htmlfile, "w", encoding="utf-8") as f:
        f.write(html_doc)

# ---------------- Main ----------------
def main():
    if len(sys.argv) != 2:
        print("Usage: scheduler-gpt.py <input file>")
        sys.exit(1)
    infile = sys.argv[1]
    if not infile.endswith(".in"):
        print("Error: Input file must have .in extension")
        sys.exit(1)
    out_txt = os.path.splitext(infile)[0] + ".out"
    out_html = os.path.splitext(infile)[0] + ".html"

    # read + strip comments
    raw_lines = []
    with open(infile) as f:
        for line in f:
            line = line.split('#', 1)[0].strip()
            if line:
                raw_lines.append(line)

    processcount = None
    runfor = None
    algo = None
    quantum = None
    saw_end = False
    processes: List[Process] = []

    for line in raw_lines:
        if line.startswith("processcount"):
            try:
                processcount = int(line.split()[1])
            except (IndexError, ValueError):
                print("Error: Missing parameter processcount")
                sys.exit(1)

        elif line.startswith("runfor"):
            try:
                runfor = int(line.split()[1])
            except (IndexError, ValueError):
                print("Error: Missing parameter runfor")
                sys.exit(1)

        elif line.startswith("use"):
            try:
                algo = line.split()[1]
            except IndexError:
                print("Error: Missing parameter use")
                sys.exit(1)

        elif line.startswith("quantum"):
            try:
                quantum = int(line.split()[1])
            except (IndexError, ValueError):
                print("Error: Missing quantum parameter when use is 'rr'")
                sys.exit(1)

        elif line.startswith("process"):
            try:
                parts = line.split()
                name = parts[2]
                arrival = int(parts[4])
                burst = int(parts[6])
            except (IndexError, ValueError):
                print("Error: Malformed process directive. Expected: process name <id> arrival <n> burst <n>")
                sys.exit(1)
            processes.append(Process(name, arrival, burst))
        elif line == "end":
            saw_end = True
            break

# after the loop
    if not saw_end:
        print("Error: Missing 'end' directive")
        sys.exit(1)

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

    timeline: List[str] = []
    header_title = ""
    if algo == "fcfs":
        header_title = "Using First-Come First-Served"
        fcfs(processes, runfor, timeline)
    elif algo == "sjf":
        header_title = "Using preemptive Shortest Job First"
        sjf_preemptive(processes, runfor, timeline)
    elif algo == "rr":
        header_title = "Using Round-Robin"
        rr(processes, runfor, quantum, timeline)
    else:
        print(f"Error: Unknown scheduling algorithm '{algo}'")
        sys.exit(1)

    out_lines: List[str] = []
    out_lines.append(f"{processcount} processes")
    out_lines.append(header_title)
    if algo == "rr":
        out_lines.append(f"Quantum {quantum}\n")
    for line in timeline:
        out_lines.append(line)
    out_lines.append(f"Finished at time {runfor:3d}")
    out_lines.append("")

    metrics = calc_metrics(processes)
    for p in sorted(processes, key=lambda x: x.name):
        if p.finish_time is not None:
            m = metrics[p.name]
            out_lines.append(f"{p.name} wait {fmt3(m['waiting'])} "
                             f"turnaround {fmt3(m['turnaround'])} "
                             f"response {fmt3(m['response'])}")
    for p in sorted(processes, key=lambda x: x.name):
        if p.finish_time is None:
            out_lines.append(f"{p.name} did not finish")

    with open(out_txt, "w") as f:
        f.write("\n".join(out_lines) + "\n")

    # write html + open automatically
    render_html(out_html, header_title, runfor, quantum if algo == "rr" else None,
                timeline, processes, metrics)
    try:
        webbrowser.open("file://" + os.path.abspath(out_html))
    except Exception as e:
        print(f"(Could not auto-open HTML: {e})")

if __name__ == "__main__":
    main()
