#include "log.h"
#include "mono_host.h"

#include <windows.h>
#include <wchar.h>

static volatile LONG g_start_state;

__declspec(dllexport) int WINAPI VrcrafterPing(int value)
{
    return value + 1;
}

__declspec(dllexport) DWORD WINAPI VrcrafterStart(void)
{
    WCHAR payload[MAX_PATH];
    DWORD length;
    DWORD error;

    if (InterlockedCompareExchange(&g_start_state, 1, 0) != 0) {
        VrcrafterLog("START_SKIPPED", ERROR_ALREADY_EXISTS,
                     L"deferred entry was already claimed");
        return 0;
    }

    length = GetEnvironmentVariableW(L"VRCRAFTER_PAYLOAD", payload, MAX_PATH);
    if (length == 0) {
        error = GetLastError();
        if (error == ERROR_SUCCESS)
            error = ERROR_ENVVAR_NOT_FOUND;
        VrcrafterLog("PAYLOAD", error, L"VRCRAFTER_PAYLOAD is unavailable");
        return error;
    }
    if (length >= MAX_PATH) {
        VrcrafterLog("PAYLOAD", ERROR_INSUFFICIENT_BUFFER,
                     L"VRCRAFTER_PAYLOAD is too long");
        return ERROR_INSUFFICIENT_BUFFER;
    }

    VrcrafterLog("DEFERRED_START", ERROR_SUCCESS, L"mono_host_start");
    return mono_host_start(payload);
}

static DWORD WINAPI deferred_start(void *context)
{
    (void)context;
    (void)VrcrafterStart();
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, void *reserved)
{
    WCHAR process_path[MAX_PATH];
    WCHAR enable[16];
    WCHAR payload[MAX_PATH];
    const WCHAR *process_name = L"<unknown>";
    const WCHAR *slash;
    const WCHAR *backslash;
    DWORD length;
    DWORD error = ERROR_SUCCESS;
    HANDLE thread;

    (void)reserved;
    if (reason != DLL_PROCESS_ATTACH)
        return TRUE;

    DisableThreadLibraryCalls(instance);

    length = GetModuleFileNameW(NULL, process_path, MAX_PATH);
    if (length != 0 && length < MAX_PATH) {
        process_name = process_path;
        slash = wcsrchr(process_name, L'/');
        backslash = wcsrchr(process_name, L'\\');
        if (backslash != NULL && backslash >= process_name)
            process_name = backslash + 1;
        if (slash != NULL && slash >= process_name)
            process_name = slash + 1;
    } else {
        error = GetLastError();
    }
    VrcrafterLog("PROCESS", error, process_name);

    length = GetEnvironmentVariableW(L"VRCRAFTER_PAYLOAD", payload, MAX_PATH);
    if (length == 0)
        wcscpy(payload, L"<unset>");
    else if (length >= MAX_PATH)
        wcscpy(payload, L"<unavailable>");
    VrcrafterLog("PAYLOAD", length >= MAX_PATH ? ERROR_INSUFFICIENT_BUFFER : ERROR_SUCCESS,
                 payload);

    length = GetEnvironmentVariableW(L"VRCRAFTER_ENABLE", enable, 16);
    if (length == 0 || length >= 16 || wcscmp(enable, L"1") != 0) {
        VrcrafterLog("ACTIVATION_SKIPPED", ERROR_SUCCESS,
                     L"VRCRAFTER_ENABLE is not 1");
        return TRUE;
    }
    if (_wcsicmp(process_name, L"Planet Crafter.exe") != 0) {
        VrcrafterLog("ACTIVATION_SKIPPED", ERROR_SUCCESS,
                     L"executable is not Planet Crafter.exe");
        return TRUE;
    }

    thread = CreateThread(NULL, 0, deferred_start, NULL, 0, NULL);
    if (thread == NULL) {
        VrcrafterLog("START_QUEUE", GetLastError(), L"CreateThread failed");
        return TRUE;
    }
    CloseHandle(thread);
    VrcrafterLog("START_QUEUED", ERROR_SUCCESS, L"deferred entry queued");
    return TRUE;
}
