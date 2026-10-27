#include "mono_host.h"
#include "log.h"

#include <stdio.h>

#define MONO_DISCOVERY_ATTEMPTS 1200
#define MONO_DISCOVERY_DELAY_MS 100
#define WIDE_STRING_INNER(text) L##text
#define WIDE_STRING(text) WIDE_STRING_INNER(#text)

typedef struct MonoApi {
    MonoGetRootDomainFn mono_get_root_domain;
    MonoThreadAttachFn mono_thread_attach;
    MonoThreadDetachFn mono_thread_detach;
    MonoDomainAssemblyOpenFn mono_domain_assembly_open;
    MonoAssemblyGetImageFn mono_assembly_get_image;
    MonoClassFromNameFn mono_class_from_name;
    MonoClassGetMethodFromNameFn mono_class_get_method_from_name;
    MonoRuntimeInvokeFn mono_runtime_invoke;
    MonoObjectUnboxFn mono_object_unbox;
    MonoFreeFn mono_free;
} MonoApi;

#define RESOLVE_MONO_EXPORT(name)                                                \
    do {                                                                         \
        api.name = (void *)GetProcAddress(module, #name);                         \
        if (api.name == NULL) {                                                   \
            error = GetLastError();                                               \
            if (error == ERROR_SUCCESS)                                           \
                error = ERROR_PROC_NOT_FOUND;                                     \
            VrcrafterLog("MONO_EXPORT", error, WIDE_STRING(name));                \
            return error;                                                         \
        }                                                                         \
    } while (0)

DWORD mono_host_start(const wchar_t *payload_dir)
{
    HMODULE module = NULL;
    MonoApi api;
    MonoDomain *domain;
    MonoThread *thread;
    MonoAssembly *assembly;
    MonoImage *image;
    MonoClass *entry_class;
    MonoMethod *entry_method;
    MonoObject *exception = NULL;
    MonoObject *result;
    void *unboxed;
    WCHAR managed_path[MAX_PATH];
    WCHAR result_message[80];
    char *managed_path_utf8;
    DWORD error = ERROR_MOD_NOT_FOUND;
    int attempt;
    int path_length;
    int utf8_length;
    int managed_result;

    if (payload_dir == NULL || payload_dir[0] == L'\0') {
        VrcrafterLog("MANAGED_PATH", ERROR_INVALID_PARAMETER,
                     L"payload directory is empty");
        return ERROR_INVALID_PARAMETER;
    }

    for (attempt = 0; attempt < MONO_DISCOVERY_ATTEMPTS; ++attempt) {
        module = GetModuleHandleW(L"mono-2.0-bdwgc.dll");
        if (module != NULL)
            break;
        error = GetLastError();
        Sleep(MONO_DISCOVERY_DELAY_MS);
    }
    if (module == NULL) {
        if (error == ERROR_SUCCESS)
            error = ERROR_MOD_NOT_FOUND;
        VrcrafterLog("MONO_MODULE", error,
                     L"mono-2.0-bdwgc.dll was not loaded within 120 seconds");
        return error;
    }
    VrcrafterLog("MONO_MODULE", ERROR_SUCCESS, L"mono-2.0-bdwgc.dll");

    RESOLVE_MONO_EXPORT(mono_get_root_domain);
    RESOLVE_MONO_EXPORT(mono_thread_attach);
    RESOLVE_MONO_EXPORT(mono_thread_detach);
    RESOLVE_MONO_EXPORT(mono_domain_assembly_open);
    RESOLVE_MONO_EXPORT(mono_assembly_get_image);
    RESOLVE_MONO_EXPORT(mono_class_from_name);
    RESOLVE_MONO_EXPORT(mono_class_get_method_from_name);
    RESOLVE_MONO_EXPORT(mono_runtime_invoke);
    RESOLVE_MONO_EXPORT(mono_object_unbox);
    RESOLVE_MONO_EXPORT(mono_free);

    domain = api.mono_get_root_domain();
    if (domain == NULL) {
        VrcrafterLog("MONO_DOMAIN", ERROR_NOT_READY, L"root domain is null");
        return ERROR_NOT_READY;
    }
    thread = api.mono_thread_attach(domain);
    if (thread == NULL) {
        VrcrafterLog("MONO_ATTACH", ERROR_NOT_READY,
                     L"mono_thread_attach returned null");
        return ERROR_NOT_READY;
    }
    VrcrafterLog("MONO_DOMAIN", ERROR_SUCCESS, L"existing root domain attached");

    path_length = _snwprintf(managed_path, MAX_PATH,
                             L"%ls\\managed\\Vrcrafter.Bootstrap.dll", payload_dir);
    if (path_length < 0 || path_length >= MAX_PATH) {
        VrcrafterLog("MANAGED_PATH", ERROR_INSUFFICIENT_BUFFER,
                     L"managed assembly path is too long");
        return ERROR_INSUFFICIENT_BUFFER;
    }
    managed_path[MAX_PATH - 1] = L'\0';

    utf8_length = WideCharToMultiByte(CP_UTF8, 0, managed_path, -1, NULL, 0, NULL, NULL);
    if (utf8_length == 0) {
        error = GetLastError();
        VrcrafterLog("MANAGED_PATH_UTF8", error, L"UTF-8 size query failed");
        return error;
    }
    managed_path_utf8 = HeapAlloc(GetProcessHeap(), 0, (SIZE_T)utf8_length);
    if (managed_path_utf8 == NULL) {
        VrcrafterLog("MANAGED_PATH_UTF8", ERROR_NOT_ENOUGH_MEMORY,
                     L"UTF-8 path allocation failed");
        return ERROR_NOT_ENOUGH_MEMORY;
    }
    if (WideCharToMultiByte(CP_UTF8, 0, managed_path, -1, managed_path_utf8,
                            utf8_length, NULL, NULL) == 0) {
        error = GetLastError();
        HeapFree(GetProcessHeap(), 0, managed_path_utf8);
        VrcrafterLog("MANAGED_PATH_UTF8", error, L"UTF-8 conversion failed");
        return error;
    }

    assembly = api.mono_domain_assembly_open(domain, managed_path_utf8);
    HeapFree(GetProcessHeap(), 0, managed_path_utf8);
    if (assembly == NULL) {
        VrcrafterLog("MANAGED_ASSEMBLY_OPEN", ERROR_FILE_NOT_FOUND, managed_path);
        return ERROR_FILE_NOT_FOUND;
    }
    image = api.mono_assembly_get_image(assembly);
    if (image == NULL) {
        VrcrafterLog("MANAGED_IMAGE", ERROR_INVALID_DATA,
                     L"mono_assembly_get_image returned null");
        return ERROR_INVALID_DATA;
    }
    entry_class = api.mono_class_from_name(image, "Vrcrafter.Bootstrap", "EntryPoint");
    if (entry_class == NULL) {
        VrcrafterLog("MANAGED_CLASS", ERROR_NOT_FOUND,
                     L"Vrcrafter.Bootstrap.EntryPoint was not found");
        return ERROR_NOT_FOUND;
    }
    entry_method = api.mono_class_get_method_from_name(entry_class, "Start", 0);
    if (entry_method == NULL) {
        VrcrafterLog("MANAGED_METHOD", ERROR_NOT_FOUND,
                     L"EntryPoint.Start():int was not found");
        return ERROR_NOT_FOUND;
    }

    VrcrafterLog("MANAGED_ENTRY", ERROR_SUCCESS,
                 L"Vrcrafter.Bootstrap.EntryPoint.Start():int");
    result = api.mono_runtime_invoke(entry_method, NULL, NULL, &exception);
    if (exception != NULL) {
        VrcrafterLog("MANAGED_EXCEPTION", ERROR_GEN_FAILURE,
                     L"mono_runtime_invoke returned an exception");
        return ERROR_GEN_FAILURE;
    }
    if (result == NULL) {
        VrcrafterLog("MANAGED_RESULT", ERROR_INVALID_DATA,
                     L"mono_runtime_invoke returned null");
        return ERROR_INVALID_DATA;
    }
    unboxed = api.mono_object_unbox(result);
    if (unboxed == NULL) {
        VrcrafterLog("MANAGED_UNBOX", ERROR_INVALID_DATA,
                     L"mono_object_unbox returned null");
        return ERROR_INVALID_DATA;
    }

    managed_result = *(int *)unboxed;
    _snwprintf(result_message, sizeof(result_message) / sizeof(result_message[0]),
               L"MANAGED_RESULT=%d", managed_result);
    result_message[sizeof(result_message) / sizeof(result_message[0]) - 1] = L'\0';
    VrcrafterLog("MANAGED_RESULT", (DWORD)managed_result, result_message);
    return managed_result == 0 ? ERROR_SUCCESS : (DWORD)managed_result;
}
