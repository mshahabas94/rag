"""
RAG setup script for document embedding and vector store initialization.
This script processes documents and creates the vector database for knowledge retrieval.
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any
import time
import shutil

# Add parent directory to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from config.rag_config import rag_config
from utils.query_logger import query_logger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RAGSetup:
    """Handles RAG system setup and document processing."""
    
    def __init__(self):
        self.rag_config = rag_config
        self.setup_stats = {
            'documents_found': 0,
            'documents_processed': 0,
            'chunks_created': 0,
            'embedding_time': 0.0,
            'errors': []
        }
    
    def run_setup(self, force_rebuild: bool = False, sample_docs: bool = True) -> bool:
        """
        Run complete RAG setup process.
        
        Args:
            force_rebuild: Whether to rebuild vector store from scratch
            sample_docs: Whether to create sample documents if none exist
            
        Returns:
            True if setup successful
        """
        try:
            logger.info("Starting RAG setup process...")
            
            # Step 1: Check and create sample documents if needed
            if sample_docs and not self._has_documents():
                if not self._create_sample_documents():
                    logger.warning("No documents found and sample creation failed")
            
            # Step 2: Initialize RAG components
            if not self._initialize_rag():
                return False
            
            # Step 3: Process and embed documents
            if not self._embed_documents(force_rebuild):
                return False
            
            # Step 4: Validate setup
            if not self._validate_setup():
                return False
            
            logger.info("RAG setup completed successfully!")
            self._print_setup_summary()
            
            return True
            
        except Exception as e:
            logger.error(f"RAG setup failed with error: {e}")
            self.setup_stats['errors'].append(str(e))
            return False
    
    def _has_documents(self) -> bool:
        """Check if documents directory has any files."""
        try:
            docs_path = self.rag_config.documents_path
            if not docs_path.exists():
                return False
            
            # Look for supported file types
            supported_extensions = {'.txt', '.pdf', '.docx', '.md'}
            for file_path in docs_path.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking for documents: {e}")
            return False
    
    def _create_sample_documents(self) -> bool:
        """Create sample e-commerce documents for testing."""
        try:
            logger.info("Creating sample documents...")
            
            docs_path = self.rag_config.documents_path
            docs_path.mkdir(parents=True, exist_ok=True)
            
            sample_documents = {
                'return_policy.txt': """
RETURN POLICY

Our Return Policy allows you to return most items within 30 days of delivery for a full refund.

ELIGIBILITY:
- Items must be in original condition
- Items must be unused and unworn
- Original packaging and tags must be included
- Return must be initiated within 30 days of delivery

PROCESS:
1. Log into your account and go to Order History
2. Select the order and click "Return Items"
3. Choose items to return and reason
4. Print the prepaid return label
5. Package items securely and attach label
6. Drop off at any authorized shipping location

REFUND TIMELINE:
- Processing: 2-3 business days after we receive your return
- Refund method: Original payment method
- Refund time: 5-10 business days depending on your bank

EXCEPTIONS:
- Final sale items cannot be returned
- Personalized items cannot be returned
- Items damaged by normal wear cannot be returned
- Returns after 30 days may be subject to restocking fee

For questions about returns, contact our customer service team.
                """,
                
                'shipping_info.txt': """
SHIPPING INFORMATION

We offer multiple shipping options to meet your needs:

SHIPPING METHODS:
- Standard Shipping (5-7 business days): FREE on orders over $50
- Express Shipping (2-3 business days): $9.99
- Overnight Shipping (1 business day): $19.99
- Same-Day Delivery (select cities): $24.99

PROCESSING TIME:
- Orders placed before 2 PM EST ship same day
- Orders placed after 2 PM EST ship next business day
- Weekend orders ship on Monday
- Holiday processing may be delayed

TRACKING:
- Tracking number sent via email once shipped
- Track your package on our website or carrier website
- SMS notifications available upon request

INTERNATIONAL SHIPPING:
- Available to most countries
- Shipping costs calculated at checkout
- Delivery time: 7-21 business days
- Customer responsible for customs fees

SHIPPING RESTRICTIONS:
- Some items cannot be shipped to certain locations
- Hazardous materials have special requirements
- Large items may require special delivery

For shipping questions, contact customer service.
                """,
                
                'payment_terms.txt': """
PAYMENT TERMS AND METHODS

We accept various payment methods for your convenience:

ACCEPTED PAYMENT METHODS:
- Credit Cards: Visa, MasterCard, American Express, Discover
- Debit Cards: All major debit cards with Visa/MC logo
- Digital Wallets: PayPal, Apple Pay, Google Pay
- Buy Now Pay Later: Klarna, Afterpay (on qualifying orders)
- Gift Cards: Our branded gift cards and e-gift cards

PAYMENT SECURITY:
- All transactions are encrypted with SSL technology
- We never store your full credit card information
- PCI DSS compliant payment processing
- Fraud protection on all transactions

BILLING:
- Payment is charged when order is processed
- Pre-authorization may occur at time of order
- Final charge occurs when order ships
- Separate charges for backordered items

