import requests
from PIL import Image
import numpy as np
from collections import Counter
from io import BytesIO
import colorsys


def download_image(url):
    """Download image from URL and return PIL Image object"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        raise Exception(f"Failed to download image: {str(e)}")


def rgb_to_brightness(r, g, b):
    """Calculate brightness using luminance formula"""
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def get_dominant_color(image, brightness_threshold=0.3, sample_size=1000):
    """
    Extract the most dominant color from an image that's brighter than threshold

    Args:
        image: PIL Image object
        brightness_threshold: Minimum brightness (0-1, where 1 is white)
        sample_size: Number of pixels to sample for performance

    Returns:
        tuple: (R, G, B) values of dominant color, or None if no color meets threshold
    """
    # Convert to RGB if necessary
    if image.mode != 'RGB':
        image = image.convert('RGB')

    # Resize image for faster processing if it's large
    max_dimension = 300
    if max(image.size) > max_dimension:
        ratio = max_dimension / max(image.size)
        new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)

    # Get pixel data
    pixels = list(image.getdata())

    # Sample pixels if image is still large
    if len(pixels) > sample_size:
        import random
        pixels = random.sample(pixels, sample_size)

    # Filter pixels by brightness threshold
    bright_pixels = []
    for pixel in pixels:
        r, g, b = pixel[:3]  # Handle RGBA images
        brightness = rgb_to_brightness(r, g, b)
        if brightness >= brightness_threshold:
            bright_pixels.append((r, g, b))

    if not bright_pixels:
        return None

    # Count occurrences of each color
    color_counts = Counter(bright_pixels)

    # Return most common color other than white
    dominant_color = color_counts.most_common(1)[0][0]
    # if white is the dominant color it might be the background, so check there isn't another color we
    # can use
    if dominant_color == (255, 255, 255) and len(color_counts)>1:
        best_two_colors = color_counts.most_common(2)
        white_count = best_two_colors[0][1]
        next_count = best_two_colors[1][1]
        if next_count > white_count * 0.1:
            dominant_color = best_two_colors[1][0]
    return dominant_color


def color_to_hex(rgb):
    """Convert RGB tuple to hex string"""
    if rgb is None:
        return None
    return "#{:02x}{:02x}{:02x}".format(rgb[0], rgb[1], rgb[2])


def extract_dominant_color_from_url(url, brightness_threshold=0.3):
    """
    Main function to extract dominant color from image URL

    Args:
        url: Image URL
        brightness_threshold: Minimum brightness (0-1)

    Returns:
        dict: Contains RGB values, hex code, and brightness info
    """
    try:
        # Download and process image
        image = download_image(url)
        dominant_rgb = get_dominant_color(image, brightness_threshold)

        if dominant_rgb is None:
            return {
                'success': False,
                'error': f'No colors found above brightness threshold {brightness_threshold}'
            }

        # Calculate actual brightness of dominant color
        actual_brightness = rgb_to_brightness(*dominant_rgb)

        return {
            'success': True,
            'rgb': dominant_rgb,
            'hex': color_to_hex(dominant_rgb),
            'brightness': round(actual_brightness, 3),
            'brightness_threshold': brightness_threshold
        }

    except Exception as e:
        return None


# Example usage
if __name__ == "__main__":
    # Example URL (replace with your image URL)
    image_url = "https://media.api-sports.io/football/teams/170.png"

    # Extract dominant color with brightness threshold of 0.4 (40%)
    result = extract_dominant_color_from_url(image_url, brightness_threshold=0.25)

    if result['success']:
        print(f"Dominant color: RGB{result['rgb']}")
        print(f"Hex code: {result['hex']}")
        print(f"Brightness: {result['brightness']:.1%}")
    else:
        print(f"Error: {result['error']}")

    # Try with different thresholds
    print("\n--- Testing different brightness thresholds ---")
    thresholds = [0.2, 0.4, 0.6, 0.8]

    for threshold in thresholds:
        result = extract_dominant_color_from_url(image_url, threshold)
        if result['success']:
            print(f"Threshold {threshold:.1%}: {result['hex']} (brightness: {result['brightness']:.1%})")
        else:
            print(f"Threshold {threshold:.1%}: {result['error']}")