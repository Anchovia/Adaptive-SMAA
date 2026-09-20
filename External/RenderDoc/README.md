# RenderDoc application capture API

`renderdoc_app.h` is copied unchanged from installed RenderDoc 1.44
(`050034a0faa37d606ce1b8cf677dba4bc36984ea`). The header contains its license.

Upstream: https://github.com/baldurk/renderdoc/blob/v1.44/renderdoc/api/app/renderdoc_app.h

SHA-256: `B7005E7DC34C3635046868BBD76D81B9B055AEDE0F56DAA0BD39FEDEE0639FFB`.
Only the opt-in `-smaaTemporalCounterCapture` diagnostic queries API 1.6.0 from
an already injected RenderDoc DLL. No RenderDoc runtime is linked or bundled.
NVIDIA profiling DLLs and raw captures remain local, outside Git.
