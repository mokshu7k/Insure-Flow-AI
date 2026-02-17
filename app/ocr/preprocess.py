"""
OCR Preprocessing Pipeline
Cleans and enhances images before OCR extraction
"""
import cv2
import numpy as np
from PIL import Image
import io
import logging
from typing import Union
from pathlib import Path

logger = logging.getLogger(__name__)


class OCRPreprocessor:
    """
    Image preprocessing for OCR accuracy improvement.

    Pipeline:
    1. Load image from bytes or path
    2. Convert to grayscale
    3. Deskew (correct rotation)
    4. Denoise
    5. Binarize (Otsu thresholding)
    6. Remove borders
    7. Return cleaned image for Tesseract
    """

    def preprocess(self, image_input: Union[bytes, str, Path]) -> np.ndarray:
        """
        Full preprocessing pipeline.

        Args:
            image_input: Raw image bytes, file path, or Path object

        Returns:
            Preprocessed numpy image array
        """
        # Load image
        image = self._load_image(image_input)

        # Step 1: Convert to grayscale
        gray = self._to_grayscale(image)

        # Step 2: Deskew
        deskewed = self._deskew(gray)

        # Step 3: Denoise
        denoised = self._denoise(deskewed)

        # Step 4: Binarize
        binary = self._binarize(denoised)

        # Step 5: Remove borders
        cleaned = self._remove_borders(binary)

        logger.debug("Image preprocessing complete")
        return cleaned

    def preprocess_for_pdf(self, page_image: np.ndarray) -> np.ndarray:
        """
        Lightweight preprocessing for PDF page images.
        Less aggressive than full pipeline.

        Args:
            page_image: Page image from PDF extraction

        Returns:
            Preprocessed numpy array
        """
        gray = self._to_grayscale(page_image)
        denoised = self._denoise(gray)
        binary = self._binarize(denoised)
        return binary

    # ─────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────

    def _load_image(self, image_input: Union[bytes, str, Path]) -> np.ndarray:
        """Load image from multiple source types"""
        if isinstance(image_input, (str, Path)):
            img = cv2.imread(str(image_input))
            if img is None:
                raise ValueError(f"Cannot read image from path: {image_input}")
            return img

        if isinstance(image_input, bytes):
            np_array = np.frombuffer(image_input, np.uint8)
            img = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
            if img is None:
                # Try Pillow as fallback
                pil_img = Image.open(io.BytesIO(image_input)).convert("RGB")
                img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            return img

        raise TypeError(f"Unsupported image input type: {type(image_input)}")

    def _to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """Convert to grayscale if not already"""
        if len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image

    def _deskew(self, gray: np.ndarray) -> np.ndarray:
        """
        Correct skewed (rotated) documents.
        Uses Hough line detection to detect and correct rotation angle.
        """
        try:
            coords = np.column_stack(np.where(gray > 0))
            if len(coords) < 10:
                return gray

            angle = cv2.minAreaRect(coords)[-1]

            # Normalize angle
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle

            # Skip if angle is negligible
            if abs(angle) < 0.5:
                return gray

            (h, w) = gray.shape
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(
                gray, M, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE
            )
            return rotated
        except Exception as e:
            logger.warning(f"Deskew failed, using original: {e}")
            return gray

    def _denoise(self, gray: np.ndarray) -> np.ndarray:
        """
        Remove noise using Non-Local Means Denoising.
        Preserves edges better than Gaussian blur for text.
        """
        return cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

    def _binarize(self, gray: np.ndarray) -> np.ndarray:
        """
        Convert to pure black/white using Otsu's thresholding.
        Adaptive thresholding handles uneven lighting (e.g., phone photos).
        """
        # Try adaptive thresholding first (better for photos)
        adaptive = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=31,
            C=10
        )

        # Otsu for comparison
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Use adaptive for low contrast images
        contrast = gray.std()
        return adaptive if contrast < 50 else otsu

    def _remove_borders(self, binary: np.ndarray) -> np.ndarray:
        """
        Remove dark borders around document scans.
        Uses contour detection to find the document boundary.
        """
        try:
            # Find contours
            contours, _ = cv2.findContours(
                binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            if not contours:
                return binary

            # Get largest contour (assumed to be the document)
            largest = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest)

            # Add small padding
            padding = 10
            x = max(0, x - padding)
            y = max(0, y - padding)
            w = min(binary.shape[1] - x, w + 2 * padding)
            h = min(binary.shape[0] - y, h + 2 * padding)

            # Only crop if result is reasonably large (>50% of original)
            if (w * h) > (0.5 * binary.shape[0] * binary.shape[1]):
                return binary[y:y + h, x:x + w]

            return binary
        except Exception as e:
            logger.warning(f"Border removal failed: {e}")
            return binary