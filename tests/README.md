# Unit Tests for Telecom AI Platform

This directory contains comprehensive unit tests for the AI-Driven Telecom Network Optimization Platform.

## Test Files

### `test_anomaly_detector.py`
Tests for the `AnomalyDetector` service in `services/anomaly_detector.py`.

**Coverage:**
- Threshold configuration (default and custom)
- Anomaly detection logic for various KPI anomalies:
  - High PRB usage (>90%)
  - High latency (>50ms)
  - High packet loss (>1%)
  - Throughput drops (>20%)
- Batch detection
- Statistics tracking
- Runtime threshold updates
- History tracking per gNB
- Edge cases and boundary conditions

**Test Count:** 18 tests

### `test_kpi_simulator.py`
Tests for the `TelecomKPISimulator` service in `services/kpi_simulator.py`.

**Coverage:**
- Simulator initialization
- Correlation matrix validation (positive definiteness)
- Time-based traffic patterns:
  - Peak hours detection
  - Off-peak reduction
  - Weekend traffic patterns
- Base metrics generation
- Anomaly injection mechanisms:
  - Congestion
  - RF interference
  - Transport issues
  - Hardware degradation
- Training data generation
- Single KPI generation
- Statistics calculation
- Edge cases

**Test Count:** 32 tests

## Running Tests

### Run All Tests
```bash
cd /workspace
python -m pytest tests/ -v
```

### Run Specific Test File
```bash
# Anomaly detector tests
python -m pytest tests/test_anomaly_detector.py -v

# KPI simulator tests
python -m pytest tests/test_kpi_simulator.py -v
```

### Run Specific Test Class
```bash
python -m pytest tests/test_anomaly_detector.py::TestAnomalyDetector -v
```

### Run with Coverage
```bash
pip install pytest-cov
python -m pytest tests/ --cov=services --cov-report=html
```

## Dependencies

Tests require the following packages (already in `requirements.txt`):
- `pytest>=7.4.3`
- `numpy`
- `pandas`
- `pydantic`
- `scikit-learn`

Install test dependencies:
```bash
pip install -r requirements.txt
```

## Test Structure

Tests follow the AAA pattern (Arrange-Act-Assert) and are organized into logical classes:

```python
class TestFeatureGroup:
    @pytest.fixture
    def resource(self):
        # Setup test resources
        pass
    
    def test_specific_behavior(self, resource):
        # Arrange
        input_data = ...
        
        # Act
        result = service.method(input_data)
        
        # Assert
        assert result == expected
```

## Continuous Integration

Add to your CI pipeline:
```yaml
test:
  script:
    - pip install -r requirements.txt
    - python -m pytest tests/ -v --tb=short
```

## Adding New Tests

When adding new features, ensure you:
1. Create corresponding test classes/methods
2. Test both happy paths and edge cases
3. Use descriptive test names that explain the behavior
4. Keep tests independent and idempotent
5. Mock external dependencies (APIs, databases, etc.)

Example:
```python
def test_new_feature_with_valid_input(self, service):
    """Test new feature processes valid input correctly"""
    input_data = {...}
    result = service.new_feature(input_data)
    assert result.is_valid
    assert result.processed_at is not None
```

## Known Limitations

1. **Reproducibility**: Due to Python's shared global random state, creating two simulator instances with the same seed may not produce identical results. Tests account for this by verifying statistical properties rather than exact values.

2. **Time-dependent tests**: Some tests use `datetime.now()` which may cause occasional failures around midnight. Consider using freezegun for time-sensitive tests in production CI.

## Contact

For questions or issues with tests, refer to the main project documentation.
