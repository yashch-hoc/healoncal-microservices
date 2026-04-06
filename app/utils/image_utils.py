"""
Image Processing Utilities

Centralized image processing functions to avoid code duplication.
"""
import base64
import logging
from typing import Union, Optional
from PIL import Image
import io

logger = logging.getLogger(__name__)

def decode_base64_image(image_data: Union[str, bytes]) -> bytes:
    """
    Decode base64 image data to bytes.
    
    Args:
        image_data: Base64 string or bytes
        
    Returns:
        Decoded image bytes
    """
    try:
        if isinstance(image_data, str):
            # Handle data URL format (data:image/jpeg;base64,...)
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            return base64.b64decode(image_data)
        elif isinstance(image_data, bytes):
            return image_data
        else:
            raise ValueError("Invalid image data type")
    except Exception as e:
        logger.error(f"Failed to decode base64 image: {str(e)}")
        raise

def encode_image_to_base64(image_path: str) -> str:
    """
    Encode image file to base64 string.
    
    Args:
        image_path: Path to image file
        
    Returns:
        Base64 encoded image string
    """
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to encode image {image_path}: {str(e)}")
        raise

def validate_image_data(image_data: Union[str, bytes]) -> bool:
    """
    Validate if image data is properly formatted.
    
    Args:
        image_data: Image data to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        if isinstance(image_data, str):
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            # Try to decode to check if it's valid base64
            base64.b64decode(image_data)
        elif isinstance(image_data, bytes):
            # Try to open as image to validate
            Image.open(io.BytesIO(image_data))
        else:
            return False
        return True
    except Exception:
        return False

def resize_image_for_analysis(image_path: str, max_size: int = 512) -> str:
    """
    Resize image to optimal size for analysis.
    
    Args:
        image_path: Path to image file
        max_size: Maximum dimension size
        
    Returns:
        Path to resized image
    """
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize maintaining aspect ratio
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Save to temporary file
            temp_path = image_path.replace('.jpg', '_resized.jpg')
            img.save(temp_path, 'JPEG', quality=85)
            return temp_path
    except Exception as e:
        logger.error(f"Failed to resize image {image_path}: {str(e)}")
        return image_path  # Return original if resize fails

def cleanup_temp_image(temp_path: str, original_path: str) -> None:
    """
    Clean up temporary image file.
    
    Args:
        temp_path: Path to temporary file
        original_path: Path to original file
    """
    try:
        if temp_path != original_path and temp_path:
            import os
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    except Exception as e:
        logger.warning(f"Failed to cleanup temp image {temp_path}: {str(e)}")
