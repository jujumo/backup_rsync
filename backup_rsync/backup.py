#!/usr/bin/env python3
# import os.path as path
from jsonargparse import CLI
from jsonargparse.typing import path_type
from typing import Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from subprocess import Popen
from backup_rsync.logger import Logger3
from pathlib import PurePosixPath


Path_d = path_type("d", docstring="path to a directory", skip_check=True)
Path_f = path_type("f", docstring="path to a file", skip_check=True)


@dataclass
class Startpoint:
    path: Path_f
    remote: bool = False


@dataclass
class Endpoint:
    path: Path_f
    remote: bool = False
    history: Optional[Path_f] = None
    partial: Optional[Path_f] = None


@dataclass
class Server:
    url: str
    sshpath: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    keyfile: Optional[Path_f] = None
    rsyncpath: Optional[str] = None
    timeout: Optional[int] = None


@dataclass
class Logging:
    actions: Optional[Path_f] = None
    progress: Optional[Path_f] = None
    errors: Optional[Path_f] = None


@dataclass
class Backup:
    source: Startpoint
    destination: Endpoint
    dryrun: bool = False
    logging: Logging = field(default_factory=lambda: Logging())
    server: Optional[Server] = None
    exclude: Optional[str | List[str]] = None
    rsync_local_path: str = 'rsync'

    def _format_path(self, node_path: Optional[Path_f | str], is_dir: bool) -> Optional[str]:
        if node_path is None:
            return
        # transform date template
        # assert isinstance(node_path, Path_f)
        assert isinstance(self._timestamp, datetime)
        if isinstance(node_path, Path_f):
            is_absolute = node_path.relative == node_path.absolute
            cwd = node_path.cwd
            node_path = node_path.relative
            if not is_absolute:
                node_path = cwd + '/' + node_path

        node_path = self._timestamp.strftime(node_path)
        # force tailing slash for directories
        if is_dir and not node_path.endswith('/'):
            node_path += '/'
        return node_path

    def __post_init__(self):
        """ check config validity """
        self._timestamp = datetime.now()  # make a common timestamp for the all lifetime

        # reformat exclude
        if self.exclude is None:
            self.exclude = []
        if isinstance(self.exclude, str):
            self.exclude = [self.exclude]

        # check remote consistency
        if self.source.remote and self.destination.remote:
            raise ValueError('Source and destination cannot be both remotes.')
        if (self.source.remote or self.destination.remote) and self.server is None:
            raise ValueError('Missing remote server info.')

        self._source_dirpath = self._format_path(self.source.path, is_dir=True)
        self._destination_dirpath = self._format_path(self.destination.path, is_dir=True)
        self._partial_dirpath = self._format_path(self.destination.partial, is_dir=True)
        self._history_dirpath = self._format_path(self.destination.history, is_dir=True)
        self._actions_filepath = self._format_path(self.logging.actions, is_dir=False)
        self._progress_filepath = self._format_path(self.logging.progress, is_dir=False)
        self._errors_filepath = self._format_path(self.logging.errors, is_dir=False)
        # logging
        # check logfile (if any) is not inside destination (or source)
        # because, it may be destroyed or unnecessarily backup
        # if self.logging is not None:
        #     logfiles = [f for f in [self.actions_filepath, self.progress_filepath, self.errors_filepath] if f]
        #     process_dirs = [f for f in [self._destination_dirpath, self._source_dirpath] if f]
        #     for logfile in logfiles:
        #         for process_dir in process_dirs:
        #             if path.commonprefix([logfile, process_dir]) == process_dir:
        #                 raise ValueError(f'Log file {logfile} cannot be in the folder processed folder {process_dir}.')
        # todo: check against parameter injection

    def __str__(self):
        rsync_cmd = self._create_rsync_command()
        # make it safe
        # destination = rsync_cmd.pop()
        # source = rsync_cmd.pop()
        # rsync = rsync_cmd.pop(0)
        for i, opt in enumerate(rsync_cmd):
            if '=' in opt and ' ' in opt:
                e = opt.split('=')
                rsync_cmd[i] = f"{e[0]}='{e[1]}'"
        return ' '.join(rsync_cmd)

    def _create_rsync_command(self) -> List[str]:
        """ create the rsync command as a list of strings """
        rsync_option_list = set()
        # generic options
        rsync_option_list.add('--update')  # Skip files that are newer on the receiver
        rsync_option_list.add('--recursive')  # recurse into directories
        rsync_option_list.add('--compress')  # Compress file data during the transfer
        rsync_option_list.add('--links')  # Copy symlinks as symlinks
        rsync_option_list.add('--times')  # preserve modification times (important for update)
        rsync_option_list.add('--checksum')  # replace the times+sizes heuristic with sizes+md5 one
        rsync_option_list.add('--delete')  # Delete extraneous files from destination dirs
        rsync_option_list.add('--delete-excluded')  # also delete the excluded files
        rsync_option_list.add('--one-file-system')  # Do not cross filesystem boundaries when recursing
        rsync_option_list.add('--verbose')
        rsync_option_list.add('--progress')

        # enable partial copy to save time on resume
        if self._partial_dirpath is not None:
            rsync_option_list.add('--partial')  # Keep partially transferred files
            rsync_option_list.add(f'--partial-dir={self._partial_dirpath}')
        # exclude
        assert isinstance(self.exclude, list)
        for e in self.exclude:
            rsync_option_list.add(f'--exclude={e}')
        # versioning
        if self._history_dirpath:
            rsync_option_list.add('--backup')  # make a backup of what changed on destination
            rsync_option_list.add(f'--backup-dir={self._history_dirpath}')
        # dryrun
        if self.dryrun:
            rsync_option_list.add('--dry-run')  # perform a trial run that does not make any changes
            rsync_option_list.add('--itemize-changes')  # show you what needs changing for each file.

        src_part = self._source_dirpath
        dst_part = self._destination_dirpath

        # logging
        if self._actions_filepath is not None:
            rsync_option_list.add(f'--log-file={self._actions_filepath}')

        if self.server is not None:
            if self.server.timeout:
                # maximum I/O timeout in seconds.
                rsync_option_list.add(f'--timeout={int(self.server.timeout)}')

            if self.server.sshpath or self.server.port or self.server.keyfile or self.server.rsyncpath:
                ssh_cmd = [self.server.sshpath or 'ssh']
                if self.server.port:
                    ssh_cmd.append(f'-p {self.server.port}')
                if self.server.keyfile:
                    ssh_cmd.append(f'-i "{self._format_path(self.server.keyfile, is_dir=False)}"')
                if self.server.rsyncpath:
                    ssh_cmd.append(f'--rsync-path="{self.server.rsyncpath}"')
                rsync_option_list.add(f'--rsh=' + ' '.join(ssh_cmd))

            server_prefix = self.server.url + ':'
            if self.server.username:
                server_prefix = self.server.username + '@' + server_prefix
            if self.source.remote:
                src_part = server_prefix + src_part
            if self.destination.remote:
                dst_part = server_prefix + dst_part

        src_part = src_part
        dst_part = dst_part
        rsync_cmd = [self.rsync_local_path] + sorted(rsync_option_list) + [src_part, dst_part]

        return rsync_cmd

    @property
    def rsync_command_pretty(self) -> str:
        """
        create the rsync command as a single string and with stdout/stderr redirections
        ready to copy past in a terminal.
        """
        cmd_str = str(self)
        # reformat
        indentation = ' ' * 4
        cmd = cmd_str.split(' ')
        # split apart source and destination
        cmd_str = ' '.join(cmd[0:-2]) + '\n' + indentation + cmd[-2] + '\n' + indentation + cmd[-1]
        # split apart options
        cmd_str = cmd_str.replace('--', '\n' + indentation * 2 + '--')
        # printout
        if self._progress_filepath:
            cmd_str += f'\n1> {self._progress_filepath}'
        if self._errors_filepath:
            cmd_str += f'\n2> {self._errors_filepath}'
        # justify
        cmd_str = ''.join(l.ljust(80) + '\n' for l in cmd_str.split('\n'))
        # EOL escape char
        cmd_str = cmd_str.replace('\n', '\\\n')
        # except last one
        cmd_str = cmd_str[0:-2]
        return cmd_str

    def debug(self):
        print(self.rsync_command_pretty)

    def save(self):
        with Logger3(actions_filepath=self._actions_filepath,
                     progress_filepath=self._progress_filepath,
                     errors_filepath=self._errors_filepath) as logger:
            logger.actions.write('-' * 80 + '\n')
            logger.actions.write(self.rsync_command_pretty + '\n')
            logger.actions.write('-' * 80 + '\n')
            logger.actions.flush()
            rsync_cmd = self._create_rsync_command()
            rsync_process = Popen(rsync_cmd, stdout=logger.progress, stderr=logger.errors)
            rsync_code = rsync_process.wait()
            logger.actions.flush()
            logger.actions.write('-' * 80 + '\n')
            logger.actions.write(f'rsync finished with code {int(rsync_code)}.\n')


def main_cli():
    CLI(Backup, as_positional=False, set_defaults={"subcommand": "save"})


if __name__ == '__main__':
    main_cli()
