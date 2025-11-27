# EasyOCR JSON API Server

GPU-accelerated OCR service for trading screenshot text extraction.

## Features

- GPU accelerated (CUDA)
- Sub-second processing (0.15-0.91s average)
- 100% reliable (no timeouts, no hallucinations)
- Simple JSON API

## Installation

```bash
# Install Flask dependency in existing venv
cd ~/code/easyocr
source .venv/bin/activate
pip install flask requests

# Copy server file to your project
mkdir -p $PROJECT_DIR/src/easyocr_server
cp server.py $PROJECT_DIR/src/easyocr_server/

# Install systemd service (edit paths in service file first)
sudo cp $PROJECT_DIR/src/easyocr_server/easyocr-server.service /etc/systemd/system/
sudo nano /etc/systemd/system/easyocr-server.service  # Update paths
sudo systemctl daemon-reload
sudo systemctl enable easyocr-server
sudo systemctl start easyocr-server

# Check status
sudo systemctl status easyocr-server
```

## API Endpoints

### POST /ocr

Extract text from image.

**Request:**
```json
{
  "image_url": "https://cdn.discordapp.com/attachments/.../image.png"
}
```

**Response:**
```json
{
  "success": true,
  "text": "Sell MSTX $7 Put 11/14\n$150.00\n15 contracts at $0.10",
  "lines": [
    {"text": "Sell MSTX $7 Put 11/14", "confidence": 0.95},
    {"text": "$150.00", "confidence": 0.98},
    {"text": "15 contracts at $0.10", "confidence": 0.97}
  ],
  "line_count": 3,
  "char_count": 58,
  "processing_time_ms": 180
}
```

### GET /health

Health check.

**Response:**
```json
{
  "status": "ok",
  "gpu_available": true,
  "cuda_devices": 1
}
```

## Usage Example

```bash
# Test from command line (replace <ocr-server> with your GPU server hostname)
curl -X POST http://<ocr-server>:5001/ocr \
  -H "Content-Type: application/json" \
  -d '{"image_url": "https://cdn.discordapp.com/attachments/.../image.png"}'

# Health check
curl http://<ocr-server>:5001/health
```

## Python Client Example

```python
import requests

OCR_SERVER = "http://<ocr-server>:5001"  # Your GPU server hostname

response = requests.post(
    f'{OCR_SERVER}/ocr',
    json={'image_url': 'https://cdn.discordapp.com/...'}
)

result = response.json()
print(result['text'])
```

## Service Management

```bash
# Start service
sudo systemctl start easyocr-server

# Stop service
sudo systemctl stop easyocr-server

# Restart service
sudo systemctl restart easyocr-server

# View logs
sudo journalctl -u easyocr-server -f

# Check status
sudo systemctl status easyocr-server
```

## Performance

Based on testing with 10 trading screenshots:

- **Success rate:** 100% (10/10 images)
- **Processing time:** 0.15-0.91s (avg 0.27s)
- **Accuracy:** No hallucinations, no missing data
- **GPU:** CUDA accelerated

## Architecture

- **Server:** Flask (single-threaded, GPU serialization)
- **OCR Engine:** EasyOCR 1.7.2
- **Backend:** PyTorch 2.9.0 + CUDA
- **Port:** 5001
- **Host:** 0.0.0.0 (accepts external connections)
