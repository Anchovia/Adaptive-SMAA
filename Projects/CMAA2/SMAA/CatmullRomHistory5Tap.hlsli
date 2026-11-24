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

#ifndef CATMULL_ROM_HISTORY_5_TAP
#define CATMULL_ROM_HISTORY_5_TAP
float3 SampleHistoryCatmullRom5Tap(Texture2D<float4> tex, SamplerState linearSampler,
                                  float2 uv, float2 texSize) {
    float2 position = uv * texSize;
    float2 base = floor(position - 0.5) + 0.5;
    float2 f = position - base;
    float2 w0 = f * (-0.5 + f * (1.0 - 0.5 * f));
    float2 w1 = 1.0 + f * f * (-2.5 + 1.5 * f);
    float2 w2 = f * (0.5 + f * (2.0 - 1.5 * f));
    float2 w3 = f * f * (-0.5 + 0.5 * f);
    float2 w12 = w1 + w2;
    float2 p0 = (base - 1.0) / texSize;
    float2 p12 = (base + w2 / w12) / texSize;
    float2 p3 = (base + 2.0) / texSize;
    float wt = w12.x * w0.y, wl = w0.x * w12.y;
    float wc = w12.x * w12.y, wr = w3.x * w12.y, wb = w12.x * w3.y;
    float3 value = tex.SampleLevel(linearSampler, float2(p12.x, p0.y), 0).rgb * wt;
    value += tex.SampleLevel(linearSampler, float2(p0.x, p12.y), 0).rgb * wl;
    value += tex.SampleLevel(linearSampler, p12, 0).rgb * wc;
    value += tex.SampleLevel(linearSampler, float2(p3.x, p12.y), 0).rgb * wr;
    value += tex.SampleLevel(linearSampler, float2(p12.x, p3.y), 0).rgb * wb;
    return value / (wt + wl + wc + wr + wb);
}
#endif
