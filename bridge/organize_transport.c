/* UTF-8 JSON stdin and bounded SSE stdout around the original Cronet API.
 * Other requests retain their original callbacks and upload providers. */
#include <windows.h>
static HMODULE original;
static int status_sent;
static void *organize_request;
static void (*read_original)(void *, void *, void *, void *, unsigned long long);
static char body[262145];
static unsigned body_length, body_offset;
static int body_ready;
static void load(void) {
    if (!original) original = LoadLibraryW(L"sscronet_original.dll");
    if (!original) ExitProcess(94);
}
static void emit(const char *text) {
    DWORD written;
    WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), text, lstrlenA(text), &written, 0);
}
static int contains(const char *text, const char *part) {
    int n = lstrlenA(part);
    for (; *text; text++) { int i = 0; while (i < n && text[i] && text[i] == part[i]) i++; if (i == n) return 1; }
    return 0;
}
static long long length(void *);
static void read_body(void *, void *, void *);
static void rewind_body(void *, void *);
static void close_body(void *);
__declspec(dllexport) int Cronet_UrlRequest_InitWithParams(void *request, void *engine,
        const char *url, void *params, void *callback, void *executor) {
    load();
    if (contains(url, "/api/v2/ai/text_organization")) {
        organize_request = request;
        void *provider = ((void *(*)(void *, void *, void *, void *))
            GetProcAddress(original, "Cronet_UploadDataProvider_CreateWith"))(length, read_body, rewind_body, close_body);
        ((void (*)(void *, void *))GetProcAddress(original, "Cronet_UrlRequestParams_upload_data_provider_set"))(params, provider);
    }
    return ((int (*)(void *, void *, const char *, void *, void *, void *))
        GetProcAddress(original, "Cronet_UrlRequest_InitWithParams"))(request, engine, url, params, callback, executor);
}
static void response(void *callback, void *request, void *info, void *buffer, unsigned long long count) {
    load();
    if (request == organize_request) {
        if (!status_sent) {
            int status = ((int (*)(void *))GetProcAddress(original, "Cronet_UrlResponseInfo_http_status_code_get"))(info);
            char line[64]; wsprintfA(line, "DOUBAO_STATUS %d\n", status); emit(line); status_sent = 1;
        }
        if (count > 1048576) ExitProcess(95);
        unsigned char *data = ((void *(*)(void *))GetProcAddress(original, "Cronet_Buffer_GetData"))(buffer);
        static const char hex[] = "0123456789abcdef";
        char line[2200];
        for (unsigned long long pos = 0; pos < count;) {
            unsigned k = 11;
            for (unsigned i = 0; i < 11; i++) line[i] = "DOUBAO_SSE "[i];
            while (pos < count && k < 2100) {
                line[k++] = hex[data[pos] >> 4]; line[k++] = hex[data[pos] & 15]; pos++;
            }
            line[k++] = '\n'; line[k] = 0; emit(line);
        }
    }
    // Keep reading until the HTTP stream finishes, even when the diagnostic
    // client's business parser rejects an empty no_rewrite completed event.
    // Python validates the captured SSE independently. Feed the diagnostic parser
    // a nonempty whitespace heartbeat; it still owns buffer recycling and the
    // next Cronet read, without interpreting/cancelling the real SSE events.
    if (request == organize_request && count) {
        char *data = ((void *(*)(void *))GetProcAddress(original, "Cronet_Buffer_GetData"))(buffer);
        data[0] = '\n';
        count = 1;
    }
    read_original(callback, request, info, buffer, count);
}
__declspec(dllexport) void *Cronet_UrlRequestCallback_CreateWith(void *a, void *b, void *c, void *d, void *e, void *f) {
    load(); read_original = c;
    return ((void *(*)(void *, void *, void *, void *, void *, void *))
        GetProcAddress(original, "Cronet_UrlRequestCallback_CreateWith"))(a, b, response, d, e, f);
}
static long long length(void *provider) {
    if (!body_ready) {
        emit("DOUBAO_READY\n");
        DWORD n;
        while (body_length < 262144) {
            if (!ReadFile(GetStdHandle(STD_INPUT_HANDLE), body + body_length, 1, &n, 0) || !n) ExitProcess(96);
            if (body[body_length] == '\n') break;
            body_length++;
        }
        if (body_length == 262144) ExitProcess(97);
        body_ready = 1;
    }
    return body_length;
}
static void read_body(void *provider, void *sink, void *buffer) {
    void *data = ((void *(*)(void *))GetProcAddress(original, "Cronet_Buffer_GetData"))(buffer);
    unsigned long long capacity = ((unsigned long long (*)(void *))GetProcAddress(original, "Cronet_Buffer_GetSize"))(buffer);
    unsigned count = body_length - body_offset;
    if (count > capacity) count = (unsigned)capacity;
    for (unsigned i = 0; i < count; i++) ((char *)data)[i] = body[body_offset + i];
    body_offset += count;
    ((void (*)(void *, unsigned long long, int))GetProcAddress(original, "Cronet_UploadDataSink_OnReadSucceeded"))(sink, count, 0);
}
static void rewind_body(void *provider, void *sink) {
    body_offset = 0;
    ((void (*)(void *))GetProcAddress(original, "Cronet_UploadDataSink_OnRewindSucceeded"))(sink);
}
static void close_body(void *provider) { }
BOOL WINAPI DllMainCRTStartup(HINSTANCE instance, DWORD reason, LPVOID reserved) { return TRUE; }
