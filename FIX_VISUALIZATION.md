# Customer ID Persistence Fix - Visual Flow

## Before the Fix ❌

```
Session: cd77b336-6fc7-440d-99d3-980335ede4b7
┌─────────────────────────────────────────────────────────┐
│ Message 1: "hi my customer_id is 1"                     │
├─────────────────────────────────────────────────────────┤
│ ❌ customer_id NOT extracted from text                  │
│ ❌ customer_id NOT stored in session                    │
│ ✓ Response: "Hello! Welcome to..."                     │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Message 2: "can you give me recent orders"              │
├─────────────────────────────────────────────────────────┤
│ ✓ Classified as SQL query                               │
│ ❌ No customer_id in request                            │
│ ❌ No customer_id in session                            │
│ ❌ ERROR: "Customer ID or email required"               │
│ ❌ Fallback to RAG: generic response                    │
└─────────────────────────────────────────────────────────┘

Result: User cannot get their orders 😞
```

## After the Fix ✅

```
Session: cd77b336-6fc7-440d-99d3-980335ede4b7
┌─────────────────────────────────────────────────────────┐
│ Message 1: "hi my customer_id is 1"                     │
├─────────────────────────────────────────────────────────┤
│ ✓ Extract: customer_id = "1"                            │
│ ✓ Store in session metadata                             │
│   → session.metadata = {'customer_id': '1'}             │
│ ✓ Response: "Hello! Welcome to..."                     │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Message 2: "can you give me recent orders"              │
├─────────────────────────────────────────────────────────┤
│ ✓ Classified as SQL query                               │
│ ✓ Check request: customer_id = None                     │
│ ✓ Check message: customer_id = None                     │
│ ✓ Check session: customer_id = "1" ← FOUND!            │
│ ✓ Use customer_id = "1" for SQL query                   │
│ ✓ Execute: SELECT * FROM orders WHERE customer_id='1'   │
│ ✓ Return order data successfully                        │
└─────────────────────────────────────────────────────────┘

Result: User gets their orders! 🎉
```

## Technical Flow Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    process_chat_request()                     │
│                                                               │
│  1. Extract customer info from message                        │
│     ┌─────────────────────────────────────────┐             │
│     │ extract_customer_info(message)          │             │
│     │ → {'customer_id': '1', 'email': None}   │             │
│     └─────────────────────────────────────────┘             │
│                          ↓                                    │
│  2. Get session metadata                                      │
│     ┌─────────────────────────────────────────┐             │
│     │ chat_db_service.get_session_metadata()  │             │
│     │ → {'customer_id': '1', ...}             │             │
│     └─────────────────────────────────────────┘             │
│                          ↓                                    │
│  3. Resolve customer_id (priority order)                      │
│     ┌─────────────────────────────────────────┐             │
│     │ request.customer_id        (highest)    │             │
│     │     ↓ (if None)                         │             │
│     │ extracted_info.customer_id (medium)     │             │
│     │     ↓ (if None)                         │             │
│     │ session_metadata.customer_id (fallback) │             │
│     └─────────────────────────────────────────┘             │
│                          ↓                                    │
│  4. Update request with resolved customer_id                  │
│     ┌─────────────────────────────────────────┐             │
│     │ request.customer_id = '1'               │             │
│     │ request.customer_email = None           │             │
│     └─────────────────────────────────────────┘             │
│                          ↓                                    │
│  5. If new info extracted, update session                     │
│     ┌─────────────────────────────────────────┐             │
│     │ chat_db_service.update_session_metadata │             │
│     │ (session_id, {'customer_id': '1'})      │             │
│     └─────────────────────────────────────────┘             │
│                          ↓                                    │
│  6. Continue normal processing with customer_id               │
└──────────────────────────────────────────────────────────────┘
```

## Code Changes Overview

### utils/customer_extractor.py (NEW)
```python
def extract_customer_info(message: str) -> Dict[str, Optional[str]]:
    """Extract customer_id and email from message text."""
    # Supports patterns like:
    # - "customer_id is 1"
    # - "my id is 1" 
    # - "email is user@example.com"
    return {'customer_id': '1', 'customer_email': None}
