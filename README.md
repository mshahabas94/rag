# Hybrid E-commerce Chatbot

A production-ready hybrid chatbot that combines Text-to-SQL using Vanna.ai with RAG (Retrieval Augmented Generation) for comprehensive e-commerce customer support.

## 🚀 Features

### Text-to-SQL with Vanna.ai
- Natural language to SQL conversion for order queries
- Trained on 160+ column `sales_order` table
- Customer data isolation and security
- Support for complex e-commerce queries (orders, payments, discounts, shipping)

### RAG Knowledge Base
- Document-based question answering
- Support for policies, procedures, and FAQs
- Vector similarity search with ChromaDB
- Contextual answer generation with OpenAI GPT

### Intelligent Intent Classification
- Automatic routing between SQL and RAG systems
- Hybrid query support (combining order data with policies)
- Confidence scoring and fallback handling

### Production-Ready Security
- SQL injection prevention
- Customer data isolation (row-level security)
- Rate limiting and audit logging
- Query validation and sanitization

### Comprehensive Monitoring
- Query logging and analytics
- Performance metrics tracking
- Health monitoring for all services
- Error tracking and alerting

## 📋 Prerequisites

- Python 3.8+
- MySQL database with `sales_order` table
- Local LLaMA model (llama-3.1-8b-q4.gguf in llama.cpp/models/)
- Sufficient RAM (8GB+ recommended for 8B model)
- Optional: CUDA-compatible GPU for faster inference

## 🛠️ Installation

### 1. Clone and Setup Environment

```bash
git clone <repository-url>
cd hybrid-chatbot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
cp env.example .env
```

Edit `.env` with your configuration:

```env
# Database Configuration
DB_HOST=localhost
DB_PORT=3306
DB_NAME=your_ecommerce_db
DB_USER=your_db_user
DB_PASSWORD=your_db_password

# Local LLaMA Model Configuration
LOCAL_MODEL_PATH=llama.cpp/models/llama-3.1-8b-q4.gguf
LOCAL_MODEL_CTX=4096
LOCAL_MODEL_GPU_LAYERS=-1  # Use -1 for all GPU layers, 0 for CPU only
LOCAL_MODEL_TEMPERATURE=0.1
LOCAL_MODEL_MAX_TOKENS=512

# Local Embeddings
LOCAL_EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### 3. Database Setup

Ensure your MySQL database has the `sales_order` table with the following key columns:

```sql
-- Key columns for the sales_order table
entity_id (Primary Key)
increment_id (Customer-facing order number)
customer_id (Customer identifier)
customer_email (Alternative customer identifier)
status, state (Order status)
grand_total, subtotal (Financial amounts)
tax_amount, discount_amount, shipping_amount
created_at, updated_at (Timestamps)
-- ... and 150+ other e-commerce columns
```

### 4. Test Local Model Setup

First, verify your local model is working:

```bash
python test_local_setup.py
```

This will test:
- Local LLaMA model loading
- Vanna integration with local model
- Local embeddings functionality
- RAG system with local LLM

### 5. Initialize Services

#### Train Vanna on Your Database Schema

```bash
python scripts/train_vanna.py
```

This will:
- Connect to your MySQL database
- Extract the `sales_order` table schema
- Train Vanna using your local LLaMA model
- Validate the training with test queries

#### Setup RAG System

```bash
python scripts/setup_rag.py
```

This will:
- Create sample e-commerce documents (policies, FAQs, etc.)
- Process and embed documents using local embeddings
- Validate RAG functionality with local LLM

## 🚀 Usage

### Command Line Interface

```bash
python main.py
```

Interactive CLI for testing queries:
- Database queries: "Show my orders from last month"
- Knowledge queries: "What is your return policy?"
- Type 'health' for system status, 'stats' for analytics

### Python API

```python
import asyncio
from main import chatbot
from models.schemas import ChatRequest

async def example():
    # Initialize chatbot
    await chatbot.initialize()
    
    # Create request
    request = ChatRequest(
        question="What's the status of order #100000123?",
        customer_id="customer_456",
        session_id="session_789"
    )
    
    # Process query
    response = await chatbot.process_chat_request(request)
    print(f"Answer: {response.answer}")
    print(f"Query Type: {response.query_type}")

