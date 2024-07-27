import os
from typing import Optional
import sys
import os.path as path


class Logger3:
    _FALLBACK = {
        'actions': sys.stdout,
        'progress': sys.stdout,
        'errors': sys.stderr
    }

    """
    give 3 differents output :
        - actions: what have been copied
        - progress: progress and removed after
        - errors: errors or remove if empty
    """
    def __init__(
            self,
            actions_filepath: Optional[str],
            progress_filepath: Optional[str],
            errors_filepath: Optional[str]
    ):
        # channel -> filepath
        self._log_filepath = {
            'actions': actions_filepath,
            'progress': progress_filepath,
            'errors': errors_filepath
        }
        # remove nones
        self._log_filepath = {k: v for k, v in self._log_filepath.items() if v is not None}

        if len(self._log_filepath.values()) != len(set(self._log_filepath.values())):
            raise ValueError(f'log files should all be uniques : {self._log_filepath.values()}')

        # filepath -> file
        self._log_files = {k: None for k in self._log_filepath.values()}

    def __enter__(self):
        for filepath in self._log_files.keys():
            os.makedirs(path.dirname(filepath), exist_ok=True)
            self._log_files[filepath] = open(filepath, 'a')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for filepath, logfile in self._log_files.items():
            self._log_files[filepath].close()
            self._log_files[filepath] = None
        # remove progress file
        progress_filepath = self._log_filepath.get('progress')
        if progress_filepath is not None:
            os.remove(progress_filepath)
        # remove errors file if empty
        errors_filepath = self._log_filepath.get('errors')
        if errors_filepath is not None and os.stat(errors_filepath).st_size == 0:
            os.remove(errors_filepath)
        return True

    def filepath(self, channel: str) -> Optional[str]:
        return self._log_filepath.get(channel)

    def file(self, channel: str):
        filepath = self.filepath(channel)
        if filepath is None:
            return self._FALLBACK[channel]
        assert self._log_files.get(filepath) is not None
        return self._log_files[filepath]

    @property
    def actions(self):
        return self.file('actions')

    @property
    def progress(self):
        return self.file('progress')

    @property
    def errors(self):
        return self.file('errors')
