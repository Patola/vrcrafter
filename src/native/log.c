#include "log.h"

#include <stdio.h>
#include <string.h>

static SRWLOCK g_log_lock = SRWLOCK_INIT;

static void write_all(HANDLE file, const void *buffer, DWORD length)
{
    const char *cursor = buffer;

    while (length != 0) {
        DWORD written;
        if (!WriteFile(file, cursor, length, &written, NULL) || written == 0)
            return;
        cursor += written;
        length -= written;
    }
}

void VrcrafterLog(const char *phase, DWORD win32_error, const wchar_t *message)
{
    WCHAR directory[MAX_PATH];
    WCHAR path[MAX_PATH];
    char prefix[160];
    char utf8[4096];
    DWORD length;
    DWORD prefix_length;
    HANDLE file;

    length = GetEnvironmentVariableW(L"VRCRAFTER_LOG_DIR", directory, MAX_PATH);
    if (length == 0 || length >= MAX_PATH) {
        length = GetTempPathW(MAX_PATH, directory);
        if (length == 0 || length >= MAX_PATH)
            return;
    }

    if (_snwprintf(path, MAX_PATH, L"%s\\vrcrafter-native.log", directory) < 0)
        return;
    path[MAX_PATH - 1] = L'\0';

    if (message == NULL)
        message = L"";
    length = WideCharToMultiByte(CP_UTF8, 0, message, -1, utf8, sizeof(utf8), NULL, NULL);
    if (length == 0) {
        memcpy(utf8, "UTF8_CONVERSION_ERROR", sizeof("UTF8_CONVERSION_ERROR"));
        length = sizeof("UTF8_CONVERSION_ERROR");
    }

    prefix_length = (DWORD)snprintf(prefix, sizeof(prefix), "[%lu] %s error=%lu ",
                                    GetCurrentProcessId(), phase, win32_error);

    AcquireSRWLockExclusive(&g_log_lock);
    file = CreateFileW(path, FILE_APPEND_DATA,
                       FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                       NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file != INVALID_HANDLE_VALUE) {
        write_all(file, prefix, prefix_length);
        write_all(file, utf8, length - 1);
        write_all(file, "\r\n", 2);
        CloseHandle(file);
    }
    ReleaseSRWLockExclusive(&g_log_lock);
}