PAYMENT ISSUES:
- Declined payments: Check with your bank
- Payment disputes: Contact customer service immediately
- Refunds: Processed to original payment method
- Chargebacks: May result in account suspension

BUSINESS ACCOUNTS:
- Net 30 terms available for qualified businesses
- Purchase orders accepted for business accounts
- Volume discounts available
- Dedicated account manager for large accounts

For payment questions, contact our billing department.
                """,
                
                'customer_support.txt': """
CUSTOMER SUPPORT

We're here to help! Contact us through multiple channels:

CONTACT METHODS:
- Phone: 1-800-SUPPORT (24/7)
- Email: support@company.com
- Live Chat: Available on website 6 AM - 12 AM EST
- Social Media: @company on Twitter, Facebook, Instagram

SUPPORT HOURS:
- Phone Support: 24/7
- Email Support: Responses within 24 hours
- Live Chat: 6 AM - 12 AM EST, 7 days a week
- Social Media: 9 AM - 6 PM EST, Monday-Friday

WHAT WE CAN HELP WITH:
- Order status and tracking
- Returns and exchanges
- Product information and recommendations
- Account management
- Technical issues with website
- Billing and payment questions
- Shipping and delivery issues

BEFORE YOU CONTACT US:
- Have your order number ready
- Check your email for order updates
- Review our FAQ section
- Try our self-service options online

ESCALATION PROCESS:
- Level 1: General customer service
- Level 2: Specialized support team
- Level 3: Management review
- Executive escalation available for complex issues

We strive to resolve all issues on first contact.
                """,
                
                'faq.txt': """
FREQUENTLY ASKED QUESTIONS

ORDER QUESTIONS:

Q: How do I track my order?
A: You'll receive a tracking number via email once your order ships. Use this number on our website or the carrier's website to track your package.

Q: Can I change or cancel my order?
A: Orders can be modified or cancelled within 1 hour of placement. After that, contact customer service for assistance.

Q: Why was my order cancelled?
A: Orders may be cancelled due to payment issues, inventory problems, or shipping restrictions. You'll receive an email explanation.

ACCOUNT QUESTIONS:

Q: How do I create an account?
A: Click "Sign Up" on our website, provide your email and create a password. You can also create an account during checkout.

Q: I forgot my password. What do I do?
A: Click "Forgot Password" on the login page and enter your email. We'll send you a password reset link.

Q: How do I update my account information?
A: Log into your account and go to "Account Settings" to update your personal information, addresses, and preferences.

PRODUCT QUESTIONS:

Q: Are your products authentic?
A: Yes, we only sell authentic products directly from manufacturers or authorized distributors.

Q: Do you offer price matching?
A: We offer price matching on identical items from authorized retailers. Contact customer service with details.

Q: How do I know what size to order?
A: Check our detailed size guides available on each product page. When in doubt, contact customer service for recommendations.

TECHNICAL QUESTIONS:

Q: Why can't I complete my order?
A: This could be due to payment issues, browser problems, or inventory. Try refreshing the page or using a different browser.

Q: Is your website secure?
A: Yes, our website uses SSL encryption and is PCI DSS compliant to protect your personal and payment information.

