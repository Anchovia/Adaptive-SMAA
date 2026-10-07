// Literal five-fetch coefficient/coordinate expression from recovered Intel
// Util/Util.hlsl BicubicTextureSample. The asymmetric (A+B) term is retained.
// RGB domain and clamp sampler remain case14's; source UNORM/border is NOT ported.
float3 SourceSampleHistory(Texture2D<float4> tex,SamplerState ss,float2 uv,float2 size) {
    float2 pixel=uv*size+0.5, t=frac(pixel), P=(floor(pixel)-0.5)/size;
    float2 t2=t*t,t3=t2*t;
    float2 w0=-0.5*t3+t2-0.5*t;
    float2 w1=1.5*t3-2.5*t2+1;
    float2 w2=-1.5*t3+2*t2+0.5*t;
    float2 w3=0.5*t3-0.5*t2;
    float2 s0=w1+w2,m0=P+(w2/s0)/size;
    float2 tc0=P-1.0/size,tc3=P+2.0/size;
    float3 A=tex.SampleLevel(ss,float2(m0.x,tc0.y),0).rgb;
    float3 B=tex.SampleLevel(ss,float2(tc0.x,m0.y),0).rgb;
    float3 C=tex.SampleLevel(ss,m0,0).rgb;
    float3 D=tex.SampleLevel(ss,float2(tc3.x,m0.y),0).rgb;
    float3 E=tex.SampleLevel(ss,float2(m0.x,tc3.y),0).rgb;
    return (0.5*(A+B)*w0.x+A*s0.x+0.5*(A+B)*w3.x)*w0.y+
        (B*w0.x+C*s0.x+D*w3.x)*s0.y+
        (0.5*(B+E)*w0.x+E*s0.x+0.5*(D+E)*w3.x)*w3.y;
}
