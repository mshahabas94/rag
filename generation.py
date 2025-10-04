from llama_cpp import Llama
import os
from typing import List, Dict, Any
from chunking import initialize_and_populate_vectorstore

class LlamaCppClient:
    def __init__(self, model_path: str, n_ctx: int = 4096, n_gpu_layers: int = -1):
        """
        Initialize llama.cpp client
        
        Args:
            model_path: Path to your .gguf model file
            n_ctx: Context window size
            n_gpu_layers: Number of layers to offload to GPU (-1 for all)
        """
        print(f"🔄 Loading LLM from: {model_path}")
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            verbose=False
        )
        print("✅ LLM loaded successfully!")
    
    def generate_response(self, prompt: str, max_tokens: int = 512, temperature: float = 0.1) -> str:
        """
        Generate response using llama.cpp
        """
        try:
            response = self.llm(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=0.9,
                echo=False,
                stop=["</s>", "###", "\n\n\n"]
            )
            return response['choices'][0]['text'].strip()
        except Exception as e:
            return f"Error generating response: {e}"

def create_llama_prompt(context: str, question: str) -> str:
    """
    Create a prompt for llama.cpp with your Q&A context
    """
    prompt = f"""<|start_header_id|>system<|end_header_id|>

You are a helpful customer support assistant for Loaded gaming platform. 
Use the following support articles to answer the user's question accurately.
If the answer isn't in the context, say you don't know but be helpful.

Support Articles:
{context}

<|start_header_id|>user<|end_header_id|>
{question}<|end_header_id|>
<|start_header_id|>assistant<|end_header_id|>"""
    
    return prompt

def create_rag_pipeline(retriever):
    """
    Create RAG pipeline with llama.cpp
    """
    # Initialize llama.cpp client
    model_path = "./llama.cpp/models/llama-3.1-8b-q4.gguf"  # Update this path if needed
    llama_client = LlamaCppClient(model_path)
    
    def rag_function(question: str) -> Dict[str, Any]:
        """
        Complete RAG pipeline: Retrieve -> Format -> Generate
        """
        # Step 1: Retrieve relevant documents
        relevant_docs = search_support_questions(question, retriever)
        
        # Step 2: Format context from retrieved documents
        context = format_retrieved_docs(relevant_docs)
        
        # Step 3: Create prompt
        prompt = create_llama_prompt(context, question)
        
        # Step 4: Generate response
        answer = llama_client.generate_response(prompt)
        
        return {
            "question": question,
            "answer": answer,
            "source_documents": relevant_docs,
            "context_used": context
        }
    
    return rag_function

def format_retrieved_docs(docs: List[Dict]) -> str:
    """
    Format retrieved documents for the context
    """
    context_parts = []
    for i, doc in enumerate(docs):
        context_parts.append(f"Article {i+1}:")
        context_parts.append(f"Q: {doc['question']}")
        context_parts.append(f"A: {doc['answer']}")
        context_parts.append("")  # Empty line between articles
    
    return "\n".join(context_parts)

def main():
    """
    Main function to run the complete RAG system
    """
    print("🎮 Loaded Gaming Support RAG System")
    print("=" * 50)
    
    # Step 1: Initialize vector store
    print("\n🔄 Step 1: Initializing vector store...")
    retriever = initialize_and_populate_vectorstore()
    
    # Step 2: Create RAG pipeline
    print("🤖 Step 2: Creating RAG pipeline with llama.cpp...")
    rag_pipeline = create_rag_pipeline(retriever)
    
    print("\n✅ System Ready! Ask your support questions.")
    print("   Type 'quit' to exit\n")
    
    # Interactive chat loop
    while True:
        try:
            user_question = input("\n🎯 Your Question: ").strip()
            
            if user_question.lower() in ['quit', 'exit', 'bye', 'q']:
                print("👋 Thank you for using Loaded Support!")
                break
                
            if not user_question:
                continue
                
            # Process the question
            print("🔍 Searching knowledge base...")
            result = rag_pipeline(user_question)
            
            # Display results
            print(f"\n🤖 Support Assistant:")
            print(f"   {result['answer']}")
            
            # Show sources
            if result['source_documents']:
                print(f"\n📚 Sources (showing top {len(result['source_documents'])}):")
                for i, doc in enumerate(result['source_documents'][:3]):
                    print(f"   {i+1}. {doc['question']}")
            
            print("\n" + "-" * 50)
            
        except KeyboardInterrupt:
            print("\n\n👋 Session ended by user.")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

# Enhanced search function with better formatting
def search_support_questions(query: str, retriever_instance = None):
    """
    Search for relevant support questions and return formatted results
    """
    retriever = initialize_and_populate_vectorstore()
    if retriever_instance is None:
        if retriever is None:
            raise ValueError("Retriever not initialized. Call initialize_and_populate_vectorstore() first.")
        retriever_instance = retriever
    
    try:
        results = retriever_instance.get_relevant_documents(query)
        
        formatted_results = []
        for i, doc in enumerate(results):
            formatted_result = {
                "rank": i + 1,
                "question": doc.metadata.get("question", "N/A"),
                "answer": doc.metadata.get("answer", "N/A"),
                "source": doc.metadata.get("source", "N/A"),
                "score": getattr(doc, 'score', 0.0)
            }
            formatted_results.append(formatted_result)
        
        # Sort by score if available
        formatted_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        return formatted_results
        
    except Exception as e:
        print(f"Search error: {e}")
        return []

# Test function
def test_rag_system():
    """
    Test the RAG system with sample questions
    """
    print("🧪 Testing RAG System...")
    
    retriever = initialize_and_populate_vectorstore()
    rag_pipeline = create_rag_pipeline(retriever)
    
    test_questions = [
        "What should I do if my code isn't working?",
        "How do I reset my password?",
        "What are CDKoins and how do I earn them?",
        "How can I delete my account?",
        "Do I need a Loaded account to make purchases?"
    ]
    
    for question in test_questions:
        print(f"\n{'='*60}")
        print(f"❓ Test Question: {question}")
        print(f"{'='*60}")
        
        result = rag_pipeline(question)
        
        print(f"🤖 Answer: {result['answer']}")
        
        if result['source_documents']:
            print(f"\n📚 Top source: {result['source_documents'][0]['question']}")
        
        print(f"{'-'*60}")

if __name__ == "__main__":
    # Choose one of the following:
    
    # Option 1: Run interactive chat
    main()
    
    # Option 2: Run tests
    # test_rag_system()