asyncio.run(example())
```

### Web Interface (Streamlit)

```bash
streamlit run streamlit_app.py
```

## 📊 Sample Queries

### SQL Queries (Database)
- "Show me my orders from last month"
- "What's the status of order #100000123?"
- "How much did I spend this year?"
- "List my orders with status 'processing'"
- "What discounts did I get on my orders?"
- "Show my orders above $100"
- "How many orders do I have?"
- "What's my most recent order total?"

### RAG Queries (Knowledge Base)
- "What is your return policy?"
- "How do I track my shipment?"
- "What payment methods do you accept?"
- "How long does shipping take?"
- "Can I cancel my order?"
- "How do I apply a coupon code?"

### Hybrid Queries (Both Systems)
- "Can I return order #100000123?" (Order details + return policy)
- "Is my recent order eligible for refund?" (Order status + refund rules)
- "Why was my order cancelled?" (Order info + cancellation reasons)

## 🔧 Configuration

### Database Configuration

The system is designed for the `sales_order` table with 160+ columns. Key configuration:

```python
# Key columns focused on for training
KEY_COLUMNS = [
    'entity_id', 'increment_id', 'customer_id', 'customer_email',
    'customer_firstname', 'customer_lastname', 'status', 'state',
    'grand_total', 'base_grand_total', 'subtotal', 'tax_amount',
    'discount_amount', 'shipping_amount', 'coupon_code',
    'created_at', 'updated_at', 'total_item_count'
]
```

### Vanna Training Strategy

For 160+ column tables:
1. **Focus on key columns**: Train primarily on the 20-25 most important columns
2. **Business context**: Include status meanings and business rules
3. **Sample queries**: Provide diverse query patterns for common use cases
4. **Incremental training**: Add more columns gradually based on usage

### RAG Optimization

```python
# Recommended settings for e-commerce
CHUNK_SIZE = 1000          # Good for policy documents
CHUNK_OVERLAP = 200        # Ensures context continuity
RETRIEVAL_K = 4            # Balance between context and relevance
```

### Security Configuration

```python
# Customer isolation (CRITICAL)
- Every query MUST filter by customer_id or customer_email
- SQL validation prevents injection attacks
- Rate limiting prevents abuse
- Audit logging for compliance
```

## 🔒 Security Features

### SQL Security
- **Injection Prevention**: Comprehensive SQL validation and sanitization
- **Customer Isolation**: Automatic customer_id/customer_email filtering
- **Query Restrictions**: Only SELECT statements allowed
- **Timeout Protection**: Query execution time limits

### Access Control
- **Rate Limiting**: Configurable request limits per customer/IP
- **Authentication**: Customer ID/email required for database queries
- **Audit Logging**: All queries logged with timestamps and metadata

### Data Protection
- **Encryption**: All database connections use SSL
- **Validation**: Input sanitization and output filtering
- **Monitoring**: Real-time security event tracking

## 📈 Monitoring & Analytics

### Query Analytics
```bash
# View system statistics
python -c "
from main import chatbot
stats = chatbot.get_stats()
print(f'Total Queries: {stats[\"system_stats\"][\"total_queries\"]}')
print(f'Success Rate: {stats[\"system_stats\"][\"successful_queries\"] / stats[\"system_stats\"][\"total_queries\"] * 100:.1f}%')
"
```

### Health Monitoring
```bash
# Check system health
python -c "
from main import chatbot
health = chatbot.get_health_status()
print(f'Status: {health.status}')
print(f'Database: {\"✓\" if health.database_healthy else \"✗\"}')
print(f'Vanna: {\"✓\" if health.vanna_healthy else \"✗\"}')
print(f'RAG: {\"✓\" if health.rag_healthy else \"✗\"}')
"
```

### Log Analysis
- Query logs: `logs/chatbot.log`
- SQLite analytics: `logs/query_logs.db`
- Performance metrics available via API

## 🧪 Testing

### Run Test Suite
```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

### Manual Testing
```bash
# Test Vanna service
python -c "
from services.vanna_service import vanna_service
vanna_service.initialize()
result = vanna_service.validate_query_syntax('Show my recent orders')
print(f'SQL suitable: {result[\"suitable_for_sql\"]}')
"

# Test RAG service
python -c "
from services.rag_service import rag_service
rag_service.initialize()
result = rag_service.validate_query_for_rag('What is your return policy?')
print(f'RAG suitable: {result[\"suitable_for_rag\"]}')
"
```

