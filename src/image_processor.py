"""Image processing module with mask functionality for Artie Scraper."""

import io
from pathlib import Path

from PIL import Image

import exceptions
from logger import LoggerSingleton as logger


class ImageProcessor:
    """Handles image processing operations including mask application."""

    def __init__(self):
        """Initialize the image processor."""
        self.supported_formats = {".png", ".jpg", ".jpeg"}
        logger.log_info("Image processor initialized")

    def apply_mask(
        self, image_data: bytes, mask_path: str, resize_mask: bool = True
    ) -> bytes:
        """
        Apply a mask to image data.

        Args:
            image_data: Original image data as bytes
            mask_path: Path to the mask image file
            resize_mask: Whether to resize mask to match image dimensions

        Returns:
            Processed image data as bytes

        Raises:
            ImageProcessingError: If processing fails
        """
        try:
            # Validate mask file exists
            mask_file = Path(mask_path)
            if not mask_file.exists():
                raise exceptions.MediaProcessingError(
                    f"Mask file not found: {mask_path}"
                )

            # Load original image from bytes
            try:
                original_image = Image.open(io.BytesIO(image_data))
                # Convert to RGBA to ensure alpha channel support
                if original_image.mode != "RGBA":
                    original_image = original_image.convert("RGBA")
            except Exception as e:
                raise exceptions.MediaProcessingError(
                    f"Failed to load original image: {e}"
                )

            # Load mask image
            try:
                mask_image = Image.open(mask_path)
                # Convert mask to RGBA
                if mask_image.mode != "RGBA":
                    mask_image = mask_image.convert("RGBA")
            except Exception as e:
                raise exceptions.MediaProcessingError(
                    f"Failed to load mask image from {mask_path}: {e}"
                )

            # Resize mask to match original image dimensions if requested
            if resize_mask and mask_image.size != original_image.size:
                logger.log_debug(
                    f"Resizing mask from {mask_image.size} to " f"{original_image.size}"
                )
                mask_image = mask_image.resize(
                    original_image.size, Image.Resampling.LANCZOS
                )

            # Apply mask using alpha compositing
            try:
                # Create a new image with the original as base
                result_image = original_image.copy()

                # Composite the mask over the original image
                result_image = Image.alpha_composite(result_image, mask_image)

                logger.log_debug(f"Successfully applied mask {mask_path} to image")

            except Exception as e:
                raise exceptions.MediaProcessingError(f"Failed to apply mask: {e}")

            # Convert back to bytes
            return self._image_to_bytes(result_image)

        except exceptions.MediaProcessingError:
            raise
        except Exception as e:
            logger.log_error(f"Unexpected error applying mask: {e}")
            raise exceptions.MediaProcessingError(f"Mask application failed: {e}")

    def _image_to_bytes(self, image: Image.Image, format: str = "PNG") -> bytes:
        """
        Convert PIL Image to bytes.

        Args:
            image: PIL Image object
            format: Output format (PNG, JPEG)

        Returns:
            Image data as bytes
        """
        try:
            output_buffer = io.BytesIO()

            # Handle format-specific conversions
            if format.upper() == "JPEG":
                # JPEG doesn't support transparency, convert to RGB
                if image.mode == "RGBA":
                    # Create white background for transparency
                    background = Image.new("RGB", image.size, (255, 255, 255))
                    # Use alpha as mask
                    background.paste(image, mask=image.split()[-1])
                    image = background
                elif image.mode != "RGB":
                    image = image.convert("RGB")

            image.save(output_buffer, format=format, optimize=True)
            return output_buffer.getvalue()

        except Exception as e:
            raise exceptions.MediaProcessingError(
                f"Failed to convert image to bytes: {e}"
            )

    def process_image_with_mask(self, image_data: bytes, mask_config: dict) -> bytes:
        """
        Process image with mask based on configuration.

        Args:
            image_data: Original image data as bytes
            mask_config: Mask configuration dictionary

        Returns:
            Processed image data as bytes, or original data if mask
            processing fails
        """
        try:
            if not mask_config.get("apply_mask", False):
                logger.log_debug("Mask processing disabled in configuration")
                return image_data

            mask_path = mask_config.get("mask_path")
            if not mask_path:
                logger.log_warning("Mask path not specified in configuration")
                return image_data

            logger.log_info(f"Applying mask from {mask_path}")
            return self.apply_mask(
                image_data, mask_path, resize_mask=mask_config.get("resize_mask", True)
            )

        except exceptions.MediaProcessingError as e:
            logger.log_error(f"Mask processing failed: {e}")
            logger.log_warning("Falling back to original image")
            return image_data
        except Exception as e:
            logger.log_error(f"Unexpected error in mask processing: {e}")
            logger.log_warning("Falling back to original image")
            return image_data

    def validate_mask_file(self, mask_path: str) -> bool:
        """
        Validate that a mask file exists and is a valid image.

        Args:
            mask_path: Path to mask file

        Returns:
            True if valid, False otherwise
        """
        try:
            mask_file = Path(mask_path)

            # Check if file exists
            if not mask_file.exists():
                logger.log_warning(f"Mask file does not exist: {mask_path}")
                return False

            # Check file extension
            if mask_file.suffix.lower() not in self.supported_formats:
                logger.log_warning(f"Unsupported mask file format: {mask_file.suffix}")
                return False

            # Try to open the image to validate it
            try:
                with Image.open(mask_path) as img:
                    # Just verify we can load it
                    img.verify()
                logger.log_debug(f"Mask file validated successfully: {mask_path}")
                return True

            except Exception as e:
                logger.log_warning(f"Invalid mask image file {mask_path}: {e}")
                return False

        except Exception as e:
            logger.log_warning(f"Error validating mask file {mask_path}: {e}")
            return False


# Global instance for easy access
_image_processor = None


def get_image_processor() -> ImageProcessor:
    """Get the global image processor instance."""
    global _image_processor
    if _image_processor is None:
        _image_processor = ImageProcessor()
    return _image_processor
