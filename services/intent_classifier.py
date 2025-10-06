"""
Intent classification service for routing queries to appropriate handlers.
Determines whether queries should go to SQL, RAG, or hybrid processing.
"""

import logging
from typing import Dict, Any, List, Tuple
import re
from datetime import datetime

from models.schemas import IntentClassification, QueryType
from services.vanna_service import vanna_service
from services.rag_service import rag_service

logger = logging.getLogger(__name__)

class IntentClassifier:
    """Classifies user queries to determine the appropriate processing method."""
    
    def __init__(self):
        # Keywords and patterns for different query types
        self.sql_keywords = {
            'order_related': ['order', 'orders', 'purchase', 'bought', 'transaction'],
            'financial': ['spent', 'total', 'amount', 'cost', 'price', 'payment', 'paid'],
            'status': ['status', 'state', 'processing', 'shipped', 'delivered', 'cancelled'],
            'temporal': ['recent', 'last', 'this month', 'this year', 'yesterday', 'today'],
            'quantitative': ['how many', 'count', 'number of', 'sum', 'average', 'total'],
            'listing': ['show', 'list', 'display', 'find', 'search', 'get my'],
            'comparative': ['most expensive', 'cheapest', 'highest', 'lowest', 'largest', 'smallest', 'biggest', 'best', 'worst'],
            'specific_fields': ['order number', 'order id', 'increment_id', 'entity_id', 'customer_id', 'grand_total']
        }
        
        self.rag_keywords = {
            'policy': ['policy', 'rule', 'guideline', 'terms', 'conditions'],
            'procedures': ['how to', 'how do i', 'what is', 'what are', 'procedure', 'process'],
            'support': ['help', 'support', 'contact', 'phone', 'email', 'assistance'],
            'shipping': ['shipping', 'delivery', 'ship', 'deliver', 'tracking', 'track'],
            'returns': ['return', 'refund', 'exchange', 'cancel', 'cancellation'],
            'general_info': ['about', 'information', 'details', 'explain', 'tell me']
        }
        
        self.hybrid_indicators = {
            'order_with_policy': ['return order', 'cancel order', 'refund order', 'refund my order'],
            'action_requests': ['i want to refund', 'i want to cancel', 'i want to return', 
                            'need to refund', 'need to cancel', 'need to return'],
            'status_with_info': ['why is', 'what happened to', 'problem with order'],
            'eligibility': ['eligible', 'qualify', 'can i return', 'can i cancel', 'can i refund']
        }
        
        # Compiled regex patterns for efficiency
        self.order_number_pattern = re.compile(r'#?\d{8,}')
        self.money_pattern = re.compile(r'\$\d+|\d+\s*dollars?|\d+\.\d{2}')
        self.date_pattern = re.compile(r'last\s+(month|week|year)|this\s+(month|week|year)|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}')
    
    def classify_intent(self, question: str, customer_id: str = None) -> IntentClassification:
        """
        Classify the intent of a user question.
        
        Args:
            question: User's question
            customer_id: Customer ID (helps with classification)
            
        Returns:
            IntentClassification with query type and confidence
        """
        try:
            question_lower = question.lower().strip()
            
            # Calculate scores for each query type
            sql_score = self._calculate_sql_score(question_lower)
            rag_score = self._calculate_rag_score(question_lower)
            hybrid_score = self._calculate_hybrid_score(question_lower)
            
            # Determine the most likely query type
            scores = {
                QueryType.SQL: sql_score,
                QueryType.RAG: rag_score,
                QueryType.HYBRID: hybrid_score
            }
            
            # Find the highest scoring type
            best_type = max(scores.keys(), key=lambda k: scores[k])
            best_score = scores[best_type]
            
            # If no clear winner or very low scores, mark as unknown
            if best_score < 0.3 or (max(scores.values()) - min(scores.values())) < 0.2:
                query_type = QueryType.UNKNOWN
                confidence = 0.1
                reasoning = "No clear intent detected"
            else:
                query_type = best_type
                confidence = min(1.0, best_score)
                reasoning = self._generate_reasoning(question_lower, query_type, sql_score, rag_score, hybrid_score)
            
            # Extract keywords that influenced the decision
            keywords = self._extract_keywords(question_lower, query_type)
            
            return IntentClassification(
                query_type=query_type,
                confidence=confidence,
                reasoning=reasoning,
                keywords=keywords
            )
            
        except Exception as e:
            logger.error(f"Failed to classify intent for question '{question}': {e}")
            return IntentClassification(
                query_type=QueryType.UNKNOWN,
                confidence=0.0,
                reasoning=f"Classification error: {str(e)}",
                keywords=[]
            )
    
    def _calculate_sql_score(self, question: str) -> float:
        """Calculate likelihood that question requires SQL processing."""
        score = 0.0
        
        # Check for SQL-related keywords
        for category, keywords in self.sql_keywords.items():
            category_score = sum(1 for keyword in keywords if keyword in question)
            if category_score > 0:
                # Weight different categories
                weights = {
                    'order_related': 0.3,
                    'financial': 0.25,
                    'status': 0.2,
                    'temporal': 0.15,
                    'quantitative': 0.25,
                    'listing': 0.2,
                    'comparative': 0.35,  # Strong indicator for SQL
                    'specific_fields': 0.4  # Very strong indicator for SQL
                }
                score += category_score * weights.get(category, 0.1)
        
        # Boost score for specific patterns
        if self.order_number_pattern.search(question):
            score += 0.4  # Strong indicator of database query
        
        if self.money_pattern.search(question):
            score += 0.3  # Financial queries usually need database
        
        if self.date_pattern.search(question):
            score += 0.2  # Date ranges suggest database queries
        
        # Check for personal pronouns (my, i, me) - suggests personal data
        personal_pronouns = ['my ', ' my ', 'i ', ' i ', ' me ', 'me ']
        if any(pronoun in question for pronoun in personal_pronouns):
            score += 0.2
        
        # Strong SQL patterns that combine question words with order data
        sql_data_patterns = [
            'what is the order number',
            'which order',
            'what order',
            'show order',
            'get order',
            'most expensive order',
            'cheapest order',
            'highest order',
            'lowest order'
        ]
        for pattern in sql_data_patterns:
            if pattern in question:
                score += 0.5  # Very strong indicator
        
        return min(1.0, score)
    
    def _calculate_rag_score(self, question: str) -> float:
        """Calculate likelihood that question requires RAG processing."""
        score = 0.0
        
        # Check for RAG-related keywords
        for category, keywords in self.rag_keywords.items():
            category_score = sum(1 for keyword in keywords if keyword in question)
            if category_score > 0:
                # Weight different categories
                weights = {
                    'policy': 0.3,
                    'procedures': 0.25,
                    'support': 0.2,
                    'shipping': 0.2,
                    'returns': 0.25,
                    'general_info': 0.15
                }
                score += category_score * weights.get(category, 0.1)
        
        # Check for question words that suggest informational queries
        question_words = ['what', 'how', 'why', 'when', 'where', 'which', 'who']
        question_word_count = sum(1 for word in question_words if word in question)
        score += question_word_count * 0.15
        
        # Boost for general inquiry patterns
        general_patterns = [
            'what is', 'how do', 'can i', 'do you', 'are you', 'will you',
            'what are', 'how to', 'tell me about', 'explain'
        ]
        for pattern in general_patterns:
            if pattern in question:
                score += 0.2
        
        return min(1.0, score)
    
    def _calculate_hybrid_score(self, question: str) -> float:
        """Calculate likelihood that question requires hybrid processing."""
        score = 0.0
        
        # Check for hybrid indicators
        for category, patterns in self.hybrid_indicators.items():
            for pattern in patterns:
                if pattern in question:
                    score += 0.4
        
        # Look for combinations of SQL and RAG keywords
        sql_present = any(
            any(keyword in question for keyword in keywords)
            for keywords in self.sql_keywords.values()
        )
        
        rag_present = any(
            any(keyword in question for keyword in keywords)
            for keywords in self.rag_keywords.values()
        )
        
        if sql_present and rag_present:
            score += 0.5
        
        # Specific hybrid patterns
        hybrid_patterns = [
            'can i return order',
            'cancel my order',
            'refund for order',
            'refund the order',  # Add this
            'i want to refund', 
            'why was my order',
            'what happened to order',
            'order problem',
            'issue with order'
        ]
        
        for pattern in hybrid_patterns:
            if pattern in question:
                score += 0.3
        
        return min(1.0, score)
    
    def _generate_reasoning(self, question: str, query_type: QueryType, 
                          sql_score: float, rag_score: float, hybrid_score: float) -> str:
        """Generate human-readable reasoning for the classification."""
        reasons = []
        
        if query_type == QueryType.SQL:
            if self.order_number_pattern.search(question):
                reasons.append("contains order number")
            if self.money_pattern.search(question):
                reasons.append("mentions monetary amounts")
            if any(keyword in question for keyword in ['my ', 'show me', 'list my']):
                reasons.append("requests personal data")
            if any(keyword in question for keyword in ['total', 'count', 'how many']):
                reasons.append("requires calculations")
        
        elif query_type == QueryType.RAG:
            if any(keyword in question for keyword in ['policy', 'how to', 'what is']):
                reasons.append("asks about policies or procedures")
            if any(keyword in question for keyword in ['return', 'shipping', 'support']):
                reasons.append("relates to general information")
            if question.startswith(('what', 'how', 'why', 'when', 'where')):
                reasons.append("informational question")
        
        elif query_type == QueryType.HYBRID:
            reasons.append("combines order-specific and policy questions")
            if any(pattern in question for pattern in ['return order', 'cancel order']):
                reasons.append("needs both order data and policy information")
        
        if not reasons:
            reasons.append(f"highest score: {query_type.value} ({max(sql_score, rag_score, hybrid_score):.2f})")
        
        return "; ".join(reasons)
    
    def _extract_keywords(self, question: str, query_type: QueryType) -> List[str]:
        """Extract keywords that influenced the classification decision."""
        keywords = []
        
        if query_type == QueryType.SQL:
            for category, kw_list in self.sql_keywords.items():
                keywords.extend([kw for kw in kw_list if kw in question])
        
        elif query_type == QueryType.RAG:
            for category, kw_list in self.rag_keywords.items():
                keywords.extend([kw for kw in kw_list if kw in question])
        
        elif query_type == QueryType.HYBRID:
            # Include keywords from both SQL and RAG
            for category, kw_list in self.sql_keywords.items():
                keywords.extend([kw for kw in kw_list if kw in question])
            for category, kw_list in self.rag_keywords.items():
                keywords.extend([kw for kw in kw_list if kw in question])
        
        # Remove duplicates and limit to most relevant
        return list(set(keywords))[:10]
    
    def get_classification_confidence_threshold(self) -> float:
        """Get the minimum confidence threshold for reliable classification."""
        return 0.6
    
    def validate_classification(self, question: str, predicted_type: QueryType) -> Dict[str, Any]:
        """
        Validate classification using service-specific validators.
        
        Args:
            question: Original question
            predicted_type: Predicted query type
            
        Returns:
            Validation results with recommendations
        """
        try:
            validation = {
                'predicted_type': predicted_type.value,
                'validations': {},
                'recommendations': []
            }
            
            # Validate with SQL service
            if predicted_type in [QueryType.SQL, QueryType.HYBRID]:
                sql_validation = vanna_service.validate_query_syntax(question)
                validation['validations']['sql'] = sql_validation
                
                if not sql_validation.get('suitable_for_sql', False):
                    validation['recommendations'].append("Consider RAG processing instead of SQL")
            
            # Validate with RAG service
            if predicted_type in [QueryType.RAG, QueryType.HYBRID]:
                rag_validation = rag_service.validate_query_for_rag(question)
                validation['validations']['rag'] = rag_validation
                
                if not rag_validation.get('suitable_for_rag', False):
                    validation['recommendations'].append("Consider SQL processing instead of RAG")
            
            # Cross-validation recommendations
            if predicted_type == QueryType.HYBRID:
                sql_suitable = validation['validations'].get('sql', {}).get('suitable_for_sql', False)
                rag_suitable = validation['validations'].get('rag', {}).get('suitable_for_rag', False)
                
                if not (sql_suitable and rag_suitable):
                    if sql_suitable:
                        validation['recommendations'].append("Use SQL processing only")
                    elif rag_suitable:
                        validation['recommendations'].append("Use RAG processing only")
                    else:
                        validation['recommendations'].append("Query may not be suitable for either system")
            
            return validation
            
        except Exception as e:
            logger.error(f"Failed to validate classification: {e}")
            return {
                'predicted_type': predicted_type.value,
                'error': str(e),
                'validations': {},
                'recommendations': ['Classification validation failed']
            }
    
    def get_sample_queries_by_type(self) -> Dict[str, List[str]]:
        """Get sample queries organized by type for testing."""
        return {
            'sql': [
                "Show me my orders from last month",
                "What's the status of order #100000123?",
                "How much did I spend this year?",
                "List my processing orders",
                "How many orders do I have?"
            ],
            'rag': [
                "What is your return policy?",
                "How do I track my shipment?",
                "What payment methods do you accept?",
                "How long does shipping take?",
                "How do I contact support?"
            ],
            'hybrid': [
                "Can I return order #100000123?",
                "Why was my recent order cancelled?",
                "Is my order eligible for refund?",
                "How do I cancel order #100000456?",
                "What's the return policy for my order?"
            ]
        }
    
    def get_classification_stats(self) -> Dict[str, Any]:
        """Get statistics about classification performance."""
        # This would typically track classification accuracy over time
        # For now, return basic configuration info
        return {
            'sql_keyword_categories': len(self.sql_keywords),
            'rag_keyword_categories': len(self.rag_keywords),
            'hybrid_indicators': len(self.hybrid_indicators),
            'confidence_threshold': self.get_classification_confidence_threshold(),
            'supported_types': [t.value for t in QueryType]
        }

# Global classifier instance
intent_classifier = IntentClassifier()

