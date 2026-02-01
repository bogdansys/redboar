import xml.etree.ElementTree as ET
import logging
from . import db

logger = logging.getLogger("redboar")

def parse_nmap_xml(xml_file_path, project_id):
    """
    Parses an Nmap XML file and saves hosts/services to the database.
    
    Args:
        xml_file_path (str): Path to the Nmap XML output.
        project_id (int): ID of the project to associate data with.
    """
    if not project_id:
        logger.warning("No project_id provided to parse_nmap_xml. Skipping DB save.")
        return

    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        hosts_count = 0
        services_count = 0

        for host in root.findall('host'):
            # Only process hosts that are 'up'
            status = host.find('status')
            if status is None or status.get('state') != 'up':
                continue
            
            # --- Extract Host Info ---
            ip_address = None
            hostname = None
            
            # Get IP
            for address in host.findall('address'):
                if address.get('addrtype') == 'ipv4':
                    ip_address = address.get('addr')
                    break
            
            if not ip_address:
                continue

            # Get Hostname
            hostnames = host.find('hostnames')
            if hostnames is not None:
                for hn in hostnames.findall('hostname'):
                    if hn.get('type') == 'user':
                        hostname = hn.get('name')
                        break
                    if not hostname: # fallback
                        hostname = hn.get('name')

            # Get OS (best guess)
            os_name = None
            os_elm = host.find('os')
            if os_elm is not None:
                os_match = os_elm.find('osmatch')
                if os_match is not None:
                    os_name = os_match.get('name')

            # --- Insert/Update Host ---
            cursor.execute(
                '''
                INSERT INTO hosts (project_id, ip_address, hostname, os_name, status)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(project_id, ip_address) DO UPDATE SET
                    hostname=excluded.hostname,
                    os_name=excluded.os_name,
                    status=excluded.status
                ''',
                (project_id, ip_address, hostname, os_name, 'up')
            )
            
            # Get the host_id (need to fetch it since lastrowid might not work on update)
            cursor.execute(
                "SELECT id FROM hosts WHERE project_id=? AND ip_address=?", 
                (project_id, ip_address)
            )
            host_row = cursor.fetchone()
            if not host_row:
                continue
            host_id = host_row['id']
            hosts_count += 1

            # --- Extract Services ---
            ports = host.find('ports')
            if ports is not None:
                for port in ports.findall('port'):
                    state_elm = port.find('state')
                    if state_elm is None or state_elm.get('state') != 'open':
                        continue
                    
                    port_id = int(port.get('portid'))
                    protocol = port.get('protocol')
                    
                    service_elm = port.find('service')
                    service_name = service_elm.get('name') if service_elm is not None else "unknown"
                    product = service_elm.get('product') if service_elm is not None else ""
                    version = service_elm.get('version') if service_elm is not None else ""
                    
                    # --- Insert/Update Service ---
                    cursor.execute(
                        '''
                        INSERT INTO services (host_id, port, protocol, service_name, product, version, state)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(host_id, port, protocol) DO UPDATE SET
                            service_name=excluded.service_name,
                            product=excluded.product,
                            version=excluded.version,
                            state=excluded.state
                        ''',
                        (host_id, port_id, protocol, service_name, product, version, 'open')
                    )
                    services_count += 1

        conn.commit()
        conn.close()
        logger.info(f"Nmap parse complete. Saved {hosts_count} hosts and {services_count} services.")

    except Exception as e:
        logger.error(f"Failed to parse Nmap XML: {e}")
