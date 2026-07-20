# VCI Automation Tests

Welcome to the test suite! Please follow this structure to keep our automation repo organized and test-able:

tests/
├── data/           # Input data for testcases during pipeline tests (calibration files, detection files etc). 
|                   # This input data is and should be commited in git!
|
├── util_for_test/  # Shared helpers for tests (custom asserts, mock generators).
|
├── local/          # Local core logic (e.g. caemra calibration). **Fast & NO SERVER CONNECTIONS ALLOWED.**
|                   # Use Mocked API respones and input data from tests/data for test cases.
|                   # Run these tests before a commit: `pytest tests/local`
|
├── playground/     # Experiments & temporary scripts. Not maintained. **Random stuff goes here**
|
├── end_to_end/     # Tests the full stack: vci-automation -> vci-capture -> Hardware.**Requires running servers + cameras.**
                    # Includes:
                    # - Real API connectivity checks.
                    # - Real-camera capture validation.
                    # - Long-term stability & stress tests.
                    
Tests should be written with the **pytest** library.

If you want to temporarilty **save some images or data** to look at or debug, please put it in **vci-capture/data**.
If the data folder doesn't exist yet you can create one. Content in that folder is temporary and not commited to git.
Do NOT put your random stuff into tests/data!!!

### Quick Start
# Run local software tests
python -m pytest tests/local

# Run end_to_end tests
python -m pytest tests/end_to_end