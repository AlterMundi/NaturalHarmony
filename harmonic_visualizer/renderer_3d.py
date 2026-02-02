"""ModernGL-based 3D renderer with shaders and bloom effects."""

import math
from typing import Optional
import struct

try:
    import numpy as np
    import moderngl
    import pygame
    from pygame import OPENGL, DOUBLEBUF
    HAS_MODERNGL = True
except ImportError:
    HAS_MODERNGL = False
    np = None  # type: ignore
    moderngl = None  # type: ignore

from . import config
from .state import VisualizerState


# Vertex shader - transforms 3D positions to screen space
VERTEX_SHADER = """
#version 330

in vec3 in_position;
in vec4 in_color;
in float in_glow;

out vec4 v_color;
out float v_glow;

uniform mat4 projection;
uniform mat4 view;

void main() {
    gl_Position = projection * view * vec4(in_position, 1.0);
    v_color = in_color;
    v_glow = in_glow;
}
"""

# Fragment shader - renders with glow effect
FRAGMENT_SHADER = """
#version 330

in vec4 v_color;
in float v_glow;

out vec4 fragColor;

void main() {
    // Base color with glow intensity
    vec3 color = v_color.rgb * (1.0 + v_glow * 2.0);
    float alpha = v_color.a * (0.5 + v_glow * 0.5);
    
    // Add bloom-like effect based on glow
    color += vec3(0.2, 0.5, 1.0) * v_glow * 0.5;
    
    fragColor = vec4(color, alpha);
}
"""

# Full-screen quad for post-processing
QUAD_VERTEX = """
#version 330

in vec2 in_position;
in vec2 in_texcoord;

out vec2 v_texcoord;

void main() {
    gl_Position = vec4(in_position, 0.0, 1.0);
    v_texcoord = in_texcoord;
}
"""

# Bloom post-processing shader
BLOOM_FRAGMENT = """
#version 330

in vec2 v_texcoord;
out vec4 fragColor;

uniform sampler2D scene_texture;
uniform float bloom_intensity;

void main() {
    vec4 color = texture(scene_texture, v_texcoord);
    
    // Simple bloom: bright areas glow
    float brightness = dot(color.rgb, vec3(0.2126, 0.7152, 0.0722));
    vec3 bloom = vec3(0.0);
    
    if (brightness > 0.5) {
        // Sample neighboring pixels for blur effect
        vec2 texel = 1.0 / textureSize(scene_texture, 0);
        for (int x = -2; x <= 2; x++) {
            for (int y = -2; y <= 2; y++) {
                vec2 offset = vec2(float(x), float(y)) * texel * 2.0;
                bloom += texture(scene_texture, v_texcoord + offset).rgb;
            }
        }
        bloom /= 25.0;
        bloom *= bloom_intensity;
    }
    
    fragColor = vec4(color.rgb + bloom, 1.0);
}
"""


def create_perspective_matrix(fov: float, aspect: float, near: float, far: float) -> np.ndarray:
    """Create perspective projection matrix."""
    f = 1.0 / math.tan(math.radians(fov) / 2.0)
    return np.array([
        [f / aspect, 0, 0, 0],
        [0, f, 0, 0],
        [0, 0, (far + near) / (near - far), (2 * far * near) / (near - far)],
        [0, 0, -1, 0]
    ], dtype='f4')


def create_view_matrix(eye: tuple, target: tuple, up: tuple = (0, 1, 0)) -> np.ndarray:
    """Create view matrix (camera transform)."""
    eye = np.array(eye, dtype='f4')
    target = np.array(target, dtype='f4')
    up = np.array(up, dtype='f4')
    
    forward = target - eye
    forward = forward / np.linalg.norm(forward)
    
    right = np.cross(forward, up)
    right = right / np.linalg.norm(right)
    
    up = np.cross(right, forward)
    
    return np.array([
        [right[0], right[1], right[2], -np.dot(right, eye)],
        [up[0], up[1], up[2], -np.dot(up, eye)],
        [-forward[0], -forward[1], -forward[2], np.dot(forward, eye)],
        [0, 0, 0, 1]
    ], dtype='f4')


