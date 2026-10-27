#ifndef VRCRAFTER_MONO_HOST_H
#define VRCRAFTER_MONO_HOST_H

#include <windows.h>
#include <wchar.h>

typedef struct MonoDomain MonoDomain;
typedef struct MonoThread MonoThread;
typedef struct MonoAssembly MonoAssembly;
typedef struct MonoImage MonoImage;
typedef struct MonoClass MonoClass;
typedef struct MonoMethod MonoMethod;
typedef struct MonoObject MonoObject;

typedef MonoDomain *(*MonoGetRootDomainFn)(void);
typedef MonoThread *(*MonoThreadAttachFn)(MonoDomain *);
typedef void (*MonoThreadDetachFn)(MonoThread *);
typedef MonoAssembly *(*MonoDomainAssemblyOpenFn)(MonoDomain *, const char *);
typedef MonoImage *(*MonoAssemblyGetImageFn)(MonoAssembly *);
typedef MonoClass *(*MonoClassFromNameFn)(MonoImage *, const char *, const char *);
typedef MonoMethod *(*MonoClassGetMethodFromNameFn)(MonoClass *, const char *, int);
typedef MonoObject *(*MonoRuntimeInvokeFn)(MonoMethod *, void *, void **, MonoObject **);
typedef void *(*MonoObjectUnboxFn)(MonoObject *);
typedef void (*MonoFreeFn)(void *);

DWORD mono_host_start(const wchar_t *payload_dir);

#endif
