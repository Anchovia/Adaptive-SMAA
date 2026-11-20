// Minimal Iris composite-pipeline emulator for checking the shader pack without Minecraft.
// It compiles and links each expanded program pair with the installed OpenGL driver, then runs
// composite, composite1..4 and final on test frames:
//  - colortexN: two textures per buffer; a pass reads the latest content and writes the other texture,
//    which becomes the latest (Iris flips after each pass and copies alt to main at frame end).
//    Formats and Clear=false flags are parsed from the expanded composite.fsh.
//  - depthtex0/1/2: R32F textures from the scenario; custom textures smaaAreaTex (linear, clamp) and
//    smaaSearchTex (nearest, clamp) uploaded with image row 0 first, like Minecraft's NativeImage.
//  - the frame's colour is uploaded into colortex0 before composite, as Iris's gbuffers would draw it.
// usage: iris_gl_harness <expanded program dir> <scenario file> <output dir>
#include <windows.h>
#include <GL/gl.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <regex>
#include <sstream>
#include <string>
#include <vector>

typedef char GLchar;
#define GL_FRAGMENT_SHADER 0x8B30
#define GL_VERTEX_SHADER 0x8B31
#define GL_COMPILE_STATUS 0x8B81
#define GL_LINK_STATUS 0x8B82
#define GL_INFO_LOG_LENGTH 0x8B84
#define GL_ACTIVE_UNIFORMS 0x8B86
#define GL_FRAMEBUFFER 0x8D40
#define GL_COLOR_ATTACHMENT0 0x8CE0
#define GL_FRAMEBUFFER_COMPLETE 0x8CD5
#define GL_TEXTURE0 0x84C0
#define GL_CLAMP_TO_EDGE 0x812F
#define GL_R8 0x8229
#define GL_RG 0x8227
#define GL_RG16F 0x822F
#define GL_R32F 0x822E
#define GL_RGBA16F 0x881A
#define GL_HALF_FLOAT 0x140B
#define GL_SAMPLER_2D 0x8B5E

#define GL_FUNCS(X) \
    X(GLuint, glCreateShader, (GLenum)) \
    X(void, glShaderSource, (GLuint, GLsizei, const GLchar *const *, const GLint *)) \
    X(void, glCompileShader, (GLuint)) \
    X(void, glGetShaderiv, (GLuint, GLenum, GLint *)) \
    X(void, glGetShaderInfoLog, (GLuint, GLsizei, GLsizei *, GLchar *)) \
    X(GLuint, glCreateProgram, (void)) \
    X(void, glAttachShader, (GLuint, GLuint)) \
    X(void, glLinkProgram, (GLuint)) \
    X(void, glGetProgramiv, (GLuint, GLenum, GLint *)) \
    X(void, glGetProgramInfoLog, (GLuint, GLsizei, GLsizei *, GLchar *)) \
    X(void, glUseProgram, (GLuint)) \
    X(GLint, glGetUniformLocation, (GLuint, const GLchar *)) \
    X(void, glGetActiveUniform, (GLuint, GLuint, GLsizei, GLsizei *, GLint *, GLenum *, GLchar *)) \
    X(void, glUniform1i, (GLint, GLint)) \
    X(void, glUniform1f, (GLint, GLfloat)) \
    X(void, glUniform3i, (GLint, GLint, GLint, GLint)) \
    X(void, glUniform3f, (GLint, GLfloat, GLfloat, GLfloat)) \
    X(void, glUniformMatrix4fv, (GLint, GLsizei, GLboolean, const GLfloat *)) \
    X(void, glGenFramebuffers, (GLsizei, GLuint *)) \
    X(void, glBindFramebuffer, (GLenum, GLuint)) \
    X(void, glFramebufferTexture2D, (GLenum, GLenum, GLenum, GLuint, GLint)) \
    X(GLenum, glCheckFramebufferStatus, (GLenum)) \
    X(void, glDrawBuffers, (GLsizei, const GLenum *)) \
    X(void, glActiveTexture, (GLenum)) \
    X(void, glMultiTexCoord2f, (GLenum, GLfloat, GLfloat))

