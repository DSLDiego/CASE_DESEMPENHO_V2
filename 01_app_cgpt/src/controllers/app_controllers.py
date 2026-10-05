"""Controllers MVC: View nao tem regra de negocio nem SQL."""
from __future__ import annotations
import threading
from src.etl.batch import CancelToken
from src.services.app_services import BatchETLService, CollectionService, DashboardService


class DashboardController:
    def __init__(self) -> None:
        self.service = DashboardService()

    def periods(self) -> list[str]:
        return self.service.periods()

    def executive(self, period: str) -> dict:
        return self.service.executive_view(period)

    def history(self, indicator: str) -> dict:
        return self.service.history(indicator)

    def productivity(self, period: str) -> dict:
        return self.service.productivity(period)


class ETLJobManager:
    """Gerencia job batch em background com progresso e cancelamento."""

    def __init__(self) -> None:
        self.service = BatchETLService()
        self.collection = CollectionService()
        self.cancel = CancelToken()
        self._thread: threading.Thread | None = None
        self.result: dict | None = None

    def run_async(self, files, mode="PROCESS", batch_size=10, scheduler="FIFO",
                  max_workers=8, on_progress=None, on_done=None) -> threading.Thread:
        self.cancel = CancelToken()
        self.result = None

        def work():
            def prog(res, done, total):
                if on_progress:
                    on_progress(res, done, total)
            self.result = self.service.run(files, mode, batch_size, scheduler,
                                           max_workers, prog, self.cancel)
            if on_done:
                on_done(self.result)

        self._thread = threading.Thread(target=work, daemon=True)
        self._thread.start()
        return self._thread

    def cancel_job(self) -> None:
        self.cancel.cancel()
