import os
from typing import Optional

# Try to import MCP dependencies, but handle gracefully if not available
try:
    from langchain_google_alloydb_pg import AlloyDBEngine
    ALLOYDB_AVAILABLE = True
except ImportError:
    AlloyDBEngine = None
    ALLOYDB_AVAILABLE = False

try:
    from langchain_google_cloud_sql_pg import CloudSQLEngine
    CLOUDSQL_AVAILABLE = True
except ImportError:
    CloudSQLEngine = None
    CLOUDSQL_AVAILABLE = False

def get_mcp_db_engine() -> Optional[object]:
    """
    Initializes and returns the MCP database engine (AlloyDB or CloudSQL) based on environment variables.
    Returns None if configuration is missing or invalid.
    """
    db_type = os.getenv("MCP_DB_TYPE", "alloydb").lower()  # 'alloydb' or 'cloudsql'
    
    if db_type == "alloydb":
        if not ALLOYDB_AVAILABLE:
            print("[MCP Config] AlloyDB dependencies not available. Install with: pip install langchain-google-alloydb-pg")
            return None
            
        # Required env vars: ALLOYDB_HOST, ALLOYDB_PORT, ALLOYDB_USER, ALLOYDB_PASSWORD, ALLOYDB_DATABASE
        host = os.getenv("ALLOYDB_HOST")
        port = os.getenv("ALLOYDB_PORT")
        user = os.getenv("ALLOYDB_USER")
        password = os.getenv("ALLOYDB_PASSWORD")
        database = os.getenv("ALLOYDB_DATABASE")
        
        if all([host, port, user, password, database]):
            try:
                return AlloyDBEngine(
                    host=host,
                    port=int(port),
                    user=user,
                    password=password,
                    database=database
                )
            except Exception as e:
                print(f"[MCP Config] Error initializing AlloyDB engine: {e}")
                return None
        else:
            print("[MCP Config] Missing AlloyDB environment variables.")
            return None
            
    elif db_type == "cloudsql":
        if not CLOUDSQL_AVAILABLE:
            print("[MCP Config] CloudSQL dependencies not available. Install with: pip install langchain-google-cloud-sql-pg")
            return None
            
        # Required env vars: CLOUDSQL_HOST, CLOUDSQL_PORT, CLOUDSQL_USER, CLOUDSQL_PASSWORD, CLOUDSQL_DATABASE
        host = os.getenv("CLOUDSQL_HOST")
        port = os.getenv("CLOUDSQL_PORT")
        user = os.getenv("CLOUDSQL_USER")
        password = os.getenv("CLOUDSQL_PASSWORD")
        database = os.getenv("CLOUDSQL_DATABASE")
        
        if all([host, port, user, password, database]):
            try:
                return CloudSQLEngine(
                    host=host,
                    port=int(port),
                    user=user,
                    password=password,
                    database=database
                )
            except Exception as e:
                print(f"[MCP Config] Error initializing CloudSQL engine: {e}")
                return None
        else:
            print("[MCP Config] Missing CloudSQL environment variables.")
            return None
    else:
        print(f"[MCP Config] Unknown or unsupported MCP_DB_TYPE: {db_type}")
        return None

def is_mcp_available() -> bool:
    """
    Returns True if MCP database engine can be initialized, False otherwise.
    """
    return get_mcp_db_engine() is not None
