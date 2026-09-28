#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <mmsystem.h>
#include <stdio.h>
#include <stdint.h>
#include <wchar.h>
#include <psapi.h>
#include <dbghelp.h>

/* Retain handles to the owned child's threads so exit does not erase their
 * CPU totals. This adds diagnostics only; never use sampled runs as timings. */
typedef struct { DWORD id; HANDLE h; } SavedThread;
static SavedThread saved[128]; static unsigned saved_count=0, thread_overflow=0;
static SIZE_T peak_working_set=0, peak_pagefile=0;
static uintptr_t seen_modules[128]; static unsigned seen_module_count=0;
static void report_modules(DWORD pid) {
    HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE,pid);
    MODULEENTRY32W module={.dwSize=sizeof(module)};
    if(snap!=INVALID_HANDLE_VALUE && Module32FirstW(snap,&module)) do {
        uintptr_t base=(uintptr_t)module.modBaseAddr; unsigned i=0;
        for(;i<seen_module_count;i++) if(seen_modules[i]==base) break;
        if(i==seen_module_count && seen_module_count<128) {
            seen_modules[seen_module_count++]=base;
            fprintf(stderr,"SAMPLE_IMAGE %p %lu %ls\n",module.modBaseAddr,module.modBaseSize,module.szExePath);
        }
    } while(Module32NextW(snap,&module));
    if(snap!=INVALID_HANDLE_VALUE)CloseHandle(snap);
}
static unsigned long long ft64(FILETIME t) {return ((unsigned long long)t.dwHighDateTime<<32)|t.dwLowDateTime;}
static void discover_threads(DWORD pid, HANDLE process) {
    report_modules(pid);
    HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD,0);
    THREADENTRY32 entry={.dwSize=sizeof(entry)};
    if(snap!=INVALID_HANDLE_VALUE && Thread32First(snap,&entry)) do {
        if(entry.th32OwnerProcessID!=pid) continue;
        unsigned i=0;for(;i<saved_count;i++) if(saved[i].id==entry.th32ThreadID) break;
        if(i!=saved_count) continue;
        if(saved_count==128) {thread_overflow++;continue;}
        HANDLE h=OpenThread(THREAD_QUERY_INFORMATION,FALSE,entry.th32ThreadID);
        if(h) saved[saved_count++]=(SavedThread){entry.th32ThreadID,h};
    } while(Thread32Next(snap,&entry));
    if(snap!=INVALID_HANDLE_VALUE)CloseHandle(snap);
    PROCESS_MEMORY_COUNTERS memory={.cb=sizeof(memory)};
    if(GetProcessMemoryInfo(process,&memory,sizeof(memory))) {
        if(memory.PeakWorkingSetSize>peak_working_set)peak_working_set=memory.PeakWorkingSetSize;
        if(memory.PeakPagefileUsage>peak_pagefile)peak_pagefile=memory.PeakPagefileUsage;
    }
}
/* With SAMPLE_BUSIEST_THREAD set, sample whichever thread has used the most
 * CPU so far (a test harness runs its test on a worker thread). */
