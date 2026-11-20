#version 330 compatibility
// Pass 0: edge luma, camera velocity and the previous frame's velocity.
out vec2 texcoord;

void main() {
    gl_Position = ftransform();
    texcoord = (gl_TextureMatrix[0] * gl_MultiTexCoord0).xy;
}