```

### services/chat_database_service.py (ENHANCED)
```python
def update_session_metadata(session_id: str, metadata: Dict) -> bool:
    """Store customer info in session for future use."""
    
def get_session_metadata(session_id: str) -> Dict:
    """Retrieve stored customer info from session."""
```

### main.py (ENHANCED)
```python
async def process_chat_request(request: ChatRequest) -> ChatResponse:
    # NEW: Extract customer info from message
    extracted_info = extract_customer_info(request.question)
    
    # NEW: Get stored customer info from session
    session_metadata = chat_db_service.get_session_metadata(session_id)
    
    # NEW: Resolve with priority: request > extracted > session
    customer_id = request.customer_id or \
                  extracted_info.get('customer_id') or \
                  session_metadata.get('customer_id')
    
    # NEW: Update request with resolved info
    request.customer_id = customer_id
    
    # NEW: Store extracted info in session for future use
    if extracted_info.get('customer_id'):
        chat_db_service.update_session_metadata(session_id, metadata)
    
    # Continue with existing processing...
```

## Supported Input Formats

| User Input | Extracted customer_id |
|------------|----------------------|
| "hi my customer_id is 1" | "1" |
| "customer_id is 123" | "123" |
| "my id is 456" | "456" |
| "id: 789" | "789" |
| "customer_number is 999" | "999" |
| "account_id is 111" | "111" |
| "user_id is 222" | "222" |
| "show me orders" | None (uses session) |

## Session Lifecycle

```
Session Created
    ↓
Message 1: customer_id provided
    ↓ (extract & store)
metadata = {'customer_id': '1'}
    ↓
Message 2: no customer_id
    ↓ (retrieve from session)
Use customer_id = '1'
    ↓
Message 3: no customer_id
    ↓ (retrieve from session)
Use customer_id = '1'
    ↓
Session Continues...
(customer_id persists throughout)
```

## Security & Privacy

- ✅ Customer info is **session-isolated**
- ✅ Different sessions cannot access each other's data
- ✅ All existing SQL security validations still apply
- ✅ Customer isolation enforced at database query level
- ✅ Session data stored securely in database
- ✅ No customer data exposed in logs (only IDs)

## Performance Impact

- **Minimal**: One additional database query per request
- **Query**: Fast metadata lookup (indexed on session_id)
- **Storage**: Negligible (small JSON in existing metadata field)
- **No schema changes**: Uses existing database structure

## Backward Compatibility

✅ **100% Backward Compatible**

Existing methods still work:
- ✅ Providing customer_id via API request parameter
- ✅ Entering customer_id in UI sidebar input field
- ✅ Including customer_id in query parameters

New capability added:
- ✅ Automatic extraction from message text
- ✅ Session-based persistence

## Testing Scenarios

### ✅ Scenario 1: Natural conversation
```
User: "hi my customer_id is 1"
Bot: "Hello! How can I help?"
User: "show my recent orders"
Bot: [Returns orders for customer_id 1]
```

### ✅ Scenario 2: Email instead of ID
```
User: "my email is user@example.com"
Bot: "Hello! How can I help?"
User: "what are my orders?"
Bot: [Returns orders for user@example.com]
```

### ✅ Scenario 3: Override with new ID
```
User: "my customer_id is 1"
Bot: [Stores customer_id = 1]
User: "actually use customer_id 2"
Bot: [Updates to customer_id = 2]
User: "show orders"
Bot: [Returns orders for customer_id 2]
```

### ✅ Scenario 4: Traditional sidebar input (still works)
```
[User enters "1" in sidebar customer_id field]
User: "show my orders"
Bot: [Returns orders for customer_id 1]
```

## Summary

| Aspect | Before | After |
|--------|--------|-------|
| Customer ID extraction | ❌ No | ✅ Yes |
| Session persistence | ❌ No | ✅ Yes |
| Natural language | ❌ Required sidebar | ✅ Chat message |
| Context retention | ❌ No | ✅ Full session |
| User experience | ❌ Repetitive | ✅ Natural |
| Backward compatible | N/A | ✅ Yes |

---

**Result**: Users can now have natural conversations without repeating their customer_id! 🎉
