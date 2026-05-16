"""
Carga de parámetros de estrategia desde la base de datos.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def load_strategy_parameters(db, strategy_id: str) -> Dict[str, Any]:
    """
    Carga todos los parámetros de una estrategia desde strategy_parameters.
    
    Returns:
        Dict con param_key -> valor convertido al tipo correcto
    """
    cursor = db.conn.cursor()
    cursor.execute(
        """SELECT param_key, param_value, data_type 
           FROM strategy_parameters 
           WHERE strategy_id = %s""",
        (strategy_id,)
    )
    rows = cursor.fetchall()
    
    params = {}
    for row in rows:
        key, value_str, data_type = row
        params[key] = _convert_value(value_str, data_type)
    
    logger.info("Cargados %d parámetros para estrategia %s", len(params), strategy_id)
    return params


def _convert_value(value_str: str, data_type: str) -> Any:
    """Convierte el valor string al tipo de dato correcto."""
    if value_str is None:
        return None
    
    try:
        if data_type == "int":
            return int(value_str)
        elif data_type == "float":
            return float(value_str)
        elif data_type == "bool":
            return value_str.lower() in ("true", "1", "yes")
        elif data_type == "list":
            # Formato: "AAPL,MSFT,GOOGL"
            return [s.strip() for s in value_str.split(",") if s.strip()]
        else:  # str
            return value_str
    except Exception as e:
        logger.warning("Error convirtiendo parámetro %s=%s (%s): %s", 
                      data_type, value_str, data_type, e)
        return value_str


def apply_parameters_to_config(config_obj, params: Dict[str, Any], prefix: str = ""):
    """
    Aplica parámetros del dict a un objeto de configuración.
    
    Args:
        config_obj: Objeto dataclass de configuración
        params: Dict con parámetros cargados de la DB
        prefix: Prefijo para las keys (ej: "market_regime.")
    """
    for field_name in dir(config_obj):
        if field_name.startswith("_"):
            continue
        
        param_key = f"{prefix}{field_name}" if prefix else field_name
        
        if param_key in params:
            try:
                setattr(config_obj, field_name, params[param_key])
                logger.debug("Aplicado parámetro %s = %s", param_key, params[param_key])
            except Exception as e:
                logger.warning("Error aplicando parámetro %s: %s", param_key, e)
