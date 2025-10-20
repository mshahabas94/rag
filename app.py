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
    page_title="Loaded Hybrid AI Chatbot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Modern Custom CSS
st.markdown("""
<style>
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
            
    
    
    /* App Background */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: #ffffff;
    }
    header, .stApp > header, .st-emotion-cache-12fmjuu, .st-emotion-cache-1avcm0n {
    visibility: visible !important;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: #ffffff !important;
    }

    /* Optional: make sure any text or icons inside header are white */
    header * {
        color: #ffffff !important;
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #2d1b4e 0%, #1a0f2e 100%) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    section[data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    
    /* Chat Messages */
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 16px 20px;
        border-radius: 20px;
        border-bottom-right-radius: 6px;
        margin: 12px 0;
        margin-left: 15%;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        color: #ffffff;
        font-size: 15px;
        line-height: 1.6;
    }
    
    .assistant-message {
        background: rgba(255, 255, 255, 0.95);
        padding: 16px 20px;
        border-radius: 20px;
        border-bottom-left-radius: 6px;
        margin: 12px 0;
        margin-right: 15%;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        color: #2d1b4e;
        font-size: 15px;
        line-height: 1.6;
    }
    
    /* Query Type Badges */
    .query-type-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        margin-left: 8px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .sql-badge {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: #ffffff;
    }
    
    .rag-badge {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        color: #ffffff;
    }
    
    .hybrid-badge {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: #ffffff;
    }
    
    /* Buttons */
    .stButton button {
        width: 100%;
        border-radius: 10px;
        font-weight: 500;
        transition: all 0.3s ease;
        border: none;
    }
    
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.2);
    }
    
    /* Session Button Styling */
    .stButton button[kind="primary"] {
    background: #1e3a8a !important;;
    color: white !important;
    border: none !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4) !important;
}

    
    

    .stButton button[kind="secondary"] {
        background: rgba(255, 255, 255, 0.1);
        color: rgba(255, 255, 255, 0.9);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    .stButton button[kind="secondary"]:hover {
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.3);
    }
    
    /* Text Input & Text Area */
    .stTextInput input, .stTextArea textarea {
        border-radius: 12px;
        border: 2px solid rgba(255, 255, 255, 0.2);
        background: rgba(255, 255, 255, 0.9);
        color: #2d1b4e;
        font-size: 15px;
    }
    
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2);
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        font-weight: 500;
    }
    
    /* Divider */
    hr {
        border-color: rgba(255, 255, 255, 0.2);
        margin: 20px 0;
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        font-size: 24px;
        font-weight: 600;
        color: #667eea;
    }
    
    /* Session Buttons */
    .session-active {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: 2px solid rgba(255, 255, 255, 0.3);
    }
    
    /* Title Styling */
    h1 {
        color: #ffffff;
        font-weight: 700;
        text-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
    }
    
    h2, h3 {
        color: #ffffff;
        font-weight: 600;
    }
    
    /* Caption */
    .caption {
        color: rgba(255, 255, 255, 0.8);
        font-size: 16px;
        margin-bottom: 30px;
    }
    
    /* Code blocks */
    code {
        background: rgba(0, 0, 0, 0.05);
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 13px;
    }
    
    /* Spinner */
    .stSpinner > div {
        border-top-color: #667eea !important;
    }
    
    /* Info box */
    .stAlert {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        border-left: 4px solid #667eea;
    }
    
    /* Form */
    .stForm {
        background: rgba(255, 255, 255, 0.05);
        padding: 20px;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }

            div.stForm button {
    background-color: #1e3a8a !important; /* deep navy blue */
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 12px rgba(30, 58, 138, 0.5) !important;
    transition: all 0.3s ease !important;
}

div.stForm button:hover {
    background-color: #1e40af !important;
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(30, 58, 138, 0.7) !important;
}
   /* Custom Floating Sidebar Toggle Button */
#custom-sidebar-toggle {
    position: fixed;
    top: 20px;
    left: 10px;
    z-index: 9999;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    transition: all 0.3s ease;
    font-size: 18px;
}

#custom-sidebar-toggle:hover {
    transform: scale(1.1);
    background: linear-gradient(135deg, #5a67d8 0%, #805ad5 100%);
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
    
    return f'<span class="query-type-badge {badge_class}">{query_type.value}</span>'

def format_message(msg: Dict[str, Any], show_metadata: bool = True):
    """Format and display a chat message."""
    is_user = msg['role'] == 'user'
    
    if is_user:
        st.markdown(f'<div class="user-message">👤 {msg["content"]}</div>', unsafe_allow_html=True)
    else:
        # Assistant message with metadata
        content = msg['content']
        
        # Add query type badge if available
        if show_metadata and 'metadata' in msg and 'query_type' in msg['metadata']:
            query_type = msg['metadata']['query_type']
            badge = get_query_type_badge(QueryType(query_type))
            st.markdown(f'<div class="assistant-message">🤖 {content} {badge}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="assistant-message">🤖 {content}</div>', unsafe_allow_html=True)
        
        # Show additional metadata in expander
        if show_metadata and 'metadata' in msg:
            metadata = msg['metadata']
            
            with st.expander("📊 View Details", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    if 'processing_time' in metadata:
                        st.metric("⚡ Processing Time", f"{metadata['processing_time']:.2f}s")
                    if 'confidence' in metadata:
                        st.metric("🎯 Confidence", f"{metadata['confidence']:.2%}")
                
                with col2:
                    if 'sql_query' in metadata and metadata['sql_query']:
                        st.text("📝 SQL Query:")
                        st.code(metadata['sql_query'], language='sql')
                    
                    if 'sources' in metadata and metadata['sources']:
                        st.text("📚 Sources:")
                        for source in metadata['sources']:
                            st.markdown(f"• {source.get('filename', 'Unknown')}")

async def process_user_message(user_input: str):
    """Process user message through the hybrid chatbot."""
    try:
        # Get conversation history for context
        conversation_history = []
        if st.session_state.conversation_memory:
            memory_vars = st.session_state.conversation_memory.load_memory_variables({})
            if 'history' in memory_vars:
                history_messages = memory_vars['history']
                if isinstance(history_messages, str):
                    conversation_history = history_messages
                else:
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
        st.title("💬 Chat Sessions")
        
        # Customer information section
        with st.expander("👤 Customer Info", expanded=False):
            st.session_state.customer_id = st.text_input(
                "Customer ID",
                value=st.session_state.customer_id or "",
                help="Optional: For personalized database queries",
                placeholder="Enter your customer ID"
            )
            st.session_state.customer_email = st.text_input(
                "Customer Email",
                value=st.session_state.customer_email or "",
                help="Optional: For personalized database queries",
                placeholder="your.email@example.com"
            )
        
        st.divider()
        
        # New session button
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button("➕ New Chat", use_container_width=True, type="primary"):
                create_new_session()
                st.rerun()
        with col2:
            if st.button("🔄", help="Refresh sessions", use_container_width=True):
                st.rerun()
        
        st.divider()
        
        # Session list
        st.subheader("📋 Recent Sessions")
        sessions = chat_db_service.get_all_sessions()
        
        if not sessions:
            st.info("No sessions yet. Create a new chat to get started! 🚀")
        
        for session in sessions:
            session_id = session['session_id']
            session_name = session['session_name']
            
            # Check if this is the current session
            is_current = session_id == st.session_state.current_session_id
            
            # Session row with better button alignment
            row_col1, row_col2, row_col3 = st.columns([11, 3.7, 3.7])
            
            with row_col1:
                button_text = f"{'📌 ' if is_current else '💭 '}{session_name[:25]}{'...' if len(session_name) > 25 else ''}"
                if st.button(
                    button_text,
                    key=f"session_{session_id}",
                    use_container_width=True,
                    type="primary" if is_current else "secondary"
                ):
                    load_session(session_id)
                    st.rerun()
            
            with row_col2:
                if st.button("✏️", key=f"edit_{session_id}", help="Rename", use_container_width=True):
                    st.session_state[f'rename_{session_id}'] = True
            
            with row_col3:
                if st.button("🗑️", key=f"delete_{session_id}", help="Delete", use_container_width=True):
                    if chat_db_service.delete_session(session_id):
                        if session_id == st.session_state.current_session_id:
                            st.session_state.current_session_id = None
                            st.session_state.chat_history = []
                            st.session_state.conversation_memory = None
                        st.rerun()
            
            # Rename dialog - placed below the session row for better layout
            if st.session_state.get(f'rename_{session_id}', False):
                st.markdown("---")
                new_name = st.text_input(
                    "Rename session:",
                    value=session_name,
                    key=f"rename_input_{session_id}",
                    placeholder="Enter new session name"
                )
                rename_col1, rename_col2 = st.columns(2)
                with rename_col1:
                    if st.button("💾 Save", key=f"save_{session_id}", use_container_width=True):
                        if new_name.strip():
                            chat_db_service.update_session_name(session_id, new_name.strip())
                        st.session_state[f'rename_{session_id}'] = False
                        st.rerun()
                with rename_col2:
                    if st.button("❌ Cancel", key=f"cancel_{session_id}", use_container_width=True):
                        st.session_state[f'rename_{session_id}'] = False
                        st.rerun()
                st.markdown("---")
        
        st.divider()
        
        # Health status
        with st.expander("🏥 System Status", expanded=False):
            try:
                chatbot = get_chatbot()
                health = chatbot.get_health_status()
            except:
                health = type('obj', (object,), {
                    'status': 'error',
                    'database_healthy': False,
                    'vanna_healthy': False,
                    'rag_healthy': False,
                    'uptime': 0
                })()
            
            status_emoji = "🟢" if health.status == "healthy" else "🔴"
            st.metric("Status", f"{status_emoji} {health.status.upper()}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.write("🗄️ Database:", "✅" if health.database_healthy else "❌")
                st.write("🔍 Vanna (SQL):", "✅" if health.vanna_healthy else "❌")
            with col2:
                st.write("📚 RAG:", "✅" if health.rag_healthy else "❌")
                st.write(f"⏱️ Uptime: {health.uptime:.0f}s")
def render_main_chat():
    """Render the main chat interface."""
    st.title("🤖 Loaded AI Chatbot")
    st.markdown('<p class="caption">Ask questions about your orders (SQL) or policies (RAG)</p>', unsafe_allow_html=True)
    
    # Initialize chatbot if not done
    if not st.session_state.initialized:
        with st.spinner("🚀 Initializing chatbot..."):
            try:
                get_chatbot()
                st.session_state.initialized = True
                st.success("✅ Chatbot initialized successfully!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to initialize chatbot: {e}")
                return
    
    # Create first session if none exists
    if not st.session_state.current_session_id:
        sessions = chat_db_service.get_all_sessions()
        if sessions:
            load_session(sessions[0]['session_id'])
        else:
            create_new_session()
    
    # Chat container with better spacing
    chat_container = st.container()
    
    # Display chat history
    with chat_container:
        if not st.session_state.chat_history:
            st.info("👋 Welcome! Start a conversation by typing a message below.")
        
        for msg in st.session_state.chat_history:
            format_message(msg)
    
    # Input form at the bottom
    st.divider()
    
    with st.form(key="chat_input", clear_on_submit=True):
        col1, col2 = st.columns([5, 1])
        
        with col1:
            user_input = st.text_area(
                "Your message:",
                key="user_message",
                height=100,
                placeholder="Type your question here... (e.g., 'Show my recent orders' or 'What's your return policy?')",
                label_visibility="collapsed"
            )
        
        with col2:
            st.write("")
            st.write("")
            submit_button = st.form_submit_button("📤 Send", use_container_width=True, type="primary")
        
        if submit_button and user_input:
            # Add user message to UI immediately
            st.session_state.chat_history.append({
                'role': 'user',
                'content': user_input
            })
            
            # Show typing indicator
            with chat_container:
                with st.spinner("🤔 Thinking..."):
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
                            'content': f"⚠️ I encountered an error: {error_msg}",
                            'metadata': {}
                        })
            
            st.rerun()
    
    # Help section
    with st.expander("❓ How to use this chatbot", expanded=False):
        st.markdown("""
        ### This hybrid chatbot can answer:
        
        **📊 SQL Queries (Database)**
        - *"Show my recent orders"*
        - *"What's the status of order #12345?"*
        - *"How much did I spend last month?"*
        
        **📚 RAG Queries (Knowledge Base)**
        - *"What's your return policy?"*
        - *"How do I track my shipment?"*
        - *"What payment methods do you accept?"*
        
        **🔀 Hybrid Queries (Both)**
        - *"Can I return order #12345?"*
        - *"Show my orders and explain the refund policy"*
        
        > 💡 **Tip:** Provide your Customer ID or Email in the sidebar for personalized results!
        """)

def main():
    """Main application entry point."""
    render_sidebar()
    render_main_chat()

if __name__ == "__main__":
    main()

st.markdown("""
<style>
/* Make Customer ID and Email text inputs visible in sidebar */
[data-testid="stSidebar"] input[type="text"], 
[data-testid="stSidebar"] input[type="email"] {
    background-color: rgba(255, 255, 255, 0.95) !important;
    color: #000000 !important;           /* Black text for readability */
    border: 1px solid #ccc !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
}

/* Placeholder styling */
[data-testid="stSidebar"] input::placeholder {
    color: rgba(0, 0, 0, 0.6) !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* Hide toolbar / deploy button in Streamlit v1.50+ */

/* Hide any element that contains "Deploy" in title or aria-label */
header button[title*="Deploy"] {
    display: none !important;
    visibility: hidden !important;
    pointer-events: none !important;
}

/* Hide known classes from previous versions */
.stAppDeployButton,
.stDeployButton,
button.stAppDeployButton {
    display: none !important;
}

/* Hide toolbar container if it still appears */
header [data-testid="stToolbarActions"],
header div[data-testid="stToolbarActions"] {
    display: none !important;
}

/* For completeness: hide the main menu and full-screen icons if undesired */
#MainMenu { visibility: hidden !important; }
footer { visibility: hidden !important; }
</style>
""", unsafe_allow_html=True)



