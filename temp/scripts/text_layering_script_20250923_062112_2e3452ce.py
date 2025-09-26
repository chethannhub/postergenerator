import cairo
import os
from PIL import Image

def main(input_image_path, output_image_path, user_prompt):
    try:
        # Load the image using PIL
        image = Image.open(input_image_path)
        width, height = image.size

        # Create a Cairo surface
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        context = cairo.Context(surface)

        # Draw the loaded image onto the Cairo context
        context.set_source_surface(cairo.ImageSurface.create_from_png(input_image_path), 0, 0)
        context.paint()

        # Define the text to be added based on the user prompt
        text = "Happy Diwali!"
        subtext = "Celebrate with Joy"

        # Set font and sizes
        context.select_font_face("Impact", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        context.set_font_size(80)  # Adjusted size for better fit
        
        # Calculate the position for the main text
        text_extents = context.text_extents(text)
        x_main = (width - text_extents.width) / 2
        y_main = height * 0.1  # Adjusted for better placement

        # Set text color and create shadow effect
        context.set_source_rgba(0, 0, 0, 0.6)  # Shadow color
        context.move_to(x_main + 2, y_main + 2)
        context.show_text(text)

        # Draw the main text
        context.set_source_rgba(1, 0.84, 0, 1)  # Gold color
        context.move_to(x_main, y_main)
        context.show_text(text)

        # Set font for the subtext
        context.select_font_face("Segoe UI", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(50)  # Adjusted size for better fit

        # Calculate position for the subtext
        subtext_extents = context.text_extents(subtext)
        x_sub = (width - subtext_extents.width) / 2
        y_sub = y_main + 100;  # Adjusted for better placement

        # Create shadow for subtext
        context.set_source_rgba(0, 0, 0, 0.6)  # Shadow color
        context.move_to(x_sub + 1, y_sub + 1)
        context.show_text(subtext)

        # Draw the subtext
        context.set_source_rgba(1, 0.84, 0, 1)  # Gold color
        context.move_to(x_sub, y_sub)
        context.show_text(subtext)

        # Save the final result
        surface.write_to_png(output_image_path)
        print(f"Poster saved to: {output_image_path}")

    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
input_image_path = 'diwali_poster_input.png'  # Path to input image
output_image_path = 'diwali_poster_output.png'  # Path to save output image
user_prompt = "Add Diwali greetings"
main(input_image_path, output_image_path, user_prompt)

if __name__ == "__main__":
    try:
        main('E:\\postergenerator\\temp\\images\\correction_input_20250923_062111_f5c627ee.png', 'E:\\postergenerator\\temp\\images\\correction_output_20250923_062111_00b1d908.png', '1. Create a Diwali poster with an happy family enjoying fireworks infront of their house.\r\n2. \u20604 member family with 2 adults and 2 kids.\r\n3. \u2060A blue Hyundai Verna is parked to the right side of their house.\r\n4. \u2060Fireworks are reflected on its windshield as if its participating in the\xa0celebration.')
        print("SUCCESS: Script executed successfully")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
