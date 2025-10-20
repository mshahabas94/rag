"""
Streamlit UI for the Hybrid SQL/RAG Chatbot with persistent sessions.
Integrates with the HybridChatbot from chatbot.py
"""

import streamlit as st
from datetime import datetime
import time
import asyncio
from typing import Dict, Any, Optional

from main import HybridChatbot
from models.schemas import ChatRequest, QueryType
from services.chat_database_service import chat_db_service
from services.conversation_memory_service import PersistentConversationMemory

# Page configuration
st.set_page_config(
    page_title=" Loaded Hybrid AI Chatbot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
            
    /* Hide top-right hamburger menu & deploy button */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}

    /* Change whole app background */
    .stApp {
        background-color: #1f133c;  /* deep blue, you can change hex */
        color: white;  /* text color for contrast */
    }

    /* Optional: Change sidebar background */
    section[data-testid="stSidebar"] {
        background-color: #1f133c !important;
    }
    .user-message {
        background-color: #2f3226;
        padding: 10px 15px;
        border-radius: 15px;
        border-bottom-right-radius: 5px;
        margin: 5px 0;
        margin-left: 20%;
        text-align: right;
    }
    .assistant-message {
        background-color: #2f3226;
        padding: 10px 15px;
        border-radius: 15px;
        border-bottom-left-radius: 5px;
        margin: 5px 0;
        margin-right: 20%;
    }
    .query-type-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.8em;
        font-weight: bold;
        margin-left: 10px;
    }
    .sql-badge {
        background-color: #d4edff;
        color: #0066cc;
    }
    .rag-badge {
        background-color: #d4f4dd;
        color: #006600;
    }
    .hybrid-badge {
        background-color: #ffe6d4;
        color: #cc6600;
    }
    .stButton button {
        width: 100%;
    }
            
            
</style>
""", unsafe_allow_html=True)

# Initialize session state
def initialize_session_state():
    """Initialize all session state variables."""
    if 'initialized' not in st.session_state:
        st.session_state.initialized = False
        st.session_state.current_session_id = None
        st.session_state.chat_history = []
        st.session_state.customer_id = None
        st.session_state.customer_email = None
        st.session_state.conversation_memory = None

initialize_session_state()

# Initialize chatbot on first run
@st.cache_resource
def get_chatbot():
    """Get the hybrid chatbot instance (cached across reruns)."""
    chatbot = HybridChatbot()
    asyncio.run(chatbot.initialize())
    return chatbot

def create_new_session(session_name: Optional[str] = None) -> str:
    """Create a new chat session."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        if not session_name:
            session_name = f"Chat Session {timestamp}"
        
        session_id = chat_db_service.create_session(
            session_name=session_name,
            metadata={
                'customer_id': st.session_state.customer_id,
                'customer_email': st.session_state.customer_email
            }
        )
        
        st.session_state.current_session_id = session_id
        st.session_state.chat_history = []
        st.session_state.conversation_memory = PersistentConversationMemory(session_id)
        
        return session_id
        
    except Exception as e:
        st.error(f"Failed to create new session: {e}")
        return None

def load_session(session_id: str):
    """Load an existing chat session."""
    try:
        st.session_state.current_session_id = session_id
        
        # Load messages from database
        messages = chat_db_service.get_session_messages(session_id)
        st.session_state.chat_history = messages
        
        # Initialize conversation memory for this session
        st.session_state.conversation_memory = PersistentConversationMemory(session_id)
        
    except Exception as e:
        st.error(f"Failed to load session: {e}")

def get_query_type_badge(query_type: QueryType) -> str:
    """Generate HTML badge for query type."""
    badge_class = {
        QueryType.SQL: "sql-badge",
        QueryType.RAG: "rag-badge",
        QueryType.HYBRID: "hybrid-badge"
    }.get(query_type, "sql-badge")
    
    return f'<span class="query-type-badge {badge_class}">{query_type.value.upper()}</span>'

