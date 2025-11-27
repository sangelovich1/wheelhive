#!/usr/bin/env python3
"""
EasyOCR JSON API Server

Provides OCR services via HTTP JSON API.
Runs on jedi.local with GPU acceleration.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.

Endpoints:
  POST /ocr - Extract text from image
    Request: {"image_url": "https://..."}
    Response: {"success": true, "text": "...", "lines": [...], "processing_time_ms": 123}

  GET /health - Health check
    Response: {"status": "ok", "gpu_available": true}
"""

import io
import logging
import time
from typing import Any

import easyocr
import requests
from flask import Flask, jsonify, request
from PIL import Image


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Global EasyOCR reader (initialized once)
reader: Any = None


def init_reader() -> Any:
    """Initialize EasyOCR reader with GPU support"""
    global reader
    if reader is None:
        logger.info("Initializing EasyOCR reader (this may take a moment)...")
        reader = easyocr.Reader(["en"], gpu=True)
        logger.info("EasyOCR reader initialized successfully")
    return reader


def process_image_url(image_url: str) -> Image.Image:
    """Download image from URL"""
    logger.info(f"Downloading image from URL: {image_url[:100]}...")
    response = requests.get(image_url, timeout=30)
    response.raise_for_status()
    return Image.open(io.BytesIO(response.content))


def extract_text(image: Image.Image) -> dict[str, Any]:
    """Extract text from image using EasyOCR"""
    start_time = time.time()

    # Save to temporary file (EasyOCR works with file paths)
    with io.BytesIO() as temp_buffer:
        image.save(temp_buffer, format="PNG")
        temp_buffer.seek(0)

        # Save to temp file
        temp_path = "/tmp/easyocr_temp.png"
        with open(temp_path, "wb") as f:
            f.write(temp_buffer.read())

    # Run OCR
    logger.info("Running EasyOCR...")
    results = reader.readtext(temp_path)

    # Extract text and confidence scores
    lines = []
    for bbox, text, confidence in results:
        lines.append({"text": text, "confidence": float(confidence)})

    # Combine all text
    full_text = "\n".join([line["text"] for line in lines])

    processing_time_ms = int((time.time() - start_time) * 1000)

    logger.info(f"OCR complete: {len(lines)} lines, {len(full_text)} chars, {processing_time_ms}ms")

    return {
        "text": full_text,
        "lines": lines,
        "line_count": len(lines),
        "char_count": len(full_text),
        "processing_time_ms": processing_time_ms,
    }


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    try:
        # Check if reader is initialized
        init_reader()

        # Check GPU availability
        import torch

        gpu_available = torch.cuda.is_available()

        return jsonify(
            {
                "status": "ok",
                "gpu_available": gpu_available,
                "cuda_devices": torch.cuda.device_count() if gpu_available else 0,
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/ocr", methods=["POST"])
def ocr():
    """OCR endpoint - extract text from image"""
    try:
        # Ensure reader is initialized
        init_reader()

        # Get request data
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        # Get image from URL
        if "image_url" not in data:
            return jsonify({"error": "image_url required"}), 400

        image = process_image_url(data["image_url"])

        # Extract text
        result = extract_text(image)

        return jsonify({"success": True, **result})

    except requests.RequestException as e:
        logger.error(f"Failed to download image: {e}")
        return jsonify({"success": False, "error": f"Failed to download image: {e!s}"}), 400
    except Exception as e:
        logger.error(f"OCR failed: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/", methods=["GET"])
def index():
    """Root endpoint - API info"""
    return jsonify(
        {
            "name": "EasyOCR JSON API Server",
            "version": "1.0.0",
            "endpoints": {
                "GET /health": "Health check",
                "POST /ocr": "Extract text from image (image_url required)",
                "GET /": "This message",
            },
        }
    )


if __name__ == "__main__":
    # Initialize reader on startup
    logger.info("Starting EasyOCR JSON API Server...")
    init_reader()

    # Run Flask server
    # Use 0.0.0.0 to allow external connections
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)
