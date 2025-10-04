"""
Integration test for customer_id persistence across session messages.
Tests the complete flow of extracting and storing customer_id in session.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import HybridChatbot
from models.schemas import ChatRequest
from services.chat_database_service import chat_db_service


async def test_customer_id_persistence():
    """Test that customer_id persists across messages in a session."""
    
    print("=" * 60)
    print("Testing Customer ID Persistence Across Session")
    print("=" * 60)
    
    # Initialize chatbot
    print("\n1. Initializing chatbot...")
    chatbot = HybridChatbot()
    await chatbot.initialize()
    print("   ✓ Chatbot initialized")
    
    # Create a test session
    print("\n2. Creating test session...")
    session_id = chat_db_service.create_session(
        session_name="Test Session - Customer ID Persistence"
    )
    print(f"   ✓ Session created: {session_id}")
    
    # First message: user provides customer_id
    print("\n3. Processing first message with customer_id...")
    request1 = ChatRequest(
        question="hi my customer_id is 1",
        session_id=session_id
    )
    
    response1 = await chatbot.process_chat_request(request1)
    print(f"   Question: {request1.question}")
    print(f"   ✓ Response received: {response1.answer[:100]}...")
    
    # Check if customer_id was stored in session
    print("\n4. Checking session metadata...")
    metadata = chat_db_service.get_session_metadata(session_id)
    print(f"   Session metadata: {metadata}")
    
    if metadata.get('customer_id') == '1':
        print("   ✓ Customer ID correctly stored in session!")
    else:
        print(f"   ✗ Customer ID not found in session. Got: {metadata}")
        return False
    
    # Second message: user asks for orders WITHOUT providing customer_id
    print("\n5. Processing second message WITHOUT customer_id...")
    request2 = ChatRequest(
        question="can you give me recent orders",
        session_id=session_id
        # Note: No customer_id or customer_email in request
    )
    
    print(f"   Question: {request2.question}")
    print(f"   Request customer_id: {request2.customer_id}")
    print(f"   Request customer_email: {request2.customer_email}")
    
    response2 = await chatbot.process_chat_request(request2)
    print(f"\n6. Response received:")
    print(f"   Success: {response2.success}")
    print(f"   Query Type: {response2.query_type}")
    print(f"   Answer: {response2.answer[:200]}...")
    
    if response2.error:
        print(f"   Error: {response2.error}")
    
    # Check if the request was processed successfully
    if response2.success or "Customer ID or email required" not in (response2.error or ""):
        print("\n" + "=" * 60)
        print("✓ TEST PASSED: Customer ID persisted across messages!")
        print("=" * 60)
        return True
    else:
        print("\n" + "=" * 60)
        print("✗ TEST FAILED: Customer ID was not used from session")
        print("=" * 60)
        return False
    
    # Clean up
    chat_db_service.delete_session(session_id)


if __name__ == "__main__":
    result = asyncio.run(test_customer_id_persistence())
    sys.exit(0 if result else 1)
