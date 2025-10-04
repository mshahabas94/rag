"""
Pydantic models for request/response schemas.
Defines data structures for API interactions and internal data flow.
"""

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum

class QueryType(str, Enum):
    """Types of queries the chatbot can handle."""
    SQL = "sql"
    RAG = "rag"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"

class QueryStatus(str, Enum):
    """Status of query processing."""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"

# Request Models

class ChatRequest(BaseModel):
    """Main chat request from user."""
    question: str = Field(..., min_length=1, max_length=1000, description="User's question")
    customer_id: Optional[str] = Field(None, description="Customer ID for database queries")
    customer_email: Optional[str] = Field(None, description="Customer email for database queries")
    session_id: Optional[str] = Field(None, description="Session ID for conversation tracking")
    conversation_history: Optional[Union[List[Dict[str, str]], str]] = Field(None, description="Previous conversation messages for context")
    
    @validator('question')
    def validate_question(cls, v):
        """Validate question content."""
        if not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()
    
    @validator('customer_email')
    def validate_email(cls, v):
        """Basic email validation."""
        if v and '@' not in v:
            raise ValueError("Invalid email format")
        return v

class SQLQueryRequest(BaseModel):
    """Request for SQL query generation."""
    question: str = Field(..., description="Natural language question")
    customer_id: Optional[str] = Field(None, description="Customer ID for filtering")
    customer_email: Optional[str] = Field(None, description="Customer email for filtering")
    
class RAGQueryRequest(BaseModel):
    """Request for RAG-based query."""
    question: str = Field(..., description="Question about policies/knowledge base")
    include_sources: bool = Field(True, description="Whether to include source documents")
    conversation_history: Optional[Union[List[Dict[str, str]], str]] = Field(None, description="Previous conversation for context")

# Response Models

class SQLResult(BaseModel):
    """Result of SQL query execution."""
    success: bool = Field(..., description="Whether query was successful")
    sql: str = Field("", description="Generated SQL query")
    data: List[Dict[str, Any]] = Field(default_factory=list, description="Query results")
    row_count: int = Field(0, description="Number of rows returned")
    execution_time: float = Field(0.0, description="Query execution time in seconds")
    columns: List[str] = Field(default_factory=list, description="Column names")
    error: Optional[str] = Field(None, description="Error message if failed")

class RAGResult(BaseModel):
    """Result of RAG query."""
    success: bool = Field(..., description="Whether query was successful")
    answer: str = Field("", description="Generated answer")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Source documents")
    confidence: Optional[float] = Field(None, description="Confidence score")
    error: Optional[str] = Field(None, description="Error message if failed")

class IntentClassification(BaseModel):
    """Result of intent classification."""
    query_type: QueryType = Field(..., description="Classified query type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence")
    reasoning: str = Field("", description="Explanation of classification")
    keywords: List[str] = Field(default_factory=list, description="Keywords that influenced classification")

