import time
from contextlib import contextmanager
from pipeline.core.utils import active_usage_log

class UsageTracker:
    def __init__(self):
        self.start_tokens = 0
        self.start_cost = 0.0
        self.logs_before = []

    @contextmanager
    def track(self):
        # 시작 전 로그 저장
        self.logs_before = active_usage_log.get().copy()
        start_time = time.time()
        
        yield
        
        # 종료 후 새로 추가된 로그만 필터링
        all_logs = active_usage_log.get()
        new_logs = all_logs[len(self.logs_before):]
        
        self.total_input = sum(log.get("input", 0) for log in new_logs)
        self.total_output = sum(log.get("output", 0) for log in new_logs)
        self.total_tokens = self.total_input + self.total_output
        self.total_cost = sum(log.get("cost", 0.0) for log in new_logs)
        self.duration = time.time() - start_time

    def get_summary(self):
        return {
            "input_tokens": self.total_input,
            "output_tokens": self.total_output,
            "total_tokens": self.total_tokens,
            "cost_usd": self.total_cost,
            "duration_sec": self.duration
        }

    def print_summary(self, label=""):
        print(f"\n[USAGE REPORT: {label}]")
        print(f" - Input Tokens:  {self.total_input:,}")
        print(f" - Output Tokens: {self.total_output:,}")
        print(f" - Total Tokens:  {self.total_tokens:,}")
        print(f" - Total Cost:    ${self.total_cost:.6f}")
        print(f" - Duration:      {self.duration:.2f}s")