#define DECLARE(ret, name, args) typedef ret(APIENTRY *PFN_##name) args; static PFN_##name name;
GL_FUNCS(DECLARE)

static std::string readText(const std::string &path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) { fprintf(stderr, "cannot read %s\n", path.c_str()); exit(2); }
    std::stringstream s; s << f.rdbuf(); return s.str();
}
static std::vector<unsigned char> readBytes(const std::string &path, size_t expected) {
    std::ifstream f(path, std::ios::binary);
    std::vector<unsigned char> data((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    if (data.size() != expected) { fprintf(stderr, "%s: %zu bytes, expected %zu\n", path.c_str(), data.size(), expected); exit(2); }
    return data;
}
static void writeBytes(const std::string &path, const void *data, size_t size) {
    std::ofstream f(path, std::ios::binary); f.write((const char *)data, size);
}

static FILE *g_log;
static GLuint compile(GLenum stage, const std::string &source, const std::string &label, bool &ok) {
    GLuint s = glCreateShader(stage);
    const char *text = source.c_str();
    glShaderSource(s, 1, &text, nullptr);
    glCompileShader(s);
    GLint status = 0, length = 0;
    glGetShaderiv(s, GL_COMPILE_STATUS, &status);
    glGetShaderiv(s, GL_INFO_LOG_LENGTH, &length);
    if (length > 1) { std::string log(length, '\0'); glGetShaderInfoLog(s, length, nullptr, &log[0]); fprintf(g_log, "[%s compile]\n%s\n", label.c_str(), log.c_str()); }
    if (!status) ok = false;
    return s;
}

struct Buffer { GLenum internal, format, type; bool keep; GLuint tex[2]; int latest; };
struct Program { std::string name; GLuint id; std::vector<int> targets; };

static GLuint makeTexture(int w, int h, GLenum internal, GLenum format, GLenum type, GLenum filter, const void *data) {
    GLuint t; glGenTextures(1, &t); glBindTexture(GL_TEXTURE_2D, t);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, filter);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, filter);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    glTexImage2D(GL_TEXTURE_2D, 0, internal, w, h, 0, format, type, data);
    return t;
}

