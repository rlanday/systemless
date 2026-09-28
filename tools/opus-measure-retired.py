#!/usr/bin/env python3
"""Count user-space host instructions a child process retires.

Owner: Opus. Linux only, single child, no sampling, no privileges beyond the
machine's existing perf_event_paranoid setting. The point is a screening
instrument for changes whose GUEST work is identical: when the guest
instruction stream is fixed, host instructions retired measure host work done,
and unlike elapsed time they do not move with power state, thermal state or an
unrelated process on another core.

  opus-measure-retired.py [--repeat N] -- COMMAND [ARGS...]

Prints one line per run and a summary. It measures a whole process, including
its startup, so compare two runs of the SAME binary that differ only in the
behaviour under test.
"""
import argparse
import ctypes
import fcntl
import os
import struct
import sys

PERF_TYPE_HARDWARE = 0
PERF_COUNT_HW_INSTRUCTIONS = 1
PERF_COUNT_HW_CPU_CYCLES = 0
PERF_COUNT_HW_BRANCH_MISSES = 5
PERF_EVENT_IOC_ENABLE = 0x2400
PERF_EVENT_IOC_DISABLE = 0x2401
PERF_EVENT_IOC_RESET = 0x2403
SYS_perf_event_open = 298

# perf_event_attr bit flags, in declaration order from the kernel header.
DISABLED, INHERIT = 1 << 0, 1 << 1
EXCLUDE_KERNEL, EXCLUDE_HV = 1 << 5, 1 << 6
ENABLE_ON_EXEC = 1 << 12

libc = ctypes.CDLL(None, use_errno=True)


def open_counter(config, pid):
    attr = bytearray(128)
    struct.pack_into('IIQ', attr, 0, PERF_TYPE_HARDWARE, 128, config)
    flags = DISABLED | INHERIT | EXCLUDE_KERNEL | EXCLUDE_HV | ENABLE_ON_EXEC
    struct.pack_into('Q', attr, 40, flags)
    buffer = (ctypes.c_char * 128).from_buffer(attr)
    fd = libc.syscall(SYS_perf_event_open, buffer, pid, -1, -1, 0)
    if fd < 0:
        error = ctypes.get_errno()
        raise OSError(error, f'perf_event_open: {os.strerror(error)}')
    return fd


def measure(command, environment):
    """Run `command` once and return its retired instructions, cycles and branch misses."""
    ready_read, ready_write = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(ready_write)
        os.read(ready_read, 1)  # wait until the counters are armed
        os.close(ready_read)
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        os.execvpe(command[0], command, environment)
        os._exit(127)
    os.close(ready_read)
    counters = {
        'instructions': open_counter(PERF_COUNT_HW_INSTRUCTIONS, child),
        'cycles': open_counter(PERF_COUNT_HW_CPU_CYCLES, child),
        'branch-misses': open_counter(PERF_COUNT_HW_BRANCH_MISSES, child),
    }
    for fd in counters.values():
        fcntl.ioctl(fd, PERF_EVENT_IOC_RESET, 0)
        fcntl.ioctl(fd, PERF_EVENT_IOC_ENABLE, 0)
    os.write(ready_write, b'\n')
    os.close(ready_write)
    _, status = os.waitpid(child, 0)
    values = {}
    for name, fd in counters.items():
        fcntl.ioctl(fd, PERF_EVENT_IOC_DISABLE, 0)
        values[name] = struct.unpack('Q', os.read(fd, 8))[0]
        os.close(fd)
    if status != 0:
        raise SystemExit(f'child exited with status {status}')
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--repeat', type=int, default=3)
    parser.add_argument('--label', default='')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    command = arguments.command[1:] if arguments.command[:1] == ['--'] else arguments.command
    if not command:
        parser.error('give a command after --')

    runs = [measure(command, os.environ.copy()) for _ in range(arguments.repeat)]
    for index, run in enumerate(runs):
        print(f'  run {index}: ' + '  '.join(f'{k}={v:,}' for k, v in run.items()))
    summary = {}
    for name in runs[0]:
        values = sorted(run[name] for run in runs)
        low, high = values[0], values[-1]
        spread = 100 * (high - low) / low if low else 0
        summary[name] = values[len(values) // 2]
        print(f'{arguments.label}{name}: median {summary[name]:,}  spread {spread:.4f}%')
    return summary


if __name__ == '__main__':
    main()
