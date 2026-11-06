"""Qt process orchestration; cancelled jobs never reach the result store."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal
from .model import ModelRecord, ResultStore, job_fields


class JobRunner(QObject):
    progress = Signal(dict)
    changed = Signal(object)
    completed = Signal(int, int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.busy = False
        self.cancelled = False
        self.current = None
        self.total = self.successes = self.failures = 0
        self._queue = []
        self._temp = None

    def start(self, records: list[ModelRecord], store: ResultStore, policy: str, device: str, *, engine=None, batch=False):
        if self.busy:
            return
        requests = []
        for record in records:
            try:
                request = job_fields(record, policy=policy, device=device, engine=engine)
            except ValueError as exc:
                if not batch:
                    raise
                request = exc
            requests.append((record, request))
        if not requests:
            return
        self.store = store
        self._queue = requests
        self.total = len(requests)
        self.successes = self.failures = 0
        self.cancelled = False
        self.busy = True
        self._next()

    def _next(self):
        if self.cancelled or not self._queue:
            self.busy = False
            self.current = None
            self.completed.emit(self.successes, self.failures, self.cancelled)
            return
        record, request = self._queue.pop(0)
        self.current = record
        if isinstance(request, ValueError):
            record.error = str(request)
            record.error_kind = 'parameters'
            self.failures += 1
            self.changed.emit(record)
            QTimer.singleShot(0, self._next)
            return
        record.running = True
        self.changed.emit(record)
        try:
            self._temp = tempfile.TemporaryDirectory(prefix='kasal-studio-')
            self.staging = Path(self._temp.name)
            request_path = self.staging / 'request.json'
            request_path.write_text(json.dumps(request), encoding='utf-8')
        except OSError as exc:
            record.running = False
            record.error = str(exc)
            record.error_kind = 'analysis'
            self.failures += 1
            self.changed.emit(record)
            if self._temp is not None:
                self._temp.cleanup()
                self._temp = None
            QTimer.singleShot(0, self._next)
            return
        self._stdout = ''
        self._stderr = ''
        self._error = ''
        self._done = False
        self._settled = False
        self._elapsed = None
        proc = QProcess(self)
        self.process = proc
        env = QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONUTF8', '1')
        env.insert('PYTHONDONTWRITEBYTECODE', '1')
        proc.setProcessEnvironment(env)
        proc.setWorkingDirectory(str(Path(__file__).resolve().parents[2]))
        proc.readyReadStandardOutput.connect(self._read_stdout)
        proc.readyReadStandardError.connect(self._read_stderr)
        proc.finished.connect(self._finished)
        proc.errorOccurred.connect(self._process_error)
        self.progress.emit({'key': 'init', 'fraction': 0., 'mesh_name': record.path.name,
                            'index': self.successes + self.failures + 1, 'total': self.total})
        proc.start(sys.executable, ['-B', '-u', '-m', 'kasal.studio.worker', str(request_path), str(self.staging / 'result')])

    def _read_stdout(self):
        self._stdout += bytes(self.process.readAllStandardOutput()).decode('utf-8', errors='replace')
        while '\n' in self._stdout:
            line, self._stdout = self._stdout.split('\n', 1)
            if not line.startswith('@STUDIO '):
                continue
            try:
                message = json.loads(line[8:])
            except ValueError:
                continue
            if message['kind'] == 'progress':
                self.progress.emit({**message, 'index': self.successes + self.failures + 1, 'total': self.total})
            elif message['kind'] == 'error':
                self._error = message['message']
            elif message['kind'] == 'done':
                self._done = True
                self._elapsed = message['elapsed']

    def _read_stderr(self):
        self._stderr = (self._stderr + bytes(self.process.readAllStandardError()).decode('utf-8', errors='replace'))[-12000:]

    def _process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self._error = self.process.errorString()
            self._finished(-1, QProcess.ExitStatus.CrashExit)

    def _finished(self, code, exit_status):
        if self._settled:
            return
        self._settled = True
        self._read_stdout()
        self._read_stderr()
        record = self.current
        record.running = False
        if not self.cancelled:
            try:
                if code != 0 or not self._done:
                    raise RuntimeError(self._error or self._stderr.strip() or 'The analysis process exited unexpectedly.')
                self.store.commit(record, self.staging / 'result')
                record.elapsed = self._elapsed
                self.successes += 1
            except Exception as exc:
                record.error = str(exc)
                record.error_kind = 'analysis'
                self.failures += 1
        self.changed.emit(record)
        self.process.deleteLater()
        self.process = None
        self._temp.cleanup()
        self._temp = None
        QTimer.singleShot(0, self._next)

    def cancel(self):
        self.cancelled = True
        self._queue.clear()
        if self.process is not None:
            self.process.kill()