int main(int argc, char **argv) {
    if (argc != 4) { fprintf(stderr, "usage: iris_gl_harness <program dir> <scenario> <out dir>\n"); return 2; }
    std::string dir = argv[1], out = argv[3];
    g_log = fopen((out + "/gl_log.txt").c_str(), "w");

    HINSTANCE inst = GetModuleHandle(nullptr);
    WNDCLASSA wc = {}; wc.lpfnWndProc = DefWindowProcA; wc.hInstance = inst; wc.lpszClassName = "IrisHarness";
    RegisterClassA(&wc);
    HWND hwnd = CreateWindowA("IrisHarness", "IrisHarness", WS_OVERLAPPEDWINDOW, 0, 0, 64, 64, nullptr, nullptr, inst, nullptr);
    HDC dc = GetDC(hwnd);
    PIXELFORMATDESCRIPTOR pfd = {}; pfd.nSize = sizeof(pfd); pfd.nVersion = 1;
    pfd.dwFlags = PFD_DRAW_TO_WINDOW | PFD_SUPPORT_OPENGL | PFD_DOUBLEBUFFER; pfd.iPixelType = PFD_TYPE_RGBA; pfd.cColorBits = 32;
    SetPixelFormat(dc, ChoosePixelFormat(dc, &pfd), &pfd);
    HGLRC rc = wglCreateContext(dc);
    wglMakeCurrent(dc, rc);
#define LOAD(ret, name, args) name = (PFN_##name)wglGetProcAddress(#name); if (!name) { fprintf(stderr, "missing %s\n", #name); return 3; }
    GL_FUNCS(LOAD)
    fprintf(g_log, "GL_VENDOR %s\nGL_RENDERER %s\nGL_VERSION %s\n", glGetString(GL_VENDOR), glGetString(GL_RENDERER), glGetString(GL_VERSION));

    // Scenario: "size W H", "frames N", then per frame "frame color depth0 depth1 depth2 dump" followed by
    // uniform lines "mat name 16 floats" / "ivec3 name x y z" / "vec3 name x y z" / "int name v".
    std::ifstream scenario(argv[2]);
    int W = 0, H = 0, frames = 0;
    std::string word; scenario >> word >> W >> H >> word >> frames;

    const char *names[] = {"composite", "composite1", "composite2", "composite3", "composite4", "final"};
    std::vector<Program> programs;
    bool allOk = true;
    for (const char *n : names) {
        std::string vs = readText(dir + "/" + n + ".vsh"), fs = readText(dir + "/" + n + ".fsh");
        bool ok = true;
        GLuint v = compile(GL_VERTEX_SHADER, vs, std::string(n) + ".vsh", ok), f = compile(GL_FRAGMENT_SHADER, fs, std::string(n) + ".fsh", ok);
        GLuint p = glCreateProgram(); glAttachShader(p, v); glAttachShader(p, f); glLinkProgram(p);
        GLint status = 0, length = 0; glGetProgramiv(p, GL_LINK_STATUS, &status); glGetProgramiv(p, GL_INFO_LOG_LENGTH, &length);
        if (length > 1) { std::string log(length, '\0'); glGetProgramInfoLog(p, length, nullptr, &log[0]); fprintf(g_log, "[%s link]\n%s\n", n, log.c_str()); }
        if (!status) ok = false;
        fprintf(g_log, "program %s %s\n", n, ok ? "OK" : "FAIL");
        allOk = allOk && ok;
        Program prog{n, p, {}};
        std::smatch m;
        if (std::regex_search(fs, m, std::regex("/\\* RENDERTARGETS: ([0-9,]+) \\*/"))) {
            std::stringstream list(m[1].str()); std::string item;
            while (std::getline(list, item, ',')) prog.targets.push_back(atoi(item.c_str()));
        }
        programs.push_back(prog);
    }
    if (!allOk) { fprintf(g_log, "RESULT compile FAIL\n"); fclose(g_log); return 1; }

    // Buffers: colortex0 RGBA8 (vanilla), others from the format comment and Clear constants.
    std::string pass0 = readText(dir + "/composite.fsh");
    std::map<std::string, std::vector<GLenum>> formats = {
        {"R8", {GL_R8, GL_RED, GL_UNSIGNED_BYTE}}, {"RGBA8", {GL_RGBA8, GL_RGBA, GL_UNSIGNED_BYTE}},
        {"RG16F", {GL_RG16F, GL_RG, GL_HALF_FLOAT}}, {"RGBA16F", {GL_RGBA16F, GL_RGBA, GL_HALF_FLOAT}}};
    std::map<int, Buffer> buffers;
    buffers[0] = {GL_RGBA8, GL_RGBA, GL_UNSIGNED_BYTE, false, {0, 0}, 0};
    std::smatch m; std::string rest = pass0;
    while (std::regex_search(rest, m, std::regex("const int colortex([0-9]+)Format = ([A-Z0-9]+);"))) {
        auto f = formats.at(m[2].str()); buffers[atoi(m[1].str().c_str())] = {f[0], f[1], f[2], false, {0, 0}, 0}; rest = m.suffix();
    }
    rest = pass0;
    while (std::regex_search(rest, m, std::regex("const bool colortex([0-9]+)Clear = false;"))) { buffers.at(atoi(m[1].str().c_str())).keep = true; rest = m.suffix(); }
    std::vector<unsigned char> zero(size_t(W) * H * 16, 0);
    for (auto &b : buffers) for (int i = 0; i < 2; ++i) b.second.tex[i] = makeTexture(W, H, b.second.internal, b.second.format, b.second.type, GL_LINEAR, zero.data());
    for (auto &b : buffers) fprintf(g_log, "colortex%d internal 0x%x keep %d\n", b.first, b.second.internal, b.second.keep);

    std::vector<unsigned char> area = readBytes(dir + "/AreaTex.rgba", 160 * 560 * 4), search = readBytes(dir + "/SearchTex.rgba", 64 * 16 * 4);
    GLuint areaTex = makeTexture(160, 560, GL_RGBA8, GL_RGBA, GL_UNSIGNED_BYTE, GL_LINEAR, area.data());
    GLuint searchTex = makeTexture(64, 16, GL_RGBA8, GL_RGBA, GL_UNSIGNED_BYTE, GL_NEAREST, search.data());
    GLuint depthTex[3];
    for (int i = 0; i < 3; ++i) depthTex[i] = makeTexture(W, H, GL_R32F, GL_RED, GL_FLOAT, GL_NEAREST, zero.data());
    GLuint screen = makeTexture(W, H, GL_RGBA8, GL_RGBA, GL_UNSIGNED_BYTE, GL_NEAREST, zero.data());
    GLuint fbo; glGenFramebuffers(1, &fbo);

    for (int frame = 0; frame < frames; ++frame) {
        std::string colorPath, depthPath[3], dump;
        scenario >> word >> colorPath >> depthPath[0] >> depthPath[1] >> depthPath[2] >> dump;
        std::map<std::string, std::vector<float>> mats, vec3s; std::map<std::string, std::vector<int>> ivec3s; std::map<std::string, int> ints;
        while (scenario >> word && word != "end") {
            std::string name; scenario >> name;
            if (word == "mat") { std::vector<float> v(16); for (float &x : v) scenario >> x; mats[name] = v; }
            else if (word == "vec3") { std::vector<float> v(3); for (float &x : v) scenario >> x; vec3s[name] = v; }
            else if (word == "ivec3") { std::vector<int> v(3); for (int &x : v) scenario >> x; ivec3s[name] = v; }
            else if (word == "int") { scenario >> ints[name]; }
        }
        std::vector<unsigned char> color = readBytes(colorPath, size_t(W) * H * 4);
        glBindTexture(GL_TEXTURE_2D, buffers[0].tex[buffers[0].latest]);
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, W, H, GL_RGBA, GL_UNSIGNED_BYTE, color.data());
        for (int i = 0; i < 3; ++i) {
            std::vector<unsigned char> depth = readBytes(depthPath[i], size_t(W) * H * 4);
            glBindTexture(GL_TEXTURE_2D, depthTex[i]);
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, W, H, GL_RED, GL_FLOAT, depth.data());
        }
        // Buffers without Clear=false start the frame cleared, as Iris clears them.
        for (auto &b : buffers) if (b.first != 0 && !b.second.keep) {
            glBindFramebuffer(GL_FRAMEBUFFER, fbo);
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, b.second.tex[b.second.latest], 0);
            GLenum db = GL_COLOR_ATTACHMENT0; glDrawBuffers(1, &db);
            glClearColor(0, 0, 0, 0); glClear(GL_COLOR_BUFFER_BIT);
        }
        for (const Program &prog : programs) {
            glBindFramebuffer(GL_FRAMEBUFFER, fbo);
            std::vector<GLenum> drawBuffers;
            bool isFinal = prog.name == "final";
            for (size_t i = 0; i < (isFinal ? 1 : prog.targets.size()); ++i) {
                GLuint target = isFinal ? screen : buffers.at(prog.targets[i]).tex[1 - buffers.at(prog.targets[i]).latest];
                glFramebufferTexture2D(GL_FRAMEBUFFER, GLenum(GL_COLOR_ATTACHMENT0 + i), GL_TEXTURE_2D, target, 0);
                drawBuffers.push_back(GLenum(GL_COLOR_ATTACHMENT0 + i));
            }
            for (size_t i = drawBuffers.size(); i < 8; ++i) glFramebufferTexture2D(GL_FRAMEBUFFER, GLenum(GL_COLOR_ATTACHMENT0 + i), GL_TEXTURE_2D, 0, 0);
            glDrawBuffers(GLsizei(drawBuffers.size()), drawBuffers.data());
            if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) { fprintf(g_log, "incomplete framebuffer in %s\n", prog.name.c_str()); return 4; }
            glUseProgram(prog.id);
            GLint count = 0; glGetProgramiv(prog.id, GL_ACTIVE_UNIFORMS, &count);
            int unit = 0;
            for (GLint u = 0; u < count; ++u) {
                char name[256]; GLsizei len; GLint size; GLenum type;
                glGetActiveUniform(prog.id, u, sizeof(name), &len, &size, &type, name);
                GLint loc = glGetUniformLocation(prog.id, name);
                std::string n = name;
                if (type == GL_SAMPLER_2D) {
                    GLuint tex = 0;
                    if (n.rfind("colortex", 0) == 0) { const Buffer &b = buffers.at(atoi(n.c_str() + 8)); tex = b.tex[b.latest]; }
                    else if (n.rfind("depthtex", 0) == 0) tex = depthTex[atoi(n.c_str() + 8)];
                    else if (n == "smaaAreaTex") tex = areaTex;
                    else if (n == "smaaSearchTex") tex = searchTex;
                    else { fprintf(g_log, "unknown sampler %s\n", name); return 5; }
                    glActiveTexture(GL_TEXTURE0 + unit); glBindTexture(GL_TEXTURE_2D, tex); glUniform1i(loc, unit++);
                } else if (n == "viewWidth") glUniform1f(loc, float(W));
                else if (n == "viewHeight") glUniform1f(loc, float(H));
                else if (mats.count(n)) glUniformMatrix4fv(loc, 1, GL_FALSE, mats[n].data());
                else if (vec3s.count(n)) glUniform3f(loc, vec3s[n][0], vec3s[n][1], vec3s[n][2]);
                else if (ivec3s.count(n)) glUniform3i(loc, ivec3s[n][0], ivec3s[n][1], ivec3s[n][2]);
                else if (ints.count(n)) glUniform1i(loc, ints[n]);
                else if (n.rfind("gl_", 0) != 0) { fprintf(g_log, "unset uniform %s in %s\n", name, prog.name.c_str()); return 6; }
            }
            glActiveTexture(GL_TEXTURE0);
            glViewport(0, 0, W, H);
            glBegin(GL_QUADS);
            glMultiTexCoord2f(GL_TEXTURE0, 0, 0); glVertex2f(-1, -1);
            glMultiTexCoord2f(GL_TEXTURE0, 1, 0); glVertex2f(1, -1);
            glMultiTexCoord2f(GL_TEXTURE0, 1, 1); glVertex2f(1, 1);
            glMultiTexCoord2f(GL_TEXTURE0, 0, 1); glVertex2f(-1, 1);
            glEnd();
            if (!isFinal) for (int t : prog.targets) buffers.at(t).latest = 1 - buffers.at(t).latest;
        }
        glFinish();
        GLenum err = glGetError();
        if (err != GL_NO_ERROR) { fprintf(g_log, "GL error 0x%x in frame %d\n", err, frame); return 7; }
        std::vector<unsigned char> pixels(size_t(W) * H * 4);
        glBindTexture(GL_TEXTURE_2D, screen);
        glGetTexImage(GL_TEXTURE_2D, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
        char path[512]; snprintf(path, sizeof(path), "%s/final_%03d.rgba", out.c_str(), frame);
        writeBytes(path, pixels.data(), pixels.size());
        if (dump == "dump") {
            for (auto &b : buffers) {
                std::vector<float> values(size_t(W) * H * 4);
                glBindTexture(GL_TEXTURE_2D, b.second.tex[b.second.latest]);
                glGetTexImage(GL_TEXTURE_2D, 0, GL_RGBA, GL_FLOAT, values.data());
                snprintf(path, sizeof(path), "%s/colortex%d_%03d.f32", out.c_str(), b.first, frame);
                writeBytes(path, values.data(), values.size() * sizeof(float));
            }
        }
    }
    fprintf(g_log, "RESULT OK frames %d\n", frames);
    fclose(g_log);
    wglMakeCurrent(nullptr, nullptr); wglDeleteContext(rc); ReleaseDC(hwnd, dc); DestroyWindow(hwnd);
    return 0;
}
