#pragma once
#include <d3d11.h>
#include "../../../External/NVAPI/nvapi.h"
#include "../../../External/NVAPI/nvShaderExtnEnums.h"

// Explicit experimental PS only. Use the official SDK and thread-local slot so
// unrelated asynchronous CreateShader calls never inherit extension state.
namespace TemporalNvWarp {
inline bool Supported(ID3D11Device* device) {
    static const NvAPI_Status initialized = NvAPI_Initialize();
    bool supported = false;
    return initialized == NVAPI_OK &&
        NvAPI_D3D11_IsNvShaderExtnOpCodeSupported(device, NV_EXTN_OP_VOTE_ANY, &supported) == NVAPI_OK && supported;
}
inline bool GroupsSupported(ID3D11Device* device) {
    bool ballot = false, lane = false;
    return Supported(device) &&
        NvAPI_D3D11_IsNvShaderExtnOpCodeSupported(device, NV_EXTN_OP_VOTE_BALLOT, &ballot) == NVAPI_OK && ballot &&
        NvAPI_D3D11_IsNvShaderExtnOpCodeSupported(device, NV_EXTN_OP_GET_LANE_ID, &lane) == NVAPI_OK && lane;
}
inline HRESULT CreatePixelShader(ID3D11Device* device, const void* bytes, SIZE_T length,
                                 ID3D11PixelShader** shader) {
    *shader = nullptr;
    if(!Supported(device)) return E_NOTIMPL;
    if(NvAPI_D3D11_SetNvShaderExtnSlotLocalThread(device, 7) != NVAPI_OK) return E_FAIL;
    const HRESULT result = device->CreatePixelShader(bytes, length, nullptr, shader);
    const NvAPI_Status reset = NvAPI_D3D11_SetNvShaderExtnSlotLocalThread(device, ~0u);
    if(reset != NVAPI_OK) {
        if(*shader) { (*shader)->Release(); *shader = nullptr; }
        return E_FAIL;
    }
    return result;
}
}
