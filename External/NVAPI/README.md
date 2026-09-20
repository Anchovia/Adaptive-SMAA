# Pinned NVIDIA NVAPI SDK subset

Unmodified upstream files from NVIDIA's official SDK repository at commit
`70d337db9186e968eab622f7e786de7e437faf3d`:
https://github.com/NVIDIA/nvapi/tree/70d337db9186e968eab622f7e786de7e437faf3d

The subset contains the HLSL extension headers, C++ declaration dependencies,
interface table and official `amd64/nvapi64.lib` SDK library. The library is an
upstream dependency, not a generated research executable. File hashes are in
`manifest.json`. Copyright/license notices are preserved in the upstream files.
The SDK repository declares the MIT license.

The experiment calls the official SDK functions directly; it does not hardcode
private driver interfaces or install/change a graphics driver. A supported NVIDIA
device is required for the opt-in warp gate. Unavailable support is reported as a
failed/unsupported experiment, not benchmarked under a silently substituted mode.

The HLSL fake UAV slot is 7 and is null-bound, as the SDK requires. Driver shader
creation uses `NvAPI_D3D11_SetNvShaderExtnSlotLocalThread` and restores the slot on
the same thread. Two small forwarding headers in the SMAA directory accommodate
the renderer's legacy include resolver without modifying the vendor files.
