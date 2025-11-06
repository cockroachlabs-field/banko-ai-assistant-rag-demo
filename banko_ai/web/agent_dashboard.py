"""
Agent Dashboard - Real-time visualization of agent activity.

Provides WebSocket-based updates for:
- Agent status (thinking, acting, idle)
- Current tasks
- Workflow execution
- Decision making
"""

from flask import Blueprint, render_template, jsonify
from flask_socketio import emit
from datetime import datetime
from sqlalchemy import text

agent_dashboard = Blueprint('agent_dashboard', __name__)


@agent_dashboard.route('/agents')
def dashboard():
    """Render agent dashboard page"""
    return render_template('agent_dashboard.html')


@agent_dashboard.route('/api/agents/status')
def get_all_agent_status():
    """Get status of all registered agents"""
    from ..config.settings import get_config
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool
    
    config = get_config()
    engine = create_engine(config.database_url, poolclass=NullPool)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    agent_id,
                    agent_type,
                    region,
                    status,
                    current_task,
                    last_heartbeat,
                    created_at
                FROM agent_state
                ORDER BY agent_type, region, created_at DESC
            """))
            
            agents = []
            for row in result.fetchall():
                agents.append({
                    'agent_id': str(row[0]),
                    'type': row[1],
                    'region': row[2],
                    'status': row[3],
                    'current_task': row[4],
                    'last_heartbeat': row[5].isoformat() if row[5] else None,
                    'created_at': row[6].isoformat() if row[6] else None
                })
        
        engine.dispose()
        
        return jsonify({
            'success': True,
            'agents': agents,
            'count': len(agents)
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@agent_dashboard.route('/api/agents/activity')
def get_recent_activity():
    """Get recent agent decisions and activity"""
    from ..config.settings import get_config
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool
    
    config = get_config()
    engine = create_engine(config.database_url, poolclass=NullPool)
    
    try:
        with engine.connect() as conn:
            # Get recent decisions
            result = conn.execute(text("""
                SELECT 
                    d.decision_id,
                    d.agent_id,
                    a.agent_type,
                    a.region,
                    d.decision_type,
                    d.confidence,
                    d.created_at,
                    d.reasoning
                FROM agent_decisions d
                JOIN agent_state a ON d.agent_id = a.agent_id
                ORDER BY d.created_at DESC
                LIMIT 50
            """))
            
            activities = []
            for row in result.fetchall():
                activities.append({
                    'decision_id': str(row[0]),
                    'agent_id': str(row[1]),
                    'agent_type': row[2],
                    'region': row[3],
                    'decision_type': row[4],
                    'confidence': float(row[5]) if row[5] else 0,
                    'created_at': row[6].isoformat() if row[6] else None,
                    'reasoning': row[7][:200] if row[7] else None  # First 200 chars
                })
        
        engine.dispose()
        
        return jsonify({
            'success': True,
            'activities': activities,
            'count': len(activities)
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# WebSocket event handlers
def emit_agent_status_update(agent_id, status, task=None):
    """Emit agent status update via WebSocket"""
    try:
        from flask_socketio import SocketIO
        socketio = SocketIO.instance()
        if socketio:
            socketio.emit('agent_status_update', {
                'agent_id': str(agent_id),
                'status': status,
                'task': task,
                'timestamp': datetime.utcnow().isoformat()
            })
    except Exception as e:
        print(f"⚠️  Could not emit agent status: {e}")


def emit_agent_decision(agent_id, decision_type, confidence, reasoning):
    """Emit agent decision via WebSocket"""
    try:
        from flask_socketio import SocketIO
        socketio = SocketIO.instance()
        if socketio:
            socketio.emit('agent_decision', {
                'agent_id': str(agent_id),
                'decision_type': decision_type,
                'confidence': confidence,
                'reasoning': reasoning[:200] if reasoning else None,
                'timestamp': datetime.utcnow().isoformat()
            })
    except Exception as e:
        print(f"⚠️  Could not emit agent decision: {e}")


def emit_workflow_update(workflow_id, step, status, result=None):
    """Emit workflow execution update via WebSocket"""
    try:
        from flask_socketio import SocketIO
        socketio = SocketIO.instance()
        if socketio:
            socketio.emit('workflow_update', {
                'workflow_id': workflow_id,
                'step': step,
                'status': status,
                'result': result,
                'timestamp': datetime.utcnow().isoformat()
            })
    except Exception as e:
        print(f"⚠️  Could not emit workflow update: {e}")
