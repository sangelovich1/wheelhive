# Vision Model Comparison for Trading Screenshot OCR

## Objective
Find a privacy-focused, self-hosted vision model that can replace Claude Sonnet 4.5 for extracting trade data from Discord screenshots.

## Current Setup
- **Model**: Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`)
- **Performance**: ~2s per image, excellent OCR quality
- **Cost**: $0.003 per image
- **Privacy**: ❌ Images sent to Anthropic's servers

## Top 5 Ollama Vision Model Candidates

### 1. **llama3.2-vision:11b** 🥇
- **Size**: ~7-8 GB
- **Strengths**:
  - State-of-the-art performance (competes with GPT-4V)
  - Excellent for complex documents and visual reasoning
  - High accuracy for financial document OCR
  - Can extract tabular data and format as Markdown
- **Weaknesses**: Larger model, slightly slower inference
- **Best For**: Complex trading screenshots with tables, charts, multiple data points
- **Ollama Command**: `ollama pull llama3.2-vision:11b`

### 2. **granite3.2-vision:2b** 🎯
- **Size**: ~2 GB (very compact)
- **Strengths**:
  - **Specifically designed for visual document understanding**
  - Optimized for tables, charts, infographics, diagrams
  - Fast inference due to small size
  - Built for structured data extraction
- **Weaknesses**: May have lower accuracy on complex scenes vs larger models
- **Best For**: Trading screenshots with clear text/tables (Robinhood, Fidelity confirmations)
- **Ollama Command**: `ollama pull granite3.2-vision:2b`
- **Notes**: IBM's specialized document-focused model

### 3. **minicpm-v:8b** ⚡
- **Size**: ~5-6 GB
- **Strengths**:
  - Surpasses GPT-4V-1106, Gemini Pro, Claude 3 in benchmarks
  - Excellent multilingual capabilities
  - Handles images up to 1.8M pixels (any aspect ratio)
  - Strong on OCR tasks
- **Weaknesses**: Less documentation/community support
- **Best For**: High-quality OCR with good performance/size ratio
- **Ollama Command**: `ollama pull minicpm-v`

### 4. **moondream:latest** 🌙
- **Size**: ~1.7 GB (smallest)
- **Strengths**:
  - **Designed specifically for OCR tasks**
  - Runs efficiently on edge devices
  - Very fast inference
  - Low memory footprint
- **Weaknesses**: Lower accuracy on complex visual reasoning
- **Best For**: Simple text extraction, fast processing of high volumes
- **Ollama Command**: `ollama pull moondream`

### 5. **llava:13b** (Already Installed) 📦
- **Size**: 7.5 GB
- **Strengths**:
  - Well-established, proven model
  - Good balance of performance and size
  - Large community support
- **Weaknesses**: Older architecture, less optimized for OCR than newer models
- **Best For**: General-purpose vision tasks
- **Status**: Already available on jedi.local

## Test Plan

### Phase 1: Model Installation
Pull the 4 missing models (llama3.2-vision, granite3.2-vision, minicpm-v, moondream)

### Phase 2: Benchmark Test Suite
Create standardized test with 5 trading screenshot types:
1. **Options trade confirmation** (STO/BTC with strike, expiration, premium)
2. **Shares trade confirmation** (Buy/Sell with quantity, price)
3. **Account summary** (Portfolio value, P&L, positions table)
4. **Dividend payment** (Symbol, amount, date)
5. **Multi-trade screenshot** (Multiple trades in one image)

### Phase 3: Evaluation Criteria
For each model, measure:
- **Accuracy**: % of correctly extracted trade data
- **Speed**: Inference time per image
- **Structured Output**: Quality of parsed trades (valid format)
- **Error Rate**: Failed extractions or hallucinations

### Phase 4: Results Analysis
Compare:
- **Baseline**: Claude Sonnet 4.5 (current)
- **Best Local Model**: Top performer from Ollama candidates
- **Recommendation**: Privacy vs Quality tradeoff

## Expected Outcomes

### Most Likely Winners:
1. **granite3.2-vision:2b** - Specialized for document OCR, fast, small
2. **llama3.2-vision:11b** - Highest accuracy, best for complex screenshots
3. **minicpm-v:8b** - Best balance of size/performance

### Decision Criteria:
- If granite3.2-vision achieves >90% accuracy → **Winner** (speed + specialization)
- If llama3.2-vision significantly better → Use for complex screenshots
- If all <80% accuracy → Consider EasyOCR HTTP service

## Installation Commands

```bash
# SSH to Ollama server
ssh jedi.local

# Pull all candidate models
ollama pull llama3.2-vision:11b
ollama pull granite3.2-vision:2b
ollama pull minicpm-v
ollama pull moondream

# Verify installations
ollama list
```

## Testing Commands

```bash
# List available vision models
python src/cli.py admin ollama-models --vision-only

# Test each model with same image
python src/cli.py messages analyze-image --url <discord-url> --model ollama/llama3.2-vision:11b
python src/cli.py messages analyze-image --url <discord-url> --model ollama/granite3.2-vision:2b
python src/cli.py messages analyze-image --url <discord-url> --model ollama/minicpm-v
python src/cli.py messages analyze-image --url <discord-url> --model ollama/moondream
python src/cli.py messages analyze-image --url <discord-url> --model ollama/llava:13b

# Baseline comparison (Claude)
python src/cli.py messages analyze-image --url <discord-url>
```

## References

- [Ollama-OCR Documentation](https://github.com/imanoop7/Ollama-OCR)
- [Granite 3.2 Vision Model](https://ollama.com/library/granite3.2-vision)
- [MiniCPM-V Benchmarks](https://github.com/OpenBMB/MiniCPM-V)
- [Llama 3.2 Vision Announcement](https://www.llama.com/docs/model-cards-and-prompt-formats/llama3_2)
