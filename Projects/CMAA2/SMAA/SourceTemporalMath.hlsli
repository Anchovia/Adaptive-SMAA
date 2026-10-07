// TSCMAA TAA_Edge.hlsl squares encoded RGB, mixes, then sqrt.
// SMAA SRVs/RTVs use hardware sRGB transfer. Convert linear samples to encoded
// values and back explicitly to avoid applying gamma twice. Filter unchanged.
float3 SourceLinearToEncoded(float3 v) {
    v=saturate(v);float3 hi=1.055*pow(v,1.0/2.4)-0.055;
    return float3(v.r<=.0031308?12.92*v.r:hi.r,v.g<=.0031308?12.92*v.g:hi.g,v.b<=.0031308?12.92*v.b:hi.b);
}
float3 SourceEncodedToLinear(float3 v) {
    float3 hi=pow((v+0.055)/1.055,2.4);
    return float3(v.r<=.04045?v.r/12.92:hi.r,v.g<=.04045?v.g/12.92:hi.g,v.b<=.04045?v.b/12.92:hi.b);
}
float3 SourceBlend(float3 current,float3 previous,float weight) {
    float3 c=SourceLinearToEncoded(current),h=SourceLinearToEncoded(previous);
    return SourceEncodedToLinear(sqrt(lerp(c*c,h*h,weight)));
}
