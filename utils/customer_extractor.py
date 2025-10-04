"""
Utility for extracting customer information from chat messages.
Handles various formats of customer ID and email mentions.
"""

import re
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class CustomerInfoExtractor:
    """Extracts customer ID and email from natural language messages."""
    
    # Patterns for customer ID extraction
    CUSTOMER_ID_PATTERNS = [
        r'customer[_\s]?id\s*(?:is|:)?\s*(\d+)',
        r'my\s+id\s*(?:is|:)?\s*(\d+)',
        r'id\s*(?:is|:)?\s*(\d+)',
        r'customer[_\s]?number\s*(?:is|:)?\s*(\d+)',
        r'account[_\s]?id\s*(?:is|:)?\s*(\d+)',
        r'user[_\s]?id\s*(?:is|:)?\s*(\d+)',
    ]
    
    # Patterns for email extraction
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    @classmethod
    def extract_customer_info(cls, message: str) -> Dict[str, Optional[str]]:
        """
        Extract customer ID and/or email from a message.
        
        Args:
            message: The chat message to extract from
            
        Returns:
            Dict with 'customer_id' and 'customer_email' keys (values may be None)
        """
        result = {
            'customer_id': None,
            'customer_email': None
        }
        
        if not message:
            return result
        
        message_lower = message.lower()
        
        # Extract customer ID
        for pattern in cls.CUSTOMER_ID_PATTERNS:
            match = re.search(pattern, message_lower, re.IGNORECASE)
            if match:
                result['customer_id'] = match.group(1)
                logger.info(f"Extracted customer_id: {result['customer_id']}")
                break
        
        # Extract email
        email_match = re.search(cls.EMAIL_PATTERN, message)
        if email_match:
            result['customer_email'] = email_match.group(0)
            logger.info(f"Extracted customer_email: {result['customer_email']}")
        
        return result
    
    @classmethod
    def has_customer_identifier(cls, message: str) -> bool:
        """
        Check if message contains customer identifier.
        
        Args:
            message: The message to check
            
        Returns:
            True if customer ID or email is present
        """
        info = cls.extract_customer_info(message)
        return bool(info['customer_id'] or info['customer_email'])

# Convenience functions
def extract_customer_info(message: str) -> Dict[str, Optional[str]]:
    """Extract customer ID and email from a message."""
    return CustomerInfoExtractor.extract_customer_info(message)

def has_customer_identifier(message: str) -> bool:
    """Check if message contains customer identifier."""
    return CustomerInfoExtractor.has_customer_identifier(message)
