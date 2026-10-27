#ifndef VRCRAFTER_LOG_H
#define VRCRAFTER_LOG_H

#include <windows.h>

void VrcrafterLog(const char *phase, DWORD win32_error, const wchar_t *message);

#endif
