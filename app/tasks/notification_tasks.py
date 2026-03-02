# Celery notification tasks — full implementation in Task 30
# Stub provided here so payment_service can import send_purchase_confirmation.


class _StubTask:
    """Minimal stub that satisfies .delay() calls before Celery is wired up."""

    def delay(self, *args, **kwargs):
        pass


send_purchase_confirmation = _StubTask()
