"""
Test Receipt Agent functionality.

This creates a sample receipt image and processes it.
"""

import os
import tempfile
from PIL import Image, ImageDraw, ImageFont
from langchain_openai import ChatOpenAI
from sentence_transformers import SentenceTransformer

from banko_ai.agents.receipt_agent import ReceiptAgent


def create_sample_receipt(filename: str) -> str:
    """Create a sample receipt image for testing"""
    
    # Create image
    img = Image.new('RGB', (400, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use a better font, fall back to default
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Draw receipt content
    y = 20
    receipt_lines = [
        "STARBUCKS COFFEE",
        "123 Main Street",
        "New York, NY 10001",
        "",
        "Date: 2024-11-04",
        "Time: 10:30 AM",
        "",
        "Items:",
        "Grande Latte         $5.50",
        "Blueberry Muffin     $3.50",
        "",
        "Subtotal:            $9.00",
        "Tax:                 $0.72",
        "Total:               $9.72",
        "",
        "Payment: Visa ****1234",
        "",
        "Thank you!"
    ]
    
    for line in receipt_lines:
        draw.text((20, y), line, fill='black', font=font_small if line else font)
        y += 25
    
    # Save
    img.save(filename)
    print(f"✅ Created sample receipt: {filename}")
    return filename


def test_receipt_agent():
    """Test Receipt Agent"""
    
    print("🧪 Testing Receipt Agent")
    print("="*60)
    
    # Configuration
    database_url = os.getenv(
        'DATABASE_URL',
        'cockroachdb://root@localhost:26257/defaultdb?sslmode=disable'
    )
    openai_api_key = os.getenv('OPENAI_API_KEY')
    
    if not openai_api_key:
        print("❌ OPENAI_API_KEY not set")
        return False
    
    print(f"✅ Database: {database_url.split('@')[1]}")
    print()
    
    # Create LLM and embedding model
    print("1️⃣  Initializing models...")
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=openai_api_key,
        temperature=0.3
    )
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    print("   ✅ Models initialized")
    print()
    
    # Create Receipt Agent
    print("2️⃣  Creating Receipt Agent...")
    agent = ReceiptAgent(
        region="us-east-1",
        llm=llm,
        database_url=database_url,
        embedding_model=embedding_model
    )
    print(f"   ✅ Receipt Agent created: {agent}")
    print(f"      Tools: {[t.name for t in agent.tools]}")
    print()
    
    # Create sample receipt
    print("3️⃣  Creating sample receipt image...")
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        receipt_path = tmp.name
    
    create_sample_receipt(receipt_path)
    print()
    
    # Process the receipt
    print("4️⃣  Processing receipt...")
    print("   This will:")
    print("   - Extract text using OCR")
    print("   - Parse fields with AI")
    print("   - Check for duplicates")
    print("   - Store in database")
    print()
    
    result = agent.process_document(
        file_path=receipt_path,
        user_id='test_user_01',
        document_type='receipt'
    )
    
    # Display results
    print("5️⃣  Results:")
    print(f"   Success: {'✅' if result['success'] else '❌'}")
    print()
    
    if result['success']:
        print("   📄 Extracted Fields:")
        fields = result.get('extracted_fields', {})
        for key, value in fields.items():
            print(f"      {key}: {value}")
        print()
        
        print(f"   📝 Document ID: {result.get('document_id')}")
        print()
        
        if result.get('duplicate_check', {}).get('found'):
            print("   ⚠️  Duplicate Check:")
            match = result['duplicate_check'].get('match')
            if match:
                print(f"      Found match: {match.get('merchant')} - ${match.get('amount')}")
        else:
            print("   ✓ No duplicates found")
        print()
    
    # Show processing steps
    print("   📊 Processing Steps:")
    for step in result.get('steps', []):
        status = '✅' if step['success'] else '❌'
        print(f"      {status} {step['step']}")
    
    if result.get('errors'):
        print("\n   ❌ Errors:")
        for error in result['errors']:
            print(f"      - {error}")
    
    print()
    
    # Cleanup
    try:
        os.unlink(receipt_path)
        print(f"🗑️  Cleaned up temp file: {receipt_path}")
    except:
        pass
    
    print()
    print("="*60)
    if result['success']:
        print("🎉 Receipt Agent test completed successfully!")
    else:
        print("⚠️  Receipt Agent test completed with errors")
    
    return result['success']


if __name__ == "__main__":
    success = test_receipt_agent()
    exit(0 if success else 1)
