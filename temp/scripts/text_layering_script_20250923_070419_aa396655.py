import os
import cairo
from PIL import Image

def main(input_image_path, output_image_path, user_prompt):
    try:
        # Load the image
        image = Image.open(input_image_path)
        width, height = image.size

        # Create a Cairo surface to draw on
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        context = cairo.Context(surface)

        # Draw the image onto the Cairo surface
        context.set_source_surface(cairo.ImageSurface.create_from_png(input_image_path), 0, 0)
        context.paint()

        # Define text properties
        texts = ["Happy Diwali!", "Celebrate Joy", "Family & Fireworks"]
        font_size = int(height / 12)  # Dynamic font size based on image height

        # Define font and color properties
        primary_font = "Impact"
        fallback_font = "Segoe UI"
        text_color = (1, 1, 1)  # White color
        shadow_color = (0, 0, 0, 0.5)  # Black shadow with some transparency
        gradient_color = cairo.LinearGradient(0, height, 0, 0)
        gradient_color.add_color_stop_rgb(0, 0.2, 0.3, 0.6)  # Light blue
        gradient_color.add_color_stop_rgb(1, 0.1, 0.1, 0.5)  # Dark blue

        # Function to draw text with shadow and gradient
        def draw_text_with_effects(text, x, y):
            # Draw shadow
            context.select_font_face(primary_font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            context.set_font_size(font_size)
            context.set_source_rgba(*shadow_color)
            context.move_to(x + 2, y + 2)  # Offset for shadow
            context.show_text(text)

            # Draw text
            context.set_source(gradient_color)
            context.move_to(x, y)
            context.show_text(text)

        # Positioning texts
        draw_text_with_effects(texts[0], width * 0.1, height * 0.1)  # Top-left
        draw_text_with_effects(texts[1], width * 0.1, height * 0.2)  # Below first text
        draw_text_with_effects(texts[2], width * 0.1, height * 0.3)  # Below second text

        # Save the final image
        surface.write_to_png(output_image_path)

        print(f"Image saved as {output_image_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
input_image_path = "path/to/your/input_image.png"
output_image_path = "path/to/your/output_image.png"
user_prompt = "Create a Diwali poster with a happy family."
main(input_image_path, output_image_path, user_prompt)

if __name__ == "__main__":
    try:
        main('E:\\postergenerator\\temp\\images\\dynamic_input_20250923_070341_80248abb.png', 'E:\\postergenerator\\temp\\images\\dynamic_output_20250923_070341_98eca0fc.png', '1. Create a Diwali poster with an happy family enjoying fireworks infront of their house.\r\n2. \u20604 member family with 2 adults and 2 kids.\r\n3. \u2060A blue Hyundai Verna is parked to the right side of their house.\r\n4. \u2060Fireworks are reflected on its windshield as if its participating in the\xa0celebration.')
        print("SUCCESS: Script executed successfully")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
