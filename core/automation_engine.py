import logging
from . import workflow_rules
from . import db

logger = logging.getLogger("redboar")

class JobProposal:
    def __init__(self, tool_name, label, reason, params):
        self.tool_name = tool_name
        self.label = label
        self.reason = reason
        self.params = params

def propose_scans(project_id, host_id=None):
    """
    Analyzes the 'services' for the given host(s) in the project
    and returns a list of JobProposal objects.
    """
    proposals = []
    
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        query = "SELECT s.id, s.host_id, s.port, s.service_name, h.ip_address FROM services s JOIN hosts h ON s.host_id = h.id WHERE h.project_id = ? AND s.state = 'open'"
        params = [project_id]
        
        if host_id:
            query += " AND s.host_id = ?"
            params.append(host_id)
            
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        
        for row in rows:
            port = row['port']
            service = (row['service_name'] or "").lower()
            ip = row['ip_address']
            
            # Check against rules
            for rule in workflow_rules.RULES:
                # Match port OR service
                match_port = (rule.get("port") == port)
                match_service = (service in rule.get("service_names", []))
                
                if match_port or match_service:
                    for tool_def in rule.get("tools", []):
                        # Format params
                        final_params = {}
                        for k, v in tool_def.get("params", {}).items():
                            if isinstance(v, str):
                                final_params[k] = v.format(ip=ip, port=port)
                            else:
                                final_params[k] = v
                        
                        prop = JobProposal(
                            tool_name=tool_def["tool_name"],
                            label=f"{tool_def['label']} ({ip}:{port})",
                            reason=tool_def["reason"],
                            params=final_params
                        )
                        proposals.append(prop)

    except Exception as e:
        logger.error(f"Error in automation engine: {e}")
    finally:
        conn.close()
        
    return proposals
