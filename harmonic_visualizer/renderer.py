"""PyGame-based renderer for the visualizer."""

import math
from typing import Optional

try:
    import pygame
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False
    pygame = None  # type: ignore

from . import config
from .state import VisualizerState, VoiceState


def frequency_to_harmonic_index(freq: float, f1: float) -> Optional[float]:
    """Convert frequency to harmonic index (n value).
    
    Returns float for interpolation (e.g., 5.5 means between n=5 and n=6).
    Returns None if frequency is below f1.
    """
    if freq < f1 or f1 <= 0:
        return None
    return freq / f1


def harmonic_to_y_position(n: float, max_n: int, spine_top: int, spine_height: int) -> int:
    """Convert harmonic index to Y position on spine.
    
    Uses logarithmic scaling so lower harmonics are more spread out.
    """
    if n <= 0:
        return spine_top + spine_height
    
    # Logarithmic scaling: log2(n) / log2(max_n)
    log_pos = math.log2(n) / math.log2(max_n)
    y = spine_top + spine_height - int(log_pos * spine_height)
    return max(spine_top, min(spine_top + spine_height, y))


class Renderer:
    """PyGame-based renderer for harmonic visualizer."""
    
    def __init__(self, state: VisualizerState):
        """Initialize the renderer.
        
        Args:
            state: Shared visualizer state
        """
        if not HAS_PYGAME:
            raise ImportError(
                "pygame is required for visualization. "
                "Install with: pip install pygame"
            )
        
        self.state = state
        self.screen: Optional[pygame.Surface] = None
        self.clock: Optional[pygame.time.Clock] = None
        self.font: Optional[pygame.font.Font] = None
        self.font_small: Optional[pygame.font.Font] = None
        self.running = False
        
        # Settings
        self.show_energy_lines = True
        
    def start(self) -> None:
        """Initialize PyGame and create window."""
        pygame.init()
        pygame.font.init()
        
        self.screen = pygame.display.set_mode(
            (config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        )
        pygame.display.set_caption(config.WINDOW_TITLE)
        
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 18)
        self.running = True
    
    def stop(self) -> None:
        """Shut down PyGame."""
        self.running = False
        pygame.quit()
    
    def handle_events(self) -> bool:
        """Process PyGame events. Returns False if should quit."""
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
        """Render one frame."""
        if not self.screen:
            return
        
        # Update fading animations
        self.state.update_fading(dt, config.GLOW_FADE_SPEED)
        
        # Clear screen
        self.screen.fill(config.COLOR_BACKGROUND)
        
        # Calculate layout
        main_height = config.WINDOW_HEIGHT - config.CC_BAR_HEIGHT
        spine_width = int(config.WINDOW_WIDTH * config.SPINE_WIDTH_RATIO)
        keyboard_width = config.WINDOW_WIDTH - spine_width
        
        # Draw sections
        self._draw_spine(0, 0, spine_width, main_height)
        self._draw_keyboard(spine_width, 0, keyboard_width, main_height)
        self._draw_cc_bar(0, main_height, config.WINDOW_WIDTH, config.CC_BAR_HEIGHT)
        
        # Draw energy lines (on top)
        if self.show_energy_lines:
            self._draw_energy_lines(0, 0, spine_width, main_height, 
                                   spine_width, keyboard_width)
        
        # Draw f1 indicator
        self._draw_f1_indicator(10, 10)
        
        pygame.display.flip()
    
    def _draw_spine(self, x: int, y: int, w: int, h: int) -> None:
        """Draw the harmonic spine (vertebrae)."""
        if not self.font_small:
            return
        
        f1 = self.state.f1
        active_freqs = self.state.get_active_frequencies()
        visible_voices = self.state.get_all_visible_voices()
        
        # Draw spine background
        pygame.draw.rect(self.screen, (25, 25, 35), (x, y, w, h))
        
        # Draw vertebrae for each harmonic
        center_x = x + w // 2
        max_vertebra_width = w * 0.7
        
        for n in range(1, config.MAX_HARMONICS_DISPLAY + 1):
            freq = f1 * n
            y_pos = harmonic_to_y_position(n, config.MAX_HARMONICS_DISPLAY, y + 20, h - 40)
            
            # Vertebra size decreases with harmonic number
            vertebra_height = max(config.VERTEBRA_HEIGHT_MIN,
                                  config.VERTEBRA_HEIGHT_BASE - n * 0.6)
            vertebra_width = max_vertebra_width * (1 - n * 0.02)
            
            # Check if this harmonic is active
            glow = 0.0
            for voice in visible_voices:
                voice_n = frequency_to_harmonic_index(voice.frequency, f1)
                if voice_n and abs(voice_n - n) < 0.5:
                    glow = max(glow, voice.glow * voice.gain)
            
            # Draw vertebra
            if glow > 0:
                # Active/glowing
                color = tuple(
                    int(c1 + (c2 - c1) * glow)
                    for c1, c2 in zip(config.COLOR_SPINE_INACTIVE, config.COLOR_SPINE_GLOW)
                )
            else:
                color = config.COLOR_SPINE_INACTIVE
            
            rect = pygame.Rect(
                center_x - vertebra_width // 2,
                y_pos - vertebra_height // 2,
                vertebra_width,
                vertebra_height
            )
            pygame.draw.rect(self.screen, color, rect, border_radius=4)
            
            # Draw harmonic label
            label = self.font_small.render(f"n={n}", True, config.COLOR_TEXT)
            self.screen.blit(label, (x + 5, y_pos - 6))
            
            # Draw frequency label on right
            freq_label = self.font_small.render(f"{freq:.1f}Hz", True, config.COLOR_TEXT)
            self.screen.blit(freq_label, (x + w - 60, y_pos - 6))
    
    def _draw_keyboard(self, x: int, y: int, w: int, h: int) -> None:
        """Draw the keyboard representation."""
        if not self.font_small:
            return
        
        # Draw background
        pygame.draw.rect(self.screen, (20, 20, 30), (x, y, w, h))
        
        # Calculate key dimensions
        key_count = config.KEYBOARD_KEYS
        key_width = (w - 40) / key_count
        key_height = h * 0.6
        keyboard_y = y + (h - key_height) // 2
        
        for i in range(key_count):
            midi_note = config.KEYBOARD_LOWEST_NOTE + i
            key_x = x + 20 + i * key_width
            
            # Determine if black or white key
            note_in_octave = midi_note % 12
            is_black = note_in_octave in [1, 3, 6, 8, 10]
            
            # Check if pressed
            is_pressed = midi_note in self.state.pressed_keys
            
            if is_pressed:
                color = config.COLOR_KEY_PRESSED
            elif is_black:
                color = config.COLOR_KEY_BLACK
            else:
                color = config.COLOR_KEY_WHITE
            
            # Draw key
            key_rect = pygame.Rect(
                key_x, keyboard_y,
                key_width - 2, key_height if not is_black else key_height * 0.6
            )
            pygame.draw.rect(self.screen, color, key_rect, border_radius=2)
            
            # Draw note name for C notes
            if note_in_octave == 0:
                octave = (midi_note // 12) - 1
                label = self.font_small.render(f"C{octave}", True, config.COLOR_TEXT)
                self.screen.blit(label, (key_x + 2, keyboard_y + key_height + 5))
    
    def _draw_cc_bar(self, x: int, y: int, w: int, h: int) -> None:
        """Draw CC status bar at bottom."""
        if not self.font_small:
            return
        
        # Background
        pygame.draw.rect(self.screen, config.COLOR_CC_BAR, (x, y, w, h))
        pygame.draw.line(self.screen, (60, 60, 80), (x, y), (x + w, y), 1)
        
        # Display key CC values
        cc_display = [
            ("Tolerance", 67),
            ("LFO Rate", 68),
            ("Mode", 22),
            ("AT Enable", 30),
        ]
        
        bar_y = y + 10
        bar_x = x + 20
        bar_width = 100
        bar_height = 8
        
        for i, (name, cc_num) in enumerate(cc_display):
            value = self.state.cc_values.get(cc_num, 64)
            
            # Label
            label = self.font_small.render(name, True, config.COLOR_TEXT)
            self.screen.blit(label, (bar_x, bar_y))
            
            # Value bar
            bar_rect = pygame.Rect(bar_x, bar_y + 15, bar_width, bar_height)
            pygame.draw.rect(self.screen, (40, 40, 55), bar_rect)
            
            fill_width = int(bar_width * (value / 127.0))
            fill_rect = pygame.Rect(bar_x, bar_y + 15, fill_width, bar_height)
            pygame.draw.rect(self.screen, config.COLOR_SPINE_ACTIVE, fill_rect)
            
            # Value text
            val_text = self.font_small.render(str(value), True, config.COLOR_TEXT)
            self.screen.blit(val_text, (bar_x + bar_width + 5, bar_y + 10))
            
            bar_x += bar_width + 80
    
    def _draw_energy_lines(self, spine_x: int, spine_y: int, spine_w: int, 
                           spine_h: int, kb_x: int, kb_w: int) -> None:
        """Draw bezier energy lines from keys to spine vertebrae."""
        f1 = self.state.f1
        visible_voices = self.state.get_all_visible_voices()
        
        key_width = (kb_w - 40) / config.KEYBOARD_KEYS
        keyboard_y = spine_y + spine_h * 0.5
        
        for voice in visible_voices:
            n = frequency_to_harmonic_index(voice.frequency, f1)
            if n is None or n > config.MAX_HARMONICS_DISPLAY:
                continue
            
            # Find corresponding key from voice_id
            # Voice IDs are assigned sequentially, we need to map back
            # For now, find any pressed key that might correspond
            spine_target_y = harmonic_to_y_position(
                round(n), config.MAX_HARMONICS_DISPLAY, spine_y + 20, spine_h - 40
            )
            
            # Draw from spine to each pressed key (copy to avoid race condition)
            for note in list(self.state.pressed_keys.keys()):
                key_index = note - config.KEYBOARD_LOWEST_NOTE
                if 0 <= key_index < config.KEYBOARD_KEYS:
                    key_x = kb_x + 20 + key_index * key_width + key_width / 2
                    
                    # Alpha based on glow
                    alpha = int(128 * voice.glow)
                    color = (*config.COLOR_SPINE_ACTIVE, alpha)
                    
                    # Draw simple line (bezier would require more complex drawing)
                    start = (spine_x + spine_w, spine_target_y)
                    end = (key_x, keyboard_y)
                    
                    # Create a surface with alpha for the line
                    line_surface = pygame.Surface((kb_w, spine_h), pygame.SRCALPHA)
                    pygame.draw.line(
                        line_surface,
                        color,
                        (0, spine_target_y - spine_y),
                        (key_x - spine_x - spine_w, keyboard_y - spine_y),
                        config.ENERGY_LINE_WIDTH
                    )
                    self.screen.blit(line_surface, (spine_x + spine_w, spine_y))
    
    def _draw_f1_indicator(self, x: int, y: int) -> None:
        """Draw f1 value indicator."""
        if not self.font:
            return
        
        text = f"f₁ = {self.state.f1:.1f} Hz"
        label = self.font.render(text, True, config.COLOR_SPINE_GLOW)
        self.screen.blit(label, (x, y))
