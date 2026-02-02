"""ModernGL-based 3D renderer - Piano Roll Style with Frequency Ruler."""

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


# Frequency range for the ruler
FREQ_MIN = 20.0      # 20 Hz (lower limit of human hearing)
FREQ_MAX = 20000.0   # 20 kHz (upper limit)

# Reference frequencies to mark on ruler
FREQ_MARKERS = [20, 50, 100, 200, 440, 1000, 2000, 5000, 10000, 20000]


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

# Shaders for 2D HUD overlay
HUD_VERTEX_SHADER = """
#version 330

in vec2 in_position;
in vec2 in_texcoord;

out vec2 v_texcoord;

void main() {
    gl_Position = vec4(in_position, 0.0, 1.0);
    v_texcoord = in_texcoord;
}
"""

HUD_FRAGMENT_SHADER = """
#version 330

uniform sampler2D hud_texture;
in vec2 v_texcoord;

out vec4 fragColor;

void main() {
    fragColor = texture(hud_texture, v_texcoord);
}
"""


def freq_to_x(freq: float, width: float = 3.5) -> float:
    """Convert frequency to X position using logarithmic scale."""
    if freq <= FREQ_MIN:
        return -width / 2
    if freq >= FREQ_MAX:
        return width / 2
    
    # Logarithmic mapping
    log_min = math.log10(FREQ_MIN)
    log_max = math.log10(FREQ_MAX)
    log_freq = math.log10(freq)
    
    t = (log_freq - log_min) / (log_max - log_min)
    return t * width - width / 2


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
    """Piano roll style 3D renderer with frequency ruler."""
    
    def __init__(self, state: VisualizerState):
        if not HAS_MODERNGL:
            raise ImportError("moderngl and numpy required")
        
        self.state = state
        self.ctx: Optional[moderngl.Context] = None
        self.clock: Optional[pygame.time.Clock] = None
        self.running = False
        
        # Settings
        self.show_energy_lines = True  # On by default
        self.show_hud = config.SHOW_HUD_DEFAULT
        self.fullscreen = config.FULLSCREEN_DEFAULT
        self.screen_width = config.WINDOW_WIDTH
        self.screen_height = config.WINDOW_HEIGHT
        
        # Particles for energy lines
        self.particles: list[dict] = []
        
        # Animation
        self.time = 0.0
        
        # Layout (Y positions)
        self.keyboard_y = 1.4       # Keyboard at top
        self.ruler_y = -0.6         # Frequency ruler below
        self.ruler_width = 3.8      # Wider to fit 88/128 keys
        
        # HUD texture and quad
        self.hud_prog: Optional[moderngl.Program] = None
        self.hud_texture: Optional[moderngl.Texture] = None
        self.hud_vao: Optional[moderngl.VertexArray] = None
        self.hud_surface: Optional[pygame.Surface] = None
        self.hud_size = (300, 200)  # Size of HUD overlay on screen
        
    def start(self) -> None:
        pygame.init()
        
        # Get display info for fullscreen
        display_info = pygame.display.Info()
        
        if self.fullscreen:
            self.screen_width = display_info.current_w
            self.screen_height = display_info.current_h
            flags = OPENGL | DOUBLEBUF | pygame.FULLSCREEN
        else:
            flags = OPENGL | DOUBLEBUF
        
        pygame.display.set_mode(
            (self.screen_width, self.screen_height),
            flags
        )
        pygame.display.set_caption(config.WINDOW_TITLE + " (3D)")
        
        self.ctx = moderngl.create_context()
        self.clock = pygame.time.Clock()
        
        self.ctx.enable(moderngl.BLEND)
        self.ctx.enable(moderngl.PROGRAM_POINT_SIZE)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
        
        # Initialize pygame font for HUD
        pygame.font.init()
        self.font = pygame.font.SysFont('monospace', 16, bold=True)
        self.hud_surface = pygame.Surface(self.hud_size, pygame.SRCALPHA)
        
        self._create_shaders()
        self._create_hud_resources()
        self.running = True
    
    def _create_shaders(self) -> None:
        self.prog = self.ctx.program(
            vertex_shader=VERTEX_SHADER,
            fragment_shader=FRAGMENT_SHADER,
        )
        self.hud_prog = self.ctx.program(
            vertex_shader=HUD_VERTEX_SHADER,
            fragment_shader=HUD_FRAGMENT_SHADER,
        )
    
    def _create_hud_resources(self) -> None:
        """Create resources for HUD overlay."""
        # Quad for HUD (top-left corner in screen space)
        # ModernGL screen coords are -1 to 1
        # We want it in the top left, roughly 300x200 pixels
        w = (self.hud_size[0] / self.screen_width) * 2
        h = (self.hud_size[1] / self.screen_height) * 2
        
        # Quad vertices: x, y, u, v
        vertices = np.array([
            -1.0,  1.0,     0.0, 0.0,  # Top Left
            -1.0+w, 1.0,     1.0, 0.0,  # Top Right
            -1.0,  1.0-h,   0.0, 1.0,  # Bottom Left
            -1.0+w, 1.0-h,   1.0, 1.0,  # Bottom Right
        ], dtype='f4')
        
        vbo = self.ctx.buffer(vertices.tobytes())
        self.hud_vao = self.ctx.vertex_array(
            self.hud_prog,
            [(vbo, '2f 2f', 'in_position', 'in_texcoord')],
            index_buffer=self.ctx.buffer(np.array([0, 1, 2, 1, 2, 3], dtype='i4').tobytes())
        )
        
        # Texture for HUD
        self.hud_texture = self.ctx.texture(self.hud_size, 4)
        self.hud_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.hud_texture.swizzle = 'BGRA'  # Ensure correct color ordering if needed
    
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
                elif event.key == pygame.K_h:
                    self.show_hud = not self.show_hud
                elif event.key == pygame.K_f:
                    self._toggle_fullscreen()
        return True
    
    def _toggle_fullscreen(self) -> None:
        """Toggle between fullscreen and windowed mode."""
        self.fullscreen = not self.fullscreen
        
        if self.fullscreen:
            display_info = pygame.display.Info()
            self.screen_width = display_info.current_w
            self.screen_height = display_info.current_h
            flags = OPENGL | DOUBLEBUF | pygame.FULLSCREEN
        else:
            self.screen_width = config.WINDOW_WIDTH
            self.screen_height = config.WINDOW_HEIGHT
            flags = OPENGL | DOUBLEBUF
        
        pygame.display.set_mode((self.screen_width, self.screen_height), flags)
        self.ctx = moderngl.create_context()
        self._create_shaders()
        self._create_hud_resources()
    
    def render(self, dt: float) -> None:
        if not self.ctx:
            return
        
        self.time += dt
        self.state.update_fading(dt, config.GLOW_FADE_SPEED)
        self._update_particles(dt)
        
        # Clear
        self.ctx.screen.use()
        self.ctx.clear(0.02, 0.02, 0.05, 1.0)
        
        # Orthographic projection using actual screen dimensions
        aspect = self.screen_width / self.screen_height
        proj = create_ortho_matrix(-aspect * 2, aspect * 2, -2, 2, -10, 10)
        view = np.eye(4, dtype='f4')
        
        self.prog['projection'].write(proj.tobytes())
        self.prog['view'].write(view.tobytes())
        
        # Render components (keyboard on top, ruler below)
        self._render_keyboard()
        self._render_frequency_ruler()
        self._render_harmonic_slots()
        
        if self.show_energy_lines:
            self._render_particles()
        
        if self.show_hud:
            self._render_hud()
        
        pygame.display.flip()
    
    def _render_hud(self) -> None:
        """Render the HUD overlay with all numeric values."""
        if not self.hud_surface or not self.hud_texture:
            return
            
        # 1. Clear HUD surface (transparent)
        self.hud_surface.fill((0, 0, 0, 0))
        
        # 2. Get active voice info
        voices = self.state.get_all_visible_voices()
        active_count = len([v for v in voices if v.glow > 0.5])
        freqs = sorted(set(v.frequency for v in voices if v.glow > 0.5))
        freq_str = ", ".join(f"{f:.0f}" for f in freqs[:3])
        if len(freqs) > 3:
            freq_str += ".."
            
        keys_pressed = sorted(self.state.pressed_keys.keys())
        key_str = ", ".join(str(k) for k in keys_pressed[:4])
        if len(keys_pressed) > 4:
            key_str += ".."
            
        # 3. Map CC values (using beacon/config.py constants)
        # Tolerance (CC 67)
        tol_cc = self.state.cc_values.get(67, 64)
        tol_val = 1.0 + (tol_cc / 127.0) * (50.0 - 1.0)
        
        # LFO Rate (CC 68)
        lfo_cc = self.state.cc_values.get(68, 10)
        lfo_val = 0.1 + (lfo_cc / 127.0) * (10.0 - 0.1)
        
        # Vibrato Mode (CC 23)
        vib_cc = self.state.cc_values.get(23, 0)
        vib_mode = "Stepped" if vib_cc >= 64 else "Smooth"
        
        # Aftertouch (CC 22, 30, 92)
        at_mode_cc = self.state.cc_values.get(22, 0)
        at_mode = "Key Anchor" if at_mode_cc >= 64 else "f1 Center"
        
        at_enabled_cc = self.state.cc_values.get(30, 0)
        at_status = "ON" if at_enabled_cc >= 64 else "OFF"
        
        # 4. Build HUD lines
        lines = [
            f"f1: {self.state.f1:.1f} Hz | Anchor: {self.state.anchor_note}",
            f"Voices: {active_count} | Keys: {key_str if keys_pressed else '--'}",
            f"Freqs: {freq_str if freqs else '--'}",
            f"Tolerance: {tol_val:.1f} cents",
            f"LFO: {lfo_val:.2f} Hz | Mode: {vib_mode}",
            f"Aftertouch: {at_status} | {at_mode}",
            "",
            "[F] Fullscreen [E] Energy [H] HUD",
        ]
        
        # Draw background panel
        pygame.draw.rect(self.hud_surface, (15, 15, 30, 220), (0, 0, self.hud_size[0], self.hud_size[1]), border_radius=10)
        pygame.draw.rect(self.hud_surface, (100, 150, 255, 100), (0, 0, self.hud_size[0], self.hud_size[1]), 2, border_radius=10)
        
        # 5. Render each line
        y_offset = 15
        for line in lines:
            if line:
                text_surface = self.font.render(line, True, (220, 240, 255))
                self.hud_surface.blit(text_surface, (15, y_offset))
                y_offset += 22
            else:
                y_offset += 8
        
        # 6. Upload PyGame surface to ModernGL texture
        # flipped=False because UVs are (0,0) at top-left
        texture_data = pygame.image.tostring(self.hud_surface, 'RGBA', False)
        self.hud_texture.write(texture_data)
        
        # 7. Render HUD quad
        self.hud_texture.use(0)
        self.hud_vao.render(moderngl.TRIANGLE_STRIP)
        
        # Update window title
        pygame.display.set_caption(f"Harmonic Visualizer | f1={self.state.f1:.1f}Hz | {active_count}v")
    
    def _update_particles(self, dt: float) -> None:
        """Update particle positions and spawn new ones from active harmonics."""
        keyboard_bottom = self.keyboard_y - 0.45  # Bottom of keyboard
        
        # Update existing particles
        new_particles = []
        for p in self.particles:
            p['life'] -= dt
            if p['life'] > 0:
                # Check if reached keyboard
                if p['y'] >= keyboard_bottom:
                    # Particle has landed - keep it briefly then fade
                    p['x'] = p['target_x']  # Snap to exact target
                    p['y'] = keyboard_bottom
                    p['vx'] = 0
                    p['vy'] = 0
                    p['life'] = min(p['life'], 0.2)  # Quick fade after landing
                else:
                    # Move toward target key
                    p['y'] += p['vy'] * dt
                    p['x'] += p['vx'] * dt
                    # Slow down less so they reach target
                    p['vx'] *= 0.99
                    p['vy'] *= 0.99
                new_particles.append(p)
        self.particles = new_particles
        
        # Spawn particles from active harmonic slots toward their source keys
        for voice in self.state.get_all_visible_voices():
            if voice.glow < 0.2:
                continue
            
            # Get actual frequency position on ruler
            voice_freq = voice.frequency
            if FREQ_MIN <= voice_freq <= FREQ_MAX:
                slot_x = freq_to_x(voice_freq, self.ruler_width)
                
                # Get the source key position
                key_idx = voice.source_note - config.KEYBOARD_LOWEST_NOTE
                if 0 <= key_idx < config.KEYBOARD_KEYS:
                    key_x = (key_idx / config.KEYBOARD_KEYS) * self.ruler_width - self.ruler_width/2
                    
                    # Spawn particles flowing toward the key
                    if random.random() < 0.35 * voice.glow:
                        # Calculate velocity to reach target in ~0.5 seconds
                        travel_time = 0.5 + random.random() * 0.2
                        dx = key_x - slot_x
                        dy = keyboard_bottom - self.ruler_y
                        
                        self.particles.append({
                            'x': slot_x + random.uniform(-0.02, 0.02),
                            'y': self.ruler_y + random.uniform(-0.05, 0.05),
                            'vx': dx / travel_time + random.uniform(-0.05, 0.05),
                            'vy': dy / travel_time + random.uniform(-0.05, 0.05),
                            'target_x': key_x,  # Store target for landing
                            'life': travel_time + 0.3,  # Extra time for landing fade
                            'glow': voice.glow,
                            'freq': voice_freq,
                        })
        
        # Limit particles
        if len(self.particles) > 500:
            self.particles = self.particles[-500:]
    
    def _render_frequency_ruler(self) -> None:
        """Render the frequency ruler background with markers."""
        vertices = []
        
        ruler_height = 0.08
        y = self.ruler_y
        
        # Background bar
        r, g, b = 0.1, 0.1, 0.15
        a = 0.9
        glow = 0.0
        
        corners = [
            (-self.ruler_width/2, y - ruler_height/2, -0.1),
            ( self.ruler_width/2, y - ruler_height/2, -0.1),
            ( self.ruler_width/2, y + ruler_height/2, -0.1),
            (-self.ruler_width/2, y - ruler_height/2, -0.1),
            ( self.ruler_width/2, y + ruler_height/2, -0.1),
            (-self.ruler_width/2, y + ruler_height/2, -0.1),
        ]
        
        for pos in corners:
            vertices.extend([pos[0], pos[1], pos[2], r, g, b, a, glow])
        
        # Frequency marker ticks
        for freq in FREQ_MARKERS:
            x = freq_to_x(freq, self.ruler_width)
            tick_height = 0.15
            tick_width = 0.01
            
            # Dim color for markers
            r, g, b = 0.3, 0.3, 0.4
            a = 0.7
            
            tick_corners = [
                (x - tick_width/2, y - tick_height, 0),
                (x + tick_width/2, y - tick_height, 0),
                (x + tick_width/2, y + tick_height, 0),
                (x - tick_width/2, y - tick_height, 0),
                (x + tick_width/2, y + tick_height, 0),
                (x - tick_width/2, y + tick_height, 0),
            ]
            
            for pos in tick_corners:
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
    
    def _render_harmonic_slots(self) -> None:
        """Render slots for actually active voice frequencies."""
        visible_voices = self.state.get_all_visible_voices()
        
        if not visible_voices:
            return
        
        vertices = []
        
        slot_height = 0.5
        slot_width = 0.025
        y = self.ruler_y
        
        # Render a slot for each active voice at its actual frequency
        for voice in visible_voices:
            freq = voice.frequency
            
            # Skip if outside visible range
            if freq < FREQ_MIN or freq > FREQ_MAX:
                continue
            
            x = freq_to_x(freq, self.ruler_width)
            glow = voice.glow * voice.gain
            
            # Color based on frequency (warm low, cool high)
            t = (math.log10(freq) - math.log10(FREQ_MIN)) / (math.log10(FREQ_MAX) - math.log10(FREQ_MIN))
            r = 0.3 + (1-t) * 0.2 + glow * 0.4
            g = 0.35 + glow * 0.5
            b = 0.5 + t * 0.3 + glow * 0.3
            a = 0.7 + glow * 0.3
            
            # Height based on activity
            height = slot_height * (0.6 + glow * 0.4)
            
            slot_corners = [
                (x - slot_width/2, y - height/2, 0),
                (x + slot_width/2, y - height/2, 0),
                (x + slot_width/2, y + height/2, 0),
                (x - slot_width/2, y - height/2, 0),
                (x + slot_width/2, y + height/2, 0),
                (x - slot_width/2, y + height/2, 0),
            ]
            
            for pos in slot_corners:
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
        """Render piano keyboard at top."""
        vertices = []
        
        key_count = config.KEYBOARD_KEYS
        total_width = self.ruler_width  # Match ruler width for 88 keys
        key_width = total_width / key_count
        keyboard_y = self.keyboard_y
        white_height = 0.35
        black_height = 0.22
        
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
                (x, keyboard_y - white_height, 0),
                (x + key_width * 0.95, keyboard_y - white_height, 0),
                (x + key_width * 0.95, keyboard_y, 0),
                (x, keyboard_y - white_height, 0),
                (x + key_width * 0.95, keyboard_y, 0),
                (x, keyboard_y, 0),
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
                (x, keyboard_y - black_height, 0.1),
                (x + key_width * 0.7, keyboard_y - black_height, 0.1),
                (x + key_width * 0.7, keyboard_y, 0.1),
                (x, keyboard_y - black_height, 0.1),
                (x + key_width * 0.7, keyboard_y, 0.1),
                (x, keyboard_y, 0.1),
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
