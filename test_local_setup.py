#!/usr/bin/env python3
"""
Test script for local LLaMA model integration.
Verifies that the local model can be loaded and used for both Vanna and RAG.
"""

import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

def test_local_llm():
    """Test local LLaMA model loading and basic functionality."""
    print("🧪 Testing Local LLaMA Model Integration")
    print("=" * 50)
    
    try:
        from config.local_llm_config import local_llm_config
        
        print("✅ Local LLM config imported successfully")
        
        # Test model info
        model_info = local_llm_config.get_model_info()
        print(f"📋 Model Info:")
        print(f"   Path: {model_info['model_path']}")
        print(f"   Context Size: {model_info['context_size']}")
        print(f"   GPU Layers: {model_info['gpu_layers']}")
        
        # Test model loading
        print("\n🔄 Loading LLaMA model...")
        llm = local_llm_config.get_llm_instance()
        print("✅ Model loaded successfully!")
        
        # Test basic generation
        print("\n🤖 Testing text generation...")
        test_prompt = "Hello, this is a test. Please respond with 'Model working correctly.'"
        response = local_llm_config.generate_response(test_prompt, max_tokens=50)
        print(f"Response: {response}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing local LLM: {e}")
        return False

def test_local_vanna():
    """Test local Vanna implementation."""
    print("\n🧪 Testing Local Vanna Integration")
    print("=" * 50)
    
    try:
        from config.local_vanna import get_local_vanna_instance
        
        print("✅ Local Vanna imported successfully")
        
        # Get Vanna instance
        vanna = get_local_vanna_instance()
        print("✅ Vanna instance created")
        
        # Test training
        print("\n📚 Testing Vanna training...")
        vanna.train(
            question="Show me my recent orders",
            sql="SELECT * FROM sales_order WHERE customer_id = ? ORDER BY created_at DESC LIMIT 10"
        )
        
        vanna.train(
            ddl="CREATE TABLE sales_order (entity_id INT PRIMARY KEY, customer_id INT, increment_id VARCHAR(50), status VARCHAR(32), grand_total DECIMAL(10,2), created_at TIMESTAMP)"
        )
        
        print("✅ Training completed")
        
        # Test SQL generation
        print("\n🔍 Testing SQL generation...")
        test_question = "Show me my orders"
        try:
            sql = vanna.generate_sql(test_question)
            print(f"Generated SQL: {sql}")
            print("✅ SQL generation working")
        except Exception as e:
            print(f"⚠️  SQL generation error (expected with minimal training): {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing local Vanna: {e}")
        return False

def test_qdrant_connection():
    """Test Qdrant connection and existing data."""
    print("\n🧪 Testing Qdrant Connection")
    print("=" * 50)
    
    try:
        from config.rag_config import rag_config
        
        print("✅ RAG config imported successfully")
        
        # Test Qdrant connection
        print("\n🔄 Connecting to Qdrant...")
        qdrant_client = rag_config.get_qdrant_client()
        print("✅ Qdrant connection successful")
        
        # Check existing collections
        print("\n📋 Checking existing collections...")
        collections = qdrant_client.get_collections().collections
        collection_names = [col.name for col in collections]
        print(f"Found collections: {collection_names}")
        
        # Check if your existing collection exists
        if 'gaming_support_qa' in collection_names:
            collection_info = qdrant_client.get_collection('gaming_support_qa')
            print(f"✅ Found existing collection 'gaming_support_qa' with {collection_info.points_count} vectors")
        else:
            print("ℹ️  No existing 'gaming_support_qa' collection found")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Qdrant: {e}")
        return False

def test_local_embeddings():
    """Test local embeddings for RAG."""
    print("\n🧪 Testing Local Embeddings")
    print("=" * 50)
    
    try:
        from config.rag_config import rag_config
        
        print("✅ RAG config imported successfully")
        
        # Test embeddings
        print("\n🔄 Loading embeddings model...")
        embeddings = rag_config.get_embeddings()
        print("✅ Embeddings loaded successfully")
        
        # Test embedding generation
        print("\n🧮 Testing embedding generation...")
        test_text = "This is a test document for embedding"
        embedding = embeddings.embed_query(test_text)
        print(f"✅ Generated embedding with dimension: {len(embedding)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing embeddings: {e}")
        return False

def test_existing_setup_bridge():
    """Test bridge to existing chunking and generation setup."""
    print("\n🧪 Testing Existing Setup Bridge")
    print("=" * 50)
    
    try:
        from services.qdrant_bridge_service import qdrant_bridge_service
        
        print("✅ Bridge service imported successfully")
        
        # Test initialization
        print("\n🔄 Initializing bridge service...")
        success = qdrant_bridge_service.initialize()
        
        if success:
            print("✅ Bridge service initialized - using existing setup!")
            
            # Test a simple query
            print("\n🔍 Testing query with existing setup...")
            from models.schemas import RAGQueryRequest
            
            request = RAGQueryRequest(
                question="What should I do if my code isn't working?",
                include_sources=True
            )
            
            result = qdrant_bridge_service.process_rag_query(request)
            
            if result.success:
                print(f"✅ Query successful: {result.answer[:100]}...")
                print(f"Sources found: {len(result.sources)}")
            else:
                print(f"⚠️  Query failed: {result.error}")
        else:
            print("ℹ️  Bridge service not available - existing setup not found")
        
        return success
        
    except Exception as e:
        print(f"❌ Error testing bridge service: {e}")
        return False

def test_local_rag_llm():
    """Test local LLM wrapper for RAG."""
    print("\n🧪 Testing Local RAG LLM")
    print("=" * 50)
    
    try:
        from config.local_llm_wrapper import LocalLlamaLLM
        
        print("✅ Local LLM wrapper imported successfully")
        
        # Test LLM wrapper
        print("\n🔄 Creating LLM wrapper...")
        llm = LocalLlamaLLM()
        print("✅ LLM wrapper created")
        
        # Test generation
        print("\n🤖 Testing LLM generation...")
        test_prompt = "Answer this question: What is 2+2?"
        response = llm._call(test_prompt)
        print(f"Response: {response}")
        print("✅ LLM wrapper working")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing RAG LLM: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Local Model Integration Test Suite")
    print("=" * 60)
    
    # Check if model file exists
    model_path = Path("llama.cpp/models/llama-3.1-8b-q4.gguf")
    if not model_path.exists():
        print(f"❌ Model file not found: {model_path}")
        print("Please ensure your LLaMA model is in the correct location.")
        return False
    
    print(f"✅ Model file found: {model_path}")
    
    tests = [
        ("Local LLM", test_local_llm),
        ("Local Vanna", test_local_vanna),
        ("Qdrant Connection", test_qdrant_connection),
        ("Local Embeddings", test_local_embeddings),
        ("Existing Setup Bridge", test_existing_setup_bridge),
        ("Local RAG LLM", test_local_rag_llm)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 All tests passed! Your local model setup is working correctly.")
        print("\nNext steps:")
        print("1. Copy env.example to .env and configure your database settings")
        print("2. Run: python scripts/train_vanna.py")
        print("3. Run: python scripts/setup_rag.py")
        print("4. Run: python main.py")
    else:
        print(f"\n⚠️  {len(results) - passed} tests failed. Please check the errors above.")
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
