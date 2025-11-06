"""
Database schema for agentic AI system.

Creates tables for:
- Agent state and coordination
- Agent memory (vector + transactional)
- Cross-agent communication
- Decision tracking and learning
- Conversation history
- Document processing
"""

from sqlalchemy import text
from typing import Optional
import sys


AGENT_SCHEMA_SQL = """
-- Agent state and coordination
CREATE TABLE IF NOT EXISTS agent_state (
    agent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_type STRING NOT NULL,
    region STRING NOT NULL,
    status STRING NOT NULL DEFAULT 'idle',
    current_task JSONB,
    last_heartbeat TIMESTAMP DEFAULT now(),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_state_region_status 
    ON agent_state (region, status);
CREATE INDEX IF NOT EXISTS idx_agent_state_type 
    ON agent_state (agent_type, status);

-- Agent memory (vector + metadata)
CREATE TABLE IF NOT EXISTS agent_memory (
    memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agent_state(agent_id) ON DELETE CASCADE,
    user_id STRING,
    memory_type STRING NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(384),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT now(),
    accessed_at TIMESTAMP DEFAULT now(),
    access_count INT DEFAULT 0
);

-- Vector index for semantic search
CREATE INDEX IF NOT EXISTS idx_agent_memory_embedding 
    ON agent_memory USING cspann (user_id, embedding vector_l2_ops);
CREATE INDEX IF NOT EXISTS idx_agent_memory_agent 
    ON agent_memory (agent_id, memory_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_memory_user 
    ON agent_memory (user_id, memory_type, created_at DESC);

-- Cross-agent communication and task queue
CREATE TABLE IF NOT EXISTS agent_tasks (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_agent_id UUID REFERENCES agent_state(agent_id),
    target_agent_id UUID REFERENCES agent_state(agent_id),
    task_type STRING NOT NULL,
    priority INT DEFAULT 5,
    payload JSONB,
    status STRING DEFAULT 'pending',
    region STRING,
    created_at TIMESTAMP DEFAULT now(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    result JSONB,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_agent_tasks_status 
    ON agent_tasks (status, priority DESC, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_target 
    ON agent_tasks (target_agent_id, status);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_region 
    ON agent_tasks (region, status);

-- Agent decisions and audit log (for learning)
CREATE TABLE IF NOT EXISTS agent_decisions (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agent_state(agent_id),
    decision_type STRING NOT NULL,
    context JSONB NOT NULL,
    reasoning TEXT,
    action JSONB,
    confidence FLOAT,
    user_feedback STRING,
    created_at TIMESTAMP DEFAULT now(),
    feedback_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_agent 
    ON agent_decisions (agent_id, decision_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_feedback 
    ON agent_decisions (user_feedback, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_type 
    ON agent_decisions (decision_type, created_at DESC);

-- Conversation history (cross-session memory)
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id STRING NOT NULL,
    session_id STRING,
    message_role STRING NOT NULL,
    message_content TEXT NOT NULL,
    message_embedding VECTOR(384),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversations_user 
    ON conversations (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_session 
    ON conversations (session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_embedding 
    ON conversations USING cspann (user_id, message_embedding vector_l2_ops);

-- Documents and receipts
CREATE TABLE IF NOT EXISTS documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id STRING NOT NULL,
    document_type STRING NOT NULL,
    s3_key STRING NOT NULL,
    original_filename STRING,
    extracted_text TEXT,
    extracted_data JSONB,
    embedding VECTOR(384),
    processing_status STRING DEFAULT 'pending',
    processed_by_agent_id UUID REFERENCES agent_state(agent_id),
    created_at TIMESTAMP DEFAULT now(),
    processed_at TIMESTAMP,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_documents_user 
    ON documents (user_id, document_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_status 
    ON documents (processing_status, created_at);
CREATE INDEX IF NOT EXISTS idx_documents_embedding 
    ON documents USING cspann (user_id, embedding vector_l2_ops);
"""


