"""Imports every domain's models so that Base.metadata is complete.

Used by alembic/env.py (autogenerate) and the tests.
"""
import app.fees.models  # noqa: F401
import app.members.models  # noqa: F401
import app.membership_types.models  # noqa: F401
import app.payments.models  # noqa: F401