def format_message(msg: Dict[str, Any], show_metadata: bool = True):
    """Format and display a chat message."""
    is_user = msg['role'] == 'user'
    
    if is_user:
        st.markdown(f'<div class="user-message">{msg["content"]}</div>', unsafe_allow_html=True)
    else:
        # Assistant message with metadata
        content = msg['content']
        
        # Add query type badge if available
        if show_metadata and 'metadata' in msg and 'query_type' in msg['metadata']:
            query_type = msg['metadata']['query_type']
            badge = get_query_type_badge(QueryType(query_type))
            st.markdown(f'<div class="assistant-message">{content} {badge}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="assistant-message">{content}</div>', unsafe_allow_html=True)
        
        # Show additional metadata in expander
        if show_metadata and 'metadata' in msg:
            metadata = msg['metadata']
            
            with st.expander("View Details", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    if 'processing_time' in metadata:
                        st.metric("Processing Time", f"{metadata['processing_time']:.2f}s")
                    if 'confidence' in metadata:
                        st.metric("Confidence", f"{metadata['confidence']:.2%}")
                
                with col2:
                    if 'sql_query' in metadata and metadata['sql_query']:
                        st.text("SQL Query:")
                        st.code(metadata['sql_query'], language='sql')
                    
                    if 'sources' in metadata and metadata['sources']:
                        st.text("Sources:")
                        for source in metadata['sources']:
                            st.markdown(f"- {source.get('filename', 'Unknown')}")

async def process_user_message(user_input: str):
    """Process user message through the hybrid chatbot."""
    try:
        # Get conversation history for context
        conversation_history = []
        if st.session_state.conversation_memory:
            memory_vars = st.session_state.conversation_memory.load_memory_variables({})
            if 'history' in memory_vars:
                # Convert to list of dicts if it's messages
                history_messages = memory_vars['history']
                if isinstance(history_messages, str):
                    conversation_history = history_messages
                else:
                    # Convert LangChain messages to simple format
                    conversation_history = []
                    for msg in history_messages:
                        conversation_history.append({
                            'role': 'user' if hasattr(msg, '__class__') and 'Human' in msg.__class__.__name__ else 'assistant',
                            'content': msg.content if hasattr(msg, 'content') else str(msg)
                        })
        
        # Create chat request with conversation history
        request = ChatRequest(
            question=user_input,
            customer_id=st.session_state.customer_id,
            customer_email=st.session_state.customer_email,
            session_id=st.session_state.current_session_id,
            conversation_history=conversation_history
        )
        
        # Process through cached chatbot instance
        chatbot = get_chatbot()
        response = await chatbot.process_chat_request(request)
        
        return response
        
    except Exception as e:
        st.error(f"Error processing message: {e}")
        return None

def render_sidebar():
    """Render the sidebar with session management and settings."""
    with st.sidebar:
        st.title("Chat Sessions")
        
        # Customer information section
        with st.expander("Customer Info", expanded=False):
            st.session_state.customer_id = st.text_input(
                "Customer ID",
                value=st.session_state.customer_id or "",
                help="Optional: For personalized database queries"
            )
            st.session_state.customer_email = st.text_input(
                "Customer Email",
                value=st.session_state.customer_email or "",
                help="Optional: For personalized database queries"
            )
        
        st.divider()
        
        # New session button
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("New Chat", use_container_width=True):
                create_new_session()
                st.rerun()
        with col2:
            if st.button("🔄", help="Refresh sessions"):
                st.rerun()
        
        st.divider()
        
        # Session list
        st.subheader("Recent Sessions")
        sessions = chat_db_service.get_all_sessions()
        
        if not sessions:
            st.info("No sessions yet. Create a new chat to get started!")
        
        for session in sessions:
            session_id = session['session_id']
            session_name = session['session_name']
            
            # Check if this is the current session
            is_current = session_id == st.session_state.current_session_id
            
            # Session row
            col1, col2, col3 = st.columns([5, 1, 1])
            
            with col1:
                if st.button(
                    f"{'📌 ' if is_current else ''}{session_name}",
                    key=f"session_{session_id}",
                    use_container_width=True,
                    type="primary" if is_current else "secondary"
                ):
                    load_session(session_id)
                    st.rerun()
            
            with col2:
                if st.button("✏️", key=f"edit_{session_id}", help="Rename"):
                    st.session_state[f'rename_{session_id}'] = True
            
            with col3:
                if st.button("🗑️", key=f"delete_{session_id}", help="Delete"):
                    if chat_db_service.delete_session(session_id):
                        if session_id == st.session_state.current_session_id:
                            st.session_state.current_session_id = None
                            st.session_state.chat_history = []
                            st.session_state.conversation_memory = None
                        st.rerun()
            
            # Rename dialog
            if st.session_state.get(f'rename_{session_id}', False):
                new_name = st.text_input(
                    "New name:",
                    value=session_name,
                    key=f"rename_input_{session_id}"
                )
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Save", key=f"save_{session_id}"):
                        chat_db_service.update_session_name(session_id, new_name)
                        st.session_state[f'rename_{session_id}'] = False
                        st.rerun()
                with col_b:
                    if st.button("Cancel", key=f"cancel_{session_id}"):
                        st.session_state[f'rename_{session_id}'] = False
                        st.rerun()
        
        st.divider()
        
        # Health status
        with st.expander("System Status"):
            try:
                chatbot = get_chatbot()
                health = chatbot.get_health_status()
            except:
                # If chatbot not initialized, show error state
                health = type('obj', (object,), {
                    'status': 'error',
                    'database_healthy': False,
                    'vanna_healthy': False,
                    'rag_healthy': False,
                    'uptime': 0
                })()
            
            st.metric("Status", health.status.upper())
            
            col1, col2 = st.columns(2)
            with col1:
                st.write("Database:", "✅" if health.database_healthy else "❌")
                st.write("Vanna (SQL):", "✅" if health.vanna_healthy else "❌")
            with col2:
                st.write("RAG:", "✅" if health.rag_healthy else "❌")
                st.write(f"Uptime: {health.uptime:.0f}s")

def render_main_chat():
    """Render the main chat interface."""
    st.title("Loaded AI Chatbot")
    st.caption("Ask questions about your orders (SQL) or policies (RAG)")
    
    # Initialize chatbot if not done
    if not st.session_state.initialized:
        with st.spinner("Initializing chatbot..."):
            try:
                get_chatbot()
                st.session_state.initialized = True
                st.success("Chatbot initialized successfully!")
            except Exception as e:
                st.error(f"Failed to initialize chatbot: {e}")
                return
    
    # Create first session if none exists
    if not st.session_state.current_session_id:
        sessions = chat_db_service.get_all_sessions()
        if sessions:
            load_session(sessions[0]['session_id'])
        else:
            create_new_session()
    
    # Chat container
    chat_container = st.container()
    
    # Display chat history
    with chat_container:
        for msg in st.session_state.chat_history:
            format_message(msg)
    
    # Input form at the bottom
    st.divider()
    
    with st.form(key="chat_input", clear_on_submit=True):
        col1, col2 = st.columns([6, 1])
        
        with col1:
            user_input = st.text_area(
                "Your message:",
                key="user_message",
                height=100,
                placeholder="Ask about orders, policies, or general information..."
            )
        
        with col2:
            st.write("")  # Spacing
            st.write("")  # Spacing
            submit_button = st.form_submit_button("Send", use_container_width=True)
        
        if submit_button and user_input:
            # Add user message to UI immediately
            st.session_state.chat_history.append({
                'role': 'user',
                'content': user_input
            })
            
            # Show typing indicator
            with chat_container:
                with st.spinner("Processing..."):
                    # Process message
                    response = asyncio.run(process_user_message(user_input))
                    
                    if response and response.success:
                        # Prepare metadata
                        metadata = {
                            'query_type': response.query_type.value,
                            'processing_time': response.processing_time,
                        }
                        
                        if response.sql_result and response.sql_result.sql:
                            metadata['sql_query'] = response.sql_result.sql
                        
                        if response.rag_result and response.rag_result.sources:
                            metadata['sources'] = response.rag_result.sources
                        
                        if response.intent_classification:
                            metadata['confidence'] = response.intent_classification.confidence
                        
                        # Add assistant message
                        st.session_state.chat_history.append({
                            'role': 'assistant',
                            'content': response.answer,
                            'metadata': metadata
                        })
                        
                        # Save to conversation memory
                        if st.session_state.conversation_memory:
                            st.session_state.conversation_memory.save_context(
                                {'input': user_input},
                                {'output': response.answer, 'metadata': metadata}
                            )
                    else:
                        error_msg = response.error if response else "Unknown error"
                        st.session_state.chat_history.append({
                            'role': 'assistant',
                            'content': f"I encountered an error: {error_msg}",
                            'metadata': {}
                        })
            
            # Force refresh
            st.rerun()
    
    # Help section
    with st.expander("How to use this chatbot"):
        st.markdown("""
        This hybrid chatbot can answer:
        
        **📊 SQL Queries (Database)**
        - "Show my recent orders"
        - "What's the status of order #12345?"
        - "How much did I spend last month?"
        
        **📚 RAG Queries (Knowledge Base)**
        - "What's your return policy?"
        - "How do I track my shipment?"
        - "What payment methods do you accept?"
        
        **🔀 Hybrid Queries (Both)**
        - "Can I return order #12345?"
        - "Show my orders and explain the refund policy"
        
        *Tip: Provide your Customer ID or Email in the sidebar for personalized results!*
        """)

def main():
    """Main application entry point."""
    render_sidebar()
    render_main_chat()

if __name__ == "__main__":
    main()