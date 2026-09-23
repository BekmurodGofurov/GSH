import pytest

import main


@pytest.fixture(autouse=True)
def clean_baselines():
    """The service keeps per-server baselines in a module-level dict.

    Without clearing it between tests, whichever test ran first would seed the
    baseline for the next one and the assertions would depend on test order.
    """
    main.histories.clear()
    yield
    main.histories.clear()
