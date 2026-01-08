import sys
from typing import Optional
from rich.progress import Progress, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
from rich.console import Console

class ProgressManager:
    _instance = None
    
    def __init__(self):
        self.console = Console(force_terminal=True)
        self.progress: Optional[Progress] = None
        self.current_task_id = None
        self.current_task: str = ""
        
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ProgressManager()
        return cls._instance

    def start_download(self, filename: str, total_size_bytes: int = 0):
        # Close existing progress if any
        if self.progress is not None:
            self.progress.stop()
            self.progress = None
        
        # Truncate filename if too long
        display_name = filename[:22] + "..." if len(filename) > 25 else filename
        self.current_task = display_name
        
        # Create compact progress bar (right side) with shorter bar
        self.progress = Progress(
            TextColumn("         "),  # Left padding to align with log indent
            TextColumn("[bold magenta]{task.description}[/bold magenta]"),
            BarColumn(bar_width=20, style="magenta", complete_style="bright_magenta"),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            transient=True,
        )
        self.progress.start()
        self.current_task_id = self.progress.add_task(
            self.current_task, 
            total=total_size_bytes if total_size_bytes > 0 else None
        )

    def update(self, inc_bytes: int):
        if self.progress is not None and self.current_task_id is not None:
            self.progress.update(self.current_task_id, advance=inc_bytes)
    
    def set_total(self, total_bytes: int):
        if self.progress is not None and self.current_task_id is not None:
            self.progress.update(self.current_task_id, total=total_bytes)

    def finish(self):
        if self.progress is not None:
            self.progress.stop()
            self.progress = None
            self.current_task_id = None

    def message(self, msg: str):
        """Legacy method - now uses logger"""
        from .logger import log_info
        log_info(msg, 'sexify')






