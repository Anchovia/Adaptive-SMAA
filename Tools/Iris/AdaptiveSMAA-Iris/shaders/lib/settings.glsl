// Options shown in the Iris shader settings screen (Options > Shader Pack Settings).
// 0 off, 1 Original SMAA 1X, 2 Adaptive SMAA 1X, 3 Original selected route, 4 Adaptive selected route,
// 5 Original selected route + Cross5, 6 Adaptive selected route + Cross5 (the final combination).
#define AA_MODE 6 // [0 1 2 3 4 5 6]

// 0 none, 1 edges, 2 search tiers, 3 selected (history) pixels, 4 camera velocity.
#define DEBUG_VIEW 0 // [0 1 2 3 4]

// Test switch: every Adaptive tier searches the Ultra maximum, so modes 2/4/6 must equal 1/3/5.
//#define TIERS_AT_MAX
