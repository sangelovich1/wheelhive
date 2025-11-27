# Ollama Failover Configuration

## Current Setup

### Primary Server: jedi.local
- **URL**: `http://jedi.local:11434`
- **Status**: ✅ Active
- **Models**: 8+ models including llava:13b
- **Configuration**: `const.OLLAMA_BASE_URL`

### Secondary Server: yoda.local
- **URL**: `http://yoda.local:11434`
- **Status**: ⚠️ Ollama not currently running
- **Host**: Reachable (192.168.68.90)

## Failover Strategy

### Option 1: Environment Variable Fallback
Use environment variable to override default Ollama URL:

```bash
# .env file
OLLAMA_BASE_URL=http://jedi.local:11434
OLLAMA_FALLBACK_URL=http://yoda.local:11434
```

```python
# constants.py
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://jedi.local:11434')
OLLAMA_FALLBACK_URL = os.getenv('OLLAMA_FALLBACK_URL', None)
```

### Option 2: Smart Client with Auto-Failover
Modify `OllamaClient` to try multiple servers:

```python
class OllamaClient:
    def __init__(self, base_urls: List[str] = None):
        """
        Initialize with multiple Ollama servers for failover

        Args:
            base_urls: List of Ollama URLs to try (None = use const.OLLAMA_BASE_URL)
        """
        if base_urls is None:
            base_urls = [const.OLLAMA_BASE_URL]
            if const.OLLAMA_FALLBACK_URL:
                base_urls.append(const.OLLAMA_FALLBACK_URL)

        self.base_urls = base_urls
        self.current_url = None
        self._find_available_server()

    def _find_available_server(self):
        """Try each server until one responds"""
        for url in self.base_urls:
            if self._test_connection(url):
                self.current_url = url
                return True
        return False
```

### Option 3: Load Balancing
Distribute vision model requests across both servers:
- jedi.local: Primary for all models
- yoda.local: Backup + load balancing for high-volume periods

## Setting Up yoda.local

### 1. Install Ollama on yoda.local
```bash
ssh yoda.local
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Start Ollama Service
```bash
# Enable on boot
sudo systemctl enable ollama

# Start now
sudo systemctl start ollama

# Check status
sudo systemctl status ollama
```

### 3. Verify Installation
```bash
ollama list
curl http://localhost:11434/api/tags
```

### 4. Pull Same Models
```bash
# From yoda.local
ollama pull llava:13b
ollama pull llama3.2-vision:11b
ollama pull granite3.2-vision:2b
ollama pull minicpm-v
ollama pull moondream

# Or remotely via CLI
python src/cli.py admin ollama-pull-vision-models --url http://yoda.local:11434
```

## Testing Failover

### Test Primary
```bash
python src/cli.py admin ollama-models --url http://jedi.local:11434
```

### Test Secondary
```bash
python src/cli.py admin ollama-models --url http://yoda.local:11434
```

### Test Auto-Failover (after implementation)
```bash
# Stop jedi.local Ollama
ssh jedi.local "sudo systemctl stop ollama"

# CLI should automatically use yoda.local
python src/cli.py admin ollama-models

# Restart jedi.local
ssh jedi.local "sudo systemctl start ollama"
```

## Implementation Priority

**Immediate** (Current):
- ✅ All CLI commands support `--url` parameter for manual override
- ✅ Can specify any Ollama server on-demand

**Short-term** (If failover needed):
1. Add `OLLAMA_FALLBACK_URL` to .env
2. Update constants.py to read fallback URL
3. Implement smart failover in OllamaClient.__init__

**Long-term** (If high-availability required):
1. Full load balancing across multiple Ollama instances
2. Health check monitoring
3. Automatic model sync between servers

## Current Capabilities

**Manual Failover** (Already Working):
```bash
# Primary down? Use secondary manually
export OLLAMA_BASE_URL=http://yoda.local:11434

# Or per-command
python src/cli.py admin ollama-models --url http://yoda.local:11434
python scripts/compare_vision_models.py --ollama-url http://yoda.local:11434
```

## Recommendations

1. **Install Ollama on yoda.local** if failover is required
2. **Mirror models** to yoda.local for true redundancy
3. **Test regularly** to ensure both servers stay in sync
4. **Monitor disk space** - vision models are large (16-18 GB for test suite)

## Next Steps

1. ⚠️ Install Ollama on yoda.local (currently not running)
2. Pull vision models to yoda.local
3. Test failover with `--url` parameter
4. Optional: Implement automatic failover in OllamaClient
