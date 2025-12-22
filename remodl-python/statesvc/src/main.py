from temporal_boost import BoostApp

app = BoostApp(
    name="statesvc",              # Application name (optional)
    temporal_endpoint=None,          # Override TEMPORAL_TARGET_HOST (optional)
    temporal_namespace=None,         # Override TEMPORAL_NAMESPACE (optional)
    debug_mode=False,                # Enable debug mode (optional)
    use_pydantic=None,               # Override Pydantic converter (optional)
    logger_config=None,              # Custom logging config (optional)
)