//--------------------------------------------------------------------------------------
// Copyright 2017 Intel Corporation
// All Rights Reserved
//
// Permission is granted to use, copy, distribute and prepare derivative works of this
// software for any purpose and without fee, provided, that the above copyright notice
// and this statement appear in all copies.  Intel makes no representations about the
// suitability of this software for any purpose.  THIS SOFTWARE IS PROVIDED "AS IS."
// INTEL SPECIFICALLY DISCLAIMS ALL WARRANTIES, EXPRESS OR IMPLIED, AND ALL LIABILITY,
// INCLUDING CONSEQUENTIAL AND OTHER INDIRECT DAMAGES, FOR THE USE OF THIS SOFTWARE,
// INCLUDING LIABILITY FOR INFRINGEMENT OF ANY PROPRIETARY RIGHTS, AND INCLUDING THE
// WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.  Intel does not
// assume any responsibility for any errors which may appear in this software nor any
// responsibility to update it.
//--------------------------------------------------------------------------------------
// Adapted from recovered Util.hlsl SHA256 dd4e9f4655704b0b18a910173dd84bb415e72e1cbfad87322800ff525484b17b.
// Only numerical change: non-negative variance guard before sqrt in ClipColor.
///////////////////////////////////////
//
// Utility function for HLSL shader
//
///////////////////////////////////////
#ifndef __UTIL_EXT_H__
#define __UTIL_EXT_H_
///////////////////////////////////////////////////////////////////////////////////
//RGB to YCoCg conversion
float3 RGB2YCoCg(float3 RGB)
{
    float3 o;
    o.x = 0.25*RGB.r + 0.5*RGB.g + 0.25*RGB.b;
    o.y = 0.5*RGB.r - 0.5*RGB.b;
    o.z = -0.25*RGB.r + 0.5*RGB.g - 0.25*RGB.b;
    return o;
}

