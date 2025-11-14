#!/bin/bash
# Auto-install system dependencies for Banko AI

set -e

echo "🔧 Installing system dependencies for Banko AI..."
echo "   - poppler-utils (PDF processing)"
echo "   - tesseract-ocr (OCR text extraction)"
echo ""

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v apt-get &> /dev/null; then
        echo "📦 Detected Debian/Ubuntu"
        sudo apt-get update
        sudo apt-get install -y poppler-utils tesseract-ocr
    elif command -v yum &> /dev/null; then
        echo "📦 Detected Red Hat/CentOS/Fedora"
        sudo yum install -y poppler-utils tesseract
    elif command -v apk &> /dev/null; then
        echo "📦 Detected Alpine Linux"
        sudo apk add --no-cache poppler-utils tesseract-ocr
    else
        echo "❌ Unknown Linux distribution. Please install manually:"
        echo "   - poppler-utils"
        echo "   - tesseract-ocr"
        exit 1
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "📦 Detected macOS"
    if ! command -v brew &> /dev/null; then
        echo "❌ Homebrew not found. Please install Homebrew first:"
        echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    brew install poppler tesseract
else
    echo "❌ Unsupported OS: $OSTYPE"
    exit 1
fi

echo ""
echo "✅ System dependencies installed successfully!"
echo ""
echo "Installed:"
echo "  ✓ poppler-utils (PDF → images)"
echo "  ✓ tesseract-ocr (Image → text)"
echo ""
echo "🚀 You can now run: pip install banko-ai-assistant"
