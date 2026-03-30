class TelecomAIException(Exception):
    """Base exception for telecom AI platform"""
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "TELECOM_AI_ERROR"
        self.details = details or {}


class ModelNotTrainedException(TelecomAIException):
    """Raised when ML model is called before training"""
    def __init__(self, message: str = "Model not trained"):
        super().__init__(message, "MODEL_NOT_TRAINED", {"action": "train_model_first"})


class InvalidKPIException(TelecomAIException):
    """Raised when KPI data is invalid"""
    def __init__(self, message: str, invalid_fields: list = None):
        super().__init__(message, "INVALID_KPI_DATA", {"fields": invalid_fields})


class SimulationException(TelecomAIException):
    """Raised during KPI simulation errors"""
    def __init__(self, message: str, gnb_id: str = None):
        super().__init__(message, "SIMULATION_ERROR", {"gNB": gnb_id})
        
# Add to existing exceptions.py
class NWDAFException(TelecomAIException):
    """Base for NWDAF analytics errors"""
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message, error_code or "NWDAF_ERROR", details)


class SubscriptionNotFoundException(NWDAFException):
    """Invalid subscription ID"""
    def __init__(self, subscription_id: str):
        super().__init__(
            f"Subscription {subscription_id} not found",
            "SUBSCRIPTION_NOT_FOUND",
            {"subscription_id": subscription_id}
        )


class AnalyticsNotSupportedException(NWDAFException):
    """Requested analytics type not available"""
    def __init__(self, analytics_type: str):
        super().__init__(
            f"Analytics type {analytics_type} not supported",
            "ANALYTICS_NOT_SUPPORTED",
            {"supported_types": ["LOAD_LEVEL", "SERVICE_EXPERIENCE", "NF_LOAD"]}
        )


class TimeSeriesException(TelecomAIException):
    """Time-series data processing error"""
    def __init__(self, message: str, operation: str = None):
        super().__init__(
            message,
            "TIME_SERIES_ERROR",
            {"operation": operation}
        )
# =================================
class TelecomAIException(Exception):
    """Base exception for telecom AI platform"""
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "TELECOM_AI_ERROR"
        self.details = details or {}


class ModelNotTrainedException(TelecomAIException):
    """Raised when ML model is called before training"""
    def __init__(self, message: str = "Model not trained"):
        super().__init__(message, "MODEL_NOT_TRAINED", {"action": "train_model_first"})


class InvalidKPIException(TelecomAIException):
    """Raised when KPI data is invalid"""
    def __init__(self, message: str, invalid_fields: list = None):
        super().__init__(message, "INVALID_KPI_DATA", {"fields": invalid_fields})


class SimulationException(TelecomAIException):
    """Raised during KPI simulation errors"""
    def __init__(self, message: str, gnb_id: str = None):
        super().__init__(message, "SIMULATION_ERROR", {"gNB": gnb_id})
        
# Add to existing exceptions.py

class ORANException(TelecomAIException):
    """Base for O-RAN xApp errors"""
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message, error_code or "ORAN_ERROR", details)


class E2InterfaceException(ORANException):
    """E2AP/E2SM communication failure"""
    def __init__(self, message: str, gnb_id: str = None):
        super().__init__(
            message,
            "E2_INTERFACE_ERROR",
            {"gNB": gnb_id, "interface": "E2"}
        )


class ControlLoopException(ORANException):
    """Real-time control loop failure"""
    def __init__(self, message: str, xapp_id: str = None):
        super().__init__(
            message,
            "CONTROL_LOOP_ERROR",
            {"xapp_id": xapp_id}
        )


class PolicyViolationException(ORANException):
    """Control action violates policy"""
    def __init__(self, message: str, policy: str = None, action: str = None):
        super().__init__(
            message,
            "POLICY_VIOLATION",
            {"policy": policy, "attempted_action": action}
        )