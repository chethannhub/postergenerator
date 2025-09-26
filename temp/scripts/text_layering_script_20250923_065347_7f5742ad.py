import cairo
import os
from PIL import Image

def add_text_overlay(input_image_path, output_image_path, user_prompt):
    try:
        # Load the image
        original_image = Image.open(input_image_path)
        width, height = original_image.size

        # Create a Cairo surface to draw on
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        context = cairo.Context(surface)

        # Draw the original image onto the surface
        context.set_source_surface(cairo.ImageSurface.create_from_png(input_image_path), 0, 0)
        context.paint()

        # Define text to add based on user prompt
        text = "Happy Diwali"
        subtext = "Celebrate with Joy!"
        
        # Set font parameters
        font_family = "Segoe UI"
        context.select_font_face(font_family, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        
        # Determine font size based on image dimensions
        font_size = min(width, height) // 15
        context.set_font_size(font_size)

        # Calculate text position for main text
        text_extents = context.text_extents(text)
        x_text = (width - text_extents[2]) / 2
        y_text = height * 0.1

        # Set text color with a gradient
        gradient = cairo.LinearGradient(0, 0, 0, height)
        gradient.add_color_stop_rgb(0, 1, 0.5, 0)  # Greenish color
        gradient.add_color_stop_rgb(1, 1, 1, 0)    # Yellowish color
        context.set_source(gradient)

        # Draw the main text with shadow
        context.save()
        context.set_source_rgba(0, 0, 0, 0.5)  # Shadow color
        context.move_to(x_text + 2, y_text + 2)  # Shadow position
        context.show_text(text)
        context.restore()

        # Draw the main text
        context.move_to(x_text, y_text)
        context.show_text(text)

        # Draw subtext
        context.select_font_face("Segoe UI", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(font_size * 0.75)  # Smaller font size for subtext
        subtext_extents = context.text_extents(subtext)
        x_subtext = (width - subtext_extents[2]) / 2
        y_subtext = y_text + text_extents[3] + 10  # Position below main text

        # Draw the subtext with shadow
        context.save()
        context.set_source_rgba(0, 0, 0, 0.5)  # Shadow color
        context.move_to(x_subtext + 2, y_subtext + 2)  # Shadow position
        context.show_text(subtext)
        context.restore()

        # Draw the subtext
        context.move_to(x_subtext, y_subtext)
        context.set_source_rgb(1, 1, 1)  # White color for subtext
        context.show_text(subtext)

        # Save the final result
        surface.write_to_png(output_image_path)

    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
input_image_path = "path/to/input/image.png"
output_image_path = "path/to/output/image.png"
user_prompt = "Happy Diwali"
add_text_overlay(input_image_path, output_image_path, user_prompt)

if __name__ == "__main__":
    try:
        main('E:\\postergenerator\\temp\\images\\dynamic_input_20250923_065304_901c9876.png', 'E:\\postergenerator\\temp\\images\\dynamic_output_20250923_065304_2c53b3f5.png', '1. Create a Diwali poster with an happy family enjoying fireworks infront of their house.\r\n2. \u20604 member family with 2 adults and 2 kids.\r\n3. \u2060A blue Hyundai Verna is parked to the right side of their house.\r\n4. \u2060Fireworks are reflected on its windshield as if its participating in the\xa0celebration.')
        print("SUCCESS: Script executed successfully")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
