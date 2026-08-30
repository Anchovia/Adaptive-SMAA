# Adaptive SMAA research branch map

This document describes the purpose of every published branch. Branches are
milestone snapshots in a shared history; they are not independent products.

## Prefixes

| Prefix | Purpose |
|---|---|
| `baseline/` | Frozen comparison baselines |
| `research/` | Major research implementations and current lineage |
| `experiment/` | Controlled alternatives and ablations |
| `validation/` | Correctness, provenance, quality, and performance gates |
| `tooling/` | External scenes and deterministic camera/capture infrastructure |
| `archive/` | Superseded, incomplete, or known-pre-fix historical states |
| `main` | Completed Adaptive SMAA spatial implementation |

## Recommended entry points

| Branch | Purpose |
|---|---|
| `baseline/original-smaa` | Original SMAA in the same runnable CMAA2 demo environment |
| `baseline/smaa-t2x` | Standard SMAA T2X with optional camera/depth reprojection |
| `main` | Completed contrast-guided Adaptive SMAA |
| `research/adaptive-temporal-smaa` | Original/Adaptive × Standard/edge-selective × reprojection Off/On eight-case foundation |
| `research/tscmaa-inspired-smaa-core` | SMAA first-pass integrated temporal candidate source |
| `research/et2x-pipeline-optimization` | Current recommended branch with integrated candidates, pass timing, and pipeline optimization |

## Experiments

| Branch | Purpose |
|---|---|
| `experiment/rgba8-packed` | Pack Adaptive SMAA edge/metadata into one RGBA8 target |
| `experiment/edge-selective-components` | Candidate, reprojection, jitter, sampling, clipping, and history-weight ablations |
| `experiment/candidate-jitter` | Candidate/jitter instability isolation |
| `experiment/candidate-jitter-real-scene` | Bistro/Minecraft candidate-jitter quality evaluation |
| `experiment/hybrid-resolve` | Standard/edge-selective hybrid temporal resolve ablation |
| `experiment/candidate-expansion-3x3` | Exact current-edge 3×3 max-filter candidate expansion |
| `experiment/candidate-expansion-arm-dual` | ARM dual-filter kernel adaptation for candidate-mask expansion |
| `experiment/rigid-object-motion-reprojection` | Default-Off rigid-object velocity extension |

## Validation branches

| Branch | Purpose |
|---|---|
| `validation/implementation-audit` | Systematic Original/Adaptive/T2X/ET2X implementation and provenance audit |
| `validation/smaa-first-pass-edge-reuse` | Formal comparison of legacy, post-pass, and first-pass candidate sources |
| `validation/filtered-quarter-postfix` | Raw-candidate-preserving FilteredQuarter correction and remeasurement |
| `validation/supersample-reference-quality` | Same-pose supersample spatial-reference proxy |
| `validation/temporal-reference-analysis` | Optical-flow-aligned temporal residual analysis |
| `validation/camera-motion-ghosting` | Camera motion/parallax ghosting evaluation |
| `validation/real-scene-temporal-retention` | Real-scene temporal-effect retention analysis |
| `validation/smooth-camera-quality` | Rotation-only, translation-only, and combined smooth-camera gate |
| `validation/wide-camera-reference` | Wide motion same-pose reference and CGVQM-2 gate |
| `validation/object-motion-investigation` | Camera-only reprojection limitation investigation |
| `validation/object-motion-reprojection-audit` | Rigid-object reprojection design audit |

## Tooling branches

| Branch | Purpose |
|---|---|
| `tooling/san-miguel-scene` | External textured San Miguel preparation, cache conversion, and loading |
| `tooling/smooth-flythrough-360` | Deterministic smooth translation/rotation camera protocols |
| `tooling/wide-flythrough-360` | Wider-translation combined flythrough/360° yaw protocol |

## Archive branches

These branches preserve research provenance and should not be used as the
current implementation.

| Branch | Reason archived |
|---|---|
| `archive/edge-guided-t2x-prototype` | Early edge-guided T2X prototype |
| `archive/tscmaa-inspired-prototype` | Performed an additional full-screen post-SMAA edge decision instead of direct first-pass reuse |
| `archive/filtered-quarter-pre-fix` | Could erase original raw candidates before the raw-union correction |
| `archive/power-plant-scene` | Incomplete Power Plant renderer, excluded from final evidence |

## Reproducibility notes

- Build `Release | x64` with Visual Studio 2022, MSVC v143, and a Windows SDK.
- The default performance path uses candidate-statistics readback Off; candidate
  characterization is run separately with readback On.
- `-R` means camera/depth reprojection unless a separately named rigid-object
  experiment explicitly enables object motion.
- San Miguel source assets are external. Follow
  `Docs/SMAA-SanMiguel-Textured-Scene-ko.md` before using `sanmiguel` commands.
- Raw AutoBench captures and generated caches are intentionally excluded from Git.
