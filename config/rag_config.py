"""
RAG (Retrieval Augmented Generation) configuration.
Handles document embedding, vector storage, and retrieval.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import (
    TextLoader, 
    PyPDFLoader, 
    UnstructuredWordDocumentLoader
)
from langchain_community.vectorstores import Qdrant
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.llms.base import LLM
from .local_llm_config import local_llm_config

logger = logging.getLogger(__name__)

class RAGConfig:
    """RAG system configuration and management."""
    
    def __init__(self):
        self.documents_path = Path(os.getenv('DOCUMENTS_PATH', 'data/documents'))
        
        # Qdrant configuration (using your existing setup)
        self.qdrant_host = os.getenv('QDRANT_HOST', 'localhost')
        self.qdrant_port = int(os.getenv('QDRANT_PORT', '6333'))
        self.collection_name = os.getenv('QDRANT_COLLECTION_NAME', 'gaming_support_qa')
        
        # Always use local embeddings (HuggingFace) - same as your chunking.py
        self.use_openai_embeddings = False
        self.local_embedding_model = os.getenv('LOCAL_EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        
        # LLM configuration (using local model)
        self.llm_temperature = float(os.getenv('LLM_TEMPERATURE', '0.1'))
        self.max_tokens = int(os.getenv('LLM_MAX_TOKENS', '512'))
        
        # Retrieval settings
        self.chunk_size = int(os.getenv('CHUNK_SIZE', '1000'))
        self.chunk_overlap = int(os.getenv('CHUNK_OVERLAP', '200'))
        self.retrieval_k = int(os.getenv('RETRIEVAL_K', '4'))
        
        # Initialize components
        self._embeddings = None
        self._vector_store = None
        self._llm = None
        self._qa_chain = None
        self._text_splitter = None
        self._qdrant_client = None
        
        # Ensure directories exist
        self.documents_path.mkdir(parents=True, exist_ok=True)
    
    def get_embeddings(self):
        """Get embedding model (using HuggingFace local embeddings)."""
        if self._embeddings is None:
            try:
                self._embeddings = HuggingFaceEmbeddings(
                    model_name=self.local_embedding_model,
                    model_kwargs={'device': 'cpu'}
                )
                logger.info(f"Initialized local embeddings: {self.local_embedding_model}")
            except Exception as e:
                logger.error(f"Failed to initialize embeddings: {e}")
                raise
        
        return self._embeddings
    
    def get_text_splitter(self):
        """Get text splitter for document chunking."""
        if self._text_splitter is None:
            self._text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", " ", ""]
            )
        return self._text_splitter
    
    def get_qdrant_client(self):
        """Get or create Qdrant client."""
        if self._qdrant_client is None:
            try:
                self._qdrant_client = QdrantClient(
                    host=self.qdrant_host, 
                    port=self.qdrant_port
                )
                logger.info(f"Connected to Qdrant at {self.qdrant_host}:{self.qdrant_port}")
            except Exception as e:
                logger.error(f"Failed to connect to Qdrant: {e}")
                raise
        return self._qdrant_client
    
    def get_vector_store(self):
        """Get or create Qdrant vector store."""
        if self._vector_store is None:
            try:
                embeddings = self.get_embeddings()
                qdrant_client = self.get_qdrant_client()
                
                # Initialize Qdrant vector store (same as your chunking.py)
                self._vector_store = Qdrant(
                    client=qdrant_client,
                    collection_name=self.collection_name,
                    embeddings=embeddings,
                )
                
                logger.info(f"Initialized Qdrant vector store with collection: {self.collection_name}")
                
            except Exception as e:
                logger.error(f"Failed to initialize vector store: {e}")
                raise
        
        return self._vector_store
    
    def get_llm(self):
        """Get LLM for answer generation (using local LLaMA model)."""
        if self._llm is None:
            try:
                from .local_llm_wrapper import LocalLlamaLLM
                self._llm = LocalLlamaLLM()
                logger.info("Initialized local LLaMA LLM")
            except Exception as e:
                logger.error(f"Failed to initialize local LLM: {e}")
                raise
        
        return self._llm
    
    def get_qa_chain(self):
        """Get QA chain for retrieval-based question answering."""
        if self._qa_chain is None:
            try:
                vector_store = self.get_vector_store()
                llm = self.get_llm()
                
                # Custom prompt template for e-commerce context
                prompt_template = """
                You are a helpful customer service assistant for an e-commerce platform. 
                Use the following context to answer the customer's question. If you cannot 
                find the answer in the context, politely say so and suggest contacting 
                customer support.
                
                Context: {context}
                
                Question: {question}
                
                Answer: """
                
                prompt = PromptTemplate(
                    template=prompt_template,
                    input_variables=["context", "question"]
                )
                
                self._qa_chain = RetrievalQA.from_chain_type(
                    llm=llm,
                    chain_type="stuff",
                    retriever=vector_store.as_retriever(
                        search_kwargs={"k": self.retrieval_k}
                    ),
                    chain_type_kwargs={"prompt": prompt},
                    return_source_documents=True
                )
                
                logger.info("Initialized QA chain")
                
            except Exception as e:
                logger.error(f"Failed to initialize QA chain: {e}")
                raise
        
        return self._qa_chain
    
    def load_documents(self) -> List[Dict[str, Any]]:
        """Load all documents from the documents directory."""
        documents = []
        
        if not self.documents_path.exists():
            logger.warning(f"Documents directory not found: {self.documents_path}")
            return documents
        
        supported_extensions = {'.txt', '.pdf', '.docx', '.md'}
        
        for file_path in self.documents_path.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                try:
                    doc_info = self._load_single_document(file_path)
                    if doc_info:
                        documents.append(doc_info)
                        logger.info(f"Loaded document: {file_path.name}")
                except Exception as e:
                    logger.error(f"Failed to load document {file_path}: {e}")
        
        logger.info(f"Loaded {len(documents)} documents")
        return documents
    
    def _load_single_document(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Load a single document based on its extension."""
        try:
            if file_path.suffix.lower() == '.pdf':
                loader = PyPDFLoader(str(file_path))
            elif file_path.suffix.lower() == '.docx':
                loader = UnstructuredWordDocumentLoader(str(file_path))
            else:  # .txt, .md
                loader = TextLoader(str(file_path), encoding='utf-8')
            
            docs = loader.load()
            
            if not docs:
                return None
            
            # Combine all pages/sections into one document
            content = "\n\n".join([doc.page_content for doc in docs])
            
            return {
                'content': content,
                'metadata': {
                    'source': str(file_path),
                    'filename': file_path.name,
                    'type': file_path.suffix.lower()
                }
            }
            
        except Exception as e:
            logger.error(f"Error loading document {file_path}: {e}")
            return None
    
    def check_existing_collection(self) -> bool:
        """Check if Qdrant collection already exists and has data."""
        try:
            qdrant_client = self.get_qdrant_client()
            collections = qdrant_client.get_collections().collections
            collection_names = [col.name for col in collections]
            
            if self.collection_name in collection_names:
                collection_info = qdrant_client.get_collection(collection_name=self.collection_name)
                if collection_info.points_count > 0:
                    logger.info(f"Collection '{self.collection_name}' exists with {collection_info.points_count} vectors")
                    return True
                else:
                    logger.info(f"Collection '{self.collection_name}' exists but is empty")
                    return False
            else:
                logger.info(f"Collection '{self.collection_name}' does not exist")
                return False
        except Exception as e:
            logger.error(f"Error checking collection: {e}")
            return False
    
    def use_existing_qdrant_data(self) -> bool:
        """Use existing Qdrant data (from your chunking.py setup)."""
        try:
            # Check if collection exists and has data
            if self.check_existing_collection():
                logger.info("Using existing Qdrant collection with your chunked data")
                return True
            else:
                logger.warning("No existing Qdrant collection found. You may need to run your chunking.py first.")
                return False
        except Exception as e:
            logger.error(f"Failed to use existing Qdrant data: {e}")
            return False
    
    def embed_documents(self, force_rebuild: bool = False) -> bool:
        """Embed all documents and store in Qdrant vector database."""
        try:
            # First, try to use existing Qdrant data
            if not force_rebuild and self.use_existing_qdrant_data():
                return True
            
            # If no existing data or force rebuild, create new embeddings
            vector_store = self.get_vector_store()
            qdrant_client = self.get_qdrant_client()
            
            # Load documents
            documents = self.load_documents()
            
            if not documents:
                logger.warning("No documents found to embed")
                return False
            
            # Create collection if it doesn't exist
            collections = qdrant_client.get_collections().collections
            collection_names = [col.name for col in collections]
            
            if self.collection_name not in collection_names:
                logger.info(f"Creating collection: {self.collection_name}")
                qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE)  # all-MiniLM-L6-v2 dimension
                )
            elif force_rebuild:
                logger.info(f"Recreating collection: {self.collection_name}")
                qdrant_client.delete_collection(collection_name=self.collection_name)
                qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
                )
            
            # Split documents into chunks
            text_splitter = self.get_text_splitter()
            all_chunks = []
            all_metadatas = []
            
            for doc in documents:
                chunks = text_splitter.split_text(doc['content'])
                for i, chunk in enumerate(chunks):
                    all_chunks.append(chunk)
                    metadata = doc['metadata'].copy()
                    metadata['chunk_id'] = i
                    all_metadatas.append(metadata)
            
            # Add documents to vector store in batches
            batch_size = 100
            for i in range(0, len(all_chunks), batch_size):
                batch_texts = all_chunks[i:i + batch_size]
                batch_metadatas = all_metadatas[i:i + batch_size]
                
                vector_store.add_texts(
                    texts=batch_texts,
                    metadatas=batch_metadatas
                )
                
                logger.info(f"Embedded batch {i//batch_size + 1}/{(len(all_chunks) + batch_size - 1)//batch_size}")
            
            logger.info(f"Successfully embedded {len(all_chunks)} chunks from {len(documents)} documents")
            return True
            
        except Exception as e:
            logger.error(f"Failed to embed documents: {e}")
            return False
    
    def query_documents(self, question: str) -> Dict[str, Any]:
        """Query the RAG system for an answer."""
        try:
            qa_chain = self.get_qa_chain()
            
            result = qa_chain({"query": question})
            
            # Extract source information
            sources = []
            if 'source_documents' in result:
                for doc in result['source_documents']:
                    sources.append({
                        'filename': doc.metadata.get('filename', 'Unknown'),
                        'source': doc.metadata.get('source', 'Unknown'),
                        'content_preview': doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                    })
            
            return {
                'success': True,
                'answer': result['result'],
                'sources': sources,
                'question': question
            }
            
        except Exception as e:
            logger.error(f"Failed to query documents for question '{question}': {e}")
            return {
                'success': False,
                'error': str(e),
                'answer': '',
                'sources': [],
                'question': question
            }
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the document collection."""
        try:
            vector_store = self.get_vector_store()
            
            # Get sample documents to count
            sample_docs = vector_store.similarity_search("", k=1000)  # Get up to 1000 docs
            
            # Count by source
            source_counts = {}
            for doc in sample_docs:
                source = doc.metadata.get('filename', 'Unknown')
                source_counts[source] = source_counts.get(source, 0) + 1
            
            return {
                'total_chunks': len(sample_docs),
                'unique_sources': len(source_counts),
                'source_breakdown': source_counts,
                'collection_name': self.collection_name
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {
                'total_chunks': 0,
                'unique_sources': 0,
                'source_breakdown': {},
                'collection_name': self.collection_name,
                'error': str(e)
            }

# Global RAG instance
rag_config = RAGConfig()
