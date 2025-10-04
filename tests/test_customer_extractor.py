"""
Tests for customer information extraction from messages.
"""

import pytest
from utils.customer_extractor import CustomerInfoExtractor, extract_customer_info, has_customer_identifier


class TestCustomerInfoExtractor:
    """Test suite for CustomerInfoExtractor."""
    
    def test_extract_customer_id_basic(self):
        """Test basic customer_id extraction."""
        message = "hi my customer_id is 1"
        result = extract_customer_info(message)
        
        assert result['customer_id'] == '1'
        assert result['customer_email'] is None
    
    def test_extract_customer_id_variations(self):
        """Test various customer_id formats."""
        test_cases = [
            ("customer_id is 123", "123"),
            ("customer id is 456", "456"),
            ("my customer_id: 789", "789"),
            ("customer id: 999", "999"),
            ("my id is 111", "111"),
            ("id is 222", "222"),
            ("customer_number is 333", "333"),
            ("account_id is 444", "444"),
            ("user_id is 555", "555"),
        ]
        
        for message, expected_id in test_cases:
            result = extract_customer_info(message)
            assert result['customer_id'] == expected_id, f"Failed for: {message}"
    
    def test_extract_email(self):
        """Test email extraction."""
        message = "my email is test@example.com"
        result = extract_customer_info(message)
        
        assert result['customer_email'] == 'test@example.com'
    
    def test_extract_both(self):
        """Test extracting both customer_id and email."""
        message = "hi my customer_id is 1 and email is user@test.com"
        result = extract_customer_info(message)
        
        assert result['customer_id'] == '1'
        assert result['customer_email'] == 'user@test.com'
    
    def test_no_customer_info(self):
        """Test message with no customer info."""
        message = "show me my recent orders"
        result = extract_customer_info(message)
        
        assert result['customer_id'] is None
        assert result['customer_email'] is None
    
    def test_has_customer_identifier_true(self):
        """Test has_customer_identifier returns True."""
        assert has_customer_identifier("customer_id is 1")
        assert has_customer_identifier("email is test@example.com")
    
    def test_has_customer_identifier_false(self):
        """Test has_customer_identifier returns False."""
        assert not has_customer_identifier("show me my orders")
    
    def test_case_insensitive(self):
        """Test case insensitive extraction."""
        test_cases = [
            "CUSTOMER_ID IS 123",
            "Customer_Id is 123",
            "customer_id is 123",
        ]
        
        for message in test_cases:
            result = extract_customer_info(message)
            assert result['customer_id'] == '123', f"Failed for: {message}"
    
    def test_multiple_numbers(self):
        """Test extraction when multiple numbers present."""
        message = "I am user 100 and my customer_id is 200"
        result = extract_customer_info(message)
        
        # Should extract the one explicitly labeled as customer_id
        assert result['customer_id'] == '200'
    
    def test_empty_message(self):
        """Test empty message handling."""
        result = extract_customer_info("")
        
        assert result['customer_id'] is None
        assert result['customer_email'] is None
    
    def test_none_message(self):
        """Test None message handling."""
        result = extract_customer_info(None)
        
        assert result['customer_id'] is None
        assert result['customer_email'] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