static HANDLE busiest(HANDLE current, DWORD *current_id) {
    unsigned long long best=0; DWORD best_id=*current_id;
    for(unsigned i=0;i<saved_count;i++){FILETIME c,e,k,u; if(GetThreadTimes(saved[i].h,&c,&e,&k,&u)){unsigned long long t=ft64(k)+ft64(u); if(t>best){best=t;best_id=saved[i].id;}}}
    if(best_id==*current_id) return current;
    HANDLE h=OpenThread(THREAD_SUSPEND_RESUME|THREAD_GET_CONTEXT|THREAD_QUERY_INFORMATION,FALSE,best_id);
    if(!h) return current;
    *current_id=best_id; return h;
}
static void report_threads(DWORD main_id,HANDLE process) {
    typedef HRESULT (WINAPI *Describe)(HANDLE,PWSTR*);
    Describe describe=(Describe)GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"GetThreadDescription");
    for(unsigned i=0;i<saved_count;i++) {
        FILETIME c,e,k,u;PWSTR name=NULL;
        if(describe)describe(saved[i].h,&name);
        if(GetThreadTimes(saved[i].h,&c,&e,&k,&u))fprintf(stderr,"SAMPLE_THREAD id=%lu main=%d cpu_seconds=%.7f name=%ls\n",saved[i].id,saved[i].id==main_id,(ft64(k)+ft64(u))/10000000.0,name?name:L"");
        if(name)LocalFree(name);
        CloseHandle(saved[i].h);
    }
    FILETIME c,e,k,u;
    if(GetProcessTimes(process,&c,&e,&k,&u))fprintf(stderr,"SAMPLE_CHILD_CPU %.7f\n",(ft64(k)+ft64(u))/10000000.0);
    fprintf(stderr,"SAMPLE_MEMORY peak_working_set=%llu peak_pagefile=%llu thread_overflow=%u\n",(unsigned long long)peak_working_set,(unsigned long long)peak_pagefile,thread_overflow);
}

/* Sample only the main thread of the benchmark child created here. No shared
 * locks or target calls are made between SuspendThread and ResumeThread. */