class ChatResponse(BaseModel):
    """Main chat response to user."""
    success: bool = Field(..., description="Whether request was successful")
    answer: str = Field("", description="Final answer to user")
    query_type: QueryType = Field(..., description="Type of query processed")
    intent_classification: Optional[IntentClassification] = Field(None, description="Intent classification details")
    sql_result: Optional[SQLResult] = Field(None, description="SQL query results if applicable")
    rag_result: Optional[RAGResult] = Field(None, description="RAG results if applicable")
    processing_time: float = Field(0.0, description="Total processing time")
    session_id: Optional[str] = Field(None, description="Session ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    error: Optional[str] = Field(None, description="Error message if failed")

# Internal Models

class CustomerInfo(BaseModel):
    """Customer information for queries."""
    customer_id: Optional[str] = Field(None, description="Customer ID")
    customer_email: Optional[str] = Field(None, description="Customer email")
    customer_name: Optional[str] = Field(None, description="Customer full name")
    
    def has_identifier(self) -> bool:
        """Check if customer has at least one identifier."""
        return bool(self.customer_id or self.customer_email)

class QueryContext(BaseModel):
    """Context for query processing."""
    original_question: str = Field(..., description="Original user question")
    processed_question: str = Field("", description="Processed/cleaned question")
    customer_info: Optional[CustomerInfo] = Field(None, description="Customer information")
    session_id: Optional[str] = Field(None, description="Session ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="Query timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

class ValidationResult(BaseModel):
    """Result of SQL validation."""
    valid: bool = Field(..., description="Whether SQL is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    security_score: float = Field(1.0, ge=0.0, le=1.0, description="Security score (1.0 = safe)")

class QueryLog(BaseModel):
    """Log entry for query tracking."""
    session_id: Optional[str] = Field(None, description="Session ID")
    customer_id: Optional[str] = Field(None, description="Customer ID")
    question: str = Field(..., description="User question")
    query_type: QueryType = Field(..., description="Query type")
    success: bool = Field(..., description="Whether query succeeded")
    processing_time: float = Field(..., description="Processing time")
    sql_query: Optional[str] = Field(None, description="Generated SQL if applicable")
    row_count: Optional[int] = Field(None, description="Number of rows returned")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Log timestamp")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")

# Configuration Models

class DatabaseConfig(BaseModel):
    """Database configuration model."""
    host: str = Field(..., description="Database host")
    port: int = Field(3306, description="Database port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    pool_size: int = Field(5, description="Connection pool size")
    query_timeout: int = Field(30, description="Query timeout in seconds")

class VannaConfig(BaseModel):
    """Vanna configuration model."""
    model_name: str = Field(..., description="Vanna model name")
    use_local: bool = Field(True, description="Use local context")
    is_trained: bool = Field(False, description="Whether model is trained")

class RAGConfig(BaseModel):
    """RAG configuration model."""
    collection_name: str = Field(..., description="Vector collection name")
    chunk_size: int = Field(1000, description="Text chunk size")
    retrieval_k: int = Field(4, description="Number of documents to retrieve")
    use_openai_embeddings: bool = Field(True, description="Use OpenAI embeddings")

# Statistics Models

class SystemStats(BaseModel):
    """System statistics."""
    total_queries: int = Field(0, description="Total queries processed")
    successful_queries: int = Field(0, description="Successful queries")
    failed_queries: int = Field(0, description="Failed queries")
    avg_processing_time: float = Field(0.0, description="Average processing time")
    sql_queries: int = Field(0, description="SQL queries count")
    rag_queries: int = Field(0, description="RAG queries count")
    hybrid_queries: int = Field(0, description="Hybrid queries count")
    uptime: float = Field(0.0, description="System uptime in seconds")

class DatabaseStats(BaseModel):
    """Database statistics."""
    connection_pool_size: int = Field(0, description="Current pool size")
    active_connections: int = Field(0, description="Active connections")
    total_queries_executed: int = Field(0, description="Total SQL queries executed")
    avg_query_time: float = Field(0.0, description="Average query execution time")
    last_connection_test: Optional[datetime] = Field(None, description="Last connection test")
    connection_healthy: bool = Field(False, description="Connection health status")

class RAGStats(BaseModel):
    """RAG system statistics."""
    total_documents: int = Field(0, description="Total documents in collection")
    total_chunks: int = Field(0, description="Total text chunks")
    collection_size_mb: float = Field(0.0, description="Collection size in MB")
    last_embedding_update: Optional[datetime] = Field(None, description="Last embedding update")
    avg_retrieval_time: float = Field(0.0, description="Average retrieval time")

# Error Models

class ErrorDetail(BaseModel):
    """Detailed error information."""
    error_type: str = Field(..., description="Type of error")
    error_code: Optional[str] = Field(None, description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")
    traceback: Optional[str] = Field(None, description="Error traceback")

class APIError(BaseModel):
    """API error response."""
    success: bool = Field(False, description="Always false for errors")
    error: ErrorDetail = Field(..., description="Error details")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")

# Health Check Models

class HealthCheck(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(default_factory=datetime.now, description="Health check timestamp")
    version: str = Field("1.0.0", description="Application version")
    database_healthy: bool = Field(False, description="Database health")
    vanna_healthy: bool = Field(False, description="Vanna service health")
    rag_healthy: bool = Field(False, description="RAG service health")
    uptime: float = Field(0.0, description="Uptime in seconds")
    memory_usage_mb: float = Field(0.0, description="Memory usage in MB")
    
# Export commonly used models
__all__ = [
    'ChatRequest', 'ChatResponse', 'SQLQueryRequest', 'RAGQueryRequest',
    'SQLResult', 'RAGResult', 'IntentClassification', 'QueryType', 'QueryStatus',
    'CustomerInfo', 'QueryContext', 'ValidationResult', 'QueryLog',
    'SystemStats', 'DatabaseStats', 'RAGStats', 'HealthCheck', 'APIError'
]


