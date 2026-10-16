/* Adapt the public AppLog device setter in a private, pinned runtime only. */
#include <windows.h>
static HMODULE original;
__declspec(dllexport) void AppLog_init(const char *aid, const char *channel) {
    original = LoadLibraryW(L"applogrs_original.dll");
    if (!original) ExitProcess(91);
    typedef void (*Flag)(int);
    ((Flag)GetProcAddress(original, "AppLog_setAutoStart"))(0);
    ((Flag)GetProcAddress(original, "AppLog_setAutoRegisterEnabled"))(0);
    ((void (*)(const char *, const char *))GetProcAddress(original, "AppLog_init"))(aid, channel);
    char value[32];
    DWORD count = GetEnvironmentVariableA("DOUBAO_ORGANIZE_DEVICE_ID", value, sizeof(value));
    if (!count || count >= sizeof(value)) ExitProcess(92);
    unsigned long long id = 0;
    for (DWORD i = 0; i < count; i++) {
        if (value[i] < '0' || value[i] > '9' || id > 1844674407370955161ULL) ExitProcess(93);
        unsigned digit = value[i] - '0';
        if (id == 1844674407370955161ULL && digit > 5) ExitProcess(93);
        id = id * 10 + digit;
    }
    if (!id) ExitProcess(93);
    ((void (*)(unsigned long long))GetProcAddress(original, "AppLog_setDeviceId"))(id);
}
BOOL WINAPI DllMainCRTStartup(HINSTANCE instance, DWORD reason, LPVOID reserved) { return TRUE; }