class Renderer3D:
    """ModernGL-based 3D renderer with bloom effects."""
    
    def __init__(self, state: VisualizerState):
        """Initialize the renderer."""
        if not HAS_MODERNGL:
            raise ImportError(
                "moderngl and numpy are required. "
                "Install with: pip install moderngl numpy"
            )
        
        self.state = state
        self.ctx: Optional[moderngl.Context] = None
        self.clock: Optional[pygame.time.Clock] = None
        self.running = False
        
        # Settings
        self.show_energy_lines = True
        self.camera_distance = 5.0
        self.camera_angle = 0.0
        self.camera_height = 1.0
        
        # Animation state
        self.time = 0.0
        
    def start(self) -> None:
        """Initialize PyGame and ModernGL."""
        pygame.init()
        pygame.display.set_mode(
            (config.WINDOW_WIDTH, config.WINDOW_HEIGHT),
            OPENGL | DOUBLEBUF
        )
        pygame.display.set_caption(config.WINDOW_TITLE + " (3D)")
        
        self.ctx = moderngl.create_context()
        self.clock = pygame.time.Clock()
        
        # Enable blending for transparency
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (
            moderngl.SRC_ALPHA, 
            moderngl.ONE_MINUS_SRC_ALPHA
        )
        
        # Create shaders
        self._create_shaders()
        self._create_geometry()
        self._create_framebuffer()
        
        self.running = True
    
    def _create_shaders(self) -> None:
        """Create shader programs."""
        # Main scene shader
        self.scene_prog = self.ctx.program(
            vertex_shader=VERTEX_SHADER,
            fragment_shader=FRAGMENT_SHADER,
        )
        
        # Bloom post-processing shader
        self.bloom_prog = self.ctx.program(
            vertex_shader=QUAD_VERTEX,
            fragment_shader=BLOOM_FRAGMENT,
        )
    
    def _create_geometry(self) -> None:
        """Create geometry buffers."""
        # Full-screen quad for post-processing
        quad_vertices = np.array([
            -1, -1, 0, 0,
             1, -1, 1, 0,
             1,  1, 1, 1,
            -1, -1, 0, 0,
             1,  1, 1, 1,
            -1,  1, 0, 1,
        ], dtype='f4')
        
        self.quad_vbo = self.ctx.buffer(quad_vertices.tobytes())
        self.quad_vao = self.ctx.vertex_array(
            self.bloom_prog,
            [(self.quad_vbo, '2f 2f', 'in_position', 'in_texcoord')]
        )
    
    def _create_framebuffer(self) -> None:
        """Create framebuffer for post-processing."""
        self.scene_texture = self.ctx.texture(
            (config.WINDOW_WIDTH, config.WINDOW_HEIGHT), 4
        )
        self.scene_depth = self.ctx.depth_renderbuffer(
            (config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        )
        self.scene_fbo = self.ctx.framebuffer(
            color_attachments=[self.scene_texture],
            depth_attachment=self.scene_depth
        )
    
    def stop(self) -> None:
        """Shut down."""
        self.running = False
        pygame.quit()
    
    def handle_events(self) -> bool:
        """Process events. Returns False if should quit."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                elif event.key == pygame.K_e:
                    self.show_energy_lines = not self.show_energy_lines
                elif event.key == pygame.K_LEFT:
                    self.camera_angle -= 0.1
                elif event.key == pygame.K_RIGHT:
                    self.camera_angle += 0.1
                elif event.key == pygame.K_UP:
                    self.camera_distance = max(2.0, self.camera_distance - 0.5)
                elif event.key == pygame.K_DOWN:
                    self.camera_distance = min(15.0, self.camera_distance + 0.5)
        return True
    
    def render(self, dt: float) -> None:
        """Render one frame."""
        if not self.ctx:
            return
        
        self.time += dt
        self.state.update_fading(dt, config.GLOW_FADE_SPEED)
        
        # Slowly rotate camera
        self.camera_angle += dt * 0.1
        
        # Render scene to framebuffer
        self.scene_fbo.use()
        self.ctx.clear(0.02, 0.02, 0.04, 1.0)
        self.ctx.enable(moderngl.DEPTH_TEST)
        
        # Set up camera
        aspect = config.WINDOW_WIDTH / config.WINDOW_HEIGHT
        projection = create_perspective_matrix(60, aspect, 0.1, 100.0)
        
        cam_x = math.sin(self.camera_angle) * self.camera_distance
        cam_z = math.cos(self.camera_angle) * self.camera_distance
        view = create_view_matrix(
            (cam_x, self.camera_height, cam_z),
            (0, 0, 0)
        )
        
        self.scene_prog['projection'].write(projection.tobytes())
        self.scene_prog['view'].write(view.tobytes())
        
        # Render spine
        self._render_spine()
        
        # Render keyboard arc
        self._render_keyboard()
        
        # Render to screen with bloom
        self.ctx.screen.use()
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.scene_texture.use()
        self.bloom_prog['bloom_intensity'].value = 0.5
        self.quad_vao.render()
        
        pygame.display.flip()
    
    def _render_spine(self) -> None:
        """Render the harmonic spine as glowing segments."""
        f1 = self.state.f1
        visible_voices = self.state.get_all_visible_voices()
        
        vertices = []
        
        # Create vertebrae as horizontal bars in 3D space
        for n in range(1, config.MAX_HARMONICS_DISPLAY + 1):
            freq = f1 * n
            
            # Y position based on harmonic (logarithmic)
            y = math.log2(n) / math.log2(config.MAX_HARMONICS_DISPLAY) * 3.0 - 1.5
            
            # Check if active
            glow = 0.0
            for voice in visible_voices:
                if f1 > 0:
                    voice_n = voice.frequency / f1
                    if abs(voice_n - n) < 0.5:
                        glow = max(glow, voice.glow * voice.gain)
            
            # Size decreases with harmonic number
            width = 1.5 * (1 - n * 0.03)
            height = 0.08 * (1 - n * 0.02)
            
            # Color: blue base, brighter when active
            r = 0.2 + glow * 0.3
            g = 0.4 + glow * 0.4
            b = 0.8 + glow * 0.2
            a = 0.6 + glow * 0.4
            
            # Add 4 corners of the vertebra bar
            # Using triangles (2 per quad)
            corners = [
                (-width/2, y - height/2, 0),
                ( width/2, y - height/2, 0),
                ( width/2, y + height/2, 0),
                (-width/2, y - height/2, 0),
                ( width/2, y + height/2, 0),
                (-width/2, y + height/2, 0),
            ]
            
            for pos in corners:
                # position (3) + color (4) + glow (1)
                vertices.extend([pos[0], pos[1], pos[2], r, g, b, a, glow])
        
        if vertices:
            vertices = np.array(vertices, dtype='f4')
            vbo = self.ctx.buffer(vertices.tobytes())
            vao = self.ctx.vertex_array(
                self.scene_prog,
                [(vbo, '3f 4f 1f', 'in_position', 'in_color', 'in_glow')]
            )
            vao.render(moderngl.TRIANGLES)
            vbo.release()
    
    def _render_keyboard(self) -> None:
        """Render keyboard as an arc of keys around the spine."""
        vertices = []
        
        key_count = config.KEYBOARD_KEYS
        arc_radius = 2.5
        arc_span = math.pi * 0.8  # Arc covers ~144 degrees
        
        for i in range(key_count):
            midi_note = config.KEYBOARD_LOWEST_NOTE + i
            
            # Angle along arc
            angle = -arc_span/2 + (i / key_count) * arc_span + math.pi/2
            
            # Position on arc
            x = math.cos(angle) * arc_radius
            z = math.sin(angle) * arc_radius
            y = -2.0  # Below the spine
            
            # Check if pressed
            is_pressed = midi_note in self.state.pressed_keys
            
            # Determine if black or white key
            note_in_octave = midi_note % 12
            is_black = note_in_octave in [1, 3, 6, 8, 10]
            
            # Size
            key_width = 0.06
            key_height = 0.3 if not is_black else 0.2
            key_depth = 0.1
            
            # Color
            if is_pressed:
                r, g, b = 0.4, 0.8, 1.0
                glow = 1.0
            elif is_black:
                r, g, b = 0.1, 0.1, 0.15
                glow = 0.0
            else:
                r, g, b = 0.6, 0.6, 0.65
                glow = 0.0
            
            a = 0.9
            
            # Create a simple quad for the key (facing outward)
            # Normal points away from center
            nx, nz = math.cos(angle), math.sin(angle)
            
            # Offset for key face
            fx = x + nx * key_depth/2
            fz = z + nz * key_depth/2
            
            # Perpendicular direction for width
            px, pz = -nz, nx
            
            corners = [
                (fx - px*key_width/2, y - key_height/2, fz - pz*key_width/2),
                (fx + px*key_width/2, y - key_height/2, fz + pz*key_width/2),
                (fx + px*key_width/2, y + key_height/2, fz + pz*key_width/2),
                (fx - px*key_width/2, y - key_height/2, fz - pz*key_width/2),
                (fx + px*key_width/2, y + key_height/2, fz + pz*key_width/2),
                (fx - px*key_width/2, y + key_height/2, fz - pz*key_width/2),
            ]
            
            for pos in corners:
                vertices.extend([pos[0], pos[1], pos[2], r, g, b, a, glow])
        
        if vertices:
            vertices = np.array(vertices, dtype='f4')
            vbo = self.ctx.buffer(vertices.tobytes())
            vao = self.ctx.vertex_array(
                self.scene_prog,
                [(vbo, '3f 4f 1f', 'in_position', 'in_color', 'in_glow')]
            )
            vao.render(moderngl.TRIANGLES)
            vbo.release()