## 🚀 Production Deployment

### Environment Setup
1. **Database**: Migrate to Aurora MySQL for production
2. **Scaling**: Use connection pooling and read replicas
3. **Security**: Enable SSL, VPC, and IAM authentication
4. **Monitoring**: Set up CloudWatch, Prometheus, or similar

### Performance Optimization
- **Database Indexing**: Ensure proper indexes on customer_id, created_at, status
- **Query Caching**: Implement Redis for frequent queries
- **Connection Pooling**: Configure appropriate pool sizes
- **Async Processing**: Use async/await for concurrent requests

### Migration from Local to Aurora
```python
# Update database configuration
DB_HOST=your-aurora-cluster.cluster-xxxxx.region.rds.amazonaws.com
DB_PORT=3306
DB_NAME=production_ecommerce
# Add SSL and other Aurora-specific settings
```

## 📚 Architecture

### System Components
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User Query    │───▶│ Intent Classifier │───▶│ Route Decision  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │ SQL (Vanna.ai)  │    │ RAG (LangChain) │
                       │ - Text-to-SQL   │    │ - Doc Retrieval │
                       │ - Query Execute │    │ - Answer Gen    │
                       └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │ MySQL Database  │    │ Vector Database │
                       │ (sales_order)   │    │ (ChromaDB)      │
                       └─────────────────┘    └─────────────────┘
```

### Data Flow
1. **Query Reception**: User submits natural language question
2. **Intent Classification**: Determine if query needs SQL, RAG, or both
3. **Security Validation**: Check rate limits, customer isolation
4. **Service Routing**: Route to appropriate service(s)
5. **Processing**: Execute SQL query and/or retrieve documents
6. **Response Generation**: Format and combine results
7. **Logging**: Record query, performance, and security events

## 🤝 Contributing

### Development Setup
```bash
# Install development dependencies
pip install -r requirements.txt
pip install black flake8 mypy pytest

# Format code
black .

# Lint code
flake8 .

# Type checking
mypy .
```

### Adding New Features
1. **New Query Types**: Extend intent classifier and add service handlers
2. **Additional Tables**: Train Vanna on new schemas
3. **Document Types**: Add loaders for new file formats
4. **Security Rules**: Update validation in `utils/security.py`

## 🐛 Troubleshooting

### Common Issues

#### Vanna Training Fails
```bash
# Check database connection
python -c "from config.database import db_config; print(db_config.test_connection())"

# Verify API keys
python -c "import os; print('OpenAI:', bool(os.getenv('OPENAI_API_KEY')))"

# Re-run training with verbose logging
python scripts/train_vanna.py --verbose --force
```

#### RAG Setup Fails
```bash
# Check document directory
ls -la data/documents/

# Verify embeddings
python -c "from config.rag_config import rag_config; rag_config.get_embeddings()"

# Re-run setup with force rebuild
python scripts/setup_rag.py --force --verbose
```

#### Database Connection Issues
```bash
# Test MySQL connection
mysql -h localhost -u your_user -p your_database -e "SELECT COUNT(*) FROM sales_order;"

# Check connection pooling
python -c "
from config.database import db_config
engine = db_config.get_engine()
print(f'Pool size: {engine.pool.size()}')
"
```

#### Performance Issues
- **Slow Queries**: Add database indexes on frequently queried columns
- **Memory Usage**: Reduce chunk size or embedding dimensions
- **Rate Limiting**: Adjust limits in environment variables

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python main.py
```

### Getting Help
1. Check logs in `logs/chatbot.log`
2. Review error messages in console output
3. Test individual components separately
4. Verify environment configuration

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Vanna.ai**: Text-to-SQL functionality
- **LangChain**: RAG framework and document processing
- **ChromaDB**: Vector database for embeddings
- **OpenAI**: Embeddings and language model
- **SQLAlchemy**: Database ORM and connection management

---

**Note**: This is a production-ready system designed for e-commerce environments. Ensure proper security measures, monitoring, and testing before deploying to production.
