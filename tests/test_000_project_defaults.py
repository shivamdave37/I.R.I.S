"""Set stable application defaults before the test modules are imported."""

import config


# The human may keep Iris enabled locally, but direct-mode tests need this baseline.
config.USE_IRIS = False