For more questions, contact our customer support team.
                """
            }
            
            created_count = 0
            for filename, content in sample_documents.items():
                file_path = docs_path / filename
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content.strip())
                    created_count += 1
                    logger.info(f"Created sample document: {filename}")
                except Exception as e:
                    logger.error(f"Failed to create {filename}: {e}")
            
            logger.info(f"Created {created_count} sample documents")
            return created_count > 0
            
        except Exception as e:
            logger.error(f"Error creating sample documents: {e}")
            self.setup_stats['errors'].append(f"Sample docs creation: {str(e)}")
            return False
    
    def _initialize_rag(self) -> bool:
        """Initialize RAG components."""
        try:
            logger.info("Initializing RAG components...")
            
            # Initialize embeddings
            embeddings = self.rag_config.get_embeddings()
            logger.info("Embeddings initialized")
            
            # Initialize vector store
            vector_store = self.rag_config.get_vector_store()
            logger.info("Vector store initialized")
            
            # Initialize LLM
            llm = self.rag_config.get_llm()
            logger.info("LLM initialized")
            
            return True
            
        except Exception as e:
            logger.error(f"RAG initialization failed: {e}")
            self.setup_stats['errors'].append(f"RAG init: {str(e)}")
            return False
    
    def _embed_documents(self, force_rebuild: bool = False) -> bool:
        """Process and embed documents into vector store."""
        try:
            logger.info("Processing and embedding documents...")
            
            start_time = time.time()
            
            # Load documents first to get count
            documents = self.rag_config.load_documents()
            self.setup_stats['documents_found'] = len(documents)
            
            if not documents:
                logger.warning("No documents found to embed")
                return False
            
            logger.info(f"Found {len(documents)} documents to process")
            
            # Embed documents
            success = self.rag_config.embed_documents(force_rebuild=force_rebuild)
            
            if success:
                self.setup_stats['documents_processed'] = len(documents)
                self.setup_stats['embedding_time'] = time.time() - start_time
                
                # Get final stats
                stats = self.rag_config.get_collection_stats()
                self.setup_stats['chunks_created'] = stats.get('total_chunks', 0)
                
                logger.info(f"Document embedding completed in {self.setup_stats['embedding_time']:.1f} seconds")
                return True
            else:
                logger.error("Document embedding failed")
                return False
            
        except Exception as e:
            logger.error(f"Document embedding error: {e}")
            self.setup_stats['errors'].append(f"Document embedding: {str(e)}")
            return False
    
    def _validate_setup(self) -> bool:
        """Validate RAG setup by testing queries."""
        try:
            logger.info("Validating RAG setup with test queries...")
            
            test_queries = [
                "What is your return policy?",
                "How long does shipping take?",
                "What payment methods do you accept?",
                "How do I contact customer support?"
            ]
            
            successful_tests = 0
            for question in test_queries:
                try:
                    result = self.rag_config.query_documents(question)
                    
                    if result['success'] and result['answer']:
                        successful_tests += 1
                        logger.debug(f"✓ Test passed: {question}")
                    else:
                        logger.warning(f"✗ Test failed: {question} - {result.get('error', 'No answer generated')}")
                        
                except Exception as e:
                    logger.warning(f"✗ Test error: {question} - {e}")
            
            success_rate = successful_tests / len(test_queries)
            logger.info(f"Validation complete: {successful_tests}/{len(test_queries)} tests passed ({success_rate:.1%})")
            
            # Consider setup successful if at least 75% of tests pass
            return success_rate >= 0.75
            
        except Exception as e:
            logger.error(f"RAG validation error: {e}")
            self.setup_stats['errors'].append(f"Validation: {str(e)}")
            return False
    
    def _print_setup_summary(self):
        """Print summary of setup results."""
        print("\n" + "="*50)
        print("RAG SETUP SUMMARY")
        print("="*50)
        print(f"Documents Found: {self.setup_stats['documents_found']}")
        print(f"Documents Processed: {self.setup_stats['documents_processed']}")
        print(f"Text Chunks Created: {self.setup_stats['chunks_created']}")
        print(f"Embedding Time: {self.setup_stats['embedding_time']:.1f} seconds")
        
        if self.setup_stats['errors']:
            print(f"\nErrors encountered: {len(self.setup_stats['errors'])}")
            for error in self.setup_stats['errors']:
                print(f"  - {error}")
        else:
            print("\nNo errors encountered!")
        
        print("\nNext steps:")
        print("1. Test the RAG system with: python main.py")
        print("2. Try sample questions like:")
        print("   - 'What is your return policy?'")
        print("   - 'How long does shipping take?'")
        print("   - 'What payment methods do you accept?'")
        print("3. Add your own documents to data/documents/ folder")
        print("4. Re-run this script to embed new documents")
        print("="*50)
    
    def add_documents_from_directory(self, source_dir: str) -> bool:
        """Add documents from an external directory."""
        try:
            source_path = Path(source_dir)
            if not source_path.exists():
                logger.error(f"Source directory does not exist: {source_dir}")
                return False
            
            docs_path = self.rag_config.documents_path
            docs_path.mkdir(parents=True, exist_ok=True)
            
            copied_count = 0
            supported_extensions = {'.txt', '.pdf', '.docx', '.md'}
            
            for file_path in source_path.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                    try:
                        dest_path = docs_path / file_path.name
                        shutil.copy2(file_path, dest_path)
                        copied_count += 1
                        logger.info(f"Copied: {file_path.name}")
                    except Exception as e:
                        logger.error(f"Failed to copy {file_path.name}: {e}")
            
            logger.info(f"Copied {copied_count} documents from {source_dir}")
            return copied_count > 0
            
        except Exception as e:
            logger.error(f"Error adding documents from directory: {e}")
            return False

def main():
    """Main function for running RAG setup."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Setup RAG system and embed documents")
    parser.add_argument("--force", action="store_true", help="Force rebuild of vector store")
    parser.add_argument("--no-samples", action="store_true", help="Don't create sample documents")
    parser.add_argument("--add-docs", type=str, help="Add documents from specified directory")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("RAG Setup Script")
    print("================")
    print("This script will set up the RAG system and embed documents.")
    print("Make sure you have the required API keys configured.")
    print()
    
    # Check for required API keys
    if not os.getenv('OPENAI_API_KEY'):
        print("Warning: No OPENAI_API_KEY found.")
        print("You'll need this for embeddings and LLM functionality.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return False
    
    setup = RAGSetup()
    
    # Add external documents if specified
    if args.add_docs:
        logger.info(f"Adding documents from {args.add_docs}")
        setup.add_documents_from_directory(args.add_docs)
    
    start_time = time.time()
    success = setup.run_setup(
        force_rebuild=args.force,
        sample_docs=not args.no_samples
    )
    duration = time.time() - start_time
    
    if success:
        print(f"\n✓ RAG setup completed successfully in {duration:.1f} seconds!")
        return True
    else:
        print(f"\n✗ RAG setup failed after {duration:.1f} seconds.")
        print("Check the logs above for error details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
