# VCI Capture Tests

Welcome to the test suite! Please follow this structure to keep our capture setup stable:

tests/
├── data/           # Input data for testcases during pipeline tests (calibration files and images). 
|                   # This input data is and should be commited in git!
|
├── util_for_test/  # Shared helpers for tests (custom asserts, mock generators).
|
├── pipeline/       # Pipeline logic. **Fast & NO HARDWARE ALLOWED.**
|                   # Use input data from tests/data for test cases.
|                   # Use simulated cameras from gibbs/cameras/simulated
|                   # Run these tests before a commit: `pytest tests/pipeline`
├── integration/    # API and End to End tests. With or without hardware.
|                   # @pytest.mark.hardware
|
├── playground/     # Experiments & temporary scripts. Not maintained. **Random stuff goes here**
|
├── hardware/       # Real-camera validation specific for manufacturer (Orbbec/Ximea).
│   ├── orbbec/     # Requires Orbbec SDK + Cameras.
│   └── ximea/      # Requires Ximea SDK + Cameras.
|
└── stress/         # Long-term stability/benchmarks that test the whole pipeline. 
                    # **Slow & Hardware dependent.**
                    # Run these before a major release or after driver updates.
                    
Tests should be written with the **pytest** library.

If you want to temporarilty **save some images or data** to look at or debug, please put it in **vci-capture/data**.
If the data folder doesn't exist yet you can create one. Content in that folder is temporary and not commited to git.
Do NOT put your random stuff into tests/data!!!

### Quick Start
# Run all software tests
python -m pytest tests/pipeline

# Run hardware-specific tests
python -m pytest tests/hardware/orbbec

# Check which cameras are connected
python scripts/check_cameras.py