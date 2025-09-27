#!/usr/bin/env python3
"""
scheduler-gpt.py

Usage:
    python scheduler-gpt.py <input file>

The input file must follow the directive-style format described in the assignment.
This version:
  * Reads the input file directly (no copy is made).
  * Always writes results to outputTEST.out.
  * Prints a confirmation message with the output file name.
"""

import sys
import os
from collections import deque

# -------------------------
# Process data structure
# -------------------------
class Process:
    def __init__(self, name, arrival, burst):
        self.name = name
        self.arrival = int(arrival)
        self.burst = int(burst)
        self.remaining = int(burst)
        self.start_time = None
        self.finish_time = None
        self.run_time = 0

    def is_finished(self):
        return self.remaining <= 0

# -------------------------
# Utility: error & usage
# -------------------------
def usage_and_exit():
    print("Usage: scheduler-gpt.py <input file>")
    sys.exit(1)

def error_and_exit(msg):
    print(msg)
    sys.exit(1)

# -------------------------
# Input parsing
# -------------------------
def parse_input_file(path):
    with open(path, 'r') as f:
        raw_lines = f.readlines()

    lines = []
    for ln in raw_lines:
        if '#' in ln:
            ln = ln.split('#', 1)[0]
        ln = ln.strip()
        if ln:
            lines.append(ln)

    params = {'processcount': None, 'runfor': None, 'use': None, 'quantum': None}
    processes = []

    i = 0
    while i < len(lines):
        tokens = lines[i].split()
        if not tokens:
            i += 1
            continue
        key = tokens[0].lower()

        if key == 'processcount':
            if len(tokens) < 2:
                error_and_exit("Error: Missing parameter processcount")
            params['processcount'] = int(tokens[1])
            i += 1
            continue

        if key == 'runfor':
            if len(tokens) < 2:
                error_and_exit("Error: Missing parameter runfor")
            params['runfor'] = int(tokens[1])
            i += 1
            continue

        if key == 'use':
            if len(tokens) < 2:
                error_and_exit("Error: Missing parameter use")
            params['use'] = tokens[1].lower()
            i += 1
            continue

        if key == 'quantum':
            if len(tokens) < 2:
                error_and_exit("Error: Missing parameter quantum")
            params['quantum'] = int(tokens[1])
            i += 1
            continue

        if key == 'process':
            try:
                tokens_lower = [t.lower() for t in tokens]
                if 'name' not in tokens_lower:
                    error_and_exit("Error: Missing parameter name")
                if 'arrival' not in tokens_lower:
                    error_and_exit("Error: Missing parameter arrival")
                if 'burst' not in tokens_lower:
                    error_and_exit("Error: Missing parameter burst")

                name_idx = tokens_lower.index('name')
                arrival_idx = tokens_lower.index('arrival')
                burst_idx = tokens_lower.index('burst')

                name = tokens[name_idx + 1]
                arrival = tokens[arrival_idx + 1]
                burst = tokens[burst_idx + 1]

            except Exception:
                error_and_exit("Error: Malformed process line")

            processes.append(Process(name, arrival, burst))
            i += 1
            continue

        if key == 'end':
            break

        i += 1

    if params['processcount'] is None:
        error_and_exit("Error: Missing parameter processcount")
    if params['runfor'] is None:
        error_and_exit("Error: Missing parameter runfor")
    if params['use'] is None:
        error_and_exit("Error: Missing parameter use")
    if params['use'] == 'rr' and params['quantum'] is None:
        error_and_exit("Error: Missing quantum parameter when use is 'rr'")

    if len(processes) < params['processcount']:
        error_and_exit("Error: Missing parameter process")
    if len(processes) > params['processcount']:
        processes = processes[:params['processcount']]

    return params, processes

# -------------------------
# Scheduling simulators
# -------------------------
def simulate_fcfs(process_list, runfor):
    ordered = sorted(process_list, key=lambda p: (p.arrival, p.name))
    log = []
    time = 0
    queue = deque()
    current_proc = None

    while time < runfor:
        for p in ordered:
            if p.arrival == time:
                log.append(f"Time {time} : {p.name} arrived")
                queue.append(p)

        if current_proc is None or current_proc.is_finished():
            if current_proc is not None and current_proc.is_finished():
                current_proc = None
            if queue:
                candidate = queue.popleft()
                if not candidate.is_finished():
                    current_proc = candidate
                    if candidate.start_time is None:
                        candidate.start_time = time
                    log.append(f"Time {time} : {candidate.name} selected (burst {candidate.remaining})")

        if current_proc is None:
            log.append(f"Time {time} : Idle")
        else:
            current_proc.remaining -= 1
            current_proc.run_time += 1
            if current_proc.remaining == 0:
                log.append(f"Time {time + 1} : {current_proc.name} finished")
                current_proc.finish_time = time + 1
        time += 1

    return log