float3 YCoCg2RGB(float3 YCoCg)
{
    float3 o;
    o.r = YCoCg.x + YCoCg.y - YCoCg.z;
    o.g = YCoCg.x + YCoCg.z;
    o.b = YCoCg.x - YCoCg.y - YCoCg.z;
    return o;
}
///////////////////////////////////////////////////////////////////////////////////
float4 R8G8B8A8_UNORM_to_FLOAT4_FF(uint packedInput)
{
    float4 unpackedOutput;
    unpackedOutput.x = (float)(packedInput & 0x000000ff) / 255;
    unpackedOutput.y = (float)(((packedInput >> 8) & 0x000000ff)) / 255;
    unpackedOutput.z = (float)(((packedInput >> 16) & 0x000000ff)) / 255;
    unpackedOutput.w = (float)(packedInput >> 24) / 255;
    return unpackedOutput;
}
uint FLOAT4_FF_to_R8G8B8A8_UNORM(float4 unpackedInput)
{
    uint packedOutput;
    packedOutput = ((uint(saturate(unpackedInput.x) * 255 + 0.5)) |
        (uint(saturate(unpackedInput.y) * 255 + 0.5) << 8) |
        (uint(saturate(unpackedInput.z) * 255 + 0.5) << 16) |
        (uint(saturate(unpackedInput.w) * 255 + 0.5) << 24));
    return packedOutput;
}
float4 B8G8R8A8_UNORM_to_FLOAT4_FF(uint packedInput)
{
    float4 unpackedOutput;
    unpackedOutput.z = (float)(packedInput & 0x000000ff) / 255;
    unpackedOutput.y = (float)(((packedInput >> 8) & 0x000000ff)) / 255;
    unpackedOutput.x = (float)(((packedInput >> 16) & 0x000000ff)) / 255;
    unpackedOutput.w = (float)(packedInput >> 24) / 255;
    return unpackedOutput;
}
uint FLOAT4_FF_to_B8G8R8A8_UNORM(float4 unpackedInput)
{
    uint packedOutput;
    packedOutput = ((uint(saturate(unpackedInput.z) * 255 + 0.5)) |
        (uint(saturate(unpackedInput.y) * 255 + 0.5) << 8) |
        (uint(saturate(unpackedInput.x) * 255 + 0.5) << 16) |
        (uint(saturate(unpackedInput.w) * 255 + 0.5) << 24));
    return packedOutput;
}
float3 R11G11B10_UNORM_to_FLOAT3_FF(uint packedInput)
{
    float3 unpackedOutput;
    unpackedOutput.x = (float)((packedInput) & 0x000007ff) / 2047.0;
    unpackedOutput.y = (float)((packedInput >> 11) & 0x000007ff) / 2047.0;
    unpackedOutput.z = (float)((packedInput >> 22) & 0x000003ff) / 1023.0;
    return unpackedOutput;
}
// 'unpackedInput' is float3 and not lpfloat3 on purpose as half float lacks precision for below!
uint FLOAT3_FF_to_R11G11B10_UNORM(float3 unpackedInput)
{
    uint packedOutput;
    packedOutput = ((uint(saturate(unpackedInput.x) * 2047 + 0.5)) |
        (uint(saturate(unpackedInput.y) * 2047 + 0.5) << 11) |
        (uint(saturate(unpackedInput.z) * 1023 + 0.5) << 22));
    return packedOutput;
}
///////////////////////////////////////////////////////////////////////////////////
float4 UnpackColorFF(uint packedColor)
{
#ifdef CMAA2_COLOR_PACK_FORMAT_R11G11B10_UNORM
    return float4(R11G11B10_UNORM_to_FLOAT3_FF(packedColor),0);
#elif defined( CMAA2_COLOR_PACK_FORMAT_R8G8B8_UNORM )
    return R8G8B8A8_UNORM_to_FLOAT4_FF(packedColor);
#elif defined( CMAA2_COLOR_PACK_FORMAT_B8G8R8_UNORM )
    return B8G8R8A8_UNORM_to_FLOAT4_FF(packedColor);
#else
#error CMAA color packing format not defined!
    return 0;
#endif
}
uint PackColorFF(float4 color)
{
#ifdef CMAA2_COLOR_PACK_FORMAT_R11G11B10_UNORM
    return FLOAT3_FF_to_R11G11B10_UNORM(float3(color.rgb));
#elif defined( CMAA2_COLOR_PACK_FORMAT_R8G8B8_UNORM )
    return FLOAT4_FF_to_R8G8B8A8_UNORM(lpfloat4(color));
#elif defined(CMAA2_COLOR_PACK_FORMAT_B8G8R8_UNORM)
    return FLOAT4_FF_to_B8G8R8A8_UNORM(lpfloat4(color));
#else
#error CMAA color packing format not defined!
    return 0;
#endif
}
///////////////////////////////////////////////////////////////////////////////////
//Bicubic Filtering
float3 BicubicTextureSample(Texture2D<float4> Texture, SamplerState Sampler, float2 PP, float WIDTH, float HEIGHT)
{
    float3 color;

    float2 pixel = float2(PP.x * (float)WIDTH + 0.5f, PP.y * (float)HEIGHT + 0.5f);

    float2 c_onePixel = float2(1.f / (float)WIDTH, 1.f / (float)HEIGHT);
    float2 c_twoPixels = float2(2.f / (float)WIDTH, 2.f / (float)HEIGHT);

    float2 Frac;
    Frac.x = frac(pixel.x);
    Frac.y = frac(pixel.y);

    float2 P = floor(pixel) - float2(0.5f, 0.5f);
    P = P / float2(WIDTH, HEIGHT);

    // 5-tap bicubic sampling (for Hermite/Carmull-Rom filter) -- (approximate from original 9-tap bilinear fetching)
    // 4-tap is possible but only for B-spline filter, whose quality is too low for TAA history resampling (more blur than single bilinear)
    float2 t = Frac;
    float2 t2 = t*t;
    float2 t3 = t2*t;
    float s = 0.5;	// s is potentially adjustable
    float2 w0 = -s*t3 + 2 * s*t2 - s*t;
    float2 w1 = (2 - s)*t3 + (s - 3)*t2 + 1;
    float2 w2 = (s - 2)*t3 + (3 - 2 * s)*t2 + s*t;
    float2 w3 = s*t3 - s*t2;

    float2 s0 = w1 + w2;
    float2 f0 = w2 / (w1 + w2);
    float2 m0 = P + (f0) / float2(WIDTH, HEIGHT);;

    float2 tc0 = P + float2(-c_onePixel.x, -c_onePixel.y);
    float2 tc3 = P + float2(c_twoPixels.x, c_twoPixels.y);

    float3 A = Texture.SampleLevel(Sampler, float2(m0.x, tc0.y), 0).rgb;
    float3 B = Texture.SampleLevel(Sampler, float2(tc0.x, m0.y), 0).rgb;
    float3 C = Texture.SampleLevel(Sampler, float2(m0.x, m0.y), 0).rgb;
    float3 D = Texture.SampleLevel(Sampler, float2(tc3.x, m0.y), 0).rgb;
    float3 E = Texture.SampleLevel(Sampler, float2(m0.x, tc3.y), 0).rgb;

    color = (0.5 * (A + B) * w0.x + A * s0.x + 0.5 * (A + B) * w3.x) * w0.y +
        (B * w0.x + C * s0.x + D * w3.x) * s0.y +
        (0.5 * (B + E) * w0.x + E * s0.x + 0.5 * (D + E) * w3.x) * w3.y;

    return color;
}
////////////////////////////////////////////////////////////////////////////////////
//Color Clipping
float3 ClipColor(float3 historyColor, float3 currentColor, Texture2D texIn, float2 texCoord, SamplerState ss, float sharpenAmount, float WIDTH, float HEIGHT)
{
    float3 newHistoryColor = historyColor;

    // Variance clip
    const float2 k  = float2(1.f / (float)WIDTH, 1.f / (float)HEIGHT);
    float3 m        = float3(0, 0, 0);
    float3 mm       = float3(0, 0, 0);
    float N         = 0;

    // 0 1 2
    // 3
    float3 t0 = texIn.SampleLevel(ss, texCoord + float2(-k.x, -k.y), 0).rgb;
    float3 t1 = texIn.SampleLevel(ss, texCoord + float2(0.f, -k.y), 0).rgb;
    float3 t2 = texIn.SampleLevel(ss, texCoord + float2(k.x, -k.y), 0).rgb;
    float3 t3 = texIn.SampleLevel(ss, texCoord + float2(-k.x, 0.f), 0).rgb;
    //     0
    // 1 2 3
    float3 b0 = texIn.SampleLevel(ss, texCoord + float2(k.x, 0.f), 0).rgb;
    float3 b1 = texIn.SampleLevel(ss, texCoord + float2(-k.x, k.y), 0).rgb;
    float3 b2 = texIn.SampleLevel(ss, texCoord + float2(0.f, k.y), 0).rgb;
    float3 b3 = texIn.SampleLevel(ss, texCoord + float2(k.x, k.y), 0).rgb;

    t0 = RGB2YCoCg(t0);
    t1 = RGB2YCoCg(t1);
    t2 = RGB2YCoCg(t2);
    t3 = RGB2YCoCg(t3);
    b0 = RGB2YCoCg(b0);
    b1 = RGB2YCoCg(b1);
    b2 = RGB2YCoCg(b2);
    b3 = RGB2YCoCg(b3);
    currentColor = RGB2YCoCg(currentColor);

    float3 corners = (t0 + t2 + b1 + b3) * 0.25f;
    currentColor += (currentColor - corners) * sharpenAmount;
    currentColor = max(0, currentColor);

    // do variance clipping
    m = t0 + t1 + t2 + t3 + b0 + b1 + b2 + b3 + currentColor;
    mm = t0*t0 + t1*t1 + t2*t2 + t3*t3 + b0*b0 + b1*b1 + b2*b2 + b3*b3 + currentColor*currentColor;
    N = 9.f;

    float3 mu = m / N;
    float3 sigma = sqrt(max(float3(0,0,0), mm / N - mu*mu));
    float gamma = 1.0f;

    float3 minimum = mu - gamma * sigma;
    float3 maximum = mu + gamma * sigma;

    minimum = YCoCg2RGB(minimum);
    maximum = YCoCg2RGB(maximum);
    currentColor = YCoCg2RGB(currentColor);

    newHistoryColor = clamp(historyColor, minimum, maximum);


    return newHistoryColor;
}
////////////////////////////////////////////////////////////////////////////////////
//For TAA: Calculate screen space velocity based on depth
float2 GetVelocity(float depth, float2 texCoord, float4x4 prevView, float4x4 prevProj, float4x4 currProjInv, float4x4 currViewInv)
{
    // For debug, compute view space depth and render as color
    //float depthV = depthHackMul / (depthHackAdd - depth);

    // viewport position at this pixel in the range -1 to 1
    float4 viewPos = float4(texCoord.x * 2 - 1, (1 - texCoord.y) * 2 - 1, depth, 1);

    float4 d;
    d = mul(viewPos, currProjInv);
    d = mul(d, currViewInv);

    // Divide by w to get the world position
    float4 worldPos = d / d.w;
    // Current viewport position is viewPos
    // Use the world position, and transform by the previous view-projection matrix
    float4 prevPos;
    prevPos = mul(worldPos, prevView);
    prevPos = mul(prevPos, prevProj);

    // Convert to nonhomogeneous points [-1, 1] by dividing by w
    prevPos /= prevPos.w;

    // For debug, compute view space depth and
    //float depthV1 = depthHackMul / (depthHackAdd - prevPos.z);

    // Use this frame's position and last frame's to compute the pixel velocity
    float2 velocity = (viewPos - prevPos).xy * float2(0.5f, -0.5f);
    return velocity;
}
#endif