int wmain(int argc, wchar_t **argv) {
    /* Generic variant: sampler.exe program.exe outdir samples.csv "arguments" */
    if (argc != 5) { fwprintf(stderr,L"usage: sampler.exe program.exe outdir samples.csv arguments\n"); return 2; }
    wchar_t command[16384];
    if (swprintf(command,16384,L"\"%ls\" %ls",argv[1],argv[4]) < 0) return 2;
    FILE *out=_wfopen(argv[3],L"w"); if(!out) return 2;
    STARTUPINFOW startup={.cb=sizeof(startup)};
    PROCESS_INFORMATION child={0};
    wchar_t error_path[8192];
    if(swprintf(error_path,8192,L"%ls\\child-stderr.log",argv[2])<0){fclose(out);return 2;}
    SECURITY_ATTRIBUTES security={.nLength=sizeof(security),.bInheritHandle=TRUE};
    HANDLE child_error=CreateFileW(error_path,GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,&security,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(child_error==INVALID_HANDLE_VALUE){fclose(out);return 2;}
    startup.dwFlags=STARTF_USESTDHANDLES;
    startup.hStdInput=GetStdHandle(STD_INPUT_HANDLE);
    startup.hStdOutput=GetStdHandle(STD_OUTPUT_HANDLE);
    startup.hStdError=child_error;
    if (!CreateProcessW(argv[1],command,NULL,NULL,TRUE,CREATE_SUSPENDED,NULL,NULL,&startup,&child)) {
        fprintf(stderr,"CreateProcess failed: %lu\n",GetLastError()); CloseHandle(child_error); fclose(out); return 2;
    }
    CloseHandle(child_error);
    LARGE_INTEGER frequency, start; QueryPerformanceFrequency(&frequency); QueryPerformanceCounter(&start);
    fprintf(out,"qpc,rip,allocation_base,type,protect,stack\n");
    timeBeginPeriod(1); ResumeThread(child.hThread); Sleep(10);
    BOOL found_module=FALSE;
    for (unsigned attempt=0; attempt<100 && !found_module; ++attempt) {
        HANDLE modules=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE,child.dwProcessId);
        MODULEENTRY32W module={.dwSize=sizeof(module)};
        if(modules != INVALID_HANDLE_VALUE && Module32FirstW(modules,&module)) {
            fprintf(stderr,"SAMPLE_MODULE %p %lu\n",module.modBaseAddr,module.modBaseSize);
            found_module=TRUE;
        }
        if(modules != INVALID_HANDLE_VALUE) CloseHandle(modules);
        if(!found_module) Sleep(10);
    }
    if(!found_module) fprintf(stderr,"SAMPLE_MODULE unavailable after retries\n");
    SymSetOptions(SYMOPT_UNDNAME|SYMOPT_DEFERRED_LOADS);
    if(!SymInitializeW(child.hProcess,NULL,TRUE)) fprintf(stderr,"SymInitialize failed: %lu\n",GetLastError());
    unsigned samples=0, failures=0;
    discover_threads(child.dwProcessId,child.hProcess);
    HANDLE target=child.hThread; DWORD target_id=child.dwThreadId; int pick=_wgetenv(L"SAMPLE_BUSIEST_THREAD")!=NULL;
    while(WaitForSingleObject(child.hProcess,1)==WAIT_TIMEOUT) {
        if(samples%64==0){discover_threads(child.dwProcessId,child.hProcess);SymRefreshModuleList(child.hProcess);if(pick)target=busiest(target,&target_id);}
        LARGE_INTEGER stamp; QueryPerformanceCounter(&stamp);
        if(stamp.QuadPart-start.QuadPart > frequency.QuadPart*300) {
            fprintf(stderr,"Benchmark child timed out\n"); TerminateProcess(child.hProcess,3); break;
        }
        CONTEXT context={0}; context.ContextFlags=CONTEXT_FULL;
        if(SuspendThread(target)==(DWORD)-1) { failures++; continue; }
        BOOL ok=GetThreadContext(target,&context);
        /* Unwind with the target's own .pdata tables (StackWalk64) while the
         * thread is still suspended. dbghelp reads the target's memory; it
         * takes no locks in the target. */
        unsigned long long returns[32]; int depth=0;
        if(ok) {
            CONTEXT unwind=context;
            STACKFRAME64 frame={0};
            frame.AddrPC.Offset=context.Rip; frame.AddrPC.Mode=AddrModeFlat;
            frame.AddrFrame.Offset=context.Rbp; frame.AddrFrame.Mode=AddrModeFlat;
            frame.AddrStack.Offset=context.Rsp; frame.AddrStack.Mode=AddrModeFlat;
            int first=1;
            while(depth<32 && StackWalk64(IMAGE_FILE_MACHINE_AMD64,child.hProcess,target,&frame,&unwind,NULL,SymFunctionTableAccess64,SymGetModuleBase64,NULL)) {
                if(first){first=0;continue;} /* the first frame is the sampled PC itself */
                if(frame.AddrPC.Offset==0) break;
                returns[depth++]=frame.AddrPC.Offset;
            }
        }
        DWORD resumed=ResumeThread(target);
        if(resumed==(DWORD)-1) { fprintf(stderr,"ResumeThread failed\n"); TerminateProcess(child.hProcess,3); break; }
        if(ok) {
            MEMORY_BASIC_INFORMATION info={0};
            VirtualQueryEx(child.hProcess,(LPCVOID)context.Rip,&info,sizeof(info));
            fprintf(out,"%lld,0x%llx,0x%llx,0x%lx,0x%lx,",stamp.QuadPart,(unsigned long long)context.Rip,(unsigned long long)info.AllocationBase,info.Type,info.Protect);
            for(int i=0;i<depth;++i) fprintf(out,"%s0x%llx",i?";":"",returns[i]);
            fputc('\n',out); samples++;
        }
        else failures++;
    }
    timeEndPeriod(1); fclose(out);
    WaitForSingleObject(child.hProcess,1000); DWORD code=3; GetExitCodeProcess(child.hProcess,&code);
    fprintf(stderr,"SAMPLE_RESULT pid=%lu samples=%u failures=%u frequency=%lld exit=%lu\n",child.dwProcessId,samples,failures,frequency.QuadPart,code);
    report_threads(child.dwThreadId,child.hProcess);
    CloseHandle(child.hThread); CloseHandle(child.hProcess); return (int)code;
}
