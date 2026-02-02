"""ModernGL-based 3D renderer - Piano Roll Style."""

import math
from typing import Optional
import random

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


# Vertex shader
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
    gl_PointSize = 4.0 + in_glow * 6.0;
    v_color = in_color;
    v_glow = in_glow;
}
"""

# Fragment shader with enhanced glow
FRAGMENT_SHADER = """
#version 330

in vec4 v_color;
in float v_glow;

out vec4 fragColor;

void main() {
    float glowIntensity = v_glow * v_glow;
    
    vec3 color = v_color.rgb * (1.0 + glowIntensity * 3.0);
    
    // Cyan/magenta highlights
    vec3 highlight = mix(
        vec3(0.2, 0.8, 1.0),
        vec3(1.0, 0.4, 0.8),
        glowIntensity
    );
    color += highlight * glowIntensity * 0.6;
    
    float alpha = v_color.a * (0.8 + glowIntensity * 0.2);
    
    fragColor = vec4(color, alpha);
}
"""


def create_ortho_matrix(left: float, right: float, bottom: float, top: float, 
                        near: float, far: float) -> np.ndarray:
    """Create orthographic projection matrix."""
    return np.array([
        [2/(right-left), 0, 0, 0],
        [0, 2/(top-bottom), 0, 0],
        [0, 0, -2/(far-near), 0],
        [-(right+left)/(right-left), -(top+bottom)/(top-bottom), -(far+near)/(far-near), 1]
    ], dtype='f4')


class Renderer3D:
    """Piano roll style 3D renderer."""
    
    def __init__(self, state: VisualizerState):
        if not HAS_MODERNGL:
            raise ImportError("moderngl and numpy required")
        
        self.state = state
        self.ctx: Optional[moderngl.Context] = None
        self.clock: Optional[pygame.time.Clock] = None
        self.running = False
        
        # Settings
        self.show_energy_lines = True  # On by default
        
        # Particles for energy lines
        self.particles: list[dict] = []
        
        # Animation
        self.time = 0.0
        
    def start(self) -> None:
        pygame.init()
        pygame.display.set_mode(
            (config.WINDOW_WIDTH, config.WINDOW_HEIGHT),
            OPENGL | DOUBLEBUF
        )
        pygame.display.set_caption(config.WINDOW_TITLE + " (3D)")
        
        self.ctx = moderngl.create_context()
        self.clock = pygame.time.Clock()
        
        self.ctx.enable(moderngl.BLEND)
        self.ctx.enable(moderngl.PROGRAM_POINT_SIZE)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
        
        self._create_shaders()
        self.running = True
    
    def _create_shaders(self) -> None:
        self.prog = self.ctx.program(
            vertex_shader=VERTEX_SHADER,
            fragment_shader=FRAGMENT_SHADER,
        )
    
    def stop(self) -> None:
        self.running = False
        pygame.quit()
    
    def handle_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                elif event.key == pygame.K_e:
                    self.show_energy_lines = not self.show_energy_lines
        return True
    
    def render(self, dt: float) -> None:
        if not self.ctx:
            return
        
        self.time += dt
        self.state.update_fading(dt, config.GLOW_FADE_SPEED)
        self._update_particles(dt)
        
        # Clear
        self.ctx.screen.use()
        self.ctx.clear(0.02, 0.02, 0.05, 1.0)
        
        # Orthographic projection for clean 2.5D look
        aspect = config.WINDOW_WIDTH / config.WINDOW_HEIGHT
        proj = create_ortho_matrix(-aspect * 2, aspect * 2, -2, 2, -10, 10)
        
        # Identity view (camera at origin looking at -Z)
        view = np.eye(4, dtype='f4')
        
        self.prog['projection'].write(proj.tobytes())
        self.prog['view'].write(view.tobytes())
        
        # Render components
        self._render_harmonic_bars()
        
        if self.show_energy_lines:
            self._render_particles()
        
        self._render_keyboard()
        
        pygame.display.flip()
    
    def _update_particles(self, dt: float) -> None:
        """Update particle positions and spawn new ones."""
        # Update existing particles
        new_particles = []
        for p in self.particles:
            p['life'] -= dt
            if p['life'] > 0:
                # Move upward
                p['y'] += p['vy'] * dt
                p['x'] += p['vx'] * dt
                new_particles.append(p)
        self.particles = new_particles
        
        # Spawn particles from active voices
        f1 = self.state.f1
        for voice in self.state.get_all_visible_voices():
            if voice.glow < 0.3:
                continue
                
            # Find harmonic position
            if f1 > 0:
                n = voice.frequency / f1
                if 1 <= n <= config.MAX_HARMONICS_DISPLAY:
                    # X position based on harmonic
                    target_x = (n / config.MAX_HARMONICS_DISPLAY) * 3.0 - 1.5
                    
                    # Spawn from pressed keys
                    for note in list(self.state.pressed_keys.keys()):
                        key_idx = note - config.KEYBOARD_LOWEST_NOTE
                        if 0 <= key_idx < config.KEYBOARD_KEYS:
                            key_x = (key_idx / config.KEYBOARD_KEYS) * 3.0 - 1.5
                            
                            # Random chance to spawn
                            if random.random() < 0.3:
                                self.particles.append({
                                    'x': key_x,
                                    'y': -1.2,  # Start at keyboard
                                    'vx': (target_x - key_x) * 0.5,
                                    'vy': 1.5 + random.random() * 0.5,
                                    'life': 0.8 + random.random() * 0.4,
                                    'glow': voice.glow,
                                    'harmonic': n,
                                })
        
        # Limit particles
        if len(self.particles) > 500:
            self.particles = self.particles[-500:]
    
    def _render_harmonic_bars(self) -> None:
        """Render horizontal harmonic bars at top."""
        f1 = self.state.f1
        visible_voices = self.state.get_all_visible_voices()
        
        vertices = []
        
        bar_y = 1.2  # Top area
        bar_height = 0.15
        
        for n in range(1, config.MAX_HARMONICS_DISPLAY + 1):
            # X position (spread horizontally)
            x = (n / config.MAX_HARMONICS_DISPLAY) * 3.0 - 1.5
            
            # Check if active
            glow = 0.0
            for voice in visible_voices:
                if f1 > 0:
                    voice_n = voice.frequency / f1
                    if abs(voice_n - n) < 0.5:
                        glow = max(glow, voice.glow * voice.gain)
            
            # Bar width based on harmonic
            bar_width = 0.08 * (1 - n * 0.01)
            
            # Color gradient: warm low, cool high
            t = n / config.MAX_HARMONICS_DISPLAY
            r = 0.2 + (1-t) * 0.2 + glow * 0.4
            g = 0.3 + glow * 0.5
            b = 0.5 + t * 0.3 + glow * 0.2
            a = 0.7 + glow * 0.3
            
            # Extend bar down when active
            height = bar_height + glow * 0.3
            
            # Create bar
            corners = [
                (x - bar_width/2, bar_y - height, 0),
                (x + bar_width/2, bar_y - height, 0),
                (x + bar_width/2, bar_y, 0),
                (x - bar_width/2, bar_y - height, 0),
                (x + bar_width/2, bar_y, 0),
                (x - bar_width/2, bar_y, 0),
            ]
            
            for pos in corners:
                vertices.extend([pos[0], pos[1], pos[2], r, g, b, a, glow])
        
        if vertices:
            vertices = np.array(vertices, dtype='f4')
            vbo = self.ctx.buffer(vertices.tobytes())
            vao = self.ctx.vertex_array(
                self.prog,
                [(vbo, '3f 4f 1f', 'in_position', 'in_color', 'in_glow')]
            )
            vao.render(moderngl.TRIANGLES)
            vbo.release()
    
    def _render_particles(self) -> None:
        """Render energy particles."""
        if not self.particles:
            return
        
        vertices = []
        for p in self.particles:
            alpha = min(1.0, p['life'] * 2)
            glow = p['glow'] * alpha
            
            # Particle color
            r, g, b = 0.3, 0.8, 1.0
            a = alpha * 0.8
            
            vertices.extend([p['x'], p['y'], 0, r, g, b, a, glow])
        
        if vertices:
            vertices = np.array(vertices, dtype='f4')
            vbo = self.ctx.buffer(vertices.tobytes())
            vao = self.ctx.vertex_array(
                self.prog,
                [(vbo, '3f 4f 1f', 'in_position', 'in_color', 'in_glow')]
            )
            vao.render(moderngl.POINTS)
            vbo.release()
    
    def _render_keyboard(self) -> None:
        """Render piano keyboard at bottom."""
        vertices = []
        
        key_count = config.KEYBOARD_KEYS
        total_width = 3.0
        key_width = total_width / key_count
        keyboard_y = -1.5
        white_height = 0.5
        black_height = 0.35
        
        # Render white keys first
        for i in range(key_count):
            midi_note = config.KEYBOARD_LOWEST_NOTE + i
            note_in_octave = midi_note % 12
            is_black = note_in_octave in [1, 3, 6, 8, 10]
            
            if is_black:
                continue
            
            x = (i / key_count) * total_width - total_width/2
            is_pressed = midi_note in list(self.state.pressed_keys.keys())
            
            if is_pressed:
                r, g, b = 0.2, 0.9, 1.0
                glow = 1.0
            else:
                r, g, b = 0.85, 0.85, 0.9
                glow = 0.0
            
            a = 1.0
            
            corners = [
                (x, keyboard_y, 0),
                (x + key_width * 0.95, keyboard_y, 0),
                (x + key_width * 0.95, keyboard_y + white_height, 0),
                (x, keyboard_y, 0),
                (x + key_width * 0.95, keyboard_y + white_height, 0),
                (x, keyboard_y + white_height, 0),
            ]
            
            for pos in corners:
                vertices.extend([pos[0], pos[1], pos[2], r, g, b, a, glow])
        
        # Render black keys on top
        for i in range(key_count):
            midi_note = config.KEYBOARD_LOWEST_NOTE + i
            note_in_octave = midi_note % 12
            is_black = note_in_octave in [1, 3, 6, 8, 10]
            
            if not is_black:
                continue
            
            x = (i / key_count) * total_width - total_width/2 - key_width * 0.15
            is_pressed = midi_note in list(self.state.pressed_keys.keys())
            
            if is_pressed:
                r, g, b = 0.15, 0.7, 0.9
                glow = 1.0
            else:
                r, g, b = 0.1, 0.1, 0.15
                glow = 0.0
            
            a = 1.0
            
            corners = [
                (x, keyboard_y + white_height - black_height, 0.1),
                (x + key_width * 0.7, keyboard_y + white_height - black_height, 0.1),
                (x + key_width * 0.7, keyboard_y + white_height, 0.1),
                (x, keyboard_y + white_height - black_height, 0.1),
                (x + key_width * 0.7, keyboard_y + white_height, 0.1),
                (x, keyboard_y + white_height, 0.1),
            ]
            
            for pos in corners:
                vertices.extend([pos[0], pos[1], pos[2], r, g, b, a, glow])
        
        if vertices:
            vertices = np.array(vertices, dtype='f4')
            vbo = self.ctx.buffer(vertices.tobytes())
            vao = self.ctx.vertex_array(
                self.prog,
                [(vbo, '3f 4f 1f', 'in_position', 'in_color', 'in_glow')]
            )
            vao.render(moderngl.TRIANGLES)
            vbo.release()
