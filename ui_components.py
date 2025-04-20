import pygame
import time

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
LIGHT_GRAY = (230, 230, 230)
DARK_GRAY = (100, 100, 100)
GREEN = (100, 200, 100)
BLUE = (100, 150, 255)
RED = (255, 100, 100)
DARK_GREEN = (0, 150, 0)

class UIComponents:
    def __init__(self, screen, fonts):
        self.screen = screen
        self.font = fonts['normal']
        self.small_font = fonts['small']
        self.title_font = fonts['title']
        self.cursor_visible = True
        self.last_cursor_toggle = 0
        self.copy_button_state = {}  # To track button states
        self.popup_message = None
        self.popup_timer = 0
        self.popup_duration = 2.0
    
    def draw_button(self, text, rect, color=BLUE, text_color=WHITE, button_id=None):
        """Draw a button with text"""
        # If this is a copy button in "copied" state, draw a checkmark instead
        if button_id and button_id in self.copy_button_state and self.copy_button_state[button_id]:
            # Draw checkmark button
            pygame.draw.rect(self.screen, DARK_GREEN, rect, border_radius=5)
            check_text = "✓"
            text_surf = self.font.render(check_text, True, text_color)
            text_rect = text_surf.get_rect(center=rect.center)
            self.screen.blit(text_surf, text_rect)
        else:
            # Draw normal button
            pygame.draw.rect(self.screen, color, rect, border_radius=5)
            text_surf = self.font.render(text, True, text_color)
            text_rect = text_surf.get_rect(center=rect.center)
            self.screen.blit(text_surf, text_rect)
    
    def draw_circle_button(self, center, radius, color):
        """Draw a circular button"""
        pygame.draw.circle(self.screen, color, center, radius)
    
    def draw_input_box(self, rect, text, active):
        """Draw an input text box with blinking cursor"""
        # Update cursor state every 0.5 seconds
        current_time = time.time()
        if current_time - self.last_cursor_toggle > 0.5:
            self.cursor_visible = not self.cursor_visible
            self.last_cursor_toggle = current_time
        
        # Draw the input box
        color = BLUE if active else LIGHT_GRAY
        pygame.draw.rect(self.screen, color, rect, border_radius=5)
        pygame.draw.rect(self.screen, BLACK, rect, 2, border_radius=5)
        
        # Draw the text
        font_surface = self.font.render(text, True, BLACK)
        self.screen.blit(font_surface, (rect.x + 10, rect.y + (rect.h - font_surface.get_height()) // 2))
        
        # Draw blinking cursor if active and cursor should be visible
        if active and self.cursor_visible:
            # Calculate cursor position after text
            text_width = self.font.size(text)[0]
            cursor_x = rect.x + 10 + text_width
            cursor_y_start = rect.y + (rect.h - font_surface.get_height()) // 2
            cursor_y_end = cursor_y_start + font_surface.get_height()
            pygame.draw.line(self.screen, BLACK, (cursor_x, cursor_y_start), (cursor_x, cursor_y_end), 2)
    
    def set_copy_button_state(self, button_id, state):
        """Set the state of a copy button"""
        self.copy_button_state[button_id] = state
    
    def draw_logs(self, log_area, log_messages):
        """Draw log messages area"""
        pygame.draw.rect(self.screen, LIGHT_GRAY, log_area, border_radius=5)
        
        title_surf = self.font.render("Logs", True, BLACK)
        self.screen.blit(title_surf, (log_area.x + 10, log_area.y + 5))
        
        y_offset = log_area.y + 40
        for log in log_messages[-5:]:  # Show only last 5 logs
            log_surf = self.small_font.render(log, True, DARK_GRAY)
            self.screen.blit(log_surf, (log_area.x + 15, y_offset))
            y_offset += 20
    
    def show_popup(self, message, duration=2.0):
        """Show a popup notification message"""
        self.popup_message = message
        self.popup_timer = time.time()
        self.popup_duration = duration
    
    def draw_popup(self):
        """Draw popup message if active"""
        if self.popup_message and time.time() - self.popup_timer < self.popup_duration:
            # Create a semi-transparent background
            # Increase minimum width and calculate based on text length
            text_width = self.font.size(self.popup_message)[0]
            popup_width = max(text_width + 60, 300)  # At least 300px wide or text width + padding
            popup_height = 60
            popup_rect = pygame.Rect(
                self.screen.get_width()//2 - popup_width//2,
                self.screen.get_height()//2 - 100,
                popup_width,
                popup_height
            )
            
            # Draw popup background with shadow
            shadow_rect = popup_rect.copy()
            shadow_rect.x += 5
            shadow_rect.y += 5
            pygame.draw.rect(self.screen, (50, 50, 50, 180), shadow_rect, border_radius=10)
            pygame.draw.rect(self.screen, (240, 240, 240), popup_rect, border_radius=10)
            pygame.draw.rect(self.screen, (100, 100, 100), popup_rect, 2, border_radius=10)
            
            # Draw message
            text_surf = self.font.render(self.popup_message, True, (0, 0, 0))
            self.screen.blit(text_surf, (popup_rect.x + popup_rect.width//2 - text_surf.get_width()//2, 
                                        popup_rect.y + popup_rect.height//2 - text_surf.get_height()//2))