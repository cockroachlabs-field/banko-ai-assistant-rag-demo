"""
Base Agent class for all specialized agents.

Provides common functionality:
- Memory management (vector + transactional)
- Tool execution
- State persistence
- Cross-region coordination
"""

import uuid
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import Tool
from sqlalchemy import text


def json_serializer(obj):
    """JSON serializer for objects not serializable by default"""
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

@dataclass
class AgentDecision:
    """Represents an agent's decision with reasoning"""
    decision_id: str
    decision_type: str
    context: Dict[str, Any]
    reasoning: str
    action: Dict[str, Any]
    confidence: float
    created_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['created_at'] = data['created_at'].isoformat()
        return data


class BaseAgent:
    """
    Base class for all agents in the system.
    
    Each agent has:
    - Unique ID and type
    - Region assignment
    - Memory (short-term and long-term)
    - Tools for specific tasks
    - Decision tracking
    """
    
    def __init__(
        self,
        agent_type: str,
        region: str,
        llm: Any,  # LangChain LLM instance
        tools: Optional[List[Tool]] = None,
        database_url: Optional[str] = None,
        system_prompt: Optional[str] = None
    ):
        """
        Initialize the base agent.
        
        Args:
            agent_type: Type of agent (e.g., 'receipt', 'fraud', 'budget')
            region: AWS region (e.g., 'us-east-1')
            llm: LangChain LLM instance (provider-agnostic)
            tools: List of tools this agent can use
            database_url: CockroachDB connection string
            system_prompt: Custom system prompt for this agent
        """
        self.agent_id = str(uuid.uuid4())
        self.agent_type = agent_type
        self.region = region
        self.llm = llm
        self.tools = tools or []
        self.database_url = database_url
        self.system_prompt = system_prompt or self._default_system_prompt()
        
        # State
        self.status = "idle"  # idle, thinking, acting, blocked
        self.current_task = None
        self.conversation_history = []
        
        # Register agent in database
        if self.database_url:
            self._register_agent()
    
    def _default_system_prompt(self) -> str:
        """Default system prompt for the agent"""
        return f"""You are a {self.agent_type} agent in the Banko AI system.
You are running in region {self.region}.
Your role is to help users with their financial data.
Always explain your reasoning before taking actions.
Be concise but thorough in your responses."""
    
    def _register_agent(self):
        """Register this agent in the database"""
        from sqlalchemy import create_engine
        from sqlalchemy.pool import NullPool
        
        try:
            engine = create_engine(
                self.database_url,
                poolclass=NullPool,
                connect_args={
                    "options": "-c timezone=utc"
                }
            )
            
            with engine.connect() as conn:
                # Check if agent_state table exists, if not, skip registration
                result = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'agent_state'
                    )
                """))
                table_exists = result.scalar()
                
                if table_exists:
                    conn.execute(text("""
                        INSERT INTO agent_state 
                        (agent_id, agent_type, region, status, last_heartbeat, metadata)
                        VALUES (:agent_id, :agent_type, :region, :status, :heartbeat, :metadata)
                        ON CONFLICT (agent_id) 
                        DO UPDATE SET 
                            status = EXCLUDED.status,
                            last_heartbeat = EXCLUDED.last_heartbeat
                    """), {
                        'agent_id': self.agent_id,
                        'agent_type': self.agent_type,
                        'region': self.region,
                        'status': self.status,
                        'heartbeat': datetime.utcnow(),
                        'metadata': json.dumps({
                            'tools': [t.name for t in self.tools],
                            'system_prompt': self.system_prompt
                        })
                    })
                    conn.commit()
                    print(f"✅ Agent {self.agent_type} ({self.agent_id}) registered in {self.region}")
            
            engine.dispose()
        except Exception as e:
            print(f"⚠️  Could not register agent: {e}")
            # Non-fatal - agent can still work without registration
    
    def update_status(self, status: str, task: Optional[Dict] = None):
        """Update agent status in database"""
        self.status = status
        self.current_task = task
        
        if not self.database_url:
            return
        
        from sqlalchemy import create_engine
        from sqlalchemy.pool import NullPool
        
        try:
            engine = create_engine(
                self.database_url,
                poolclass=NullPool
            )
            
            with engine.connect() as conn:
                conn.execute(text("""
                    UPDATE agent_state
                    SET status = :status,
                        current_task = :task,
                        last_heartbeat = :heartbeat
                    WHERE agent_id = :agent_id
                """), {
                    'agent_id': self.agent_id,
                    'status': status,
                    'task': json.dumps(task, default=json_serializer) if task else None,
                    'heartbeat': datetime.utcnow()
                })
                conn.commit()
            
            engine.dispose()
        except Exception as e:
            print(f"⚠️  Could not update status: {e}")
    
    def store_decision(
        self,
        decision_type: str,
        context: Dict[str, Any],
        reasoning: str,
        action: Dict[str, Any],
        confidence: float
    ) -> AgentDecision:
        """
        Store an agent decision for audit and learning.
        
        Args:
            decision_type: Type of decision (e.g., 'fraud_flag', 'budget_alert')
            context: Input data that led to decision
            reasoning: Agent's thought process
            action: What action was taken
            confidence: Confidence score (0.0 to 1.0)
        
        Returns:
            AgentDecision object
        """
        decision = AgentDecision(
            decision_id=str(uuid.uuid4()),
            decision_type=decision_type,
            context=context,
            reasoning=reasoning,
            action=action,
            confidence=confidence,
            created_at=datetime.utcnow()
        )
        
        if not self.database_url:
            return decision
        
        from sqlalchemy import create_engine
        from sqlalchemy.pool import NullPool
        
        try:
            engine = create_engine(
                self.database_url,
                poolclass=NullPool
            )
            
            with engine.connect() as conn:
                # Check if table exists
                result = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'agent_decisions'
                    )
                """))
                
                if result.scalar():
                    conn.execute(text("""
                        INSERT INTO agent_decisions
                        (decision_id, agent_id, decision_type, context, reasoning, 
                         action, confidence, created_at)
                        VALUES (:decision_id, :agent_id, :decision_type, :context, 
                                :reasoning, :action, :confidence, :created_at)
                    """), {
                        'decision_id': decision.decision_id,
                        'agent_id': self.agent_id,
                        'decision_type': decision_type,
                        'context': json.dumps(context),
                        'reasoning': reasoning,
                        'action': json.dumps(action),
                        'confidence': confidence,
                        'created_at': decision.created_at
                    })
                    conn.commit()
            
            engine.dispose()
        except Exception as e:
            print(f"⚠️  Could not store decision: {e}")
        
        return decision
    
    def think(self, user_input: str, context: Optional[Dict] = None) -> str:
        """
        Agent's thinking process using the LLM.
        
        Args:
            user_input: User's message or task
            context: Additional context (e.g., retrieved memories, data)
        
        Returns:
            Agent's response
        """
        self.update_status("thinking", {"input": user_input})
        
        # Build messages
        messages = [SystemMessage(content=self.system_prompt)]
        
        # Add conversation history
        for msg in self.conversation_history[-5:]:  # Last 5 messages
            messages.append(msg)
        
        # Add current input with context
        user_message = user_input
        if context:
            user_message += f"\n\nContext: {json.dumps(context, indent=2)}"
        
        messages.append(HumanMessage(content=user_message))
        
        # Get LLM response
        try:
            response = self.llm.invoke(messages)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Update conversation history
            self.conversation_history.append(HumanMessage(content=user_input))
            self.conversation_history.append(AIMessage(content=response_text))
            
            self.update_status("idle")
            return response_text
        
        except Exception as e:
            self.update_status("idle")
            return f"Error in thinking: {str(e)}"
    
    def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Execute a tool by name.
        
        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool arguments
        
        Returns:
            Tool execution result
        """
        self.update_status("acting", {"tool": tool_name, "args": kwargs})
        
        tool = next((t for t in self.tools if t.name == tool_name), None)
        if not tool:
            self.update_status("idle")
            raise ValueError(f"Tool '{tool_name}' not found")
        
        try:
            result = tool.func(**kwargs)
            self.update_status("idle")
            return result
        except Exception as e:
            self.update_status("idle")
            raise RuntimeError(f"Tool execution failed: {str(e)}")
    
    def get_info(self) -> Dict[str, Any]:
        """Get agent information"""
        return {
            'agent_id': self.agent_id,
            'agent_type': self.agent_type,
            'region': self.region,
            'status': self.status,
            'current_task': self.current_task,
            'tools': [t.name for t in self.tools],
            'conversation_length': len(self.conversation_history)
        }
    
    def __repr__(self) -> str:
        return f"<{self.agent_type.title()}Agent id={self.agent_id[:8]}... region={self.region} status={self.status}>"
