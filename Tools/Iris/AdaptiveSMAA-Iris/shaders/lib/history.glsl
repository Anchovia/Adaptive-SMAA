// GLSL port of Projects/CMAA2/SMAA/CatmullRomHistory5Tap.hlsli. Each of the five bilinear taps is
// filtered in linear space (BilinearLinear), as the demo's linear sampler does on its sRGB history view.
//
// Catmull-Rom weights based on MJP's public Tex2DCatmullRom.hlsl.
// https://gist.github.com/TheRealMJP/c83b8c0f46b63f3a88a5986f4fa982b1
// Five-tap approximation: omit four corner taps, then normalize retained weights.
// Normalization is explicit to preserve constant colors. This is not exact 16-tap
// Catmull-Rom, nor a verbatim port of the recovered Intel implementation.
// MIT License
// Copyright (c) 2019 MJP
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

vec3 SampleHistoryCatmullRom5Tap(sampler2D tex, vec2 uv, vec2 texSize) {
    vec2 position = uv * texSize;
    vec2 base = floor(position - 0.5) + 0.5;
    vec2 f = position - base;
    vec2 w0 = f * (-0.5 + f * (1.0 - 0.5 * f));
    vec2 w1 = 1.0 + f * f * (-2.5 + 1.5 * f);
    vec2 w2 = f * (0.5 + f * (2.0 - 1.5 * f));
    vec2 w3 = f * f * (-0.5 + 0.5 * f);
    vec2 w12 = w1 + w2;
    vec2 p0 = (base - 1.0) / texSize;
    vec2 p12 = (base + w2 / w12) / texSize;
    vec2 p3 = (base + 2.0) / texSize;
    float wt = w12.x * w0.y, wl = w0.x * w12.y;
    float wc = w12.x * w12.y, wr = w3.x * w12.y, wb = w12.x * w3.y;
    vec3 value = BilinearLinear(tex, vec2(p12.x, p0.y)) * wt;
    value += BilinearLinear(tex, vec2(p0.x, p12.y)) * wl;
    value += BilinearLinear(tex, p12) * wc;
    value += BilinearLinear(tex, vec2(p3.x, p12.y)) * wr;
    value += BilinearLinear(tex, vec2(p12.x, p3.y)) * wb;
    return value / (wt + wl + wc + wr + wb);
}
