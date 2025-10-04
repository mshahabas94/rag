"""
Main chatbot orchestrator - coordinates all services and handles user interactions.
This is the primary entry point for the hybrid chatbot system.
"""

import os
import logging
import time
from typing import Dict, Any, List
from datetime import datetime
import asyncio
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/chatbot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Import all services and utilities
from models.schemas import (
    ChatRequest, ChatResponse, SQLQueryRequest, RAGQueryRequest,
    QueryType, QueryLog, CustomerInfo, HealthCheck
)
from services.vanna_service import vanna_service
from services.rag_service import rag_service
from services.intent_classifier import intent_classifier
from utils.security import (
    validate_sql_security, enforce_rate_limit, log_security_event
)
from utils.query_logger import query_logger, system_monitor

class HybridChatbot:
    """
    Main chatbot orchestrator that coordinates SQL and RAG services.
    Handles intent classification, routing, and response generation.
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.is_initialized = False
        self.initialization_errors = []
        
        # Ensure logs directory exists
        Path("logs").mkdir(exist_ok=True)
        
        logger.info("Initializing Hybrid Chatbot...")
    
    async def initialize(self) -> bool:
        """
        Initialize all services asynchronously.
        
        Returns:
            True if initialization successful
        """
        try:
            if self.is_initialized:
                return True
            
            logger.info("Starting chatbot initialization...")
            
            # Initialize services in parallel where possible
            initialization_tasks = []
            
            # Initialize Vanna service
            logger.info("Initializing Vanna service...")
            vanna_success = vanna_service.initialize()
            if not vanna_success:
                self.initialization_errors.append("Vanna service initialization failed")
            
            # Initialize RAG service
            logger.info("Initializing RAG service...")
            rag_success = rag_service.initialize()
            if not rag_success:
                self.initialization_errors.append("RAG service initialization failed")
            
            # Check if at least one service is working
            if not (vanna_success or rag_success):
                logger.error("Both Vanna and RAG services failed to initialize")
                return False
            
            # Log any partial failures
            if self.initialization_errors:
                logger.warning(f"Partial initialization failures: {self.initialization_errors}")
            
            self.is_initialized = True
            uptime = time.time() - self.start_time
            logger.info(f"Chatbot initialized successfully in {uptime:.2f} seconds")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize chatbot: {e}")
            self.initialization_errors.append(str(e))
            return False
    
    async def process_chat_request(self, request: ChatRequest) -> ChatResponse:
        """
        Process a chat request and return appropriate response.
        
        Args:
            request: Chat request from user
            
        Returns:
            ChatResponse with answer and metadata
        """
        start_time = time.time()
        session_id = request.session_id or f"session_{int(time.time())}"
        
        try:
            # Ensure chatbot is initialized
            if not self.is_initialized:
                await self.initialize()
                if not self.is_initialized:
                    return self._create_error_response(
                        "Chatbot not properly initialized",
                        session_id,
                        start_time
                    )
            
            # Rate limiting check
            rate_limit_id = request.customer_id or request.customer_email or "anonymous"
            allowed, rate_info = enforce_rate_limit(rate_limit_id)
            
            if not allowed:
                log_security_event(
                    'rate_limit_exceeded',
                    {
                        'identifier': rate_limit_id,
                        'current_count': rate_info['current_count'],
                        'session_id': session_id
                    },
                    'medium'
                )
                
                return self._create_error_response(
                    f"Rate limit exceeded. Try again in {rate_info.get('reset_time', 3600)} seconds.",
                    session_id,
                    start_time
                )
            
            # Classify intent
            logger.info(f"Processing question: {request.question[:100]}...")
            
            intent_classification = intent_classifier.classify_intent(
                request.question,
                request.customer_id
            )
            
            logger.info(
                f"Intent classified as {intent_classification.query_type.value} "
                f"with confidence {intent_classification.confidence:.2f}"
            )
            
            # Route to appropriate service(s)
            response = await self._route_query(request, intent_classification, session_id)
            
            # Log the query
            await self._log_query(request, response, intent_classification, session_id, start_time)
            
            return response
            
        except Exception as e:
            logger.error(f"Unexpected error processing chat request: {e}")
            
            # Log error query
            try:
                await self._log_error_query(request, str(e), session_id, start_time)
            except:
                pass  # Don't fail on logging errors
            
            return self._create_error_response(
                f"An unexpected error occurred: {str(e)}",
                session_id,
                start_time
            )
    
    async def _route_query(self, request: ChatRequest, 
                          intent: Any, session_id: str) -> ChatResponse:
        """Route query to appropriate service based on intent classification."""
        
        if intent.query_type == QueryType.SQL:
            return await self._process_sql_query(request, intent, session_id)
        
        elif intent.query_type == QueryType.RAG:
            return await self._process_rag_query(request, intent, session_id)
        
        elif intent.query_type == QueryType.HYBRID:
            return await self._process_hybrid_query(request, intent, session_id)
        
        else:  # UNKNOWN
            return await self._process_unknown_query(request, intent, session_id)
    
    async def _process_sql_query(self, request: ChatRequest, 
                               intent: Any, session_id: str) -> ChatResponse:
        """Process SQL-based query."""
        start_time = time.time()
        
        try:
            # Create SQL request
            sql_request = SQLQueryRequest(
                question=request.question,
                customer_id=request.customer_id,
                customer_email=request.customer_email
            )
            
            # Process with Vanna service
            sql_result = vanna_service.process_sql_query(sql_request, session_id)
            
            processing_time = time.time() - start_time
            
            if sql_result.success:
                # Format successful response
                answer = self._format_sql_answer(sql_result)
                
                return ChatResponse(
                    success=True,
                    answer=answer,
                    query_type=QueryType.SQL,
                    intent_classification=intent,
                    sql_result=sql_result,
                    processing_time=processing_time,
                    session_id=session_id
                )
            else:
                # Handle SQL failure - try RAG as fallback
                logger.warning(f"SQL processing failed: {sql_result.error}")
                
                # Try RAG as fallback for better user experience
                rag_request = RAGQueryRequest(question=request.question)
                rag_result = rag_service.process_rag_query(rag_request, session_id)
                
                if rag_result.success:
                    answer = f"I couldn't find specific data for your query, but here's some general information: {rag_result.answer}"
                    
                    return ChatResponse(
                        success=True,
                        answer=answer,
                        query_type=QueryType.RAG,  # Changed to RAG since that's what worked
                        intent_classification=intent,
                        rag_result=rag_result,
                        processing_time=processing_time,
                        session_id=session_id
                    )
                else:
                    return ChatResponse(
                        success=False,
                        answer="I'm sorry, I couldn't process your query. Please try rephrasing or contact support.",
                        query_type=QueryType.SQL,
                        intent_classification=intent,
                        sql_result=sql_result,
                        processing_time=processing_time,
                        session_id=session_id,
                        error=sql_result.error
                    )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error in SQL query processing: {e}")
            
            return ChatResponse(
                success=False,
                answer="An error occurred while processing your database query.",
                query_type=QueryType.SQL,
                intent_classification=intent,
                processing_time=processing_time,
                session_id=session_id,
                error=str(e)
            )
    
    async def _process_rag_query(self, request: ChatRequest, 
                               intent: Any, session_id: str) -> ChatResponse:
        """Process RAG-based query."""
        start_time = time.time()
        
        try:
            # Create RAG request
            rag_request = RAGQueryRequest(
                question=request.question,
                include_sources=True
            )
            
            # Process with RAG service
            rag_result = rag_service.process_rag_query(rag_request, session_id)
            
            processing_time = time.time() - start_time
            
            if rag_result.success:
                answer = rag_result.answer
                
                # Add source information if available
                if rag_result.sources:
                    source_info = "\n\nSources: " + ", ".join([
                        src.get('filename', 'Unknown') for src in rag_result.sources[:3]
                    ])
                    answer += source_info
                
                return ChatResponse(
                    success=True,
                    answer=answer,
                    query_type=QueryType.RAG,
                    intent_classification=intent,
                    rag_result=rag_result,
                    processing_time=processing_time,
                    session_id=session_id
                )
            else:
                return ChatResponse(
                    success=False,
                    answer="I couldn't find relevant information to answer your question. Please contact support for assistance.",
                    query_type=QueryType.RAG,
                    intent_classification=intent,
                    rag_result=rag_result,
                    processing_time=processing_time,
                    session_id=session_id,
                    error=rag_result.error
                )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error in RAG query processing: {e}")
            
            return ChatResponse(
                success=False,
                answer="An error occurred while searching our knowledge base.",
                query_type=QueryType.RAG,
                intent_classification=intent,
                processing_time=processing_time,
                session_id=session_id,
                error=str(e)
            )
    
    async def _process_hybrid_query(self, request: ChatRequest, 
                            intent: Any, session_id: str) -> ChatResponse:
        """Process hybrid query requiring both SQL and RAG."""
        start_time = time.time()
        
        try:
            # Process both SQL and RAG in parallel
            sql_task = self._get_sql_data(request, session_id)
            rag_task = self._get_rag_data(request, session_id)
            
            sql_result, rag_result = await asyncio.gather(sql_task, rag_task, return_exceptions=True)
            
            # Add debug logging
            logger.info(f"SQL result type: {type(sql_result)}, success: {getattr(sql_result, 'success', 'N/A')}")
            logger.info(f"RAG result type: {type(rag_result)}, success: {getattr(rag_result, 'success', 'N/A')}")
            
            processing_time = time.time() - start_time
            
            # Combine results
            answer_parts = []
            
            # Add SQL results if successful
            if not isinstance(sql_result, Exception) and sql_result and sql_result.success:
                sql_answer = self._format_sql_answer(sql_result, brief=False)
                answer_parts.append(f"📋 Your Order Details:\n{sql_answer}")
            else:
                logger.warning(f"SQL failed: {sql_result}")
            
            # Add RAG results if successful
            if not isinstance(rag_result, Exception) and rag_result and rag_result.success:
                answer_parts.append(f"\n📖 Policy Information:\n{rag_result.answer}")
            else:
                logger.warning(f"RAG failed: {rag_result}")
            
            # Create combined answer
            if answer_parts:
                answer = "\n".join(answer_parts)
                success = True
            else:
                answer = "I couldn't retrieve complete information for your query. Please contact support."
                success = False
            
            return ChatResponse(
                success=success,
                answer=answer,
                query_type=QueryType.HYBRID,
                intent_classification=intent,
                sql_result=sql_result if not isinstance(sql_result, Exception) else None,
                rag_result=rag_result if not isinstance(rag_result, Exception) else None,
                processing_time=processing_time,
                session_id=session_id
            )
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error in hybrid query processing: {e}")
            
            return ChatResponse(
                success=False,
                answer="An error occurred while processing your complex query.",
                query_type=QueryType.HYBRID,
                intent_classification=intent,
                processing_time=processing_time,
                session_id=session_id,
                error=str(e)
            )
    
    async def _process_unknown_query(self, request: ChatRequest, 
                                   intent: Any, session_id: str) -> ChatResponse:
        """Process query with unknown intent."""
        start_time = time.time()
        
        # Try both services and see which one works better
        try:
            # First try RAG (safer for unknown queries)
            rag_request = RAGQueryRequest(question=request.question)
            rag_result = rag_service.process_rag_query(rag_request, session_id)
            
            processing_time = time.time() - start_time
            
            if rag_result.success and rag_result.confidence and rag_result.confidence > 0.5:
                return ChatResponse(
                    success=True,
                    answer=rag_result.answer,
                    query_type=QueryType.RAG,
                    intent_classification=intent,
                    rag_result=rag_result,
                    processing_time=processing_time,
                    session_id=session_id
                )
            
            # If RAG didn't work well, suggest clarification
            return ChatResponse(
                success=False,
                answer=(
                    "I'm not sure how to help with that. Could you please rephrase your question? "
                    "I can help you with:\n"
                    "• Order information (status, history, totals)\n"
                    "• Policies (returns, shipping, payments)\n"
                    "• General support questions"
                ),
                query_type=QueryType.UNKNOWN,
                intent_classification=intent,
                processing_time=processing_time,
                session_id=session_id
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error processing unknown query: {e}")
            
            return ChatResponse(
                success=False,
                answer="I'm having trouble understanding your question. Please contact support for assistance.",
                query_type=QueryType.UNKNOWN,
                intent_classification=intent,
                processing_time=processing_time,
                session_id=session_id,
                error=str(e)
            )
    
    async def _get_sql_data(self, request: ChatRequest, session_id: str):
        """Helper to get SQL data asynchronously."""
        try:
            sql_request = SQLQueryRequest(
                question=request.question,
                customer_id=request.customer_id,
                customer_email=request.customer_email
            )
            return vanna_service.process_sql_query(sql_request, session_id)
        except Exception as e:
            logger.error(f"Error getting SQL data: {e}")
            return None
    
    async def _get_rag_data(self, request: ChatRequest, session_id: str):
        """Helper to get RAG data asynchronously - extracts policy question."""
        try:
            # Extract the policy-related question from the original query
            policy_question = self._extract_policy_question(request.question)
            
            rag_request = RAGQueryRequest(
                question=policy_question,
                include_sources=True
            )
            return rag_service.process_rag_query(rag_request, session_id)
        except Exception as e:
            logger.error(f"Error getting RAG data: {e}")
            return None

    def _extract_policy_question(self, question: str) -> str:
        """Extract policy-related question from hybrid query."""
        question_lower = question.lower()
        
        # Map action keywords to policy questions
        policy_mappings = {
            'refund': "What is your refund policy? How do I get a refund?",
            'return': "What is your return policy? How do I return an item?",
            'cancel': "What is your cancellation policy? How do I cancel an order?",
            'exchange': "What is your exchange policy? How do I exchange an item?",
            'tracking': "How do I track my order?",
            'shipping': "What are your shipping policies and timelines?",
            'delivery': "What are your delivery policies and timelines?"
        }
        
        # Find matching policy keywords
        for keyword, policy_question in policy_mappings.items():
            if keyword in question_lower:
                logger.info(f"Extracted policy question for '{keyword}': {policy_question}")
                return policy_question
        
        # Default: ask about general order policies
        return "What are your order policies for returns, refunds, and cancellations?"
    
    def _format_sql_answer(self, sql_result, brief: bool = False) -> str:
        """Format SQL results into human-readable answer."""
        try:
            if not sql_result.data:
                return "No results found for your query."
            
            data = sql_result.data
            row_count = len(data)
            
            if row_count == 1:
                # Single result - format as details
                row = data[0]
                if brief:
                    # Brief format for hybrid queries
                    key_fields = ['increment_id', 'status', 'grand_total', 'created_at']
                    details = []
                    for field in key_fields:
                        if field in row and row[field] is not None:
                            details.append(f"{field}: {row[field]}")
                    return "; ".join(details) if details else "Order found"
                else:
                    # Full format for SQL-only queries
                    return self._format_single_order(row)
            
            elif row_count <= 10:
                # Multiple results - format as list
                return self._format_multiple_orders(data, brief)
            
            else:
                # Too many results - summarize
                return f"Found {row_count} results. Showing summary of recent items."
            
        except Exception as e:
            logger.error(f"Error formatting SQL answer: {e}")
            return f"Found {sql_result.row_count} results."
    
    def _format_single_order(self, order: Dict[str, Any]) -> str:
        """Format a single order record."""
        try:
            parts = []
            
            # Order identification
            if order.get('increment_id'):
                parts.append(f"Order #{order['increment_id']}")
            
            # Status
            if order.get('status'):
                parts.append(f"Status: {order['status']}")
            
            # Total
            if order.get('grand_total'):
                parts.append(f"Total: ${order['grand_total']}")
            
            # Date
            if order.get('created_at'):
                parts.append(f"Date: {order['created_at']}")
            
            return " | ".join(parts) if parts else "Order information available"
            
        except Exception as e:
            logger.error(f"Error formatting single order: {e}")
            return "Order details available"
    
    def _format_multiple_orders(self, orders: List[Dict[str, Any]], brief: bool = False) -> str:
        """Format multiple order records."""
        try:
            if brief:
                return f"Found {len(orders)} orders"
            
            formatted_orders = []
            for order in orders[:5]:  # Limit to first 5
                order_str = self._format_single_order(order)
                formatted_orders.append(order_str)
            
            result = "\n".join(formatted_orders)
            
            if len(orders) > 5:
                result += f"\n... and {len(orders) - 5} more orders"
            
            return result
            
        except Exception as e:
            logger.error(f"Error formatting multiple orders: {e}")
            return f"Found {len(orders)} orders"
    
    async def _log_query(self, request: ChatRequest, response: ChatResponse, 
                        intent: Any, session_id: str, start_time: float):
        """Log query for monitoring and analytics."""
        try:
            query_log = QueryLog(
                session_id=session_id,
                customer_id=request.customer_id,
                question=request.question,
                query_type=response.query_type,
                success=response.success,
                processing_time=time.time() - start_time,
                sql_query=response.sql_result.sql if response.sql_result else None,
                row_count=response.sql_result.row_count if response.sql_result else None,
                error_message=response.error
            )
            
            query_logger.log_query(query_log)
            
        except Exception as e:
            logger.error(f"Failed to log query: {e}")
    
    async def _log_error_query(self, request: ChatRequest, error: str, 
                             session_id: str, start_time: float):
        """Log failed query."""
        try:
            query_log = QueryLog(
                session_id=session_id,
                customer_id=request.customer_id,
                question=request.question,
                query_type=QueryType.UNKNOWN,
                success=False,
                processing_time=time.time() - start_time,
                error_message=error
            )
            
            query_logger.log_query(query_log)
            
        except Exception as e:
            logger.error(f"Failed to log error query: {e}")
    
    def _create_error_response(self, error_message: str, session_id: str, 
                             start_time: float) -> ChatResponse:
        """Create standardized error response."""
        return ChatResponse(
            success=False,
            answer="I'm sorry, I'm experiencing technical difficulties. Please try again later or contact support.",
            query_type=QueryType.UNKNOWN,
            processing_time=time.time() - start_time,
            session_id=session_id,
            error=error_message
        )
    
    def get_health_status(self) -> HealthCheck:
        """Get comprehensive health status of the chatbot."""
        try:
            # Get service health statuses
            vanna_health = vanna_service.get_service_health()
            rag_health = rag_service.get_service_health()
            system_health = system_monitor.get_system_health()
            
            # Determine overall status
            database_healthy = vanna_health.get('database_connected', False)
            vanna_healthy = vanna_health.get('healthy', False)
            rag_healthy = rag_health.get('healthy', False)
            
            overall_healthy = self.is_initialized and (vanna_healthy or rag_healthy)
            status = "healthy" if overall_healthy else "unhealthy"
            
            return HealthCheck(
                status=status,
                database_healthy=database_healthy,
                vanna_healthy=vanna_healthy,
                rag_healthy=rag_healthy,
                uptime=time.time() - self.start_time,
                memory_usage_mb=system_health.get('memory', {}).get('used_mb', 0)
            )
            
        except Exception as e:
            logger.error(f"Failed to get health status: {e}")
            return HealthCheck(
                status="error",
                database_healthy=False,
                vanna_healthy=False,
                rag_healthy=False,
                uptime=time.time() - self.start_time
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get chatbot statistics."""
        try:
            return {
                'system_stats': query_logger.get_stats().dict(),
                'performance_metrics': query_logger.get_performance_metrics(),
                'health_status': self.get_health_status().dict(),
                'initialization_errors': self.initialization_errors,
                'uptime_seconds': time.time() - self.start_time
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {'error': str(e)}

# Global chatbot instance
chatbot = HybridChatbot()

# Main function for CLI usage
async def main():
    """Main function for command-line interface."""
    print("Initializing Hybrid Chatbot...")
    
    success = await chatbot.initialize()
    if not success:
        print("Failed to initialize chatbot. Check logs for details.")
        return
    
    print("Chatbot ready! Type 'quit' to exit, 'health' for status, 'stats' for statistics.")
    print("Note: For database queries, you'll need to provide customer_id or customer_email.")
    
    while True:
        try:
            question = input("\nYour question: ").strip()
            
            if question.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            if question.lower() == 'health':
                health = chatbot.get_health_status()
                print(f"Health Status: {health.status}")
                print(f"Database: {'✓' if health.database_healthy else '✗'}")
                print(f"Vanna: {'✓' if health.vanna_healthy else '✗'}")
                print(f"RAG: {'✓' if health.rag_healthy else '✗'}")
                continue
            
            if question.lower() == 'stats':
                stats = chatbot.get_stats()
                system_stats = stats.get('system_stats', {})
                print(f"Total Queries: {system_stats.get('total_queries', 0)}")
                print(f"Success Rate: {system_stats.get('successful_queries', 0) / max(1, system_stats.get('total_queries', 1)) * 100:.1f}%")
                print(f"Uptime: {stats.get('uptime_seconds', 0):.0f} seconds")
                continue
            
            if not question:
                continue
            
            # For CLI, use demo customer ID
            request = ChatRequest(
                question=question,
                customer_id="demo_customer_123",  # Demo customer for CLI
                session_id="cli_session"
            )
            
            print("Processing...")
            response = await chatbot.process_chat_request(request)
            
            print(f"\nAnswer: {response.answer}")
            print(f"Query Type: {response.query_type.value}")
            print(f"Processing Time: {response.processing_time:.2f}s")
            
            if not response.success and response.error:
                print(f"Error: {response.error}")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
