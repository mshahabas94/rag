"""
Vanna training script for the sales_order table.
This script trains Vanna.ai on the e-commerce database schema and sample queries.
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any
import time
from dotenv import load_dotenv

# This loads variables from your .env file
load_dotenv()
# Add parent directory to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from config.database import db_config
from config.vanna_config import vanna_config
from utils.query_logger import query_logger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VannaTrainer:
    """Handles training of Vanna.ai model on sales_order table."""
    
    def __init__(self):
        self.db_config = db_config
        self.vanna_config = vanna_config
        self.training_stats = {
            'ddl_trained': False,
            'sample_queries_trained': 0,
            'documentation_trained': 0,
            'errors': []
        }
    
    def run_training(self, force_retrain: bool = False) -> bool:
        """
        Run complete Vanna training process.
        
        Args:
            force_retrain: Whether to retrain even if already trained
            
        Returns:
            True if training successful
        """
        try:
            logger.info("Starting Vanna training process...")
            
            # Check if already trained
            if not force_retrain and self.vanna_config.is_trained():
                logger.info("Vanna model already trained. Use force_retrain=True to retrain.")
                return True
            
            # Step 1: Test database connection
            if not self._test_database_connection():
                return False
            
            # Step 2: Initialize Vanna
            if not self._initialize_vanna():
                return False
            
            # Step 3: Train on schema
            if not self._train_schema():
                return False
            
            # Step 4: Train on sample queries
            if not self._train_sample_queries():
                return False
            
            # Step 5: Train on documentation
            if not self._train_documentation():
                return False
            
            # Step 6: Validate training
            if not self._validate_training():
                return False
            
            logger.info("Vanna training completed successfully!")
            self._print_training_summary()
            
            return True
            
        except Exception as e:
            logger.error(f"Training failed with error: {e}")
            self.training_stats['errors'].append(str(e))
            return False
    
    def _test_database_connection(self) -> bool:
        """Test database connectivity."""
        try:
            logger.info("Testing database connection...")
            
            if not self.db_config.test_connection():
                logger.error("Database connection test failed")
                return False
            
            logger.info("Database connection successful")
            return True
            
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            self.training_stats['errors'].append(f"Database connection: {str(e)}")
            return False
    
    def _initialize_vanna(self) -> bool:
        """Initialize Vanna instance."""
        try:
            logger.info("Initializing Vanna...")
            
            vn = self.vanna_config.get_vanna_instance()
            logger.info("Vanna initialized successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Vanna initialization failed: {e}")
            self.training_stats['errors'].append(f"Vanna init: {str(e)}")
            return False
    
    def _train_schema(self) -> bool:
        """Train Vanna on the sales_order table schema."""
        try:
            logger.info("Training Vanna on sales_order schema...")
            
            # Get table schema
            schema_info = self.db_config.get_table_schema('sales_order')
            
            if not schema_info or not schema_info.get('columns'):
                logger.error("Failed to get sales_order schema")
                return False
            
            logger.info(f"Found {len(schema_info['columns'])} columns in sales_order table")
            
            # Train on schema using the config method
            success = self.vanna_config.train_on_sales_order_schema()
            
            if success:
                self.training_stats['ddl_trained'] = True
                logger.info("Schema training completed")
                return True
            else:
                logger.error("Schema training failed")
                return False
            
        except Exception as e:
            logger.error(f"Schema training error: {e}")
            self.training_stats['errors'].append(f"Schema training: {str(e)}")
            return False
    
    def _train_sample_queries(self) -> bool:
        """Train Vanna on additional e-commerce specific queries."""
        try:
            logger.info("Training on additional sample queries...")
            
            vn = self.vanna_config.get_vanna_instance()
            
            # Additional training queries beyond what's in vanna_config
            additional_queries = [
                # Complex aggregations
                {
                    "question": "What's my total spending by month this year?",
                    "sql": """
                        SELECT 
                            DATE_FORMAT(created_at, '%Y-%m') as month,
                            SUM(grand_total) as total_spent,
                            COUNT(*) as order_count
                        FROM sales_order 
                        WHERE customer_id = :customer_id 
                        AND YEAR(created_at) = YEAR(NOW())
                        AND status IN ('complete', 'processing')
                        GROUP BY DATE_FORMAT(created_at, '%Y-%m')
                        ORDER BY month
                    """
                },
                
                # Order status analysis
                {
                    "question": "Show me orders by status",
                    "sql": """
                        SELECT 
                            status,
                            COUNT(*) as count,
                            SUM(grand_total) as total_amount
                        FROM sales_order 
                        WHERE customer_id = :customer_id
                        GROUP BY status
                        ORDER BY count DESC
                    """
                },
                
                # Shipping analysis
                {
                    "question": "What shipping methods have I used?",
                    "sql": """
                        SELECT 
                            shipping_method,
                            COUNT(*) as times_used,
                            AVG(shipping_amount) as avg_cost
                        FROM sales_order 
                        WHERE customer_id = :customer_id 
                        AND shipping_method IS NOT NULL
                        GROUP BY shipping_method
                        ORDER BY times_used DESC
                    """
                },
                
                # Discount analysis
                {
                    "question": "How much have I saved with discounts?",
                    "sql": """
                        SELECT 
                            SUM(discount_amount) as total_discounts,
                            COUNT(CASE WHEN discount_amount > 0 THEN 1 END) as orders_with_discounts,
                            AVG(CASE WHEN discount_amount > 0 THEN discount_amount END) as avg_discount
                        FROM sales_order 
                        WHERE customer_id = :customer_id
                    """
                },
                
                # Time-based analysis
                {
                    "question": "Show my order frequency by day of week",
                    "sql": """
                        SELECT 
                            DAYNAME(created_at) as day_of_week,
                            COUNT(*) as order_count
                        FROM sales_order 
                        WHERE customer_id = :customer_id
                        GROUP BY DAYOFWEEK(created_at), DAYNAME(created_at)
                        ORDER BY DAYOFWEEK(created_at)
                    """
                },
                
                # Large orders
                {
                    "question": "Show my largest orders",
                    "sql": """
                        SELECT 
                            increment_id,
                            grand_total,
                            created_at,
                            status,
                            total_item_count
                        FROM sales_order 
                        WHERE customer_id = :customer_id
                        ORDER BY grand_total DESC
                        LIMIT 10
                    """
                },
                
                # Recent activity
                {
                    "question": "What's my recent order activity?",
                    "sql": """
                        SELECT 
                            increment_id,
                            status,
                            grand_total,
                            created_at,
                            DATEDIFF(NOW(), created_at) as days_ago
                        FROM sales_order 
                        WHERE customer_id = :customer_id
                        AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                        ORDER BY created_at DESC
                    """
                },
                
                # Payment analysis
                {
                    "question": "Show my payment history",
                    "sql": """
                        SELECT 
                            increment_id,
                            grand_total,
                            base_total_paid,
                            (grand_total - COALESCE(base_total_paid, 0)) as remaining_balance,
                            created_at
                        FROM sales_order 
                        WHERE customer_id = :customer_id
                        AND grand_total > 0
                        ORDER BY created_at DESC
                        LIMIT 20
                    """
                }
            ]
            
            trained_count = 0
            for query in additional_queries:
                try:
                    vn.train(question=query["question"], sql=query["sql"])
                    trained_count += 1
                    logger.debug(f"Trained: {query['question']}")
                except Exception as e:
                    logger.warning(f"Failed to train query '{query['question']}': {e}")
            
            self.training_stats['sample_queries_trained'] = trained_count
            logger.info(f"Trained {trained_count} additional sample queries")
            
            return True
            
        except Exception as e:
            logger.error(f"Sample queries training error: {e}")
            self.training_stats['errors'].append(f"Sample queries: {str(e)}")
            return False
    
    def _train_documentation(self) -> bool:
        """Train Vanna on database documentation and business rules."""
        try:
            logger.info("Training on documentation and business rules...")
            
            vn = self.vanna_config.get_vanna_instance()
            
            # Business rules and documentation
            documentation = [
                {
                    "doc": """
                    Sales Order Status Values:
                    - 'pending': Order placed but not yet processed
                    - 'processing': Order is being prepared for shipment
                    - 'shipped': Order has been shipped to customer
                    - 'complete': Order delivered and completed
                    - 'cancelled': Order was cancelled
                    - 'closed': Order is closed (usually after completion)
                    
                    Only orders with status 'complete' or 'processing' should be counted for spending totals.
                    """
                },
                {
                    "doc": """
                    Sales Order Financial Fields:
                    - grand_total: Final total amount customer pays (includes tax, shipping, discounts)
                    - base_grand_total: Grand total in base currency
                    - subtotal: Order subtotal before tax and shipping
                    - tax_amount: Tax charged on the order
                    - discount_amount: Discount applied (positive value means discount given)
                    - shipping_amount: Shipping cost charged
                    
                    For spending calculations, use grand_total as it represents actual amount paid.
                    """
                },
                {
                    "doc": """
                    Customer Identification:
                    - customer_id: Primary customer identifier (integer)
                    - customer_email: Customer email address (alternative identifier)
                    
                    SECURITY: Always filter by customer_id or customer_email to ensure data isolation.
                    Never return data for other customers.
                    """
                },
                {
                    "doc": """
                    Date Fields:
                    - created_at: When the order was placed
                    - updated_at: When the order was last modified
                    
                    Use created_at for order date analysis and filtering.
                    """
                },
                {
                    "doc": """
                    Order Identification:
                    - entity_id: Internal database ID (primary key)
                    - increment_id: Customer-facing order number (what customers see)
                    
                    Use increment_id when displaying order numbers to customers.
                    """
                }
            ]
            
            trained_count = 0
            for doc_item in documentation:
                try:
                    vn.train(documentation=doc_item["doc"])
                    trained_count += 1
                except Exception as e:
                    logger.warning(f"Failed to train documentation: {e}")
            
            self.training_stats['documentation_trained'] = trained_count
            logger.info(f"Trained {trained_count} documentation items")
            
            return True
            
        except Exception as e:
            logger.error(f"Documentation training error: {e}")
            self.training_stats['errors'].append(f"Documentation: {str(e)}")
            return False
    
    def _validate_training(self) -> bool:
        """Validate that training was successful by testing sample queries."""
        try:
            logger.info("Validating training with test queries...")
            
            test_queries = [
                "Show me my recent orders",
                "How much did I spend last month?",
                "What's the status of my orders?",
                "List my completed orders"
            ]
            
            successful_tests = 0
            for question in test_queries:
                try:
                    result = self.vanna_config.generate_sql(
                        question=question,
                        customer_id="test_customer_123"
                    )
                    
                    if result['success'] and result['sql']:
                        successful_tests += 1
                        logger.debug(f"✓ Test passed: {question}")
                    else:
                        logger.warning(f"✗ Test failed: {question} - {result.get('error', 'No SQL generated')}")
                        
                except Exception as e:
                    logger.warning(f"✗ Test error: {question} - {e}")
            
            success_rate = successful_tests / len(test_queries)
            logger.info(f"Validation complete: {successful_tests}/{len(test_queries)} tests passed ({success_rate:.1%})")
            
            # Consider training successful if at least 75% of tests pass
            return success_rate >= 0.75
            
        except Exception as e:
            logger.error(f"Training validation error: {e}")
            self.training_stats['errors'].append(f"Validation: {str(e)}")
            return False
    
    def _print_training_summary(self):
        """Print summary of training results."""
        print("\n" + "="*50)
        print("VANNA TRAINING SUMMARY")
        print("="*50)
        print(f"DDL Training: {'✓' if self.training_stats['ddl_trained'] else '✗'}")
        print(f"Sample Queries Trained: {self.training_stats['sample_queries_trained']}")
        print(f"Documentation Items: {self.training_stats['documentation_trained']}")
        
        if self.training_stats['errors']:
            print(f"\nErrors encountered: {len(self.training_stats['errors'])}")
            for error in self.training_stats['errors']:
                print(f"  - {error}")
        else:
            print("\nNo errors encountered!")
        
        print("\nNext steps:")
        print("1. Test the chatbot with: python main.py")
        print("2. Try sample questions like:")
        print("   - 'Show me my recent orders'")
        print("   - 'How much did I spend this year?'")
        print("   - 'What's the status of my orders?'")
        print("="*50)

def main():
    """Main function for running Vanna training."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Train Vanna.ai on sales_order table")
    parser.add_argument("--force", action="store_true", help="Force retraining even if already trained")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("Vanna Training Script")
    print("====================")
    print("This script will train Vanna.ai on your sales_order table.")
    print("Make sure your database connection is configured in .env file.")
    print()
    print("DB_USER =", os.getenv('DB_USER'))
    # Check environment variables
    required_vars = ['DB_HOST', 'DB_NAME', 'DB_USER']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file or environment.")
        return False
    
    # Check for API keys
    if not (os.getenv('OPENAI_API_KEY') or os.getenv('VANNA_API_KEY')):
        print("Warning: No OPENAI_API_KEY or VANNA_API_KEY found.")
        print("You'll need one of these for Vanna to work.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return False
    
    trainer = VannaTrainer()
    
    start_time = time.time()
    success = trainer.run_training(force_retrain=args.force)
    duration = time.time() - start_time
    
    if success:
        print(f"\n✓ Training completed successfully in {duration:.1f} seconds!")
        return True
    else:
        print(f"\n✗ Training failed after {duration:.1f} seconds.")
        print("Check the logs above for error details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