def create_agent_schema(database_url: str, verbose: bool = True) -> bool:
    """
    Create agent-related database schema.
    
    Args:
        database_url: CockroachDB connection string
        verbose: Print progress messages
    
    Returns:
        True if successful, False otherwise
    """
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool
    
    try:
        if verbose:
            print("🔧 Creating agent schema in CockroachDB...")
        
        engine = create_engine(
            database_url,
            poolclass=NullPool,
            connect_args={"options": "-c timezone=utc"}
        )
        
        with engine.connect() as conn:
            # Execute schema creation
            statements = [s.strip() for s in AGENT_SCHEMA_SQL.split(';') if s.strip()]
            
            for i, statement in enumerate(statements, 1):
                if verbose:
                    # Extract table/index name for progress
                    if 'CREATE TABLE' in statement:
                        table_name = statement.split('CREATE TABLE IF NOT EXISTS')[1].split('(')[0].strip()
                        print(f"  [{i}/{len(statements)}] Creating table: {table_name}")
                    elif 'CREATE INDEX' in statement:
                        index_name = statement.split('CREATE INDEX IF NOT EXISTS')[1].split('ON')[0].strip()
                        print(f"  [{i}/{len(statements)}] Creating index: {index_name}")
                
                conn.execute(text(statement))
            
            conn.commit()
        
        engine.dispose()
        
        if verbose:
            print("✅ Agent schema created successfully")
            print("\nCreated tables:")
            print("  - agent_state: Agent registration and status")
            print("  - agent_memory: Vector memory + metadata")
            print("  - agent_tasks: Cross-agent communication")
            print("  - agent_decisions: Decision audit log")
            print("  - conversations: Chat history")
            print("  - documents: Receipt/document storage")
        
        return True
    
    except Exception as e:
        if verbose:
            print(f"❌ Failed to create agent schema: {e}")
        return False


def verify_agent_schema(database_url: str) -> dict:
    """
    Verify that all agent tables exist.
    
    Args:
        database_url: CockroachDB connection string
    
    Returns:
        Dictionary with table existence status
    """
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool
    
    required_tables = [
        'agent_state',
        'agent_memory', 
        'agent_tasks',
        'agent_decisions',
        'conversations',
        'documents'
    ]
    
    results = {}
    
    try:
        engine = create_engine(database_url, poolclass=NullPool)
        
        with engine.connect() as conn:
            for table in required_tables:
                result = conn.execute(text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = '{table}'
                    )
                """))
                results[table] = result.scalar()
        
        engine.dispose()
    
    except Exception as e:
        print(f"Error verifying schema: {e}")
        for table in required_tables:
            results[table] = False
    
    return results


def drop_agent_schema(database_url: str, confirm: bool = False) -> bool:
    """
    Drop all agent tables (dangerous!).
    
    Args:
        database_url: CockroachDB connection string
        confirm: Must be True to actually drop tables
    
    Returns:
        True if successful
    """
    if not confirm:
        print("⚠️  Must pass confirm=True to drop tables")
        return False
    
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool
    
    try:
        print("🗑️  Dropping agent schema...")
        
        engine = create_engine(database_url, poolclass=NullPool)
        
        with engine.connect() as conn:
            # Drop in reverse order due to foreign keys
            tables = ['documents', 'conversations', 'agent_decisions', 
                     'agent_tasks', 'agent_memory', 'agent_state']
            
            for table in tables:
                print(f"  Dropping table: {table}")
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
            
            conn.commit()
        
        engine.dispose()
        print("✅ Agent schema dropped")
        return True
    
    except Exception as e:
        print(f"❌ Failed to drop schema: {e}")
        return False


if __name__ == "__main__":
    """
    Run this script directly to create agent schema:
    python -m banko_ai.utils.agent_schema
    """
    import os
    
    database_url = os.getenv(
        'DATABASE_URL',
        'cockroachdb://root@localhost:26257/defaultdb?sslmode=disable'
    )
    
    print(f"Database: {database_url.split('@')[1] if '@' in database_url else database_url}")
    print()
    
    # Create schema
    success = create_agent_schema(database_url, verbose=True)
    
    if success:
        print("\n" + "="*60)
        print("Verifying schema...")
        print("="*60)
        
        results = verify_agent_schema(database_url)
        all_exist = all(results.values())
        
        for table, exists in results.items():
            status = "✅" if exists else "❌"
            print(f"{status} {table}")
        
        if all_exist:
            print("\n🎉 All agent tables created successfully!")
        else:
            print("\n⚠️  Some tables missing")
            sys.exit(1)
    else:
        sys.exit(1)