def simulate_sjf_preemptive(process_list, runfor):
    log = []
    time = 0
    last_selected = None

    while time < runfor:
        for p in process_list:
            if p.arrival == time:
                log.append(f"Time {time} : {p.name} arrived")

        ready = [p for p in process_list if p.arrival <= time and not p.is_finished()]

        if ready:
            selected = min(ready, key=lambda x: (x.remaining, x.arrival, x.name))
            if last_selected is None or last_selected.name != selected.name:
                if selected.start_time is None:
                    selected.start_time = time
                log.append(f"Time {time} : {selected.name} selected (burst {selected.remaining})")
            selected.remaining -= 1
            selected.run_time += 1
            if selected.remaining == 0:
                selected.finish_time = time + 1
                log.append(f"Time {time + 1} : {selected.name} finished")
                last_selected = None
            else:
                last_selected = selected
        else:
            log.append(f"Time {time} : Idle")
            last_selected = None

        time += 1

    return log

def simulate_rr(process_list, runfor, quantum):
    log = []
    time = 0
    ready_queue = deque()
    running = None
    remaining_quantum = 0

    while time < runfor:
        for p in process_list:
            if p.arrival == time:
                log.append(f"Time {time} : {p.name} arrived")
                if not p.is_finished():
                    ready_queue.append(p)

        if running is None or running.is_finished() or remaining_quantum == 0:
            if running is not None and (not running.is_finished()) and remaining_quantum == 0:
                ready_queue.append(running)
            running = None
            remaining_quantum = 0
            while ready_queue:
                candidate = ready_queue.popleft()
                if not candidate.is_finished():
                    running = candidate
                    remaining_quantum = quantum
                    if candidate.start_time is None:
                        candidate.start_time = time
                    log.append(f"Time {time} : {candidate.name} selected (burst {candidate.remaining})")
                    break

        if running is None:
            log.append(f"Time {time} : Idle")
        else:
            running.remaining -= 1
            running.run_time += 1
            remaining_quantum -= 1
            if running.remaining == 0:
                running.finish_time = time + 1
                log.append(f"Time {time + 1} : {running.name} finished")
                running = None
                remaining_quantum = 0

        time += 1

    return log

# -------------------------
# Metrics
# -------------------------
def print_metrics_lines(process_list):
    lines = []
    unfinished = []
    for p in process_list:
        if p.is_finished() and (p.finish_time is not None):
            turnaround = p.finish_time - p.arrival
            waiting = turnaround - p.burst
            response = p.start_time - p.arrival if p.start_time is not None else 0
            lines.append(f"{p.name} wait {waiting} turnaround {turnaround} response {response}")
        else:
            unfinished.append(p.name)
    return lines, unfinished

# -------------------------
# Main
# -------------------------
def main():
    if len(sys.argv) != 2:
        usage_and_exit()

    input_file = sys.argv[1]
    if not input_file.endswith('.in'):
        usage_and_exit()
    if not os.path.exists(input_file):
        usage_and_exit()

    params, processes = parse_input_file(input_file)
    runfor = params['runfor']
    use_algo = params['use']
    quantum = params['quantum']

    sim_procs = [Process(p.name, p.arrival, p.burst) for p in processes]

    output_file = "outputTEST.out"
    with open(output_file, 'w') as out:
        out.write(f"{params['processcount']} processes\n")

        if use_algo == 'sjf':
            out.write("Using preemptive Shortest Job First\n")
            log = simulate_sjf_preemptive(sim_procs, runfor)
        elif use_algo == 'fcfs':
            out.write("Using First Come First Served\n")
            log = simulate_fcfs(sim_procs, runfor)
        elif use_algo == 'rr':
            out.write("Using Round Robin\n")
            out.write(f"Quantum {quantum}\n")
            log = simulate_rr(sim_procs, runfor, quantum)
        else:
            error_and_exit("Error: Missing parameter use")

        for line in log:
            out.write(line + "\n")

        out.write(f"Finished at time {runfor}\n\n")

        metric_lines, unfinished = print_metrics_lines(sim_procs)
        for ml in metric_lines:
            out.write(ml + "\n")
        for name in unfinished:
            out.write(f"{name} did not finish\n")

    print(f"? Simulation complete. Results written to {output_file}")

if __name__ == "__main__":
    main()
