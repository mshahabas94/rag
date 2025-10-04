import os
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import JSONLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Qdrant
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
import json
from typing import List, Dict, Any

# Global variable to store the initialized retriever
retriever = None
vector_store_initialized = False

def initialize_and_populate_vectorstore():
    """
    Initialize Qdrant DB connection and populate vector store with Q&A documentation.
    Returns the retriever (initializes only once).
    """
    global retriever, vector_store_initialized
    
    # If already initialized, return the retriever
    if retriever is not None and vector_store_initialized:
        print("---USING EXISTING VECTOR STORE---")
        return retriever
    
    print("---INITIALIZING VECTOR STORE (FIRST TIME)---")
    # Load environment variables
    load_dotenv()
    
    # Qdrant configuration
    QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
    COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "gaming_support_qa")
    
    print(f"Qdrant Host: {QDRANT_HOST}")
    print(f"Qdrant Port: {QDRANT_PORT}")
    
    # Initialize Qdrant client
    try:
        qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        print("Successfully connected to Qdrant")
    except Exception as e:
        print(f"Error connecting to Qdrant: {e}")
        raise
    
    # Initialize embeddings
    print("Initializing embeddings...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # Check if collection exists and has data
    collection_exists = False
    collection_has_data = False
    
    try:
        collections = qdrant_client.get_collections().collections
        collection_names = [col.name for col in collections]
        
        if COLLECTION_NAME in collection_names:
            collection_exists = True
            print(f"Collection '{COLLECTION_NAME}' exists")
            
            # Check if collection has data
            collection_info = qdrant_client.get_collection(collection_name=COLLECTION_NAME)
            if collection_info.points_count > 0:
                collection_has_data = True
                print(f"Collection has {collection_info.points_count} vectors")
            else:
                print("Collection exists but is empty")
        else:
            print(f"Collection '{COLLECTION_NAME}' does not exist")
            
    except Exception as e:
        print(f"Error checking collection: {e}")
        raise
    
    # If collection exists and has data, just initialize the retriever
    if collection_exists and collection_has_data:
        print("Collection already has data - skipping document processing")
        vector_store = Qdrant(
            client=qdrant_client,
            collection_name=COLLECTION_NAME,
            embeddings=embeddings,
        )
        
        retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 5}
        )
        vector_store_initialized = True
        print("Vector store retriever initialized from existing data!")
        return retriever
    
    # If we reach here, we need to process and add documents
    print("Processing and adding documents to vector store...")
    
    # Create collection if it doesn't exist
    if not collection_exists:
        print(f"Creating collection: {COLLECTION_NAME}")
        qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
        print("Collection created successfully")
    
    # Load and process Q&A JSON documents
    print("Loading Q&A documents...")
    docs_list = load_qa_documents("./data/")
    
    if not docs_list:
        raise ValueError("No Q&A documents found to process!")
    
    print(f"Loaded {len(docs_list)} Q&A pairs")
    
    # Initialize Qdrant vector store
    print("Initializing Qdrant vector store...")
    vector_store = Qdrant(
        client=qdrant_client,
        collection_name=COLLECTION_NAME,
        embeddings=embeddings,
    )
    
    # Add documents to vector store
    print("Adding documents to vector store...")
    vector_store.add_documents(docs_list)
    print(f"Inserted {len(docs_list)} Q&A pairs.")
    
    # Create retriever
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 5}
    )
    
    vector_store_initialized = True
    print("Vector store initialization complete!")
    return retriever

def load_qa_documents(data_path: str) -> List[Any]:
    """
    Load and process Q&A JSON documents specifically for the given format
    """
    from langchain.schema import Document
    import json
    
    documents = []
    
    if not os.path.exists(data_path):
        print(f"Data path '{data_path}' does not exist")
        return documents
    
    # Process all JSON files in the data directory
    for root, dirs, files in os.walk(data_path):
        for file in files:
            if file.endswith('.json'):
                file_path = os.path.join(root, file)
                print(f"Processing Q&A file: {file}")
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Process the array of Q&A objects
                    if isinstance(data, list):
                        for i, qa_item in enumerate(data):
                            if isinstance(qa_item, dict) and 'question' in qa_item and 'answer' in qa_item:
                                # Create a combined text for better retrieval
                                combined_text = f"Question: {qa_item['question']}\nAnswer: {qa_item['answer']}"
                                
                                # Create metadata
                                metadata = {
                                    "source": file_path,
                                    "doc_id": f"{os.path.basename(file_path)}_{i}",
                                    "type": "qa_pair",
                                    "question": qa_item['question'],
                                    "answer": qa_item['answer'],
                                    "item_index": i
                                }
                                
                                documents.append(Document(
                                    page_content=combined_text, 
                                    metadata=metadata
                                ))
                                
                        print(f"  - Added {len([d for d in documents if d.metadata['source'] == file_path])} Q&A pairs from {file}")
                    
                except Exception as e:
                    print(f"Error processing Q&A file {file_path}: {e}")
    
    return documents

def search_support_questions(query: str, retriever_instance = None):
    """
    Search for relevant support questions and return formatted results
    """
    if retriever_instance is None:
        if retriever is None:
            raise ValueError("Retriever not initialized. Call initialize_and_populate_vectorstore() first.")
        retriever_instance = retriever
    
    print(f"Searching for: '{query}'")
    results = retriever_instance.get_relevant_documents(query)
    
    formatted_results = []
    for i, doc in enumerate(results):
        formatted_result = {
            "rank": i + 1,
            "question": doc.metadata.get("question", "N/A"),
            "answer": doc.metadata.get("answer", "N/A"),
            "score": getattr(doc, 'score', 'N/A'),  # Some retrievers include score
            "source": doc.metadata.get("source", "N/A")
        }
        formatted_results.append(formatted_result)
    
    return formatted_results

def get_retriever_stats():
    """
    Get statistics about the vector store
    """
    if retriever is None:
        return "Retriever not initialized"
    
    return {
        "status": "initialized",
        "search_kwargs": retriever.search_kwargs,
        "vector_store_initialized": vector_store_initialized
    }

def clear_vector_store():
    """
    Clear the vector store (useful for testing or re-indexing)
    """
    global retriever, vector_store_initialized
    
    load_dotenv()
    QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
    COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "gaming_support_qa")
    
    try:
        qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        qdrant_client.delete_collection(collection_name=COLLECTION_NAME)
        print(f"Collection '{COLLECTION_NAME}' deleted successfully")
        
        # Reset global variables
        retriever = None
        vector_store_initialized = False
        print("Vector store cleared. Next run will re-process documents.")
        
    except Exception as e:
        print(f"Error clearing vector store: {e}")

# Example usage
if __name__ == "__main__":
    # Initialize the vector store (will process only first time)
    retriever_instance = initialize_and_populate_vectorstore()
    
    # Test some queries
    test_queries = [
        "code not working",
        "technical support",
        "delete account",
        "CDKoins",
        "password reset"
    ]
    
    for query in test_queries:
        print(f"\n{'='*50}")
        results = search_support_questions(query, retriever_instance)
        print(f"Query: '{query}' - Found {len(results)} results")
        
        for result in results[:5]:  # Show top 2 results
            print(f"\nQ: {result['question']}")
            print(f"A: {result['answer'][:1000]}...")
            print(f"Source: {result['source']}")
    
    # Second run - should use existing data
    print(f"\n{'='*50}")
    print("SECOND RUN - Should use existing vector store")
    retriever_instance2 = initialize_and_populate_vectorstore()
    print(f"Same retriever: {retriever_instance is retriever_instance2}")
    # clear_vector_store()