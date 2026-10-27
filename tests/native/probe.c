#include <windows.h>
#include <winhttp.h>
#include <stdio.h>

typedef int (WINAPI *VrcrafterPingFn)(int value);

int wmain(void)
{
    HMODULE winhttp = GetModuleHandleW(L"winhttp.dll");
    VrcrafterPingFn ping;
    WINHTTP_PROXY_INFO proxy_info = {0};

    if (winhttp == NULL) {
        fprintf(stderr, "FAIL: GetModuleHandleW(winhttp.dll): %lu\n", GetLastError());
        return 1;
    }

    ping = (VrcrafterPingFn)(void *)GetProcAddress(winhttp, "VrcrafterPing");
    if (ping == NULL) {
        fprintf(stderr, "FAIL: VrcrafterPing is missing: %lu\n", GetLastError());
        return 2;
    }

    if (ping(41) != 42) {
        fputs("FAIL: VrcrafterPing(41) did not return 42\n", stderr);
        return 3;
    }

    if (!WinHttpGetDefaultProxyConfiguration(&proxy_info)) {
        fprintf(stderr, "FAIL: WinHttpGetDefaultProxyConfiguration: %lu\n", GetLastError());
        return 4;
    }

    if (proxy_info.lpszProxy != NULL)
        GlobalFree(proxy_info.lpszProxy);
    if (proxy_info.lpszProxyBypass != NULL)
        GlobalFree(proxy_info.lpszProxyBypass);

    puts("PROBE_OK");
    return 0;
}
