// Recovered Util.hlsl ClipColor: 3x3 moments and gamma=1.
// Safety adaptation: retain signed Co/Cg, clamp variance >=0, and clamp HISTORY
// in the same YCoCg coordinates as its bounds. No sharpening in this ablation.
float3 SourceRGBToYCoCg(float3 c) {return float3(dot(c,float3(.25,.5,.25)),(c.r-c.b)*.5,(-c.r+2*c.g-c.b)*.25);}
float3 SourceYCoCgToRGB(float3 c) {return float3(c.x+c.y-c.z,c.x+c.z,c.x-c.y-c.z);}
float3 SourceClipHistory(Texture2D<float4> tex,SamplerState ss,float2 uv,float2 size,float3 current,float3 history) {
    float3 m=SourceRGBToYCoCg(current),mm=m*m;
    [unroll] for(int y=-1;y<=1;++y) [unroll] for(int x=-1;x<=1;++x) {
        if(x!=0 || y!=0) {float3 c=SourceRGBToYCoCg(tex.SampleLevel(ss,uv+float2(x,y)/size,0).rgb);m+=c;mm+=c*c;}
    }
    float3 mu=m/9.0;
    float3 sigma=sqrt(max(mm/9.0-mu*mu,0.0));
    return max(SourceYCoCgToRGB(clamp(SourceRGBToYCoCg(history),mu-sigma,mu+sigma)),0.0);
}
