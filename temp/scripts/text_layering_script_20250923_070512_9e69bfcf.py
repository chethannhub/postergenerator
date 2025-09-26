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
        font_size_headline = int(height / 12)  # Dynamic font size for headline
        font_size_subhead = int(height / 20)  # Dynamic font size for subhead
        font_size_cta = int(height / 25)  # Dynamic font size for CTA

        # Define font and color properties
        primary_font = "Impact"
        fallback_font = "Segoe UI"
        text_color = (1, 1, 1)  # White color
        shadow_color = (0, 0, 0, 0.5)  # Black shadow with some transparency

        # Function to draw text with shadow
        def draw_text_with_effects(text, x, y, font_size):
            # Draw shadow
            context.select_font_face(primary_font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            context.set_font_size(font_size)
            context.set_source_rgba(*shadow_color)
            context.move_to(x + 2, y + 2)  # Offset for shadow
            context.show_text(text)

            # Draw text
            context.set_source_rgba(*text_color)
            context.move_to(x, y)
            context.show_text(text)

        # Positioning texts with safe margins
        draw_text_with_effects(texts[0], width * 0.1, height * 0.1, font_size_headline)  # Top-left
        draw_text_with_effects(texts[1], width * 0.1, height * 0.2, font_size_subhead)  # Below first text
        draw_text_with_effects(texts[2], width * 0.1, height * 0.3, font_size_cta)  # Below second text

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
        main('E:\\postergenerator\\temp\\images\\correction_input_20250923_070511_2f627a9f.png', 'E:\\postergenerator\\temp\\images\\correction_output_20250923_070511_0eb2aaec.png', '1. Create a Diwali poster with an happy family enjoying fireworks infront of their house.\r\n2. \u20604 member family with 2 adults and 2 kids.\r\n3. \u2060A blue Hyundai Verna is parked to the right side of their house.\r\n4. \u2060Fireworks are reflected on its windshield as if its participating in the\xa0celebration.')
        print("SUCCESS: Script executed successfully")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
